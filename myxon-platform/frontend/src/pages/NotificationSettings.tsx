/**
 * NotificationSettings — управление контактами и правилами уведомлений.
 *
 * Два таба:
 *   Contacts — справочник людей (имя, телефон, email, каналы)
 *   Rules    — routing: кто получает уведомления о каких устройствах/локациях
 *
 * Доступно только admin/superadmin. Остальные видят сообщение "недостаточно прав".
 */
import { useEffect, useState } from 'react'
import {
  Bell, Plus, Pencil, Trash2, Phone, Mail, X, Check,
  ChevronDown, Building2, MapPin, Monitor, AlertTriangle,
} from 'lucide-react'
import {
  notificationsApi,
  sitesApi,
  devicesApi,
  type NotificationContact,
  type NotificationRule,
} from '../api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

type Tab = 'contacts' | 'rules'

interface ScopeOption { id: string; name: string }

// ── Helpers ───────────────────────────────────────────────────────────────────

const CHANNEL_LABELS: Record<string, string> = { sms: 'SMS', email: 'Email' }
const SEVERITY_LABELS: Record<string, string> = { warning: 'Warning+', alarm: 'Alarm only' }
const SEVERITY_COLORS: Record<string, string> = {
  warning: 'text-amber-600 bg-amber-50 border-amber-200',
  alarm:   'text-red-600 bg-red-50 border-red-200',
}
const SCOPE_ICONS: Record<string, React.ReactNode> = {
  tenant: <Building2 size={13} />,
  site:   <MapPin size={13} />,
  device: <Monitor size={13} />,
}
const SCOPE_LABELS: Record<string, string> = {
  tenant: 'Tenant-wide',
  site:   'Site',
  device: 'Device',
}

// ── Contact form modal ────────────────────────────────────────────────────────

interface ContactFormProps {
  initial?: NotificationContact | null
  onSave: (data: Omit<NotificationContact, 'id'>) => void
  onClose: () => void
}

