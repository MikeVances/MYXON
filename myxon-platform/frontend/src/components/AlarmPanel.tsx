import { useEffect, useState } from 'react'
import { alarmsApi } from '../api/client'
import { AlertTriangle, Bell, BellOff, CheckCircle2, Filter } from 'lucide-react'

interface Alarm {
  id: string
  device_id: string
  code: number
  category: string
  severity: string
  state: string
  message: string | null
  triggered_at: string
  acknowledged_at: string | null
  cleared_at: string | null
}

type SeverityFilter = 'all' | 'critical' | 'warning' | 'info'
type StateFilter = 'all' | 'active' | 'acknowledged' | 'cleared'

interface AlarmPanelProps {
  deviceId: string
  /** auto-refresh interval in ms, 0 = disabled */
  refreshMs?: number
  /** Whether the current user is permitted to acknowledge alarms (from AccessPolicy) */
  canAcknowledge?: boolean
}

const severityIcon = (severity: string) => {
  switch (severity) {
    case 'critical':
      return <AlertTriangle size={14} className="text-red-500" />
    case 'warning':
      return <AlertTriangle size={14} className="text-amber-500" />
    default:
      return <Bell size={14} className="text-blue-400" />
  }
}

const severityBadge = (severity: string) => {
  switch (severity) {
    case 'critical':
      return 'bg-red-100 text-red-700 border-red-200'
    case 'warning':
      return 'bg-amber-50 text-amber-700 border-amber-200'
    default:
      return 'bg-blue-50 text-blue-600 border-blue-200'
  }
}

const stateBadge = (state: string) => {
  switch (state) {
    case 'active':
      return 'bg-red-50 text-red-600'
    case 'acknowledged':
      return 'bg-slate-100 text-slate-600'
    case 'cleared':
      return 'bg-green-50 text-green-600'
    default:
      return 'bg-slate-100 text-slate-500'
  }
}

const categoryLabel = (cat: string) =>
  cat.charAt(0).toUpperCase() + cat.slice(1).replace(/_/g, ' ')

const formatTime = (iso: string) => {
  const d = new Date(iso)
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function AlarmPanel({ deviceId, refreshMs = 30_000, canAcknowledge = true }: AlarmPanelProps) {
  const [alarms, setAlarms] = useState<Alarm[]>([])
  const [loading, setLoading] = useState(true)
  const [acking, setAcking] = useState<string | null>(null)
  const [sevFilter, setSevFilter] = useState<SeverityFilter>('all')
  const [stateFilter, setStateFilter] = useState<StateFilter>('all')

  const fetchAlarms = async () => {
    try {
      const params: Record<string, string> = { device_id: deviceId }
      if (sevFilter !== 'all') params.severity = sevFilter
      if (stateFilter !== 'all') params.state = stateFilter
      const { data } = await alarmsApi.list(params)
      // alarmsApi returns PagedResponse<AlarmItem> — unwrap .items
      setAlarms(data.items ?? [])
    } catch {
      // silently fail — dashboard stays usable
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAlarms()
    if (refreshMs > 0) {
      const iv = setInterval(fetchAlarms, refreshMs)
      return () => clearInterval(iv)
    }
  }, [deviceId, sevFilter, stateFilter, refreshMs])

  const handleAck = async (alarmId: string) => {
    setAcking(alarmId)
    try {
      await alarmsApi.acknowledge(alarmId)
      await fetchAlarms()
    } catch {
      // ignore — UI stays consistent after refetch
    } finally {
      setAcking(null)
    }
  }

  const activeCritical = alarms.filter(
    (a) => a.state === 'active' && a.severity === 'critical'
  ).length
  const activeWarning = alarms.filter(
    (a) => a.state === 'active' && a.severity === 'warning'
  ).length

  return (
    <div>
      {/* Summary bar */}
      <div className="mb-3 flex items-center gap-3 text-sm">
        {activeCritical > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700">
            <AlertTriangle size={12} />
            {activeCritical} critical
          </span>
        )}
        {activeWarning > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
            <AlertTriangle size={12} />
            {activeWarning} warning
          </span>
        )}
        {activeCritical === 0 && activeWarning === 0 && !loading && (
          <span className="inline-flex items-center gap-1 text-xs text-green-600">
            <CheckCircle2 size={12} />
            No active alarms
          </span>
        )}
      </div>

      {/* Filters */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Filter size={14} className="text-slate-400" />
        <select
          value={sevFilter}
          onChange={(e) => setSevFilter(e.target.value as SeverityFilter)}
          className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
        >
          <option value="all">All severity</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
          <option value="info">Info</option>
        </select>
        <select
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value as StateFilter)}
          className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
        >
          <option value="all">All states</option>
          <option value="active">Active</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="cleared">Cleared</option>
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <p className="text-sm text-slate-400">Loading alarms...</p>
      ) : alarms.length === 0 ? (
        <div className="flex items-center gap-2 py-4 text-sm text-slate-400">
          <BellOff size={16} />
          No alarms match current filters.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-200">
                <th className="py-1.5 pr-3 w-6"></th>
                <th className="py-1.5 pr-3">Code</th>
                <th className="py-1.5 pr-3">Category</th>
                <th className="py-1.5 pr-3">Message</th>
                <th className="py-1.5 pr-3">Time</th>
                <th className="py-1.5 pr-3">State</th>
                <th className="py-1.5 w-20"></th>
              </tr>
            </thead>
            <tbody>
              {alarms.map((a) => (
                <tr
                  key={a.id}
                  className={`border-b border-slate-100 last:border-b-0 ${
                    a.state === 'active' && a.severity === 'critical'
                      ? 'bg-red-50/50'
                      : ''
                  }`}
                >
                  <td className="py-1.5 pr-3">{severityIcon(a.severity)}</td>
                  <td className="py-1.5 pr-3">
                    <span
                      className={`inline-block rounded border px-1.5 py-0.5 text-xs font-mono ${severityBadge(
                        a.severity
                      )}`}
                    >
                      {a.code}
                    </span>
                  </td>
                  <td className="py-1.5 pr-3 text-slate-600">
                    {categoryLabel(a.category)}
                  </td>
                  <td className="py-1.5 pr-3 max-w-[200px] truncate" title={a.message || ''}>
                    {a.message || '-'}
                  </td>
                  <td className="py-1.5 pr-3 whitespace-nowrap text-slate-500">
                    {formatTime(a.triggered_at)}
                  </td>
                  <td className="py-1.5 pr-3">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${stateBadge(a.state)}`}
                    >
                      {a.state}
                    </span>
                  </td>
                  <td className="py-1.5">
                    {a.state === 'active' && canAcknowledge && (
                      <button
                        onClick={() => handleAck(a.id)}
                        disabled={acking === a.id}
                        className="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-200 disabled:opacity-50"
                      >
                        {acking === a.id ? '...' : 'Ack'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
