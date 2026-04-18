# Activation Code Flow — Technical Reference

This page explains the exact API interaction during device self-registration for developers and integrators who need to understand or extend the flow.

## Full sequence

```mermaid
sequenceDiagram
    participant A as Edge Agent (Orange Pi)
    participant S as MYXON Backend
    participant DB as PostgreSQL

    Note over A: First boot — device.json not found
    Note over A: MYXON_ACTIVATION_CODE=A3F1-B2E4-C9D7-0F56

    A->>A: Discover LAN controllers<br/>(scan ports 5843, 5900, 80)

    A->>S: POST /api/v0/agent/activate
    Note right of A: {"code": "A3F1-B2E4-C9D7-0F56",<br/>"metadata": {"firmware_version": "...",<br/>"published_resources": [...]}}

    S->>DB: SELECT * FROM activation_codes WHERE code = ?
    DB-->>S: code row (expires_at, used_at=NULL, tenant_id)

    alt Code expired
        S-->>A: 410 Gone — code has expired
    else Code already used
        S-->>A: 409 Conflict — code already used
    else Code not found
        S-->>A: 404 Not Found
    else Code valid
        S->>DB: SELECT COUNT(*) FROM devices
        DB-->>S: 42
        S->>S: serial = "MX-2026-00043"
        S->>DB: INSERT INTO devices (serial_number, tenant_id, status='online', claim_state='claimed')
        S->>S: Allocate tunnel port (10043)
        S->>S: Generate frpc_token (random 256-bit)
        S->>DB: UPDATE activation_codes SET used_at=now(), device_id=new_device_id
        S->>DB: INSERT INTO audit_events (action='device.activated')
        S-->>A: 201 Created
        Note left of S: {"device_id": "uuid",<br/>"serial_number": "MX-2026-00043",<br/>"frpc_token": "...",<br/>"tunnel": {"frps_host": "...", "assigned_port": 10043}}
    end

    A->>A: Save /etc/myxon/device.json<br/>(device_id, serial, frpc_token)
    A->>A: Write /etc/myxon/agent_token (chmod 0600)
    A->>A: Start frpc tunnel (port 10043)
    A->>S: POST /api/v0/agent/heartbeat (every 15s)
```

## API endpoint

```
POST /api/v0/agent/activate
Content-Type: application/json
(no Authorization header required)
```

### Request body

```typescript
{
  code: string              // Activation code: "XXXX-XXXX-XXXX-XXXX"
  metadata?: {
    firmware_version?: string
    hardware_info?: string
    model?: string
    published_resources?: Resource[]
  }
}

interface Resource {
  id: string           // e.g. "remote-plus"
  protocol: string     // "tcp" | "vnc" | "http"
  host: string         // LAN IP of the controller
  port: number         // LAN port
  name: string         // Human-readable name
}
```

### Response (201 Created)

```typescript
{
  accepted: true
  device_id: string          // UUID of newly created device
  serial_number: string      // Generated: "MX-2026-00043"
  frpc_token: string         // Store this — never sent again
  tunnel: {
    frps_host: string        // frps server hostname
    frps_port: number        // frps bind port (default 7000)
    assigned_port: number    // Unique port for this device's tunnel
    subdomain: string | null // Optional subdomain routing
  }
}
```

### Error responses

| Status | When |
|--------|------|
| `404 Not Found` | Code does not exist |
| `409 Conflict` | Code already used by another device |
| `410 Gone` | Code has expired |

## Serial number format

Serial numbers are generated automatically:

```
MX-{YEAR}-{SEQUENCE}
```

- `{YEAR}` — 4-digit activation year
- `{SEQUENCE}` — 5-digit zero-padded count of devices at time of activation

Example: `MX-2026-00043` — 43rd device activated in 2026.

::: warning Not a true DB sequence
The current implementation uses `SELECT COUNT(*) FROM devices` to determine the next number. In high-concurrency scenarios (multiple activations at exactly the same time), there is a small chance of collision — the database unique constraint will reject the duplicate and the device will see a 500 error and retry. For typical OEM deployments (one device at a time), this is not a concern.
:::

## Security properties

| Property | How it's enforced |
|----------|-----------------|
| One-time use | `used_at` is set on first use; server rejects subsequent calls |
| Expiry | `expires_at` is checked server-side on every request |
| No auth required | The code IS the proof of authorization |
| frpc_token issued once | Returned only in the 201 response; subsequent registrations use it without re-issuing |
| Token stored securely | Saved to `chmod 0600` file; never logged |
