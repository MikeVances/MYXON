import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT token to all requests (skip for public endpoints)
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 → redirect to login (except public auth endpoints)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url: string = error.config?.url ?? ''
    const isPublic = url.includes('/auth/register-by-invite') || url.includes('/auth/invite/')
    if (error.response?.status === 401 && !isPublic) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api

// ---------------------------------------------------------------------------
// Pagination helpers
// ---------------------------------------------------------------------------

export interface PagedResponse<T> {
  items: T[]
  next_cursor: string | null
}

/**
 * Decode role from stored JWT without a library.
 * Returns null if token is missing or malformed.
 */
export function getStoredUserRole(): string | null {
  try {
    const token = localStorage.getItem('access_token')
    if (!token) return null
    // JWT payload is base64url (no padding) — add padding before atob()
    let b64 = token.split('.')[1]
    b64 = b64.replace(/-/g, '+').replace(/_/g, '/')
    b64 += '='.repeat((4 - (b64.length % 4)) % 4)
    const payload = JSON.parse(atob(b64))
    return payload.role ?? null
  } catch {
    return null
  }
}

export function isAdminRole(role: string | null): boolean {
  return ['customer_admin', 'superadmin', 'admin', 'platform_admin'].includes(role ?? '')
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/api/v0/auth/login', { email, password }),
  refresh: (refreshToken: string) =>
    api.post('/api/v0/auth/refresh', { refresh_token: refreshToken }),
  me: () => api.get('/api/v0/auth/me'),

  // Invite flow
  createInvite: (customerEmail: string, customerName: string) =>
    api.post('/api/v0/auth/invite', { customer_email: customerEmail, customer_name: customerName }),
  getInviteInfo: (token: string) =>
    api.get(`/api/v0/auth/invite/${token}`),
  registerByInvite: (inviteToken: string, password: string, fullName?: string) =>
    api.post('/api/v0/auth/register-by-invite', {
      invite_token: inviteToken,
      password,
      full_name: fullName,
    }),
}

// ---------------------------------------------------------------------------
// Devices (customer view) — cursor-paginated
// ---------------------------------------------------------------------------
export const devicesApi = {
  list: (siteId?: string, cursor?: string, limit = 50) =>
    api.get<PagedResponse<Device>>('/api/v0/devices', {
      params: { ...(siteId ? { site_id: siteId } : {}), ...(cursor ? { cursor } : {}), limit },
    }),
  get: (id: string) => api.get<Device>(`/api/v0/devices/${id}`),
  claimPreview: (serial: string) =>
    api.post('/api/v0/devices/claim/preview', { serial_number: serial }),
  claim: (serial: string, siteId?: string) =>
    api.post('/api/v0/devices/claim', { serial_number: serial, site_id: siteId }),
  createSession: (deviceId: string, resourceId: string, protocol: string, ttl = 30) =>
    api.post(`/api/v0/devices/${deviceId}/sessions`, { resource_id: resourceId, protocol, ttl_minutes: ttl }),
}

export interface Device {
  id: string
  serial_number: string
  name: string
  model: string | null
  firmware_version: string | null
  status: string
  claim_state: string
  last_seen_at: string | null
  tenant_id: string | null
  site_id: string | null
  dealer_id: string | null
  partner_id: string | null
  vendor_id: string | null
  device_family: string | null
  device_capabilities: Record<string, unknown> | null
  published_resources?: Array<{ id: string; name: string; protocol: string; port: number }>
}

// ---------------------------------------------------------------------------
// Dealer API — cursor-paginated
// ---------------------------------------------------------------------------
export const dealerApi = {
  registerDevice: (serialNumber: string, model?: string, vendorId?: string) =>
    api.post('/api/v0/devices/register', { serial_number: serialNumber, model, vendor_id: vendorId }),
  listDevices: (cursor?: string, limit = 50) =>
    api.get<PagedResponse<Device>>('/api/v0/devices/dealer', {
      params: { ...(cursor ? { cursor } : {}), limit },
    }),
}

// ---------------------------------------------------------------------------
// Sites / Locations
// ---------------------------------------------------------------------------
export const sitesApi = {
  list: () => api.get('/api/v0/sites'),
  create: (name: string, location?: string) =>
    api.post('/api/v0/sites', { name, location }),
}

