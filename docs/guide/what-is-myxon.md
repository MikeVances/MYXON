# What is MYXON?

MYXON is a **remote access and monitoring platform** built for agricultural automation. It lets integrators, dealers, and their customers connect to farm controllers — climate systems, ventilation units, lighting controllers — from anywhere in the world, without touching firewall or router settings.

## The problem it solves

Agricultural controllers (HOTRACO, SCOV, Stienen, Siemens) live deep inside farm networks. Reaching them remotely traditionally requires:

- Port forwarding on the farm router (IT knowledge, security risk)
- VPN infrastructure (expensive, complex to maintain)
- On-site visits for every configuration change (time and cost)

**MYXON eliminates all of this.** A small agent process runs on an Orange Pi (or the controller's built-in Linux server) and creates an outbound encrypted tunnel to the MYXON cloud. The farm network only makes outbound connections — no inbound ports needed.

## How it works — in one picture

```
  Controller (Modbus/HMI)          MYXON Cloud
  ┌────────────────────┐           ┌────────────────────────┐
  │  192.168.1.100     │           │  frps.myxon.io:7000    │
  │  port 5843 (HMI)   │           │  Backend (FastAPI)      │
  └────────┬───────────┘           │  Frontend (React)       │
           │ LAN                   └───────────┬────────────┘
  ┌────────▼───────────┐                       │
  │  Orange Pi          │──── outbound TCP ────▶│
  │  myxon_agent.py     │◀─── tunnel config ───│
  │  frpc               │                       │
  └────────────────────┘                       │
                                               │ HTTPS
                                          ┌────▼──────────┐
                                          │  Web browser  │
                                          │  (dealer or   │
                                          │   customer)   │
                                          └───────────────┘
```

## Key actors

| Actor | Who they are | What they do in MYXON |
|-------|-------------|----------------------|
| **Platform admin** | MYXON team | Manages the cloud infrastructure |
| **Dealer** | Integrator / reseller / OEM manufacturer | Registers devices, invites customers, monitors fleet |
| **Customer** | Farm owner / operator | Activates devices, monitors alarms, opens HMI sessions |
| **Engineer** | Farm technician (customer's staff) | Views devices, opens connections, sees alarms |
| **Viewer** | Farm manager | Read-only alarm monitoring |

## Two deployment scenarios

MYXON supports two business models:

### Scenario 1 — MYXON Box

You (the dealer) sell a pre-built Orange Pi router with the agent pre-installed. You register each serial number in the Dealer Portal, print a QR label, and attach it to the box. The customer scans the QR to claim and activate the device.

→ See [Dealer: Register devices](/dealer/register-devices)

### Scenario 2 — OEM SDK

Your company already ships controllers with an embedded Linux server (like an Orange Pi). You install the MYXON agent using a one-line installer and configure it with a one-time activation code generated from your Dealer Portal.

→ See [OEM / SDK Integration](/oem/overview)