function ContactForm({ initial, onSave, onClose }: ContactFormProps) {
  const [name, setName]       = useState(initial?.name ?? '')
  const [phone, setPhone]     = useState(initial?.phone ?? '')
  const [email, setEmail]     = useState(initial?.email ?? '')
  const [channels, setChannels] = useState<string[]>(initial?.channels ?? ['sms', 'email'])
  const [active, setActive]   = useState(initial?.active ?? true)
  const [error, setError]     = useState('')

  function toggleChannel(ch: string) {
    setChannels(prev => prev.includes(ch) ? prev.filter(c => c !== ch) : [...prev, ch])
  }

  function submit() {
    if (!name.trim()) return setError('Name is required')
    if (!phone.trim() && !email.trim()) return setError('Provide at least a phone or email')
    if (channels.length === 0) return setError('Select at least one notification channel')
    onSave({ name: name.trim(), phone: phone.trim() || null, email: email.trim() || null, channels, active })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="font-semibold text-slate-800">
            {initial ? 'Edit contact' : 'New contact'}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X size={18} />
          </button>
        </div>

        <div className="space-y-4 p-5">
          {error && (
            <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Name</label>
            <input
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              placeholder="Ivan Petrov (Engineer)"
              value={name}
              onChange={e => setName(e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Phone (E.164)</label>
            <div className="flex items-center gap-2">
              <Phone size={15} className="text-slate-400" />
              <input
                className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                placeholder="+31612345678"
                value={phone}
                onChange={e => setPhone(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Email</label>
            <div className="flex items-center gap-2">
              <Mail size={15} className="text-slate-400" />
              <input
                type="email"
                className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                placeholder="ivan@farm.nl"
                value={email}
                onChange={e => setEmail(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Notification channels</label>
            <div className="flex gap-3">
              {['sms', 'email'].map(ch => (
                <button
                  key={ch}
                  onClick={() => toggleChannel(ch)}
                  className={`flex items-center gap-2 rounded border px-3 py-1.5 text-sm transition-colors ${
                    channels.includes(ch)
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-slate-300 text-slate-600 hover:border-slate-400'
                  }`}
                >
                  {channels.includes(ch) && <Check size={12} />}
                  {CHANNEL_LABELS[ch]}
                </button>
              ))}
            </div>
          </div>

          <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={active}
              onChange={e => setActive(e.target.checked)}
              className="rounded"
            />
            Active (receives notifications)
          </label>
        </div>

        <div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-4">
          <button
            onClick={onClose}
            className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            {initial ? 'Save' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Rule form modal ───────────────────────────────────────────────────────────

const ALL_CATEGORIES = [
  'temperature', 'humidity', 'co2', 'ventilation',
  'pressure', 'weather', 'communication', 'power', 'sensor', 'general',
]

interface RuleFormProps {
  initial?: NotificationRule | null
  contacts: NotificationContact[]
  tenantId: string
  sites: ScopeOption[]
  devices: ScopeOption[]
  onSave: (data: Partial<NotificationRule>) => void
  onClose: () => void
}

function RuleForm({ initial, contacts, tenantId, sites, devices, onSave, onClose }: RuleFormProps) {
  const [contactId, setContactId]     = useState(initial?.contact_id ?? '')
  const [scopeType, setScopeType]     = useState<string>(initial?.scope_type ?? 'tenant')
  const [scopeId, setScopeId]         = useState(initial?.scope_id ?? tenantId)
  const [minSeverity, setMinSeverity] = useState(initial?.min_severity ?? 'alarm')
  const [categories, setCategories]   = useState<string[]>(initial?.categories ?? [])
  const [active, setActive]           = useState(initial?.active ?? true)
  const [notes, setNotes]             = useState(initial?.notes ?? '')
  const [error, setError]             = useState('')

  // When scope type changes, reset scope_id to a sensible default
  function handleScopeType(t: string) {
    setScopeType(t)
    if (t === 'tenant') setScopeId(tenantId)
    else setScopeId('')
  }

  function toggleCategory(cat: string) {
    setCategories(prev => prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat])
  }

  function submit() {
    if (!contactId) return setError('Select a contact')
    if (scopeType !== 'tenant' && !scopeId) return setError('Select a scope target')
    onSave({ contact_id: contactId, scope_type: scopeType, scope_id: scopeId, min_severity: minSeverity, categories, active, notes: notes || null })
  }

  const scopeTargets = scopeType === 'site' ? sites : scopeType === 'device' ? devices : []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="font-semibold text-slate-800">
            {initial ? 'Edit rule' : 'New notification rule'}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X size={18} />
          </button>
        </div>

        <div className="space-y-4 p-5">
          {error && (
            <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          {/* Contact */}
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Contact</label>
            <div className="relative">
              <select
                className="w-full appearance-none rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                value={contactId}
                onChange={e => setContactId(e.target.value)}
              >
                <option value="">— Select contact —</option>
                {contacts.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.name} {c.phone ? `📞 ${c.phone}` : ''} {c.email ? `✉ ${c.email}` : ''}
                  </option>
                ))}
              </select>
              <ChevronDown size={14} className="pointer-events-none absolute right-3 top-2.5 text-slate-400" />
            </div>
          </div>

          {/* Scope type */}
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Scope</label>
            <div className="flex gap-2">
              {(['tenant', 'site', 'device'] as const).map(t => (
                <button
                  key={t}
                  onClick={() => handleScopeType(t)}
                  className={`flex items-center gap-1.5 rounded border px-3 py-1.5 text-sm transition-colors ${
                    scopeType === t
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-slate-300 text-slate-600 hover:border-slate-400'
                  }`}
                >
                  {SCOPE_ICONS[t]}
                  {SCOPE_LABELS[t]}
                </button>
              ))}
            </div>
          </div>

          {/* Scope target (site / device selector) */}
          {scopeType !== 'tenant' && (
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                {scopeType === 'site' ? 'Select site' : 'Select device'}
              </label>
              <div className="relative">
                <select
                  className="w-full appearance-none rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  value={scopeId}
                  onChange={e => setScopeId(e.target.value)}
                >
                  <option value="">— Select —</option>
                  {scopeTargets.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
                <ChevronDown size={14} className="pointer-events-none absolute right-3 top-2.5 text-slate-400" />
              </div>
            </div>
          )}

          {/* Severity threshold */}
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Minimum severity</label>
            <div className="flex gap-2">
              {(['warning', 'alarm'] as const).map(s => (
                <button
                  key={s}
                  onClick={() => setMinSeverity(s)}
                  className={`rounded border px-3 py-1.5 text-sm transition-colors ${
                    minSeverity === s
                      ? SEVERITY_COLORS[s]
                      : 'border-slate-300 text-slate-600 hover:border-slate-400'
                  }`}
                >
                  {SEVERITY_LABELS[s]}
                </button>
              ))}
            </div>
            <p className="mt-1 text-xs text-slate-500">
              "Alarm only" = only critical alarms. "Warning+" = warnings and alarms both.
            </p>
          </div>

          {/* Category filter */}
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">
              Categories{' '}
              <span className="font-normal text-slate-400">(empty = all)</span>
            </label>
            <div className="flex flex-wrap gap-1.5">
              {ALL_CATEGORIES.map(cat => (
                <button
                  key={cat}
                  onClick={() => toggleCategory(cat)}
                  className={`rounded border px-2 py-0.5 text-xs transition-colors ${
                    categories.includes(cat)
                      ? 'border-blue-400 bg-blue-50 text-blue-700'
                      : 'border-slate-200 text-slate-500 hover:border-slate-300'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Notes (optional)</label>
            <input
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              placeholder="e.g. Farm Noord manager — only during working hours"
              value={notes}
              onChange={e => setNotes(e.target.value)}
            />
          </div>

          <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={active}
              onChange={e => setActive(e.target.checked)}
              className="rounded"
            />
            Rule active
          </label>
        </div>

        <div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-4">
          <button
            onClick={onClose}
            className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            {initial ? 'Save' : 'Create rule'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function NotificationSettings() {
  const [tab, setTab] = useState<Tab>('contacts')

  // Contacts state
  const [contacts, setContacts]           = useState<NotificationContact[]>([])
  const [contactModal, setContactModal]   = useState<NotificationContact | null | 'new'>(null)

  // Rules state
  const [rules, setRules]               = useState<NotificationRule[]>([])
  const [ruleModal, setRuleModal]       = useState<NotificationRule | null | 'new'>(null)
  const [sites, setSites]               = useState<ScopeOption[]>([])
  const [devices, setDevices]           = useState<ScopeOption[]>([])

  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  // Decode tenant ID from JWT
  const tenantId = (() => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) return ''
      let b64 = token.split('.')[1]
      b64 = b64.replace(/-/g, '+').replace(/_/g, '/')
      b64 += '='.repeat((4 - (b64.length % 4)) % 4)
      return JSON.parse(atob(b64)).tenant_id ?? ''
    } catch { return '' }
  })()

  useEffect(() => {
    Promise.all([
      notificationsApi.listContacts(),
      notificationsApi.listRules(),
      sitesApi.list(),
      devicesApi.list(),
    ]).then(([c, r, s, d]) => {
      setContacts(c.data)
      setRules(r.data)
      setSites((s.data as { id: string; name: string }[]).map(x => ({ id: x.id, name: x.name })))
      setDevices(d.data.items.map(x => ({ id: x.id, name: x.name || x.serial_number })))
      setLoading(false)
    }).catch(() => {
      setError('Failed to load notification settings')
      setLoading(false)
    })
  }, [])

  // ── Contact actions ──
  async function saveContact(data: Omit<NotificationContact, 'id'>) {
    if (contactModal === 'new') {
      const res = await notificationsApi.createContact(data)
      setContacts(prev => [...prev, res.data])
    } else if (contactModal) {
      const res = await notificationsApi.updateContact(contactModal.id, data)
      setContacts(prev => prev.map(c => c.id === contactModal.id ? res.data : c))
    }
    setContactModal(null)
  }

  async function deleteContact(id: string) {
    if (!confirm('Delete this contact? All rules referencing it will also be removed.')) return
    await notificationsApi.deleteContact(id)
    setContacts(prev => prev.filter(c => c.id !== id))
    setRules(prev => prev.filter(r => r.contact_id !== id))
  }

  // ── Rule actions ──
  async function saveRule(data: Partial<NotificationRule>) {
    if (ruleModal === 'new') {
      const res = await notificationsApi.createRule(data as Parameters<typeof notificationsApi.createRule>[0])
      setRules(prev => [...prev, res.data])
    } else if (ruleModal) {
      const res = await notificationsApi.updateRule(ruleModal.id, data)
      setRules(prev => prev.map(r => r.id === ruleModal.id ? res.data : r))
    }
    setRuleModal(null)
  }

  async function deleteRule(id: string) {
    if (!confirm('Delete this notification rule?')) return
    await notificationsApi.deleteRule(id)
    setRules(prev => prev.filter(r => r.id !== id))
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-400 text-sm">
        Loading...
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-64 items-center justify-center text-red-500 text-sm">{error}</div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-4xl">

        {/* Header */}
        <div className="mb-6 flex items-center gap-3">
          <Bell size={22} className="text-slate-600" />
          <div>
            <h1 className="text-xl font-semibold text-slate-800">Notifications</h1>
            <p className="text-sm text-slate-500">Manage alarm contacts and routing rules</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="mb-6 flex border-b border-slate-200">
          {(['contacts', 'rules'] as Tab[]).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-5 py-2.5 text-sm font-medium transition-colors ${
                tab === t
                  ? 'border-b-2 border-blue-600 text-blue-600'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {t === 'contacts' ? `Contacts (${contacts.length})` : `Rules (${rules.length})`}
            </button>
          ))}
        </div>

        {/* ── Contacts tab ── */}
        {tab === 'contacts' && (
          <div>
            <div className="mb-4 flex justify-end">
              <button
                onClick={() => setContactModal('new')}
                className="flex items-center gap-2 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                <Plus size={15} /> Add contact
              </button>
            </div>

            {contacts.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center">
                <Bell size={32} className="mx-auto mb-3 text-slate-300" />
                <p className="text-sm text-slate-500">No contacts yet.</p>
                <p className="mt-1 text-xs text-slate-400">Add engineers and managers who should receive alarm notifications.</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
                {contacts.map(c => (
                  <div key={c.id} className="flex items-center gap-4 px-4 py-3.5">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-slate-800 text-sm">{c.name}</span>
                        {!c.active && (
                          <span className="rounded border border-slate-200 bg-slate-100 px-1.5 py-0.5 text-xs text-slate-400">
                            inactive
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 flex items-center gap-4 text-xs text-slate-500">
                        {c.phone && (
                          <span className="flex items-center gap-1">
                            <Phone size={11} /> {c.phone}
                          </span>
                        )}
                        {c.email && (
                          <span className="flex items-center gap-1">
                            <Mail size={11} /> {c.email}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {c.channels.map(ch => (
                        <span
                          key={ch}
                          className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600"
                        >
                          {CHANNEL_LABELS[ch] ?? ch}
                        </span>
                      ))}
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setContactModal(c)}
                        className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                        title="Edit"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        onClick={() => deleteContact(c.id)}
                        className="rounded p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-500"
                        title="Delete"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Rules tab ── */}
        {tab === 'rules' && (
          <div>
            <div className="mb-4 flex items-start justify-between gap-4">
              <p className="text-sm text-slate-500 max-w-lg">
                Rules define who gets notified when an alarm fires.
                Notifications are routed by scope (tenant → site → device) and filtered by severity and category.
              </p>
              <button
                onClick={() => setRuleModal('new')}
                disabled={contacts.length === 0}
                title={contacts.length === 0 ? 'Add contacts first' : undefined}
                className="flex shrink-0 items-center gap-2 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                <Plus size={15} /> Add rule
              </button>
            </div>

            {contacts.length === 0 && (
              <div className="mb-4 flex items-center gap-2 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
                <AlertTriangle size={15} />
                Create at least one contact before adding rules.
              </div>
            )}

            {rules.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center">
                <Bell size={32} className="mx-auto mb-3 text-slate-300" />
                <p className="text-sm text-slate-500">No rules yet.</p>
                <p className="mt-1 text-xs text-slate-400">Rules control who gets notified for which devices and at which severity.</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
                {rules.map(r => (
                  <div key={r.id} className="flex items-start gap-4 px-4 py-3.5">
                    <div className="flex-1 min-w-0">
                      {/* Contact + channels */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-slate-800 text-sm">{r.contact_name}</span>
                        {r.contact_channels.map(ch => (
                          <span key={ch} className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-xs text-slate-500">
                            {CHANNEL_LABELS[ch] ?? ch}
                          </span>
                        ))}
                        {!r.active && (
                          <span className="rounded border border-slate-200 bg-slate-100 px-1.5 py-0.5 text-xs text-slate-400">
                            inactive
                          </span>
                        )}
                      </div>
                      {/* Scope */}
                      <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-500">
                        <span className="flex items-center gap-1 text-slate-400">
                          {SCOPE_ICONS[r.scope_type]}
                          {SCOPE_LABELS[r.scope_type]}:
                        </span>
                        <span className="text-slate-600">
                          {r.scope_type === 'tenant'
                            ? 'all devices'
                            : sites.find(s => s.id === r.scope_id)?.name
                              ?? devices.find(d => d.id === r.scope_id)?.name
                              ?? r.scope_id.slice(0, 8) + '…'}
                        </span>
                        <span className="mx-1 text-slate-300">·</span>
                        <span className={`rounded border px-1.5 py-0.5 ${SEVERITY_COLORS[r.min_severity]}`}>
                          {SEVERITY_LABELS[r.min_severity]}
                        </span>
                        {r.categories.length > 0 && (
                          <>
                            <span className="mx-1 text-slate-300">·</span>
                            <span className="text-slate-500">{r.categories.join(', ')}</span>
                          </>
                        )}
                      </div>
                      {r.notes && (
                        <p className="mt-0.5 text-xs text-slate-400 italic">{r.notes}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => setRuleModal(r)}
                        className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                        title="Edit"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        onClick={() => deleteRule(r.id)}
                        className="rounded p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-500"
                        title="Delete"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modals */}
      {contactModal !== null && (
        <ContactForm
          initial={contactModal === 'new' ? null : contactModal}
          onSave={saveContact}
          onClose={() => setContactModal(null)}
        />
      )}
      {ruleModal !== null && (
        <RuleForm
          initial={ruleModal === 'new' ? null : ruleModal}
          contacts={contacts.filter(c => c.active)}
          tenantId={tenantId}
          sites={sites}
          devices={devices}
          onSave={saveRule}
          onClose={() => setRuleModal(null)}
        />
      )}
    </div>
  )
}
