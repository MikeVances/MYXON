# API CONTRACTS V0

> Обновлено: 04 April 2026 — приведено в соответствие с MYXON_PLATFORM_ARCHITECTURE.md v2
> Реализован: `myxon-platform/backend/app/api/`
> Swagger UI: http://localhost:8000/docs (при dev-запуске)

---

## Auth

`POST /api/v0/auth/login`
- input: `email, password`
- output: `access_token, refresh_token, user, tenant_type, roles`

`POST /api/v0/auth/refresh`
- input: `refresh_token`
- output: `access_token`

`POST /api/v0/auth/invite`  _(Этап 1)_
- caller: dealer
- input: `customer_email, customer_name, dealer_id`
- output: `invite_token, expires_at`

`POST /api/v0/auth/register-by-invite`  _(Этап 1)_
- input: `invite_token, email, password, name`
- output: `access_token, user`

---

## Devices

`GET /api/v0/devices`
- auth: customer (свои) / dealer (только online/offline своих клиентов)
- output: `[{ id, name, serial_number, status, site_id, last_seen_at }]`
- ⚠️ Dealer получает только status + serial_number, без данных клиента

`POST /api/v0/devices/register`  _(Этап 1, dealer only)_
- input: `serial_number, model, partner_id`
- output: `device_id, status: "registered"`

`POST /api/v0/devices/claim`
- caller: customer (самостоятельная активация через ClaimWizard)
- input: `serial_number, site_id`
- output: `device_id, claim_status`
- note: `activation_code` больше не нужен — только серийник с наклейки

`GET /api/v0/devices/{device_id}`
- auth: только customer-owner или platform_admin
- output: `device card + published_resources + tunnel_port`

---

## Sites  _(Этап 1)_

`GET /api/v0/sites`
- auth: customer (свои площадки по user → site_access)
- output: `[{ id, name, location, device_count }]`

`POST /api/v0/sites`
- auth: customer_admin
- input: `name, location`
- output: `site_id`

`POST /api/v0/sites/{site_id}/users`
- auth: customer_admin
- input: `user_id, role`
- output: `ok`

---

## Access Sessions

`POST /api/v0/devices/{device_id}/sessions`
- auth: customer_engineer+ (не dealer!)
- input: `resource_id, protocol (tcp/vnc/http), ttl_minutes`
- output: `session_id, ws_url, expires_at`

`DELETE /api/v0/sessions/{session_id}`
- output: `revoked: true`

---

## Agent

`POST /api/v0/agent/register`
- input: `agent_public_id, serial_number, signature, metadata: { firmware_version, hardware_info, published_resources: [{id, protocol, host, port, name}] }`
- output: `device_id, tunnel: { frps_host, frps_port, assigned_port }`

`POST /api/v0/agent/heartbeat`
- input: `device_id, tunnel_state, metrics: { uptime_seconds, timestamp }`
- output: `ok: true, server_time`

---

## Alarms

`GET /api/v0/alarms`
- filters: `device_id, severity, state, from, to`
- auth: customer only (dealer не имеет доступа)
- output: `[{ id, code, severity, category, message, state, created_at }]`

`POST /api/v0/alarms/{alarm_id}/acknowledge`
- auth: customer_engineer+
- output: `ok: true`

---

## Audit

`GET /api/v0/audit/events`
- filters: `tenant_id, device_id, actor_id, from, to`
- auth: customer_admin (своих) / platform_admin (всех)
- ⚠️ dealer не имеет доступа к audit клиента
- output: `event list`

---

## WebSocket HMI Bridge

`WS /api/v0/ws/{device_id}`
- auth: JWT в query param `?token=...`
- поведение: бридж TCP через frpc-тоннель (`frps_host:tunnel_port`) к контроллеру
- путь: только через тоннель, прямой IP — только dev-fallback

---

## Vendor / Catalog

`GET /api/v0/vendors`
- output: список производителей (HOTRACO и др.)

`GET /api/v0/vendors/{vendor_id}/models`
- output: модели устройств с описанием портов
