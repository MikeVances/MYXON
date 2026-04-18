# OEM / SDK Integration Overview

The MYXON OEM SDK lets you add remote access capabilities to **your own hardware** — without shipping separate gateway hardware. If your controller already has a Linux-based server board (like an Orange Pi, Raspberry Pi, or similar), you can install the MYXON agent alongside your existing software.

## What you get

- **Outbound-only tunnel** — no firewall rules needed at customer sites
- **Auto-discovery** — agent finds your controller's services on the LAN automatically
- **One-time activation** — generate a code in the Dealer Portal, set it in the device env, done
- **Fleet visibility** — see all your deployed devices from the Dealer Portal
- **No serial pre-registration** — server assigns serial numbers automatically on first activation

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Debian/Ubuntu-based Linux | Tested on Debian 11/12, Ubuntu 22.04 |
| Python 3.9+ | Usually pre-installed |
| Outbound internet (port 7000 TCP) | For frpc tunnel |
| Outbound HTTPS (port 443) | For agent registration API |
| Architecture | aarch64 (Orange Pi 5), armv7l, x86_64 |

## Integration checklist

- [ ] Get dealer credentials from your MYXON account manager
- [ ] Log in to the Dealer Portal
- [ ] Generate an activation code for each device batch
- [ ] Run `install.sh` on each device (or include it in your OS image)
- [ ] Verify device appears in Dealer Portal → Devices
- [ ] Set up your customer's account and invite them

## Architecture overview

```
  Your controller board (ARM Linux)
  ┌─────────────────────────────────────────────────┐
  │  Your software (Modbus server, web UI, etc.)    │
  │  port 80, 5843, 5900, ...                       │
  │                                                  │
  │  myxon_agent.py                                  │
  │    ├── LAN scan → finds above ports              │
  │    ├── POST /api/v0/agent/activate               │
  │    └── frpc → tunnel → MYXON Cloud               │
  └─────────────────────────────────────────────────┘
                         │ outbound TCP :7000
                    ┌────▼─────────────────┐
                    │  MYXON Cloud         │
                    │  frps :7000          │
                    │  Backend :443        │
                    └────────────────────┘
```

## Next steps

1. [Quick install](/oem/install) — one-command setup with `install.sh`
2. [Agent configuration](/oem/agent-config) — all configuration options
3. [Activation code flow](/oem/activation-flow) — how self-registration works
4. [LAN auto-discovery](/oem/lan-discovery) — how the agent finds controllers
