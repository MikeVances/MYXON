import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { devicesApi, auditApi, accessPoliciesApi } from '../api/client'
import type { AccessPolicy } from '../api/client'
import { RefreshCw, ChevronLeft, CircleDot, ShieldAlert, MonitorPlay, X } from 'lucide-react'
import HmiScreenViewer from '../components/HmiScreenViewer'
import VncViewer from '../components/VncViewer'
import AlarmPanel from '../components/AlarmPanel'
import type { DeviceFamily } from '../lib/screen-decoders'

interface Device {
  id: string
  serial_number: string
  name: string
  model: string | null
  firmware_version: string | null
  status: string
  claim_state: string
  last_seen_at: string | null
  vendor_id: string | null
  device_family: string | null
  published_resources: Resource[] | null
}

interface Resource {
  id: string
  name: string
  protocol: string
  port?: number
}

interface AuditEntry {
  id: string
  action: string
  details: Record<string, unknown> | null
  created_at: string
  actor_id: string | null
}

interface AccessSession {
  id: string
  access_url: string
  protocol: string
  resource_id: string
  status: string
  expires_at: string | null
}

export default function DeviceDashboard() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [device, setDevice] = useState<Device | null>(null)
  const [events, setEvents] = useState<AuditEntry[]>([])
  const [session, setSession] = useState<AccessSession | null>(null)
  const [policy, setPolicy] = useState<AccessPolicy | null>(null)
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState('')
  const [vncActive, setVncActive] = useState(false)

  useEffect(() => {
    if (!id) return
    Promise.all([
      devicesApi.get(id),
      auditApi.events({ device_id: id, limit: '20' }),
      accessPoliciesApi.effective(id).catch(() => ({ data: null })),
    ])
      .then(([deviceRes, auditRes, policyRes]) => {
        setDevice(deviceRes.data)
        // auditApi returns PagedResponse<AuditEventItem> — unwrap .items
        setEvents(auditRes.data.items ?? [])
        setPolicy(policyRes.data)
      })
      .catch(() => setError('Failed to load device'))
      .finally(() => setLoading(false))
  }, [id])

  const openSession = async (resource: Resource) => {
    if (!id) return
    setConnecting(true)
    setError('')
    try {
      const { data } = await devicesApi.createSession(id, resource.id, resource.protocol)
      setSession(data)
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response: { data: { detail: string } } }).response?.data?.detail
          : 'Failed to create session'
      setError(msg || 'Failed to create session')
    } finally {
      setConnecting(false)
    }
  }

  const statusColor = (status: string) => {
    if (status === 'online') return 'bg-green-500'
    if (status === 'offline') return 'bg-red-400'
    return 'bg-slate-300'
  }

  const statusBadge = (status: string) => {
    if (status === 'online') return 'bg-green-100 text-green-700'
    if (status === 'offline') return 'bg-red-100 text-red-600'
    return 'bg-slate-100 text-slate-600'
  }

  const actionLabel = (action: string) => {
    const map: Record<string, string> = {
      'device.claimed': 'Device claimed',
      'device.status_change': 'Status changed',
      'session.opened': 'Session opened',
      'session.closed': 'Session closed',
      'agent.registered': 'Agent registered',
    }
    return map[action] || action
  }

  const formatTime = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <p className="text-slate-500">Loading device...</p>
      </div>
    )
  }

  if (!device) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-600 mb-4">Device not found</p>
          <button
            onClick={() => navigate('/devices')}
            className="text-myxon-600 hover:underline text-sm"
          >
            Back to devices
          </button>
        </div>
      </div>
    )
  }

  const resources = device.published_resources || []

  // Policy-derived capability flags (default permissive when no policy)
  const canHmi = policy ? policy.allow_hmi : true
  const canVnc = policy ? policy.allow_vnc : true
  const canHttp = policy ? policy.allow_http : true
  const canAudit = policy ? policy.allow_audit_view : true
  const canAlarms = policy ? policy.allow_alarms_view : true

  return (
    <div className="min-h-screen bg-[#eef0f4] text-slate-800">
      <header className="border-b border-slate-200 bg-white/85 px-4 py-3 md:px-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/devices')}
              className="rounded-md p-1 text-slate-600 hover:bg-slate-100"
            >
              <ChevronLeft size={18} />
            </button>
            <h1 className="text-lg md:text-xl font-semibold tracking-tight">
              {device.name || device.serial_number}
            </h1>
          </div>
          <div className="flex items-center gap-2">
            {policy && (
              <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
                <ShieldAlert size={11} />
                {policy.name}
              </span>
            )}
            <button className="inline-flex items-center gap-1 rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs">
              <RefreshCw size={12} />
              5m
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl p-4 md:p-6">
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {session && (
          <div className="mb-4 rounded-lg border border-myxon-200 bg-myxon-50 p-4">
            <p className="text-sm font-medium text-myxon-900">
              Active session · {session.protocol.toUpperCase()} · {session.resource_id}
            </p>
            <a
              href={session.access_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-block rounded bg-myxon-700 px-3 py-1.5 text-xs text-white"
            >
              Open Web Access
            </a>
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 xl:grid-cols-12">
          <section className="rounded-lg border border-slate-300 bg-white p-4 xl:col-span-4">
            <h3 className="mb-2 text-lg font-semibold">VPN</h3>
            <div className="mb-3 h-2 rounded bg-slate-200">
              <div className={`h-2 rounded ${device.status === 'online' ? 'w-full bg-green-500' : 'w-0'}`} />
            </div>
            <button
              disabled={device.status !== 'online'}
              className={`mb-4 w-full rounded py-2 text-sm font-semibold ${
                device.status === 'online' ? 'bg-amber-500 text-white' : 'bg-slate-200 text-slate-500'
              }`}
            >
              VPN connect
            </button>

            <div className="rounded border border-slate-200">
              <div className="px-3 py-2 text-sm font-semibold border-b border-slate-200">
                {device.name || device.serial_number}
              </div>
              <div className="grid grid-cols-2 gap-y-1 px-3 py-2 text-sm">
                <span className="text-slate-500">Status</span>
                <span className="inline-flex items-center gap-1">
                  <CircleDot size={12} className={device.status === 'online' ? 'text-green-500' : 'text-slate-400'} />
                  {device.status}
                </span>
                <span className="text-slate-500">Serial</span>
                <span>{device.serial_number}</span>
                <span className="text-slate-500">Firmware</span>
                <span>{device.firmware_version || '-'}</span>
                <span className="text-slate-500">Model</span>
                <span>{device.model || '-'}</span>
                <span className="text-slate-500">Last seen</span>
                <span>{device.last_seen_at ? formatTime(device.last_seen_at) : '-'}</span>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-slate-300 bg-white p-4 xl:col-span-4">
            <h3 className="mb-3 text-lg font-semibold">Web Access</h3>
            {!canHmi && !canVnc ? (
              <div className="flex items-center gap-2 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                <ShieldAlert size={14} />
                Your access policy does not permit remote access to this device.
              </div>
            ) : resources.length === 0 ? (
              <p className="text-sm text-slate-400">No resources published.</p>
            ) : (
              <div className="space-y-2">
                {resources.map((r) => {
                  const isVnc = r.protocol === 'vnc'
                  const isHttp = r.protocol === 'http'
                  const isAllowed = isVnc ? canVnc : isHttp ? canHttp : canHmi
                  return (
                    <div key={r.id} className="rounded border border-slate-200 p-2">
                      <div className="mb-2 flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium">{r.name}</p>
                          <p className="text-xs text-slate-500">
                            {r.protocol.toUpperCase()}{r.port ? ` · ${r.port}` : ''}
                          </p>
                        </div>
                        {!isAllowed && (
                          <span className="text-xs text-amber-600 flex items-center gap-1">
                            <ShieldAlert size={11} /> restricted
                          </span>
                        )}
                      </div>
                      <button
                        onClick={() => openSession(r)}
                        disabled={connecting || device.status !== 'online' || !isAllowed}
                        className="w-full rounded bg-amber-500 py-1.5 text-sm font-semibold text-white disabled:bg-slate-200 disabled:text-slate-500"
                      >
                        {connecting ? 'Connecting...' : 'Connect'}
                      </button>
                    </div>
                  )
                })}
              </div>
            )}
          </section>

          {/* Direct HMI — for HOTRACO devices with screen capability */}
          {canHmi &&
            device.vendor_id === 'hotraco' &&
            device.device_family &&
            device.status === 'online' && (
              <section className="rounded-lg border border-slate-300 bg-white p-4 xl:col-span-8">
                <h3 className="mb-3 text-lg font-semibold">
                  Direct HMI — {device.device_family.charAt(0).toUpperCase() + device.device_family.slice(1)}
                </h3>
                <HmiScreenViewer
                  deviceId={device.id}
                  family={device.device_family as DeviceFamily}
                  dest={0}
                  resourceId={`screen-${device.device_family}`}
                  scale={3}
                  refreshMs={250}
                />
              </section>
            )}

          {/* VNC viewer — shown when VNC resource is present and access is allowed */}
          {canVnc &&
            device.status === 'online' &&
            resources.some((r) => r.protocol === 'vnc') && (
              <section className="rounded-lg border border-slate-300 bg-white p-4 xl:col-span-8">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-lg font-semibold">VNC Access</h3>
                  {vncActive ? (
                    <button
                      onClick={() => setVncActive(false)}
                      className="flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
                    >
                      <X size={12} /> Disconnect
                    </button>
                  ) : (
                    <button
                      onClick={() => setVncActive(true)}
                      className="flex items-center gap-1 rounded bg-myxon-600 px-3 py-1.5 text-sm text-white hover:bg-myxon-700"
                    >
                      <MonitorPlay size={14} /> Connect VNC
                    </button>
                  )}
                </div>

                {vncActive ? (
                  <VncViewer
                    deviceId={device.id}
                    token={localStorage.getItem('access_token') ?? ''}
                    onClose={() => setVncActive(false)}
                  />
                ) : (
                  <p className="text-sm text-slate-500">
                    Click <strong>Connect VNC</strong> to open an interactive VNC session
                    in this panel. Mouse and keyboard are forwarded to the device.
                  </p>
                )}
              </section>
            )}

          <section className="rounded-lg border border-slate-300 bg-white p-4 xl:col-span-4">
            <h3 className="mb-3 text-lg font-semibold">Cloud connection status</h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <span>VPN connection</span>
                <span className={statusBadge(device.status)}>{device.status === 'online' ? 'active' : 'offline'}</span>
              </div>
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <span>Configuration connection</span>
                <span className={statusBadge(device.status)}>{device.status === 'online' ? 'active' : 'inactive'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Data logging connection</span>
                <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                  {device.last_seen_at ? `last: ${formatTime(device.last_seen_at)}` : 'no data'}
                </span>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-slate-300 bg-white p-4 xl:col-span-12">
            <h3 className="mb-3 text-lg font-semibold">Alarms</h3>
            {canAlarms ? (
              <AlarmPanel
                deviceId={device.id}
                refreshMs={30_000}
                canAcknowledge={policy ? policy.allow_alarms_acknowledge : true}
              />
            ) : (
              <div className="flex items-center gap-2 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                <ShieldAlert size={14} />
                Your access policy does not permit viewing alarms on this device.
              </div>
            )}
          </section>

          <section className="rounded-lg border border-slate-300 bg-white p-4 xl:col-span-12">
            <h3 className="mb-3 text-lg font-semibold">Event log</h3>
            {!canAudit ? (
              <div className="flex items-center gap-2 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                <ShieldAlert size={14} />
                Your access policy does not permit viewing the audit log.
              </div>
            ) : events.length === 0 ? (
              <p className="text-sm text-slate-400">No events recorded yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-500 border-b border-slate-200">
                      <th className="py-1 pr-4">Who</th>
                      <th className="py-1 pr-4">When</th>
                      <th className="py-1">What</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((ev) => (
                      <tr key={ev.id} className="border-b border-slate-100 last:border-b-0">
                        <td className="py-1.5 pr-4">{ev.actor_id ? ev.actor_id.slice(0, 8) : 'system'}</td>
                        <td className="py-1.5 pr-4">{formatTime(ev.created_at)}</td>
                        <td className="py-1.5">
                          {actionLabel(ev.action)}
                          {ev.details && Object.keys(ev.details).length > 0 ? (
                            <span className="ml-2 text-xs text-slate-500">
                              {Object.entries(ev.details)
                                .map(([k, v]) => `${k}:${v}`)
                                .join(' · ')}
                            </span>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
