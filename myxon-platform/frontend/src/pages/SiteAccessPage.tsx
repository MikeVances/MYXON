/**
 * SiteAccessPage — управление доступом пользователей к площадкам.
 *
 * customer_admin видит:
 *   - список площадок → выбирает одну
 *   - таблицу пользователей тенанта с их текущей политикой на выбранной площадке
 *   - может назначить/снять доступ и выбрать AccessPolicy
 */
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Shield,
  Users,
  ChevronLeft,
  Plus,
  Trash2,
  Check,
  AlertCircle,
  Loader2,
} from 'lucide-react'
import {
  sitesApi,
  siteAccessApi,
  accessPoliciesApi,
  type SiteAccessEntry,
  type TenantUser,
  type AccessPolicy,
} from '../api/client'

interface Site {
  id: string
  name: string
  address: string | null
  devices_count: number
}

// ── Inline role badge ─────────────────────────────────────────────────────────
function RoleBadge({ role }: { role: string }) {
  const map: Record<string, string> = {
    customer_admin: 'bg-purple-100 text-purple-700',
    customer_engineer: 'bg-blue-100 text-blue-700',
    customer_viewer: 'bg-slate-100 text-slate-600',
  }
  const label: Record<string, string> = {
    customer_admin: 'Администратор',
    customer_engineer: 'Инженер',
    customer_viewer: 'Наблюдатель',
  }
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${map[role] ?? 'bg-slate-100 text-slate-600'}`}>
      {label[role] ?? role}
    </span>
  )
}

// ── Row: one user's access record ─────────────────────────────────────────────
function AccessRow({
  user,
  entry,
  policies,
  onSave,
  onRemove,
}: {
  user: TenantUser
  entry: SiteAccessEntry | null
  policies: AccessPolicy[]
  onSave: (userId: string, role: string, policyId: string | null) => Promise<void>
  onRemove: (userId: string) => Promise<void>
}) {
  const [role, setRole] = useState(entry?.role ?? 'customer_viewer')
  const [policyId, setPolicyId] = useState<string>(entry?.access_policy_id ?? '')
  const [saving, setSaving] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [saved, setSaved] = useState(false)

  const hasAccess = entry !== null
  const dirty =
    role !== (entry?.role ?? 'customer_viewer') ||
    policyId !== (entry?.access_policy_id ?? '')

  async function handleSave() {
    setSaving(true)
    await onSave(user.id, role, policyId || null)
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  async function handleRemove() {
    setRemoving(true)
    await onRemove(user.id)
    setRemoving(false)
  }

  return (
    <tr className="border-b border-slate-100 last:border-0">
      <td className="py-3 pr-4">
        <p className="text-sm font-medium text-slate-800">{user.full_name}</p>
        <p className="text-xs text-slate-500">{user.email}</p>
      </td>

      <td className="py-3 pr-4">
        <RoleBadge role={user.role} />
      </td>

      <td className="py-3 pr-4">
        {hasAccess ? (
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="rounded border border-slate-200 bg-white px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-myxon-400"
          >
            <option value="customer_viewer">Наблюдатель</option>
            <option value="customer_engineer">Инженер</option>
            <option value="customer_admin">Администратор</option>
          </select>
        ) : (
          <span className="text-xs text-slate-400">Нет доступа</span>
        )}
      </td>

      <td className="py-3 pr-4">
        {hasAccess ? (
          <select
            value={policyId}
            onChange={(e) => setPolicyId(e.target.value)}
            className="rounded border border-slate-200 bg-white px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-myxon-400"
          >
            <option value="">— по умолчанию тенанта —</option>
            {policies.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        ) : (
          <span className="text-xs text-slate-400">—</span>
        )}
      </td>

      <td className="py-3 text-right">
        <div className="flex items-center justify-end gap-2">
          {!hasAccess ? (
            <button
              onClick={() => handleSave()}
              disabled={saving}
              className="flex items-center gap-1 rounded bg-myxon-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-myxon-700 disabled:opacity-50"
            >
              {saving ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
              Дать доступ
            </button>
          ) : (
            <>
              {dirty && (
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-1 rounded bg-myxon-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-myxon-700 disabled:opacity-50"
                >
                  {saving ? (
                    <Loader2 size={12} className="animate-spin" />
                  ) : saved ? (
                    <Check size={12} />
                  ) : null}
                  Сохранить
                </button>
              )}
              {saved && !dirty && (
                <span className="flex items-center gap-1 text-xs text-green-600">
                  <Check size={12} /> Сохранено
                </span>
              )}
              <button
                onClick={handleRemove}
                disabled={removing}
                className="rounded p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-500"
                title="Убрать доступ"
              >
                {removing ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
              </button>
            </>
          )}
        </div>
      </td>
    </tr>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function SiteAccessPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedSiteId = searchParams.get('site')

  const [sites, setSites] = useState<Site[]>([])
  const [users, setUsers] = useState<TenantUser[]>([])
  const [accessEntries, setAccessEntries] = useState<SiteAccessEntry[]>([])
  const [policies, setPolicies] = useState<AccessPolicy[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load sites + users + policies on mount
  useEffect(() => {
    Promise.all([
      sitesApi.list(),
      siteAccessApi.listUsers(),
      accessPoliciesApi.list(),
    ]).then(([s, u, p]) => {
      setSites(s.data)
      setUsers(u.data)
      setPolicies(p.data)
    }).catch(() => setError('Ошибка загрузки данных'))
  }, [])

  // Load site access when site selected
  useEffect(() => {
    if (!selectedSiteId) {
      setAccessEntries([])
      return
    }
    setLoading(true)
    setError(null)
    siteAccessApi.listSiteAccess(selectedSiteId)
      .then(({ data }) => setAccessEntries(data))
      .catch(() => setError('Ошибка загрузки доступов'))
      .finally(() => setLoading(false))
  }, [selectedSiteId])

  const selectedSite = sites.find((s) => s.id === selectedSiteId)

  async function handleSave(userId: string, role: string, policyId: string | null) {
    if (!selectedSiteId) return
    try {
      const { data } = await siteAccessApi.upsert(selectedSiteId, userId, role, policyId)
      setAccessEntries((prev) => {
        const existing = prev.findIndex((e) => e.user_id === userId)
        if (existing >= 0) {
          const next = [...prev]
          next[existing] = data
          return next
        }
        return [...prev, data]
      })
    } catch {
      setError('Ошибка сохранения')
    }
  }

  async function handleRemove(userId: string) {
    if (!selectedSiteId) return
    try {
      await siteAccessApi.remove(selectedSiteId, userId)
      setAccessEntries((prev) => prev.filter((e) => e.user_id !== userId))
    } catch {
      setError('Ошибка удаления доступа')
    }
  }

  return (
    <div className="min-h-screen bg-[#eef0f4] text-slate-800">
      <div className="mx-auto max-w-5xl p-4 md:p-6">

        {/* Header */}
        <header className="mb-6 flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="rounded-lg border border-slate-200 bg-white p-2 text-slate-500 hover:bg-slate-50"
          >
            <ChevronLeft size={16} />
          </button>
          <div className="flex items-center gap-2">
            <Shield size={18} className="text-myxon-600" />
            <h1 className="text-xl font-bold tracking-tight">Управление доступом</h1>
          </div>
        </header>

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle size={14} /> {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-[240px_1fr]">

          {/* Site list */}
          <aside className="rounded-lg border border-slate-200 bg-white p-3">
            <p className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Площадки
            </p>
            {sites.length === 0 && (
              <p className="px-2 text-sm text-slate-400">Нет площадок</p>
            )}
            {sites.map((site) => (
              <button
                key={site.id}
                onClick={() => setSearchParams({ site: site.id })}
                className={`w-full rounded-lg px-3 py-2.5 text-left text-sm transition ${
                  site.id === selectedSiteId
                    ? 'bg-myxon-50 font-medium text-myxon-800'
                    : 'text-slate-700 hover:bg-slate-50'
                }`}
              >
                <p className="font-medium">{site.name}</p>
                {site.address && (
                  <p className="mt-0.5 text-xs text-slate-500 truncate">{site.address}</p>
                )}
              </button>
            ))}
          </aside>

          {/* Access table */}
          <main className="rounded-lg border border-slate-200 bg-white">
            {!selectedSiteId ? (
              <div className="flex h-48 items-center justify-center text-slate-400">
                <div className="text-center">
                  <Users size={32} className="mx-auto mb-2 opacity-30" />
                  <p className="text-sm">Выберите площадку слева</p>
                </div>
              </div>
            ) : loading ? (
              <div className="flex h-48 items-center justify-center text-slate-400">
                <Loader2 size={24} className="animate-spin" />
              </div>
            ) : (
              <>
                <div className="border-b border-slate-100 px-5 py-3">
                  <h2 className="font-semibold">{selectedSite?.name}</h2>
                  <p className="text-xs text-slate-500">
                    {accessEntries.length} из {users.length} пользователей имеют доступ
                  </p>
                </div>

                <div className="overflow-x-auto px-5">
                  <table className="w-full min-w-[600px]">
                    <thead>
                      <tr className="border-b border-slate-100">
                        <th className="py-3 pr-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Пользователь
                        </th>
                        <th className="py-3 pr-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Роль в тенанте
                        </th>
                        <th className="py-3 pr-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Роль на площадке
                        </th>
                        <th className="py-3 pr-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Политика доступа
                        </th>
                        <th className="py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Действия
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map((u) => {
                        const entry = accessEntries.find((e) => e.user_id === u.id) ?? null
                        return (
                          <AccessRow
                            key={u.id}
                            user={u}
                            entry={entry}
                            policies={policies}
                            onSave={handleSave}
                            onRemove={handleRemove}
                          />
                        )
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="border-t border-slate-100 px-5 py-3">
                  <p className="text-xs text-slate-400">
                    Политика "—" означает применение дефолтной политики тенанта.
                    Индивидуальная политика имеет приоритет.
                  </p>
                </div>
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  )
}
