import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MapPin, ChevronRight, Search, Building2 } from 'lucide-react'
import { devicesApi, sitesApi } from '../api/client'

interface Site {
  id: string
  name: string
  address: string | null
  devices_count: number
}

interface Device {
  id: string
  site_id: string | null
}

export default function LocationsPage() {
  const navigate = useNavigate()
  const [sites, setSites] = useState<Site[]>([])
  const [devices, setDevices] = useState<Device[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([sitesApi.list(), devicesApi.list()])
      .then(([sitesRes, devicesRes]) => {
        setSites(sitesRes.data)
        // devicesApi.list() returns PagedResponse<Device> — unwrap .items
        setDevices(devicesRes.data.items ?? [])
      })
      .finally(() => setLoading(false))
  }, [])

  const unassignedCount = useMemo(
    () => devices.filter((d) => !d.site_id).length,
    [devices]
  )

  const filtered = sites.filter(
    (s) =>
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      (s.address || '').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="min-h-screen bg-[#eef0f4] p-4 md:p-6">
      <div className="mx-auto max-w-4xl">
        <header className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-myxon-900">Locations</h1>
            <p className="text-sm text-slate-500">Choose where to open device list</p>
          </div>
          <button
            onClick={() => navigate('/devices')}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600"
          >
            All devices
          </button>
        </header>

        <div className="mb-4 relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search locations..."
            className="w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-myxon-500"
          />
        </div>

        {loading ? (
          <p className="text-slate-500">Loading locations...</p>
        ) : (
          <div className="space-y-3">
            {filtered.map((site) => (
              <button
                key={site.id}
                onClick={() => navigate(`/devices?site=${site.id}`)}
                className="w-full rounded-lg border border-slate-200 bg-white p-4 text-left transition hover:border-myxon-400"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-base font-semibold text-slate-800">{site.name}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {site.address || 'No address specified'}
                    </p>
                  </div>
                  <ChevronRight size={16} className="text-slate-400" />
                </div>
                <div className="mt-3 inline-flex items-center gap-2 rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">
                  <MapPin size={12} />
                  {site.devices_count} devices
                </div>
              </button>
            ))}

            <button
              onClick={() => navigate('/devices?site=unassigned')}
              className="w-full rounded-lg border border-dashed border-slate-300 bg-white p-4 text-left transition hover:border-myxon-400"
            >
              <p className="text-base font-semibold text-slate-700">Unassigned Devices</p>
              <p className="mt-1 text-xs text-slate-500">Devices without bound location</p>
              <div className="mt-3 inline-flex items-center gap-2 rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">
                <Building2 size={12} />
                {unassignedCount} devices
              </div>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

