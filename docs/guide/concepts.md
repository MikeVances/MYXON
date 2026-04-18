# Core concepts

Understanding these concepts will make the rest of the documentation much clearer.

## Device lifecycle

Every device in MYXON goes through a defined lifecycle:

```
  pre_registered ──► online / offline ──► claimed ──► (in use)
       │                                     ▲
       └── Dealer registers SN               │
                                        Customer claims
```

| State | Meaning |
|-------|---------|
| `pre_registered` | Serial number exists in DB; agent has never connected |
| `online` | Agent connected and tunnel is active |
| `offline` | Agent was online but hasn't sent heartbeat in >30 seconds |
| `claimed` | Customer tenant has taken ownership (via QR claim or activation code) |

## Claim state vs connectivity state

These are two independent dimensions:

- **Claim state** — ownership: who owns this device? (`ready_for_transfer` / `claimed`)
- **Connectivity state** — is the device online right now? (`online` / `offline`)

A device can be **claimed but offline** (the customer owns it, but it's powered down), or **online but unclaimed** (agent is running, but no customer has activated it yet).

## Tunnel architecture

MYXON uses [FRP (Fast Reverse Proxy)](https://github.com/fatedier/frp):

- **frps** runs on the MYXON cloud server, listening on port 7000
- **frpc** runs on the Orange Pi alongside the agent
- Each device gets a unique **tunnel port** (e.g. 10001) allocated from a pool
- When you open a Web Access session, the backend proxies your browser to `frps-host:tunnel-port`

This means **no VPN, no static IP needed** on the farm side. The Orange Pi only needs outbound internet access.

## Published resources

A device can expose multiple **resources** — services the agent discovered on the LAN:

```json
[
  { "id": "remote-plus", "protocol": "tcp",  "host": "192.168.1.100", "port": 5843, "name": "HOTRACO Remote+" },
  { "id": "vnc",         "protocol": "vnc",  "host": "192.168.1.100", "port": 5900, "name": "VNC" },
  { "id": "http",        "protocol": "http", "host": "192.168.1.100", "port": 80,   "name": "Web UI" }
]
```

Each resource gets its own tunnel port offset (`assigned_port + 0`, `+1`, `+2`, …).

## Access policies

Access policies let customer admins restrict what specific users can do. Policies apply per-site and per-user:

| Permission | What it controls |
|------------|-----------------|
| `allow_hmi` | Open HMI sessions (HOTRACO Direct HMI) |
| `allow_vnc` | Open VNC connections |
| `allow_http` | Open HTTP/web sessions |
| `allow_alarms_view` | See the alarm panel |
| `allow_alarms_acknowledge` | Acknowledge active alarms |
| `allow_audit_view` | See the event log |

Default (no policy assigned): all permissions granted.

## Tenant model

Every user belongs to a **tenant** — an isolated organization. Dealers and customers are in separate tenants:

```
  Dealer Tenant (e.g. "AgriTech BV")
    ├── Users: dealer employees
    └── Devices: registered by this dealer

  Customer Tenant (e.g. "Farm Noord BV")
    ├── Users: farmer + technicians
    ├── Sites: "Stable A", "Stable B", "Greenhouse 1"
    └── Devices: claimed from dealer fleet
```

The `dealer_id` on a Device record is **never cleared** — even after the customer claims it. This is how dealers retain fleet visibility without accessing customer data.
