# Quick Install

The fastest way to install the MYXON agent on any Debian-based device.

## Requirements

Before installing:
1. [Generate an activation code](/dealer/activation-codes) in your Dealer Portal
2. Know your MYXON server URL (e.g. `https://myxon.yourcompany.com`)
3. Have root access to the target device

## One-line install

```bash
curl -fsSL https://your-domain.com/install.sh | bash -s -- \
    --code A3F1-B2E4-C9D7-0F56 \
    --server https://myxon.yourcompany.com
```

Replace `A3F1-B2E4-C9D7-0F56` with your generated activation code.

::: tip Run from local file
If you're provisioning devices from a local network without internet access (e.g. factory floor), copy the agent files to the device and run:
```bash
scp -r edge-agent/ technician@device-ip:/tmp/myxon-agent
ssh technician@device-ip
cd /tmp/myxon-agent
sudo bash install.sh --code A3F1-B2E4-C9D7-0F56 --server https://myxon.yourcompany.com
```
:::

## What the installer does

```
▶ Installing system packages...
    apt-get: python3 python3-pip python3-venv curl iproute2

▶ Installing frpc 0.61.0...
    Downloads frp for your architecture (aarch64/armv7l/x86_64)
    Installs to /usr/local/bin/frpc

▶ Installing agent to /opt/myxon-agent...
    Copies myxon_agent.py, local_api.py

▶ Setting up Python virtualenv...
    /opt/myxon-agent/venv: httpx fastapi uvicorn

▶ Writing agent configuration...
    /opt/myxon-agent/agent.env

▶ Installing systemd service...
    /etc/systemd/system/myxon-agent.service
    systemctl enable myxon-agent

▶ Starting myxon-agent...
    Waits 3 seconds, checks /etc/myxon/device.json

  ✓ Device activated successfully!
    Serial: MX-2026-00001
```

## Verify the installation

Check service status:
```bash
systemctl status myxon-agent
```

Follow live logs:
```bash
journalctl -u myxon-agent -f
```

Confirm device is registered:
```bash
cat /etc/myxon/device.json
```

Expected output:
```json
{
  "device_id": "550e8400-e29b-41d4-a716-446655440000",
  "serial_number": "MX-2026-00001",
  "frpc_token": "..."
}
```

## Router mode — Orange Pi as LAN gateway

If your Orange Pi has a **USB Ethernet adapter** connected to an industrial switch,
you can make it act as a full DHCP router for the PLC/HMI network.
This is the same role that IXrouter plays in IXON deployments.

```
Internet ──── eth0 (DHCP from ISP/uplink)
                      Orange Pi
USB adapter ── eth1 ──── switch ──── PLC / HMI / VNC devices
                      (192.168.10.1/24)
```

### What it configures

| Component | What happens |
|-----------|-------------|
| `eth1` static IP | `192.168.10.1/24` (configurable via `--lan-ip`) |
| dnsmasq DHCP | Devices get `.100`–`.200`, gateway `192.168.10.1`, DNS `8.8.8.8` |
| IP forwarding | `sysctl net.ipv4.ip_forward=1` (persistent) |
| iptables NAT | PLCs can reach internet through Orange Pi |
| `MYXON_SCAN_MODE` | Automatically set to `lan-only` — agent only scans `eth1` |

### Install command

```bash
sudo bash install.sh \
    --code A3F1-B2E4-C9D7-0F56 \
    --server https://myxon.yourcompany.com \
    --lan-iface eth1
```

Custom gateway IP (if `192.168.10.1` conflicts with your existing network):

```bash
sudo bash install.sh \
    --code A3F1-B2E4-C9D7-0F56 \
    --server https://myxon.yourcompany.com \
    --lan-iface eth1 \
    --lan-ip 10.20.0.1
```

### Finding your USB adapter name

USB Ethernet adapters on Debian appear as `enxXXXXXXXXXXXX` (MAC-based) or `eth1`:

```bash
ip link show
# Look for: enx001122334455 or eth1 — the one that is DOWN or has no IP
```

### Verify router setup

After install, confirm devices on the switch get DHCP leases:

```bash
# DHCP leases
cat /var/lib/misc/dnsmasq.leases

# Routing table
ip route show

# NAT rules
iptables -t nat -L POSTROUTING -n -v
```

::: tip Re-running install
The router setup is **idempotent** — you can safely re-run `install.sh --lan-iface eth1`
after a reboot or when adding a new device. iptables rules are checked before adding.
:::

## Silent / non-interactive install

For factory imaging or cloud-init scripts:

```bash
MYXON_ACTIVATION_CODE=A3F1-B2E4-C9D7-0F56 \
MYXON_CLOUD_URL=https://myxon.yourcompany.com \
MYXON_SCAN_MODE=auto \
    bash install.sh
```

Or via environment in cloud-init `runcmd`:
```yaml
runcmd:
  - MYXON_ACTIVATION_CODE=A3F1-B2E4-C9D7-0F56 MYXON_CLOUD_URL=https://myxon.yourcompany.com bash /opt/myxon-installer/install.sh
```

## Re-installation (already activated device)

If you re-run `install.sh` on a device that already has `/etc/myxon/device.json`:

- The installer **detects the existing state** and prints a warning
- It updates `agent.env` with the new server URL (if changed) but **does not overwrite** the activation code
- The service is restarted with the updated config

To reset a device and re-activate it with a new code:
```bash
rm /etc/myxon/device.json
sudo bash install.sh --code NEW-CODE-XXXX --server https://myxon.yourcompany.com
```

::: danger New code required
You must generate a **new activation code** for each reset. The original code is already marked as used on the server and cannot be reused.
:::

## Uninstall

```bash
systemctl stop myxon-agent myxon-local-api 2>/dev/null
systemctl disable myxon-agent myxon-local-api 2>/dev/null
rm -rf /opt/myxon-agent /etc/myxon
rm -f /etc/systemd/system/myxon-agent.service
systemctl daemon-reload
```
