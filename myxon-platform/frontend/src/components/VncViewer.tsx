/**
 * VncViewer — встроенный VNC-клиент на базе Apache Guacamole.
 *
 * Подключается к /api/v0/ws/vnc/{deviceId} (наш WS прокси → guacd → VNC устройство).
 * Backend перехватывает guacamole handshake и подставляет реальный адрес VNC-туннеля,
 * поэтому здесь не нужно указывать hostname/port — backend делает это сам.
 *
 * Поддерживает мышь и клавиатуру через guacamole-common-js.
 */
import { useEffect, useRef, useState } from 'react'
import { MonitorOff } from 'lucide-react'
// guacamole-common-js экспортирует ESM default без TypeScript типов
// @ts-expect-error — no type declarations for this package
import Guacamole from 'guacamole-common-js'

type ConnState = 'connecting' | 'connected' | 'error' | 'disconnected'

interface VncViewerProps {
  deviceId: string
  token: string
  onClose?: () => void
}

export default function VncViewer({ deviceId, token, onClose }: VncViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const clientRef = useRef<any>(null)
  const [connState, setConnState] = useState<ConnState>('connecting')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    if (!containerRef.current) return

    // Строим WS URL — Vite proxy перенаправляет /api/v0/ws/* → ws://localhost:8000
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsHost = window.location.host
    const url = `${wsProto}//${wsHost}/api/v0/ws/vnc/${deviceId}?token=${encodeURIComponent(token)}`

    const tunnel = new Guacamole.WebSocketTunnel(url)
    const client = new Guacamole.Client(tunnel)
    clientRef.current = client

    // Монтируем canvas guacamole в наш контейнер
    const displayEl: HTMLElement = client.getDisplay().getElement()
    displayEl.style.cursor = 'default'
    containerRef.current.appendChild(displayEl)

    // ── Мышь ──
    const mouse = new Guacamole.Mouse(displayEl)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mouse.onmousedown = mouse.onmouseup = mouse.onmousemove = (state: any) =>
      client.sendMouseState(state)

    // ── Клавиатура — привязана к document для захвата фокуса ──
    const keyboard = new Guacamole.Keyboard(document)
    keyboard.onkeydown = (keysym: number) => client.sendKeyEvent(1, keysym)
    keyboard.onkeyup   = (keysym: number) => client.sendKeyEvent(0, keysym)

    // ── Состояние соединения ──
    // Guacamole.Client.State: IDLE=0, CONNECTING=1, WAITING=2, CONNECTED=3,
    //                          DISCONNECTING=4, DISCONNECTED=5
    client.onstatechange = (state: number) => {
      if (state === 3) setConnState('connected')
      if (state === 5) {
        setConnState('disconnected')
        onClose?.()
      }
    }

    client.onerror = (err: { message?: string }) => {
      setConnState('error')
      setErrorMsg(err?.message || 'VNC connection error')
    }

    // Подключаемся без параметров — backend перехватит connect и
    // подставит реальный hostname/port из frpc туннеля
    client.connect()

    return () => {
      keyboard.onkeydown = null
      keyboard.onkeyup   = null
      mouse.onmousedown  = null
      mouse.onmouseup    = null
      mouse.onmousemove  = null
      client.disconnect()
      if (containerRef.current && containerRef.current.contains(displayEl)) {
        containerRef.current.removeChild(displayEl)
      }
    }
  }, [deviceId, token])

  return (
    <div className="relative">
      {/* Оверлей "Подключаемся..." */}
      {connState === 'connecting' && (
        <div className="absolute inset-0 z-10 flex items-center justify-center rounded bg-black/70">
          <p className="text-sm text-white">Connecting to VNC...</p>
        </div>
      )}

      {/* Ошибка или отключение */}
      {(connState === 'error' || connState === 'disconnected') && (
        <div className="mb-2 flex items-center gap-2 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <MonitorOff size={16} />
          {connState === 'disconnected'
            ? 'VNC session disconnected'
            : errorMsg || 'VNC connection failed'}
        </div>
      )}

      {/* Canvas-контейнер guacamole */}
      <div
        ref={containerRef}
        className="overflow-auto rounded border border-slate-200 bg-black"
        style={{ minHeight: '400px' }}
        tabIndex={0}
      />
    </div>
  )
}