// ---------------------------------------------------------------------------
// Vendors
// ---------------------------------------------------------------------------
export const vendorsApi = {
  list: () => api.get('/api/v0/vendors'),
  keyMap: (vendorId: string, family: string) =>
    api.get(`/api/v0/vendors/${vendorId}/families/${family}/keys`),
  capabilities: (vendorId: string, family: string) =>
    api.get(`/api/v0/vendors/${vendorId}/families/${family}/capabilities`),
}

// ---------------------------------------------------------------------------
// Alarms — cursor-paginated
// ---------------------------------------------------------------------------
export interface AlarmItem {
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

export const alarmsApi = {
  list: (params?: Record<string, string>, cursor?: string, limit = 50) =>
    api.get<PagedResponse<AlarmItem>>('/api/v0/alarms', {
      params: { ...params, ...(cursor ? { cursor } : {}), limit },
    }),
  acknowledge: (alarmId: string) =>
    api.post(`/api/v0/alarms/${alarmId}/acknowledge`),
}

// ---------------------------------------------------------------------------
// Audit — cursor-paginated
// ---------------------------------------------------------------------------
export interface AuditEventItem {
  id: string
  tenant_id: string
  actor_id: string | null
  device_id: string | null
  action: string
  details: Record<string, unknown> | null
  ip_address: string | null
  resource: string | null
  created_at: string
}

export const auditApi = {
  events: (params?: Record<string, string>, cursor?: string, limit = 50) =>
    api.get<PagedResponse<AuditEventItem>>('/api/v0/audit/events', {
      params: { ...params, ...(cursor ? { cursor } : {}), limit },
    }),
}

// ---------------------------------------------------------------------------
// Access Policies
// ---------------------------------------------------------------------------
export interface AccessPolicy {
  id: string
  name: string
  description: string | null
  tenant_id: string
  allow_hmi: boolean
  allow_vnc: boolean
  allow_http: boolean
  allow_alarms_view: boolean
  allow_alarms_acknowledge: boolean
  alarm_severity_filter: string  // "all" | "warning_and_above" | "critical_only"
  allow_audit_view: boolean
  is_default: boolean
}

export const accessPoliciesApi = {
  list: () => api.get<AccessPolicy[]>('/api/v0/access-policies'),
  get: (id: string) => api.get<AccessPolicy>(`/api/v0/access-policies/${id}`),
  create: (data: Partial<AccessPolicy>) =>
    api.post<AccessPolicy>('/api/v0/access-policies', data),
  update: (id: string, data: Partial<AccessPolicy>) =>
    api.patch<AccessPolicy>(`/api/v0/access-policies/${id}`, data),
  delete: (id: string) => api.delete(`/api/v0/access-policies/${id}`),
  effective: (deviceId?: string) =>
    api.get<AccessPolicy | null>('/api/v0/access-policies/effective', {
      params: deviceId ? { device_id: deviceId } : undefined,
    }),
  seedDefaults: () => api.post('/api/v0/access-policies/seed-defaults'),
}

// ---------------------------------------------------------------------------
// Site Access (user → site → policy assignment)
// ---------------------------------------------------------------------------
export interface SiteAccessEntry {
  id: string
  user_id: string
  user_email: string
  user_full_name: string
  site_id: string
  role: string
  access_policy_id: string | null
  access_policy_name: string | null
}

export interface TenantUser {
  id: string
  email: string
  full_name: string
  role: string
}

export const siteAccessApi = {
  listUsers: () => api.get<TenantUser[]>('/api/v0/users'),
  listSiteAccess: (siteId: string) =>
    api.get<SiteAccessEntry[]>(`/api/v0/sites/${siteId}/access`),
  upsert: (siteId: string, userId: string, role: string, accessPolicyId?: string | null) =>
    api.put<SiteAccessEntry>(`/api/v0/sites/${siteId}/access/${userId}`, {
      role,
      access_policy_id: accessPolicyId ?? null,
    }),
  remove: (siteId: string, userId: string) =>
    api.delete(`/api/v0/sites/${siteId}/access/${userId}`),
}
