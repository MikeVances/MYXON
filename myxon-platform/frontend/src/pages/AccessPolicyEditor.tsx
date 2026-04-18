/**
 * AccessPolicyEditor — admin UI для управления политиками доступа.
 *
 * Доступен только пользователям с ролью customer_admin (и выше).
 * Позволяет:
 *  - Видеть все политики тенанта
 *  - Создать новую политику
 *  - Редактировать существующую (inline)
 *  - Удалить политику (если не назначена)
 *  - Засеять дефолтные политики (Полный доступ / Инженер / Оператор / Наблюдатель)
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { accessPoliciesApi } from '../api/client'
import type { AccessPolicy } from '../api/client'
import {
  Shield,
  Plus,
  Trash2,
  ChevronLeft,
  Check,
  X,
  Sparkles,
} from 'lucide-react'

const SEVERITY_LABELS: Record<string, string> = {
  all: 'Все аларми',
  warning_and_above: 'Предупреждения и выше',
  critical_only: 'Только критические',
}

function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      onClick={() => !disabled && onChange(!checked)}
      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
        checked ? 'bg-myxon-600' : 'bg-slate-300'
      } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
    >
      <span
        className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${
          checked ? 'translate-x-4' : 'translate-x-1'
        }`}
      />
    </button>
  )
}

interface PolicyRowProps {
  policy: AccessPolicy
  onUpdate: (id: string, data: Partial<AccessPolicy>) => Promise<void>
  onDelete: (id: string) => Promise<void>
}

function PolicyRow({ policy, onUpdate, onDelete }: PolicyRowProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<AccessPolicy>(policy)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      await onUpdate(policy.id, draft)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  const cancel = () => {
    setDraft(policy)
    setEditing(false)
  }

  const del = async () => {
    if (!confirm(`Удалить политику «${policy.name}»?`)) return
    setDeleting(true)
    try {
      await onDelete(policy.id)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          {editing ? (
            <input
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              className="rounded border border-slate-300 px-2 py-1 text-sm font-semibold"
            />
          ) : (
            <p className="font-semibold text-slate-800">
              {policy.name}
              {policy.is_default && (
                <span className="ml-2 rounded-full bg-myxon-100 px-2 py-0.5 text-xs font-normal text-myxon-700">
                  по умолчанию
                </span>
              )}
            </p>
          )}
          {editing ? (
            <input
              value={draft.description ?? ''}
              onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              placeholder="Описание (необязательно)"
              className="mt-1 w-full rounded border border-slate-200 px-2 py-0.5 text-xs text-slate-500"
            />
          ) : (
            <p className="text-xs text-slate-500">{policy.description || '—'}</p>
          )}
        </div>

        <div className="flex items-center gap-2">
          {editing ? (
            <>
              <button
                onClick={save}
                disabled={saving}
                className="flex items-center gap-1 rounded bg-myxon-600 px-2 py-1 text-xs text-white disabled:opacity-50"
              >
                <Check size={12} />
                {saving ? 'Сохраняем...' : 'Сохранить'}
              </button>
              <button onClick={cancel} className="flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs text-slate-600">
                <X size={12} /> Отмена
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setEditing(true)}
                className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
              >
                Редактировать
              </button>
              <button
                onClick={del}
                disabled={deleting}
                className="rounded border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-50"
              >
                <Trash2 size={12} />
              </button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
        {[
          { label: 'HMI доступ', key: 'allow_hmi' },
          { label: 'VNC доступ', key: 'allow_vnc' },
          { label: 'HTTP доступ', key: 'allow_http' },
          { label: 'Просмотр алармов', key: 'allow_alarms_view' },
          { label: 'Подтверждение алармов', key: 'allow_alarms_acknowledge' },
          { label: 'Просмотр аудита', key: 'allow_audit_view' },
        ].map(({ label, key }) => (
          <div key={key} className="flex items-center justify-between gap-2">
            <span className="text-slate-600">{label}</span>
            <Toggle
              checked={!!draft[key as keyof AccessPolicy]}
              onChange={(v) => setDraft({ ...draft, [key]: v })}
              disabled={!editing}
            />
          </div>
        ))}

        <div className="col-span-2 flex items-center justify-between gap-2 sm:col-span-3">
          <span className="text-slate-600">Фильтр аларм по уровню</span>
          {editing ? (
            <select
              value={draft.alarm_severity_filter}
              onChange={(e) => setDraft({ ...draft, alarm_severity_filter: e.target.value })}
              className="rounded border border-slate-200 px-2 py-0.5 text-xs"
            >
              <option value="all">Все аларми</option>
              <option value="warning_and_above">Предупреждения и выше</option>
              <option value="critical_only">Только критические</option>
            </select>
          ) : (
            <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
              {SEVERITY_LABELS[policy.alarm_severity_filter] ?? policy.alarm_severity_filter}
            </span>
          )}
        </div>

        {editing && (
          <div className="col-span-2 flex items-center justify-between gap-2 sm:col-span-3">
            <span className="text-slate-600">По умолчанию для тенанта</span>
            <Toggle
              checked={draft.is_default}
              onChange={(v) => setDraft({ ...draft, is_default: v })}
            />
          </div>
        )}
      </div>
    </div>
  )
}

export default function AccessPolicyEditor() {
  const navigate = useNavigate()
  const [policies, setPolicies] = useState<AccessPolicy[]>([])
  const [loading, setLoading] = useState(true)
  const [seeding, setSeeding] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [newPolicy, setNewPolicy] = useState<Partial<AccessPolicy>>({
    name: '',
    description: '',
    allow_hmi: true,
    allow_vnc: false,
    allow_http: false,
    allow_alarms_view: true,
    allow_alarms_acknowledge: true,
    alarm_severity_filter: 'all',
    allow_audit_view: false,
    is_default: false,
  })
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    try {
      const { data } = await accessPoliciesApi.list()
      setPolicies(data)
    } catch {
      setError('Не удалось загрузить политики')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleUpdate = async (id: string, data: Partial<AccessPolicy>) => {
    setError('')
    try {
      await accessPoliciesApi.update(id, data)
      await load()
    } catch {
      setError('Не удалось сохранить политику')
    }
  }

  const handleDelete = async (id: string) => {
    setError('')
    try {
      await accessPoliciesApi.delete(id)
      await load()
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response: { data: { detail: string } } }).response?.data?.detail
          : null
      setError(detail || 'Не удалось удалить политику')
    }
  }

  const handleCreate = async () => {
    if (!newPolicy.name?.trim()) {
      setError('Название обязательно')
      return
    }
    setCreating(true)
    setError('')
    try {
      await accessPoliciesApi.create(newPolicy)
      setShowCreate(false)
      setNewPolicy({
        name: '',
        description: '',
        allow_hmi: true,
        allow_vnc: false,
        allow_http: false,
        allow_alarms_view: true,
        allow_alarms_acknowledge: true,
        alarm_severity_filter: 'all',
        allow_audit_view: false,
        is_default: false,
      })
      await load()
    } catch {
      setError('Не удалось создать политику')
    } finally {
      setCreating(false)
    }
  }

  const handleSeedDefaults = async () => {
    setSeeding(true)
    setError('')
    try {
      await accessPoliciesApi.seedDefaults()
      await load()
    } catch {
      setError('Не удалось создать дефолтные политики')
    } finally {
      setSeeding(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#eef0f4] text-slate-800">
      <header className="border-b border-slate-200 bg-white/85 px-4 py-3 md:px-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="rounded-md p-1 text-slate-600 hover:bg-slate-100"
          >
            <ChevronLeft size={18} />
          </button>
          <Shield size={18} className="text-myxon-600" />
          <h1 className="text-lg font-semibold tracking-tight">Политики доступа</h1>
        </div>
      </header>

      <div className="mx-auto max-w-4xl p-4 md:p-6 space-y-4">
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-slate-500">
            Политики определяют что пользователь может делать на устройствах площадки.
          </p>
          <div className="flex gap-2">
            {policies.length === 0 && !loading && (
              <button
                onClick={handleSeedDefaults}
                disabled={seeding}
                className="flex items-center gap-1 rounded border border-myxon-300 bg-myxon-50 px-3 py-1.5 text-sm text-myxon-700 hover:bg-myxon-100 disabled:opacity-50"
              >
                <Sparkles size={14} />
                {seeding ? 'Создаём...' : 'Загрузить стандартные'}
              </button>
            )}
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-1 rounded bg-myxon-600 px-3 py-1.5 text-sm text-white hover:bg-myxon-700"
            >
              <Plus size={14} />
              Новая политика
            </button>
          </div>
        </div>

        {showCreate && (
          <div className="rounded-lg border border-myxon-200 bg-myxon-50 p-4">
            <h3 className="mb-3 text-sm font-semibold text-myxon-800">Новая политика</h3>
            <div className="space-y-2">
              <input
                value={newPolicy.name ?? ''}
                onChange={(e) => setNewPolicy({ ...newPolicy, name: e.target.value })}
                placeholder="Название *"
                className="w-full rounded border border-slate-300 px-3 py-1.5 text-sm"
              />
              <input
                value={newPolicy.description ?? ''}
                onChange={(e) => setNewPolicy({ ...newPolicy, description: e.target.value })}
                placeholder="Описание (необязательно)"
                className="w-full rounded border border-slate-200 px-3 py-1.5 text-sm"
              />
              <div className="grid grid-cols-2 gap-x-6 gap-y-2 pt-2 text-sm sm:grid-cols-3">
                {[
                  { label: 'HMI доступ', key: 'allow_hmi' },
                  { label: 'VNC доступ', key: 'allow_vnc' },
                  { label: 'HTTP доступ', key: 'allow_http' },
                  { label: 'Просмотр алармов', key: 'allow_alarms_view' },
                  { label: 'Подтверждение алармов', key: 'allow_alarms_acknowledge' },
                  { label: 'Просмотр аудита', key: 'allow_audit_view' },
                ].map(({ label, key }) => (
                  <div key={key} className="flex items-center justify-between gap-2">
                    <span className="text-slate-600">{label}</span>
                    <Toggle
                      checked={!!newPolicy[key as keyof AccessPolicy]}
                      onChange={(v) => setNewPolicy({ ...newPolicy, [key]: v })}
                    />
                  </div>
                ))}
                <div className="col-span-2 flex items-center justify-between gap-2 sm:col-span-3">
                  <span className="text-slate-600">Фильтр алармов</span>
                  <select
                    value={newPolicy.alarm_severity_filter ?? 'all'}
                    onChange={(e) => setNewPolicy({ ...newPolicy, alarm_severity_filter: e.target.value })}
                    className="rounded border border-slate-200 px-2 py-0.5 text-xs"
                  >
                    <option value="all">Все аларми</option>
                    <option value="warning_and_above">Предупреждения и выше</option>
                    <option value="critical_only">Только критические</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  onClick={handleCreate}
                  disabled={creating}
                  className="rounded bg-myxon-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
                >
                  {creating ? 'Создаём...' : 'Создать'}
                </button>
                <button
                  onClick={() => setShowCreate(false)}
                  className="rounded border border-slate-200 px-3 py-1.5 text-sm text-slate-600"
                >
                  Отмена
                </button>
              </div>
            </div>
          </div>
        )}

        {loading ? (
          <p className="text-sm text-slate-400">Загружаем политики...</p>
        ) : policies.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center">
            <Shield size={32} className="mx-auto mb-2 text-slate-300" />
            <p className="text-sm text-slate-500">Политик пока нет.</p>
            <p className="mt-1 text-xs text-slate-400">
              Нажмите «Загрузить стандартные», чтобы создать шаблоны,
              или создайте политику вручную.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {policies.map((p) => (
              <PolicyRow
                key={p.id}
                policy={p}
                onUpdate={handleUpdate}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
