/**
 * DealerPortal — dealer-tier workspace.
 *
 * Tabs:
 *  1. Devices   — register new SN + list of dealer's devices (status only, no customer data)
 *  2. Customers — create invite link for new customer
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import QRCode from 'react-qr-code'
import { dealerApi, authApi, activationCodesApi } from '../api/client'
import type { ActivationCodeItem } from '../api/client'

type Tab = 'devices' | 'codes' | 'customers'

interface DealerDevice {
  id: string
  serial_number: string
  model: string | null
  status: string
  claim_state: string
  last_seen_at: string | null
}

interface InviteResult {
  invite_url: string
  customer_email: string
  expires_at: string
}

// ---- Helpers ---------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    online: 'bg-green-100 text-green-700',
    offline: 'bg-slate-100 text-slate-500',
    pre_registered: 'bg-blue-50 text-blue-600',
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium ${map[status] ?? 'bg-slate-100 text-slate-500'}`}>
      {status === 'online' && <span className="w-1.5 h-1.5 rounded-full bg-green-500" />}
      {status}
    </span>
  )
}

function ClaimStateBadge({ state }: { state: string }) {
  const map: Record<string, string> = {
    ready_for_transfer: 'bg-amber-50 text-amber-600',
    claimed: 'bg-green-50 text-green-600',
  }
  const labels: Record<string, string> = {
    ready_for_transfer: 'Unclaimed',
    claimed: 'Activated',
  }
  return (
    <span className={`inline-flex rounded px-2 py-0.5 text-xs font-medium ${map[state] ?? 'bg-slate-100 text-slate-500'}`}>
      {labels[state] ?? state}
    </span>
  )
}

// ---- Main Component --------------------------------------------------------

export default function DealerPortal() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('devices')

  // Devices tab state
  const [devices, setDevices] = useState<DealerDevice[]>([])
  const [devLoading, setDevLoading] = useState(true)
  const [newSerial, setNewSerial] = useState('')
  const [newModel, setNewModel] = useState('')
  const [registering, setRegistering] = useState(false)
  const [regError, setRegError] = useState('')
  // SN только что зарегистрированного устройства — показываем QR
  const [qrSerial, setQrSerial] = useState<string | null>(null)

  // Activation Codes tab state
  const [codes, setCodes] = useState<ActivationCodeItem[]>([])
  const [codesLoading, setCodesLoading] = useState(false)
  const [codeDeviceName, setCodeDeviceName] = useState('')
  const [codeTtl, setCodeTtl] = useState(7)
  const [generatingCode, setGeneratingCode] = useState(false)
  const [codeError, setCodeError] = useState('')
  const [newCode, setNewCode] = useState<ActivationCodeItem | null>(null)
  const [copiedCode, setCopiedCode] = useState<string | null>(null)

  // Customers tab state
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteName, setInviteName] = useState('')
  const [inviting, setInviting] = useState(false)
  const [inviteError, setInviteError] = useState('')
  const [inviteResult, setInviteResult] = useState<InviteResult | null>(null)

  useEffect(() => {
    loadDevices()
  }, [])

  // Load codes when switching to the codes tab
  useEffect(() => {
    if (tab === 'codes') loadCodes()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab])

  async function loadDevices() {
    setDevLoading(true)
    try {
      const { data } = await dealerApi.listDevices()
      // dealerApi.listDevices() returns PagedResponse<Device> — unwrap .items
      setDevices(data.items ?? [])
    } catch {
      // not a dealer account or network error
    } finally {
      setDevLoading(false)
    }
  }

  async function loadCodes() {
    setCodesLoading(true)
    try {
      const { data } = await activationCodesApi.list()
      setCodes(data)
    } catch {
      // ignore
    } finally {
      setCodesLoading(false)
    }
  }

  async function handleGenerateCode() {
    setGeneratingCode(true)
    setCodeError('')
    setNewCode(null)
    try {
      const { data } = await activationCodesApi.generate(
        codeDeviceName.trim() || undefined,
        codeTtl,
      )
      setNewCode(data)
      setCodeDeviceName('')
      loadCodes()
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response: { data: { detail: string } } }).response?.data?.detail
        : 'Failed to generate code'
      setCodeError(msg || 'Failed to generate code')
    } finally {
      setGeneratingCode(false)
    }
  }

  async function handleRevokeCode(code: string) {
    try {
      await activationCodesApi.revoke(code)
      setCodes((prev) => prev.filter((c) => c.code !== code))
    } catch {
      // ignore
    }
  }

  function copyCode(code: string) {
    navigator.clipboard.writeText(code).catch(() => {})
    setCopiedCode(code)
    setTimeout(() => setCopiedCode(null), 2000)
  }

  async function handleRegister() {
    if (!newSerial.trim()) { setRegError('Serial number is required'); return }
    setRegistering(true)
    setRegError('')
    setQrSerial(null)
    try {
      const sn = newSerial.trim()
      await dealerApi.registerDevice(sn, newModel.trim() || undefined)
      setQrSerial(sn)   // показываем QR для только что зарегистрированного SN
      setNewSerial('')
      setNewModel('')
      loadDevices()
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response: { data: { detail: string } } }).response?.data?.detail
        : 'Registration failed'
      setRegError(msg || 'Registration failed')
    } finally {
      setRegistering(false)
    }
  }

  async function handleInvite() {
    if (!inviteEmail.trim()) { setInviteError('Email is required'); return }
    if (!inviteName.trim()) { setInviteError('Customer name is required'); return }
    setInviting(true)
    setInviteError('')
    setInviteResult(null)
    try {
      const { data } = await authApi.createInvite(inviteEmail.trim(), inviteName.trim())
      setInviteResult(data)
      setInviteEmail('')
      setInviteName('')
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response: { data: { detail: string } } }).response?.data?.detail
        : 'Failed to create invite'
      setInviteError(msg || 'Failed to create invite')
    } finally {
      setInviting(false)
    }
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text).catch(() => {})
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center gap-4">
        <h1 className="text-xl font-bold text-myxon-900">MYXON</h1>
        <span className="text-xs font-medium bg-amber-100 text-amber-700 px-2 py-0.5 rounded">
          Dealer Portal
        </span>
        <div className="ml-auto flex items-center gap-3">
          <button
            onClick={() => navigate('/devices')}
            className="text-sm text-slate-500 hover:text-slate-700 transition"
          >
            Customer View
          </button>
          <button
            onClick={() => { localStorage.clear(); navigate('/login') }}
            className="text-sm text-slate-400 hover:text-slate-600 transition"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Tabs */}
        <div className="flex gap-1 mb-8 bg-slate-100 p-1 rounded-lg w-fit">
          {([
            ['devices', 'Devices'],
            ['codes', 'Activation Codes'],
            ['customers', 'Customers'],
          ] as [Tab, string][]).map(([t, label]) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-5 py-2 rounded-md text-sm font-medium transition ${
                tab === t ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* ---- Devices Tab ---- */}
        {tab === 'devices' && (
          <div className="space-y-6">
            {/* Register new device */}
            <div className="bg-white rounded-lg border border-slate-200 p-5">
              <h2 className="text-sm font-semibold text-slate-700 mb-4">Register New Device</h2>
              <div className="flex gap-3">
                <div className="flex-1">
                  <input
                    type="text"
                    value={newSerial}
                    onChange={(e) => setNewSerial(e.target.value.toUpperCase())}
                    onKeyDown={(e) => e.key === 'Enter' && handleRegister()}
                    placeholder="Serial number (e.g. MX-2024-00001)"
                    className="w-full px-3 py-2 border border-slate-300 rounded-md font-mono text-sm
                      focus:outline-none focus:ring-2 focus:ring-myxon-500"
                  />
                </div>
                <div className="w-40">
                  <input
                    type="text"
                    value={newModel}
                    onChange={(e) => setNewModel(e.target.value)}
                    placeholder="Model (optional)"
                    className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm
                      focus:outline-none focus:ring-2 focus:ring-myxon-500"
                  />
                </div>
                <button
                  onClick={handleRegister}
                  disabled={registering || !newSerial.trim()}
                  className="px-4 py-2 bg-myxon-600 text-white rounded-md text-sm font-medium
                    hover:bg-myxon-700 transition disabled:opacity-50 whitespace-nowrap"
                >
                  {registering ? 'Registering...' : '+ Register'}
                </button>
              </div>
              {regError && (
                <p className="mt-2 text-red-600 text-xs">{regError}</p>
              )}
              <p className="mt-3 text-xs text-slate-400">
                After registering, print the QR code and attach it to the device. Customer scans it to activate.
              </p>
            </div>

            {/* QR-код появляется сразу после регистрации */}
            {qrSerial && (
              <div className="bg-white rounded-lg border border-green-200 p-5">
                <div className="flex items-start gap-5">
                  {/* QR */}
                  <div className="flex-shrink-0 bg-white p-3 border border-slate-200 rounded-lg" id="qr-print-area">
                    <QRCode
                      value={`${window.location.origin}/claim?sn=${qrSerial}`}
                      size={140}
                      level="M"
                    />
                    <p className="text-center font-mono text-xs text-slate-600 mt-2 tracking-wider">{qrSerial}</p>
                  </div>

                  {/* Описание и кнопки */}
                  <div className="flex-1 space-y-3">
                    <div>
                      <p className="text-sm font-semibold text-green-700">Device registered!</p>
                      <p className="text-xs text-slate-500 mt-1">
                        QR code leads to:<br />
                        <span className="font-mono text-slate-400 break-all">
                          {window.location.origin}/claim?sn={qrSerial}
                        </span>
                      </p>
                    </div>
                    <div className="flex flex-col gap-2">
                      <button
                        onClick={() => window.print()}
                        className="w-full border border-slate-300 text-slate-700 py-1.5 rounded text-xs font-medium hover:bg-slate-50 transition"
                      >
                        Print QR Label
                      </button>
                      <button
                        onClick={() => setQrSerial(null)}
                        className="w-full text-slate-400 py-1 text-xs hover:text-slate-600 transition"
                      >
                        Dismiss
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Device list */}
            <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-700">Your Registered Devices</h2>
                <span className="text-xs text-slate-400">{devices.length} total</span>
              </div>

              {devLoading ? (
                <div className="px-5 py-8 text-center text-slate-400 text-sm">Loading...</div>
              ) : devices.length === 0 ? (
                <div className="px-5 py-8 text-center text-slate-400 text-sm">
                  No devices registered yet. Register a serial number above.
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 bg-slate-50">
                      <th className="text-left px-5 py-2.5 text-xs font-medium text-slate-500">Serial</th>
                      <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">Model</th>
                      <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">Connectivity</th>
                      <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">Activation</th>
                      <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">Last seen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {devices.map((d) => (
                      <tr key={d.id} className="border-b border-slate-50 hover:bg-slate-50/50">
                        <td className="px-5 py-3 font-mono text-slate-700">{d.serial_number}</td>
                        <td className="px-4 py-3 text-slate-500">{d.model ?? '—'}</td>
                        <td className="px-4 py-3"><StatusBadge status={d.status} /></td>
                        <td className="px-4 py-3"><ClaimStateBadge state={d.claim_state} /></td>
                        <td className="px-4 py-3 text-slate-400 text-xs">
                          {d.last_seen_at
                            ? new Date(d.last_seen_at).toLocaleString()
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <p className="text-xs text-slate-400">
              You see connectivity status only. Customer data (alarms, HMI, history) is not accessible to dealers.
            </p>
          </div>
        )}

        {/* ---- Activation Codes Tab ---- */}
        {tab === 'codes' && (
          <div className="space-y-6">
            {/* Generate new code */}
            <div className="bg-white rounded-lg border border-slate-200 p-5">
              <h2 className="text-sm font-semibold text-slate-700 mb-1">Generate Activation Code</h2>
              <p className="text-xs text-slate-400 mb-4">
                Generate a one-time code for OEM partner devices. The device uses this code on first boot to self-register.
              </p>
              <div className="flex gap-3">
                <div className="flex-1">
                  <input
                    type="text"
                    value={codeDeviceName}
                    onChange={(e) => setCodeDeviceName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleGenerateCode()}
                    placeholder="Device label (e.g. Farm Noord unit #3)"
                    className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm
                      focus:outline-none focus:ring-2 focus:ring-myxon-500"
                  />
                </div>
                <div className="w-28">
                  <select
                    value={codeTtl}
                    onChange={(e) => setCodeTtl(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm
                      focus:outline-none focus:ring-2 focus:ring-myxon-500"
                  >
                    <option value={7}>7 days</option>
                    <option value={14}>14 days</option>
                    <option value={30}>30 days</option>
                    <option value={90}>90 days</option>
                  </select>
                </div>
                <button
                  onClick={handleGenerateCode}
                  disabled={generatingCode}
                  className="px-4 py-2 bg-myxon-600 text-white rounded-md text-sm font-medium
                    hover:bg-myxon-700 transition disabled:opacity-50 whitespace-nowrap"
                >
                  {generatingCode ? 'Generating...' : '+ Generate'}
                </button>
              </div>
              {codeError && <p className="mt-2 text-red-600 text-xs">{codeError}</p>}
            </div>

            {/* Newly generated code — highlighted */}
            {newCode && (
              <div className="bg-white rounded-lg border border-green-200 p-5">
                <p className="text-sm font-semibold text-green-700 mb-3">Code generated!</p>
                <div className="bg-slate-50 rounded-md border border-slate-200 p-4 flex items-center justify-between">
                  <span className="font-mono text-xl font-bold tracking-widest text-slate-800">
                    {newCode.code}
                  </span>
                  <button
                    onClick={() => copyCode(newCode.code)}
                    className="ml-4 px-3 py-1.5 border border-slate-300 rounded text-xs font-medium
                      text-slate-700 hover:bg-slate-100 transition whitespace-nowrap"
                  >
                    {copiedCode === newCode.code ? '✓ Copied' : 'Copy'}
                  </button>
                </div>
                {newCode.device_name && (
                  <p className="mt-2 text-xs text-slate-500">For: <strong>{newCode.device_name}</strong></p>
                )}
                <p className="mt-1 text-xs text-slate-400">
                  Expires: {new Date(newCode.expires_at).toLocaleDateString()}
                </p>
                <p className="mt-3 text-xs text-slate-400">
                  Set <code className="bg-slate-100 px-1 rounded">MYXON_ACTIVATION_CODE={newCode.code}</code> in the device agent environment before first boot.
                </p>
                <button
                  onClick={() => setNewCode(null)}
                  className="mt-3 text-xs text-slate-400 hover:text-slate-600 underline"
                >
                  Dismiss
                </button>
              </div>
            )}

            {/* Code list */}
            <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-700">All Activation Codes</h2>
                <span className="text-xs text-slate-400">{codes.length} total</span>
              </div>

              {codesLoading ? (
                <div className="px-5 py-8 text-center text-slate-400 text-sm">Loading...</div>
              ) : codes.length === 0 ? (
                <div className="px-5 py-8 text-center text-slate-400 text-sm">
                  No codes generated yet.
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 bg-slate-50">
                      <th className="text-left px-5 py-2.5 text-xs font-medium text-slate-500">Code</th>
                      <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">Label</th>
                      <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">Status</th>
                      <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">Expires</th>
                      <th className="px-4 py-2.5" />
                    </tr>
                  </thead>
                  <tbody>
                    {codes.map((c) => {
                      const isUsed = c.used_at !== null
                      const isExpired = !isUsed && new Date(c.expires_at) < new Date()
                      return (
                        <tr key={c.id} className="border-b border-slate-50 hover:bg-slate-50/50">
                          <td className="px-5 py-3">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-slate-700 text-xs">{c.code}</span>
                              {!isUsed && !isExpired && (
                                <button
                                  onClick={() => copyCode(c.code)}
                                  className="text-slate-400 hover:text-slate-600 transition text-xs"
                                >
                                  {copiedCode === c.code ? '✓' : '⎘'}
                                </button>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-slate-500 text-xs">
                            {c.device_name ?? <span className="text-slate-300">—</span>}
                          </td>
                          <td className="px-4 py-3">
                            {isUsed ? (
                              <span className="inline-flex rounded px-2 py-0.5 text-xs font-medium bg-green-50 text-green-600">
                                Used
                              </span>
                            ) : isExpired ? (
                              <span className="inline-flex rounded px-2 py-0.5 text-xs font-medium bg-red-50 text-red-500">
                                Expired
                              </span>
                            ) : (
                              <span className="inline-flex rounded px-2 py-0.5 text-xs font-medium bg-amber-50 text-amber-600">
                                Pending
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-slate-400 text-xs">
                            {new Date(c.expires_at).toLocaleDateString()}
                          </td>
                          <td className="px-4 py-3 text-right">
                            {!isUsed && !isExpired && (
                              <button
                                onClick={() => handleRevokeCode(c.code)}
                                className="text-xs text-red-400 hover:text-red-600 transition"
                              >
                                Revoke
                              </button>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* ---- Customers Tab ---- */}
        {tab === 'customers' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-5">
              <div>
                <h2 className="text-sm font-semibold text-slate-700">Invite New Customer</h2>
                <p className="text-xs text-slate-400 mt-1">
                  Send an invite link to the customer. They will create their own account and activate their devices independently.
                </p>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Customer Email</label>
                  <input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="customer@company.ru"
                    className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm
                      focus:outline-none focus:ring-2 focus:ring-myxon-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Company / Customer Name</label>
                  <input
                    type="text"
                    value={inviteName}
                    onChange={(e) => setInviteName(e.target.value)}
                    placeholder="ООО Птицефабрика Юг"
                    className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm
                      focus:outline-none focus:ring-2 focus:ring-myxon-500"
                  />
                </div>
                {inviteError && <p className="text-red-600 text-xs">{inviteError}</p>}
                <button
                  onClick={handleInvite}
                  disabled={inviting || !inviteEmail.trim() || !inviteName.trim()}
                  className="w-full bg-myxon-600 text-white py-2 rounded-md text-sm font-medium
                    hover:bg-myxon-700 transition disabled:opacity-50"
                >
                  {inviting ? 'Creating invite...' : 'Generate Invite Link'}
                </button>
              </div>
            </div>

            {/* Invite result */}
            {inviteResult && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
                    <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <p className="text-sm font-semibold text-green-800">Invite created for {inviteResult.customer_email}</p>
                </div>
                <div className="bg-white rounded-md border border-green-200 p-3">
                  <p className="text-xs text-slate-500 mb-1">Send this link to the customer:</p>
                  <p className="font-mono text-xs text-slate-700 break-all">{inviteResult.invite_url}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => copyToClipboard(inviteResult.invite_url)}
                    className="flex-1 border border-green-300 text-green-700 py-1.5 rounded text-xs font-medium hover:bg-green-100 transition"
                  >
                    Copy Link
                  </button>
                  <button
                    onClick={() => {
                      window.open(
                        `mailto:${inviteResult.customer_email}?subject=MYXON%20Invite&body=${encodeURIComponent(
                          `You have been invited to MYXON platform.\n\nClick here to register:\n${inviteResult.invite_url}\n\nThe link expires on ${new Date(inviteResult.expires_at).toLocaleDateString()}.`
                        )}`,
                        '_blank'
                      )
                    }}
                    className="flex-1 border border-green-300 text-green-700 py-1.5 rounded text-xs font-medium hover:bg-green-100 transition"
                  >
                    Open in Mail
                  </button>
                </div>
                <p className="text-xs text-slate-400">
                  Expires: {new Date(inviteResult.expires_at).toLocaleDateString()}
                </p>
                <button
                  onClick={() => setInviteResult(null)}
                  className="text-xs text-slate-400 hover:text-slate-600 underline"
                >
                  Create another invite
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
