import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { devicesApi, sitesApi } from '../api/client'

type Step = 'input' | 'preview' | 'site' | 'done'

interface ClaimPreview {
  serial_number: string
  model: string | null
  claim_state: string
  current_tenant: string | null
}

interface ClaimResult {
  device_id: string
  claim_status: string
  message: string
}

interface Site {
  id: string
  name: string
  address?: string | null
}

export default function ClaimWizard() {
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>('input')
  const [serial, setSerial] = useState('')
  const [preview, setPreview] = useState<ClaimPreview | null>(null)
  const [sites, setSites] = useState<Site[]>([])
  const [selectedSiteId, setSelectedSiteId] = useState<string>('')
  const [result, setResult] = useState<ClaimResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    sitesApi.list().then((r) => setSites(r.data)).catch(() => {})
  }, [])

  const handlePreview = async () => {
    if (!serial.trim()) {
      setError('Enter the serial number printed on the device label')
      return
    }
    setLoading(true)
    setError('')
    try {
      const { data } = await devicesApi.claimPreview(serial.trim())
      setPreview(data)
      setStep('preview')
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response: { data: { detail: string } } }).response?.data?.detail
          : 'Device not found'
      setError(msg || 'Device not found')
    } finally {
      setLoading(false)
    }
  }

  const handleClaim = async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await devicesApi.claim(serial.trim(), selectedSiteId || undefined)
      setResult(data)
      setStep('done')
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response: { data: { detail: string } } }).response?.data?.detail
          : 'Activation failed'
      setError(msg || 'Activation failed')
    } finally {
      setLoading(false)
    }
  }

  const STEPS: Step[] = ['input', 'preview', 'site', 'done']
  const currentIdx = STEPS.indexOf(step)

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center gap-4">
        <button
          onClick={() => navigate('/devices')}
          className="text-slate-400 hover:text-slate-600 transition"
        >
          ← Back
        </button>
        <h1 className="text-xl font-bold text-myxon-900">MYXON</h1>
        <span className="text-slate-400 text-sm ml-auto">Activate Device</span>
      </header>

      <div className="max-w-lg mx-auto px-6 py-10">
        {/* Step indicator */}
        <div className="flex items-center gap-2 mb-8">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition
                  ${step === s ? 'bg-myxon-600 text-white' :
                    currentIdx > i ? 'bg-green-500 text-white' : 'bg-slate-200 text-slate-500'}`}
              >
                {currentIdx > i ? '✓' : i + 1}
              </div>
              {i < STEPS.length - 1 && <div className="w-8 h-px bg-slate-200" />}
            </div>
          ))}
          <span className="ml-2 text-xs text-slate-400">
            {step === 'input' && 'Enter serial'}
            {step === 'preview' && 'Confirm device'}
            {step === 'site' && 'Assign location'}
            {step === 'done' && 'Done'}
          </span>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm mb-6">
            {error}
          </div>
        )}

        {/* Step 1: Serial number */}
        {step === 'input' && (
          <div className="bg-white rounded-lg border border-slate-200 p-6 space-y-5">
            <div>
              <h2 className="text-base font-semibold text-slate-800">Enter Serial Number</h2>
              <p className="text-sm text-slate-500 mt-1">
                Find the serial number on the label attached to your Orange Pi router.
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Serial Number</label>
              <input
                type="text"
                value={serial}
                onChange={(e) => setSerial(e.target.value.toUpperCase())}
                onKeyDown={(e) => e.key === 'Enter' && handlePreview()}
                placeholder="e.g. MX-2024-00001"
                className="w-full px-4 py-2.5 border border-slate-300 rounded-md font-mono text-sm
                  focus:outline-none focus:ring-2 focus:ring-myxon-500"
                autoFocus
              />
            </div>
            <button
              onClick={handlePreview}
              disabled={loading || !serial.trim()}
              className="w-full bg-myxon-600 text-white py-2.5 rounded-md text-sm font-medium
                hover:bg-myxon-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Checking...' : 'Find Device →'}
            </button>
          </div>
        )}

        {/* Step 2: Confirm device */}
        {step === 'preview' && preview && (
          <div className="bg-white rounded-lg border border-slate-200 p-6 space-y-5">
            <div>
              <h2 className="text-base font-semibold text-slate-800">Confirm Device</h2>
              <p className="text-sm text-slate-500 mt-1">Make sure this is your device before activating.</p>
            </div>
            <div className="bg-slate-50 rounded-lg p-4 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-slate-500">Serial Number</span>
                <span className="font-mono font-medium text-slate-800">{preview.serial_number}</span>
              </div>
              {preview.model && (
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Model</span>
                  <span className="font-medium text-slate-800">{preview.model}</span>
                </div>
              )}
              <div className="flex justify-between text-sm">
                <span className="text-slate-500">Status</span>
                <span className={`font-medium ${
                  preview.claim_state === 'ready_for_transfer' ? 'text-green-600' : 'text-amber-600'
                }`}>
                  {preview.claim_state === 'ready_for_transfer' ? '✓ Available' : preview.claim_state}
                </span>
              </div>
            </div>
            {preview.claim_state !== 'ready_for_transfer' && (
              <div className="bg-amber-50 border border-amber-200 text-amber-700 rounded-lg p-3 text-sm">
                This device cannot be activated (state: {preview.claim_state}). Contact your vendor.
              </div>
            )}
            <div className="flex gap-3">
              <button
                onClick={() => { setStep('input'); setError('') }}
                className="flex-1 border border-slate-300 text-slate-700 py-2 rounded-md text-sm font-medium hover:bg-slate-50 transition"
              >
                ← Back
              </button>
              <button
                onClick={() => setStep('site')}
                disabled={preview.claim_state !== 'ready_for_transfer'}
                className="flex-1 bg-myxon-600 text-white py-2 rounded-md text-sm font-medium
                  hover:bg-myxon-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Continue →
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Assign to site */}
        {step === 'site' && (
          <div className="bg-white rounded-lg border border-slate-200 p-6 space-y-5">
            <div>
              <h2 className="text-base font-semibold text-slate-800">Assign Location</h2>
              <p className="text-sm text-slate-500 mt-1">
                Which farm or site does this device belong to?
              </p>
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              <button
                onClick={() => setSelectedSiteId('')}
                className={`w-full text-left p-3 rounded-md border text-sm transition ${
                  selectedSiteId === ''
                    ? 'border-myxon-500 bg-myxon-50 text-myxon-700'
                    : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                <span className="font-medium">Skip for now</span>
                <span className="block text-slate-400 text-xs mt-0.5">Assign to a location later</span>
              </button>
              {sites.map((site) => (
                <button
                  key={site.id}
                  onClick={() => setSelectedSiteId(site.id)}
                  className={`w-full text-left p-3 rounded-md border text-sm transition ${
                    selectedSiteId === site.id
                      ? 'border-myxon-500 bg-myxon-50 text-myxon-700'
                      : 'border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <span className="font-medium">{site.name}</span>
                  {site.address && (
                    <span className="block text-slate-400 text-xs mt-0.5">{site.address}</span>
                  )}
                </button>
              ))}
              {sites.length === 0 && (
                <p className="text-sm text-slate-400 text-center py-4">
                  No locations yet — you can add them later in Settings
                </p>
              )}
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => { setStep('preview'); setError('') }}
                className="flex-1 border border-slate-300 text-slate-700 py-2 rounded-md text-sm font-medium hover:bg-slate-50 transition"
              >
                ← Back
              </button>
              <button
                onClick={handleClaim}
                disabled={loading}
                className="flex-1 bg-myxon-600 text-white py-2 rounded-md text-sm font-medium
                  hover:bg-myxon-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Activating...' : 'Activate Device'}
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Success */}
        {step === 'done' && result && (
          <div className="bg-white rounded-lg border border-slate-200 p-6 text-center space-y-4">
            <div className="w-14 h-14 bg-green-100 rounded-full flex items-center justify-center mx-auto">
              <svg className="w-7 h-7 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-800">Device Activated!</h3>
              <p className="text-sm text-slate-500 mt-1">{result.message}</p>
            </div>
            <p className="text-xs text-slate-400">
              The device will appear online once it establishes a tunnel connection.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => navigate('/devices')}
                className="flex-1 border border-slate-300 text-slate-700 py-2 rounded-md text-sm font-medium hover:bg-slate-50 transition"
              >
                All Devices
              </button>
              <button
                onClick={() => navigate(`/devices/${result.device_id}`)}
                className="flex-1 bg-myxon-600 text-white py-2 rounded-md text-sm font-medium hover:bg-myxon-700 transition"
              >
                Open Dashboard →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
