/**
 * HMI Screen Viewer — interactive Remote+ device screen.
 *
 * Connects via WebSocket to the backend bridge, receives screen payloads,
 * decodes them per device family (Orion/Cygnus/Sirius), and renders to canvas.
 * Provides a virtual keypad for sending key events to the device.
 *
 * Props:
 *   deviceId   - UUID of the device
 *   family     - device family: 'orion' | 'cygnus' | 'sirius'
 *   dest       - device destination address (from ConfigurationRead)
 *   resourceId - published resource ID for policy check
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import { type DeviceFamily, decodeScreen, renderToCanvas } from '../lib/screen-decoders'
import { getKeysForFamily, type KeyDef } from '../lib/keymaps'

interface HmiScreenViewerProps {
  deviceId: string
  family: DeviceFamily
  dest: number
  resourceId?: string
  scale?: number
  refreshMs?: number
}

type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error'

const SCREEN_SIZES: Record<DeviceFamily, { w: number; h: number }> = {
  orion: { w: 240, h: 128 },
  cygnus: { w: 128, h: 64 },
  sirius: { w: 122, h: 32 },
}

export default function HmiScreenViewer({
  deviceId,
  family,
  dest,
  resourceId = 'screen',
  scale = 3,
  refreshMs = 200,
}: HmiScreenViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const refreshTimerRef = useRef<number | null>(null)
  const [connState, setConnState] = useState<ConnectionState>('connecting')
  const [error, setError] = useState('')
  const [frameCount, setFrameCount] = useState(0)

  const screenSize = SCREEN_SIZES[family]
  const keys = getKeysForFamily(family)

  // ── WebSocket connection ──
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setConnState('error')
      setError('Not authenticated')
      return
    }

    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsHost = window.location.host
    const url = `${wsProto}//${wsHost}/api/v0/ws/remote/${deviceId}?token=${token}&dest=${dest}&resource_id=${resourceId}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnState('connecting') // waiting for 'connected' message
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)

        if (msg.type === 'connected') {
          setConnState('connected')
          // Start requesting screen frames
          requestScreen()
          return
        }

        if (msg.type === 'screen_data') {
          const decoded = decodeScreen(family, msg.hex, msg.command === 96)
          const canvas = canvasRef.current
          if (canvas) {
            const ctx = canvas.getContext('2d')
            if (ctx) {
              renderToCanvas(ctx, decoded, scale)
            }
          }
          setFrameCount((c) => c + 1)

          // Schedule next screen request
          if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current)
          refreshTimerRef.current = window.setTimeout(requestScreen, refreshMs)
          return
        }

        if (msg.type === 'error') {
          setError(msg.message)
          setConnState('error')
          return
        }

        if (msg.type === 'closed') {
          setConnState('disconnected')
          return
        }
      } catch {
        // Ignore parse errors
      }
    }

    ws.onerror = () => {
      setConnState('error')
      setError('WebSocket connection error')
    }

    ws.onclose = () => {
      if (connState !== 'error') {
        setConnState('disconnected')
      }
    }

    return () => {
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current)
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'close' }))
        ws.close()
      }
      wsRef.current = null
    }
  }, [deviceId, family, dest, resourceId])

  // ── Send commands ──
  const requestScreen = useCallback(() => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'screen_request', mode: 1 })) // delta mode
    }
  }, [])

  const sendKey = useCallback((keyCode: number) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'send_key', key_code: keyCode }))
      // Request screen update after key press
      setTimeout(requestScreen, 100)
    }
  }, [requestScreen])

  // ── Render ──
  const navKeys = keys.filter((k) => k.group === 'nav')
  const funcKeys = keys.filter((k) => k.group === 'func')
  const numKeys = keys.filter((k) => k.group === 'num')
  const miscKeys = keys.filter((k) => k.group === 'misc')

  const renderKeyGroup = (keyGroup: KeyDef[], label: string) => {
    if (keyGroup.length === 0) return null
    return (
      <div className="flex flex-col gap-1">
        <span className="text-xs text-slate-400">{label}</span>
        <div className="flex flex-wrap gap-1">
          {keyGroup.map((k) => (
            <button
              key={k.code}
              onClick={() => sendKey(k.code)}
              disabled={connState !== 'connected'}
              className="min-w-[36px] h-9 px-2 bg-slate-700 text-white text-sm rounded
                         hover:bg-slate-600 active:bg-slate-500
                         disabled:opacity-30 disabled:cursor-not-allowed
                         transition-colors font-mono"
            >
              {k.label}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Status bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              connState === 'connected'
                ? 'bg-green-500'
                : connState === 'connecting'
                ? 'bg-yellow-400 animate-pulse'
                : 'bg-red-400'
            }`}
          />
          <span className="text-xs text-slate-500">
            {connState === 'connected'
              ? `Connected — ${family.toUpperCase()} ${screenSize.w}×${screenSize.h}`
              : connState === 'connecting'
              ? 'Connecting...'
              : connState === 'error'
              ? error
              : 'Disconnected'}
          </span>
        </div>
        {connState === 'connected' && (
          <span className="text-xs text-slate-400">Frames: {frameCount}</span>
        )}
      </div>

      {/* Screen canvas */}
      <div
        className="bg-black rounded-lg overflow-hidden inline-block border-2 border-slate-700"
        style={{ width: screenSize.w * scale, height: screenSize.h * scale }}
      >
        <canvas
          ref={canvasRef}
          width={screenSize.w * scale}
          height={screenSize.h * scale}
          className="block"
        />
      </div>

      {/* Virtual keypad */}
      <div className="bg-slate-800 rounded-lg p-4 space-y-3" style={{ maxWidth: screenSize.w * scale }}>
        {renderKeyGroup(navKeys, 'Navigation')}
        {renderKeyGroup(funcKeys, 'Function')}
        {numKeys.length > 0 && renderKeyGroup(numKeys, 'Numeric')}
        {miscKeys.length > 0 && renderKeyGroup(miscKeys, 'Other')}
      </div>
    </div>
  )
}
