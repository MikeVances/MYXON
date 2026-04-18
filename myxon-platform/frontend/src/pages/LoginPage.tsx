import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { authApi } from '../api/client'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const { data } = await authApi.login(email, password)
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      // Если пришли через QR-ссылку — вернуться на исходный путь (напр. /claim?sn=...)
      const redirect = searchParams.get('redirect')
      navigate(redirect ? decodeURIComponent(redirect) : '/locations', { replace: true })
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#eceff3] p-4">
      <div className="w-full max-w-sm">
        <div className="rounded-2xl border border-slate-200 bg-white/80 px-8 py-10 shadow-sm backdrop-blur">
          <div className="text-center mb-8">
            <h1 className="text-5xl font-extrabold tracking-tight text-myxon-900">Myxon</h1>
            <p className="text-xs text-slate-500 mt-2 uppercase tracking-[0.22em]">Remote Console</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                E-mail address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-md border-b-2 border-slate-400 bg-slate-200 px-3 py-2.5 text-sm focus:border-myxon-600 focus:outline-none"
                required
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-md border-b-2 border-slate-400 bg-slate-200 px-3 py-2.5 text-sm focus:border-myxon-600 focus:outline-none"
                required
              />
            </div>

            {error && (
              <div className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-600">{error}</div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-full bg-myxon-900 py-2.5 text-sm font-semibold text-white hover:bg-myxon-700 disabled:opacity-50"
            >
              {loading ? 'Signing in...' : 'Log in'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <a href="#" className="text-sm text-slate-600 underline underline-offset-2 hover:text-myxon-700">
              Privacy statement
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
