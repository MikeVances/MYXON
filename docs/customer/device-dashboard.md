# Device Dashboard

The device dashboard is the main workspace for a single device. Open it by clicking on a device in the Devices list.

> **Screenshot:** *Device dashboard header: back arrow, device name "HOTRACO Orion — Stable A", shield badge with policy name, and "5m" refresh button.*

## Dashboard sections

### VPN

Shows the current tunnel status and basic device information.

> **Screenshot:** *VPN card: progress bar (full green = online), "VPN connect" button (amber when online), device info table with Status, Serial, Firmware, Model, Last seen fields.*

| Field | Description |
|-------|-------------|
| Status | `online` — tunnel active; `offline` — no connection |
| Serial | The device serial number |
| Firmware | Agent firmware version (updated on registration) |
| Last seen | Timestamp of last heartbeat |

### Web Access

Lists all services published by this device. Each service can be opened as a remote access session.

> **Screenshot:** *Web Access card with two resources: "HOTRACO Remote+ (TCP · port 5843)" and "VNC (VNC · port 5900)". Each has a Connect button (amber) or "restricted" label if policy blocks it.*

::: info Access policy restrictions
If your user role or site access policy restricts a resource type, the Connect button shows as disabled with a "restricted" label. Contact your admin to adjust access policies.
:::

**Opening a session:**
1. Click **Connect** on the resource you want to access
2. The system creates a time-bounded access session (30 minutes by default)
3. Click **Open Web Access** in the session panel that appears

> **Screenshot:** *Active session panel (light blue background): "Active session · TCP · remote-plus", with "Open Web Access" amber button.*

### Direct HMI

For HOTRACO devices (Orion, Cygnus, Sirius families), the dashboard shows a **live HMI screen** — the same display you'd see on the physical controller — refreshed every 250ms.

> **Screenshot:** *Direct HMI section: pixel-perfect controller display showing temperature graphs and zone settings, rendered at 3× scale.*

This view is read-only screen rendering. Interactive control (key presses) is available through separate HMI protocol sessions.

### Cloud connection status

A summary panel showing the state of all three cloud services:

| Connection | What it means |
|------------|--------------|
| **VPN connection** | frpc tunnel — main channel for remote access sessions |
| **Configuration connection** | Backend API connection for device management |
| **Data logging connection** | Last data sync timestamp |

### Alarms

Live alarm panel for this device, auto-refreshed every 30 seconds.

→ [Alarms documentation](/customer/alarms)

### Event log

Audit trail of all significant events for this device — registrations, status changes, session opens/closes.

| Column | Content |
|--------|---------|
| Who | User ID (first 8 characters) or "system" |
| When | Local timestamp |
| What | Event type and details |

> **Screenshot:** *Event log table with 3 rows: "system" / "18.04.2026 14:23" / "Device claimed"; "system" / "18.04.2026 14:20" / "Agent registered · tunnel_port:10001"; "system" / "18.04.2026 14:24" / "Session opened · protocol:tcp".*
