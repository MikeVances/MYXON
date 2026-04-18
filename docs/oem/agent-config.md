# Agent Configuration

The MYXON agent reads its configuration from `/opt/myxon-agent/agent.env`. This is a plain key=value file loaded at startup.

## Full configuration reference

```ini
# ─── Required ────────────────────────────────────────────────────────────────

# MYXON cloud server URL (must be reachable from the device)
MYXON_CLOUD_URL=https://myxon.yourcompany.com

# ─── Registration flow (choose one) ─────────────────────────────────────────

# Option A — Activation code (Scenario 2 / OEM SDK)
# Set once before first boot. The agent will consume this code on first connect
# and save the resulting identity to MYXON_DEVICE_STATE.
# After first boot this value is ignored (device.json takes priority).
MYXON_ACTIVATION_CODE=A3F1-B2E4-C9D7-0F56

# Option B — Pre-registered serial (Scenario 1 / legacy)
# Use when the device serial was manually registered in the Dealer Portal.
# MYXON_SERIAL=MX-2026-00001

# ─── State persistence ────────────────────────────────────────────────────────

# Where activated device identity is stored (device_id, serial, frpc token).
# Created automatically by the agent on first successful activation.
# Do NOT delete this file unless you want to reset the device registration.
MYXON_DEVICE_STATE=/etc/myxon/device.json

# ─── LAN discovery ───────────────────────────────────────────────────────────

# Scan mode — how the agent finds controllers on the LAN:
#
#   auto (default)
#     Scans non-WAN interfaces first (dedicated LAN port).
#     Falls back to scanning the WAN interface subnet if no dedicated LAN port.
#     Best for: Orange Pi on existing farm LAN (single cable to switch).
#
#   lan-only
#     Scans only non-WAN interfaces. Never touches the WAN subnet.
#     Best for: Orange Pi as router/gateway with separate eth0 (WAN) and eth1 (LAN).
#
#   all
#     Scans all interfaces including WAN.
#     Use when: single-interface device where WAN IS the farm LAN.
#
MYXON_SCAN_MODE=auto

# ─── Timing ──────────────────────────────────────────────────────────────────

# How often to send a heartbeat to the server (seconds)
MYXON_HEARTBEAT_INTERVAL=15

# How often to re-scan the LAN for new controllers (seconds)
MYXON_DISCOVERY_INTERVAL=60

# ─── Paths ───────────────────────────────────────────────────────────────────

# Path to the frpc binary
MYXON_FRPC_BIN=/usr/local/bin/frpc

# Per-device frpc token file — managed automatically, do not edit
# MYXON_TOKEN_FILE=/etc/myxon/agent_token

# ─── Manual resource override ─────────────────────────────────────────────────
# Skip LAN auto-discovery and use a fixed list of resources.
# JSON array format. Useful when controller IP is static and discovery is slow.
#
# MYXON_RESOURCES=[
#   {"id":"hmi","protocol":"tcp","host":"192.168.1.100","port":5843,"name":"HMI Panel"}
# ]
```

## Boot priority

On each startup, the agent checks in this order:

```
1. /etc/myxon/device.json exists?
   YES → restore identity (serial + token), call /register
   NO  ↓

2. MYXON_ACTIVATION_CODE is set?
   YES → call /activate, save identity to device.json
   NO  ↓

3. MYXON_SERIAL is set?
   YES → call /register (legacy pre-registered flow)
   NO  → use default "MYXON-DEV-001" (development only)
```

## Systemd service

The agent runs as a systemd service. Key settings:

```ini
[Service]
EnvironmentFile=/opt/myxon-agent/agent.env
ExecStart=/opt/myxon-agent/venv/bin/python myxon_agent.py
Restart=always
RestartSec=10
```

`Restart=always` means the agent automatically recovers from crashes or network outages. After a disconnect, it re-registers and re-establishes the tunnel — no manual intervention needed.

## Troubleshooting

**Agent keeps restarting:**
```bash
journalctl -u myxon-agent -n 100 --no-pager
```

**Tunnel not connecting:**
```bash
# Verify frpc is installed
frpc --version

# Check frps host reachability (port 7000)
nc -zv frps.myxon.yourcompany.com 7000
```

**Activation code rejected:**
- Code expired: generate a new one in the Dealer Portal
- Code already used: check `/etc/myxon/device.json` — device may already be activated
- Wrong code format: must be `XXXX-XXXX-XXXX-XXXX` (hex digits, uppercase)

**Discovery finds nothing:**
```bash
# Check which interfaces are available
ip -o -4 addr show

# Try switching to scan mode 'all' if controllers are on the WAN interface subnet
# MYXON_SCAN_MODE=all
```
