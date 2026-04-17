import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { devicesApi, getStoredUserRole, isAdminRole, type Device } from '../api/client'
import { Monitor, Search, Mail, LogOut, Shield, ChevronDown } from 'lucide-react'

export default function DevicesPage() {
  const [devices, setDevices] = useState<Device[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const selectedSite = params.get('site')

  const userRole = getStoredUserRole()
  const canManageAccess = isAdminRole(userRole)

  useEffect(() => {
    const siteArg = selectedSite && selectedSite !== 'unassigned' ? selectedSite : undefined
    setLoading(true)
    setDevices([])
    setNextCursor(null)
    devicesApi.list(siteArg).then(({ data }) => {
      const items = selectedSite === 'unassigned'
        ? data.items.filter((d) => !d.site_id)
        : data.items
      setDevices(items)
      setNextCursor(data.next_cursor)
      setLoading(false)
    })
  }, [selectedSite])

  async function loadMore() {
    if (!nextCursor) return
    setLoadingMore(true)
    const siteArg = selectedSite && selectedSite !== 'unassigned' ? selectedSite : undefined
    const { data } = await devicesApi.list(siteArg, nextCursor)
    setDevices((prev) => [...prev, ...data.items])
    setNextCursor(data.next_cursor)
    setLoadingMore(false)
  }

  const filtered = devices.filter(
    (d) =>
      d.name.toLowerCase().includes(search.toLowerCase()) ||
      d.serial_number.toLowerCase().includes(search.toLowerCase())
  )

  const statusColor = (status: string) => {
    if (status === 'online') return 'bg-green-500'
    if (status === 'offline') return 'bg-red-400'
    return 'bg-slate-300'
  }

  return (
    <div className="min-h-screen bg-[#eef0f4] text-slate-800">
      <div className="flex min-h-screen">

        {/* Sidebar */}
        <aside className="w-[84px] border-r border-slate-200 bg-white/75 backdrop-blur flex flex-col">
          <div className="p-4 text-[24px] font-semibold tracking-tight text-myxon-900">M</div>
          <div className="px-2 pt-2 space-y-1 flex-1">
            <button
              onClick={() => navigate('/devices')}
              className="w-full rounded-xl bg-[#e8ecff] text-myxon-900 py-2 flex flex-col items-center gap-1 text-[11px] font-medium"
            >
              <Monitor size={16} />
              Devices
            </button>

            {/* Access management — only for customer_admin and above */}
            {canManageAccess && (
              <button
                onClick={() => navigate('/site-access')}
                className="w-full rounded-xl py-2 flex flex-col items-center gap-1 text-[11px] text-slate-500 hover:bg-slate-50"
                title="Управление доступом"
              >
                <Shield size={16} />
                Access
              </button>
            )}
          </div>

          {/* Logout at bottom */}
          <div className="px-2 pb-3">
            <button
              onClick={() => { localStorage.clear(); navigate('/login') }}
              className="w-full rounded-xl py-2 flex flex-col items-center gap-1 text-[11px] text-slate-400 hover:bg-slate-50"
              title="Sign out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </aside>

        <main className="flex-1 p-4 md:p-6">
          <header className="mb-6 flex items-center gap-3">
            <button
              onClick={() => navigate('/locations')}
              className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
            >
              Locations
            </button>
            <div className="inline-flex items-center rounded-lg bg-white border border-slate-200 px-2 py-1 text-xs text-slate-600">
              {selectedSite === 'unassigned' ? 'Unassigned' : selectedSite ? 'Location' : 'All'}
            </div>
            <div className="relative w-full max-w-2xl">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search for devices"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full rounded-full border border-slate-200 bg-white pl-9 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-myxon-500"
              />
            </div>
            <button className="rounded-lg border border-slate-200 bg-white p-2 text-slate-500">
              <Mail size={16} />
            </button>
            <button
              onClick={() => navigate('/claim')}
              className="rounded-lg bg-myxon-600 px-3 py-2 text-xs text-white hover:bg-myxon-700"
            >
              Claim
            </button>
          </header>

          {loading ? (
            <p className="text-slate-500">Loading devices...</p>
          ) : filtered.length === 0 ? (
            <p className="text-slate-500">No devices found.</p>
          ) : (
            <>
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 max-w-6xl">
                {filtered.map((device) => (
                  <section
                    key={device.id}
                    className="rounded-lg border border-slate-300 bg-white p-3 shadow-[0_1px_1px_rgba(0,0,0,0.03)]"
                  >
                    <div className="mb-2 flex items-center justify-between">
                      <div>
                        <h3 className="text-[22px] leading-tight font-semibold tracking-tight">
                          {device.name || device.serial_number}
                        </h3>
                        <p className="text-xs text-slate-500">
                          {device.serial_number}{device.model ? ` · ${device.model}` : ''}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        <span className={`w-2.5 h-2.5 rounded-full ${statusColor(device.status)}`} />
                        <span className={device.status === 'online' ? 'text-green-600' : 'text-slate-500'}>
                          {device.status}
                        </span>
                      </div>
                    </div>

                    <button
                      onClick={() => navigate(`/devices/${device.id}`)}
                      className={`mb-2 w-full rounded-sm py-1.5 text-sm font-semibold ${
                        device.status === 'online'
                          ? 'bg-amber-500 text-white hover:bg-amber-600'
                          : 'bg-slate-200 text-slate-400'
                      }`}
                    >
                      Connect
                    </button>

                    <div className="space-y-1">
                      {(device.published_resources ?? [{ id: 'panel', name: 'Panel' }, { id: 'vnc', name: 'VNC' }, { id: 'http', name: 'HTTP' }]).map(
                        (res, idx) => (
                          <div
                            key={res.id}
                            className={`rounded-sm px-3 py-1 text-sm ${
                              idx % 2 === 0 ? 'bg-amber-500 text-white' : 'bg-slate-100 text-slate-500'
                            }`}
                          >
                            {res.name}
                          </div>
                        )
                      )}
                    </div>
                  </section>
                ))}
              </div>

              {/* Load more */}
              {nextCursor && (
                <div className="mt-6 flex justify-center">
                  <button
                    onClick={loadMore}
                    disabled={loadingMore}
                    className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                  >
                    {loadingMore ? 'Загрузка...' : (
                      <><ChevronDown size={14} /> Загрузить ещё</>
                    )}
                  </button>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  )
}
