/**
 * RegisterByInvite — public page.
 * Customer arrives here via invite link: /register?token=<token>
 * Fetches invite info (pre-filled email/name), customer sets password → signs up.
 */
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { authApi } from '../api/client'

type PageState = 'loading' | 'ready' | 'error' | 'done'

export default function RegisterByInvite() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''

  const [pageState, setPageState] = useState<PageState>('loading')
  const [errorMsg, setErrorMsg] = useState('')

  // Pre-filled from invite
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')

  // User fills in
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')

  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')

  useEffect(() => {
    if (!token) {
      setErrorMsg('No invite token in URL. Check the link.')
      setPageState('error')
      return
    }
    authApi
      .getInviteInfo(token)
      .then(({ data }) => {
        setEmail(data.customer_email)
        setName(data.customer_name)
        setPageState('ready')
      })
      .catch((err: unknown) => {
        const detail =
          err && typeof err === 'object' && 'response' in err
            ? (err as { response: { data: { detail: string } } }).response?.data?.detail
            : null
        setErrorMsg(detail || 'Invite not found or expired.')
        setPageState('error')
      })
  }, [token])

  async function handleSubmit() {
    if (!password) { setFormError('Password is required'); return }
    if (password.length < 8) { setFormError('Password must be at least 8 characters'); return }
    if (password !== passwordConfirm) { setFormError('Passwords do not match'); return }

    setSubmitting(true)
    setFormError('')
    try {
      const { data } = await authApi.registerByInvite(token, password, name)
      // Store tokens and redirect
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      setPageState('done')
      setTimeout(() => navigate('/devices'), 1500)
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response: { data: { detail: string } } }).response?.data?.detail
          : 'Registration failed'
      setFormError(msg || 'Registration failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-myxon-900">MYXON</h1>
          <p className="text-sm text-slate-500 mt-1">Industrial IoT Platform</p>
        </div>

        {/* Loading */}
        {pageState === 'loading' && (
          <div className="bg-white rounded-lg border border-slate-200 p-8 text-center">
            <div className="w-8 h-8 border-2 border-myxon-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-slate-500">Verifying invite...</p>
          </div>
        )}

        {/* Error */}
        {pageState === 'error' && (
          <div className="bg-white rounded-lg border border-slate-200 p-8 text-center space-y-4">
            <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto">
              <svg className="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-800">Invalid Invite</h2>
              <p className="text-sm text-slate-500 mt-1">{errorMsg}</p>
            </div>
            <p className="text-xs text-slate-400">
              Contact your vendor to request a new invite link.
            </p>
          </div>
        )}

        {/* Registration form */}
        {pageState === 'ready' && (
          <div className="bg-white rounded-lg border border-slate-200 p-6 space-y-5">
            <div>
              <h2 className="text-base font-semibold text-slate-800">Create Your Account</h2>
              <p className="text-sm text-slate-500 mt-1">
                You've been invited to MYXON. Set a password to complete registration.
              </p>
            </div>

            {/* Pre-filled info */}
            <div className="bg-slate-50 rounded-lg p-4 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-slate-500">Email</span>
                <span className="font-medium text-slate-700">{email}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-500">Company</span>
                <span className="font-medium text-slate-700">{name}</span>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Your Name <span className="text-slate-400 font-normal">(optional)</span>
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Full name"
                  className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm
                    focus:outline-none focus:ring-2 focus:ring-myxon-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 8 characters"
                  className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm
                    focus:outline-none focus:ring-2 focus:ring-myxon-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Confirm Password</label>
                <input
                  type="password"
                  value={passwordConfirm}
                  onChange={(e) => setPasswordConfirm(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                  placeholder="Repeat password"
                  className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm
                    focus:outline-none focus:ring-2 focus:ring-myxon-500"
                />
              </div>
            </div>

            {formError && (
              <p className="text-red-600 text-sm">{formError}</p>
            )}

            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="w-full bg-myxon-600 text-white py-2.5 rounded-md text-sm font-medium
                hover:bg-myxon-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? 'Creating account...' : 'Create Account & Sign In'}
            </button>

            <p className="text-xs text-center text-slate-400">
              Already have an account?{' '}
              <button
                onClick={() => navigate('/login')}
                className="text-myxon-600 hover:underline"
              >
                Sign in
              </button>
            </p>
          </div>
        )}

        {/* Success */}
        {pageState === 'done' && (
          <div className="bg-white rounded-lg border border-slate-200 p-8 text-center space-y-4">
            <div className="w-14 h-14 bg-green-100 rounded-full flex items-center justify-center mx-auto">
              <svg className="w-7 h-7 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-800">Account Created!</h2>
              <p className="text-sm text-slate-500 mt-1">Signing you in...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
