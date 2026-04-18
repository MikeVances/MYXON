#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# MYXON OEM Agent Installer — Scenario 2 (activation-code flow)
#
# Предназначен для OEM-производителей оборудования, у которых уже стоит
# Orange Pi/Debian-based устройство. Установка — одна команда:
#
#   curl -fsSL https://get.myxon.io/install.sh | bash -s -- \
#       --code A3F1-B2E4-C9D7-0F56 \
#       --server https://myxon.example.com
#
# Режим роутера (Orange Pi как шлюз с DHCP для промышленной сети):
#
#   bash install.sh \
#       --code A3F1-B2E4-C9D7-0F56 \
#       --server https://myxon.example.com \
#       --lan-iface eth1           # USB Ethernet-адаптер → промышленный свитч
#       --lan-ip 192.168.10.1      # IP шлюза (по умолчанию 192.168.10.1)
#
#   Что произойдёт:
#     • eth1 получит статический IP 192.168.10.1/24
#     • dnsmasq будет раздавать DHCP .100–.200 устройствам в свитче
#     • NAT+IP forwarding позволяет PLC'шкам выходить в интернет через Orange Pi
#     • Агент сканирует только eth1 подсеть (MYXON_SCAN_MODE=lan-only)
#
# Переменные среды вместо аргументов (для CI/образов):
#
#   MYXON_ACTIVATION_CODE=A3F1-B2E4-C9D7-0F56 \
#   MYXON_CLOUD_URL=https://myxon.example.com \
#   MYXON_SCAN_MODE=auto \
#     bash install.sh
#
# Что делает скрипт:
#   1. Устанавливает Python3, pip, frpc
#   2. Копирует агента в /opt/myxon-agent
#   3. Создаёт Python venv
#   4. Записывает /opt/myxon-agent/agent.env с activation code
#   5. (Опционально) Настраивает LAN роутер: static IP, dnsmasq, NAT
#   6. Регистрирует и запускает systemd-сервис
#
# После первого запуска агент:
#   • Вызывает POST /api/v0/agent/activate
#   • Получает serial number + frpc token
#   • Сохраняет их в /etc/myxon/device.json (0600)
#   • Поднимает frpc-тоннель
#
# При перезапуске device.json уже есть — агент переходит к /register flow,
# activation code больше не используется (но остаётся в agent.env для справки).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

AGENT_DIR=/opt/myxon-agent
FRP_VERSION=0.61.0
MYXON_STATE_DIR=/etc/myxon

# ── Helpers ───────────────────────────────────────────────────────────────────
_green() { echo -e "\033[1;32m$*\033[0m"; }
_cyan()  { echo -e "  \033[0;36m$*\033[0m"; }
_warn()  { echo -e "\033[1;33m⚠ $*\033[0m" >&2; }
_die()   { echo -e "\033[1;31m✖ $*\033[0m" >&2; exit 1; }
_sep()   { echo -e "\033[0;90m────────────────────────────────────────────────\033[0m"; }

# ── Parse arguments ───────────────────────────────────────────────────────────
ACTIVATION_CODE="${MYXON_ACTIVATION_CODE:-}"
CLOUD_URL="${MYXON_CLOUD_URL:-}"
SCAN_MODE="${MYXON_SCAN_MODE:-auto}"
LAN_IFACE="${MYXON_LAN_IFACE:-}"         # e.g. eth1 (USB Ethernet adapter)
LAN_IP="${MYXON_LAN_IP:-192.168.10.1}"   # gateway IP on the LAN interface
BACKUP_MODEM="${MYXON_BACKUP_MODEM:-}"   # e.g. /dev/ttyUSB0 — 4G USB modem for WAN failover

while [[ $# -gt 0 ]]; do
    case "$1" in
        --code)          ACTIVATION_CODE="$2"; shift 2 ;;
        --server)        CLOUD_URL="$2";       shift 2 ;;
        --scan)          SCAN_MODE="$2";       shift 2 ;;
        --lan-iface)     LAN_IFACE="$2";       shift 2 ;;
        --lan-ip)        LAN_IP="$2";          shift 2 ;;
        --backup-modem)  BACKUP_MODEM="$2";    shift 2 ;;
        *) _die "Unknown argument: $1. Usage: install.sh --code XXXX-XXXX-XXXX-XXXX --server https://myxon.example.com [--lan-iface eth1] [--backup-modem /dev/ttyUSB0]" ;;
    esac
done

# ── Validate ──────────────────────────────────────────────────────────────────
[ "$(id -u)" -eq 0 ] || _die "Must run as root: sudo bash install.sh [args]"

[[ -n "$ACTIVATION_CODE" ]] || _die \
    "Activation code is required. Pass --code XXXX-XXXX-XXXX-XXXX or set MYXON_ACTIVATION_CODE."

[[ -n "$CLOUD_URL" ]] || _die \
    "Server URL is required. Pass --server https://myxon.example.com or set MYXON_CLOUD_URL."

# Validate code format: XXXX-XXXX-XXXX-XXXX (hex groups)
if ! echo "$ACTIVATION_CODE" | grep -qE '^[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}$'; then
    _die "Invalid activation code format. Expected: XXXX-XXXX-XXXX-XXXX (hex groups)"
fi

# Normalize: uppercase
ACTIVATION_CODE="${ACTIVATION_CODE^^}"

# ── Welcome ───────────────────────────────────────────────────────────────────
echo ""
_green "  ╔════════════════════════════════════════════╗"
_green "  ║     MYXON Edge Agent — OEM Installer      ║"
_green "  ╚════════════════════════════════════════════╝"
echo ""
_cyan "Code   : ${ACTIVATION_CODE:0:4}-****-****-****"
_cyan "Server : $CLOUD_URL"
_cyan "Scan   : $SCAN_MODE"
[[ -n "$LAN_IFACE" ]]     && _cyan "Router : $LAN_IFACE → $LAN_IP/24 (DHCP + NAT)"
[[ -n "$BACKUP_MODEM" ]]  && _cyan "4G WAN : $BACKUP_MODEM (failover via ModemManager)"
echo ""

# ── Guard: already activated? ─────────────────────────────────────────────────
if [ -f "$MYXON_STATE_DIR/device.json" ]; then
    EXISTING_SERIAL=$(python3 -c "import json; d=json.load(open('$MYXON_STATE_DIR/device.json')); print(d.get('serial_number','?'))" 2>/dev/null || echo "?")
    _warn "Device already activated! Serial: $EXISTING_SERIAL"
    _warn "State file: $MYXON_STATE_DIR/device.json"
    _warn "To re-activate, remove the state file first: rm $MYXON_STATE_DIR/device.json"
    echo ""
    # Continue install (agent files/service may need updating) but skip overwriting env code
    ALREADY_ACTIVATED=1
else
    ALREADY_ACTIVATED=0
fi

# ── 4G WAN failover setup (called if --backup-modem is set) ──────────────────
#
# Architecture mirrors IXON IXrouter failover:
#   eth0  (primary WAN)   — route metric 100  → NM manages via DHCP
#   wwan0 (4G backup WAN) — route metric 200  → NM manages via ModemManager
#
# NetworkManager automatically promotes wwan0 default route when eth0 drops.
# No custom watchdog needed — NM tracks carrier state and online detection.
#
# Tested with:
#   - Huawei E3372 (HiLink mode — appears as USB Ethernet, not modem)
#   - Quectel EC25 / Sierra Wireless EM7455 (ModemManager mode)
#
_setup_wan_failover() {
    local modem_dev="$1"   # e.g. /dev/ttyUSB0

    _green "▶ Setting up 4G WAN failover..."
    _cyan  "  Primary   : eth0 (Ethernet, metric 100)"
    _cyan  "  Backup    : $modem_dev → wwan0 (4G, metric 200)"

    # Install ModemManager + NetworkManager (NM replaces ifupdown for WAN ifaces)
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        modemmanager \
        network-manager \
        usb-modeswitch     # Switches composite USB modems into modem-only mode

    systemctl enable ModemManager NetworkManager
    systemctl start  ModemManager NetworkManager

    # ── Configure primary WAN (eth0) via NetworkManager ──
    # Lower metric = higher priority. NM will prefer eth0 as long as it has a carrier.
    # The connection is named "myxon-wan-primary" for easy identification.
    if ! nmcli connection show myxon-wan-primary &>/dev/null; then
        nmcli connection add \
            type ethernet \
            ifname eth0 \
            con-name myxon-wan-primary \
            ipv4.method auto \
            ipv4.route-metric 100 \
            ipv6.method disabled
        _cyan "Primary WAN connection created: eth0 metric=100"
    else
        nmcli connection modify myxon-wan-primary ipv4.route-metric 100
        _cyan "Primary WAN connection updated: eth0 metric=100"
    fi

    # ── Configure 4G backup WAN via ModemManager ──
    # NM uses ModemManager as a backend for GSM modems connected via USB.
    # 'gsm' type works with most USB modems; APN 'internet' is the most common.
    # The operator APN can be changed via: nmcli connection modify myxon-wan-4g gsm.apn <apn>
    if ! nmcli connection show myxon-wan-4g &>/dev/null; then
        nmcli connection add \
            type gsm \
            con-name myxon-wan-4g \
            ifname '*' \
            gsm.apn internet \
            ipv4.method auto \
            ipv4.route-metric 200 \
            ipv6.method disabled \
            connection.autoconnect yes
        _cyan "4G backup connection created: metric=200, APN=internet"
        _warn "APN may need adjustment for your carrier:"
        _warn "  nmcli connection modify myxon-wan-4g gsm.apn <your-apn>"
    else
        nmcli connection modify myxon-wan-4g ipv4.route-metric 200
        _cyan "4G backup connection updated: metric=200"
    fi

    # ── Connectivity monitor (systemd service) ──
    # NM handles the actual failover, but this monitor gives us clear logging
    # in journalctl so we can see failover events: "eth0 DOWN → 4G active"
    cat > /usr/local/bin/myxon-wan-monitor <<'MONITOR'
#!/usr/bin/env bash
# MYXON WAN failover monitor — runs as a systemd service, logs route changes
# Checks default route every 30s and reports which interface is carrying WAN traffic.
while true; do
    gw_iface=$(ip route show default 2>/dev/null | awk '/dev/{for(i=1;i<=NF;i++) if($i=="dev") print $(i+1); exit}')
    if [[ "$gw_iface" == wwan* ]]; then
        logger -t myxon-wan "WAN failover ACTIVE: using 4G ($gw_iface) — eth0 unavailable"
    elif [[ -n "$gw_iface" ]]; then
        logger -t myxon-wan "WAN primary OK: $gw_iface"
    else
        logger -t myxon-wan "WAN WARNING: no default route found"
    fi
    sleep 30
done
MONITOR
    chmod +x /usr/local/bin/myxon-wan-monitor

    cat > /etc/systemd/system/myxon-wan-monitor.service <<'MONSVC'
[Unit]
Description=MYXON WAN Failover Monitor
After=network-online.target ModemManager.service NetworkManager.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/myxon-wan-monitor
Restart=always
RestartSec=5
SyslogIdentifier=myxon-wan

[Install]
WantedBy=multi-user.target
MONSVC

    systemctl daemon-reload
    systemctl enable myxon-wan-monitor
    systemctl restart myxon-wan-monitor

    _cyan "WAN monitor service: myxon-wan-monitor (journalctl -t myxon-wan -f)"

    # Activate primary connection immediately
    nmcli connection up myxon-wan-primary 2>/dev/null || true

    _green "▶ 4G failover ready."
    _cyan  "  Verify: nmcli device status"
    _cyan  "  Logs  : journalctl -t myxon-wan -f"
}

# ── LAN router setup (called if --lan-iface is set) ──────────────────────────
_setup_lan_router() {
    local iface="$1"
    local gw_ip="$2"                        # e.g. 192.168.10.1
    local prefix="${gw_ip%.*}"              # e.g. 192.168.10
    local dhcp_start="${prefix}.100"
    local dhcp_end="${prefix}.200"

    # Auto-detect WAN interface from default route
    local wan_iface
    wan_iface=$(ip route show default 2>/dev/null \
        | awk '/dev/{for(i=1;i<=NF;i++) if($i=="dev") print $(i+1); exit}')

    [[ -n "$wan_iface" ]] || _die \
        "Cannot detect WAN interface from default route. Is internet connected on this device?"
    [[ "$iface" != "$wan_iface" ]] || _die \
        "LAN interface ($iface) is the same as WAN interface ($wan_iface). Use a different interface."

    # Check the interface exists (USB adapters appear as enxXXX or ethX)
    ip link show "$iface" &>/dev/null || _die \
        "Interface '$iface' not found. Connected USB adapter? Run: ip link show"

    _green "▶ Setting up LAN router: $iface → $wan_iface"

    # Install networking tools (non-interactive to skip iptables-persistent prompts)
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        dnsmasq iptables iptables-persistent

    # ── Static IP on LAN interface ──
    # Apply immediately
    ip addr flush dev "$iface" 2>/dev/null || true
    ip addr add "${gw_ip}/24" dev "$iface"
    ip link set "$iface" up

    # Persist via /etc/network/interfaces.d/ (survives reboots)
    cat > "/etc/network/interfaces.d/myxon-lan-${iface}.cfg" <<NETCFG
# MYXON LAN gateway — managed by install.sh, do not edit manually
auto ${iface}
iface ${iface} inet static
    address ${gw_ip}
    netmask 255.255.255.0
NETCFG
    _cyan "Static IP: ${gw_ip}/24 on ${iface}"

    # ── DHCP server (dnsmasq) ──
    # bind-interfaces ensures dnsmasq ONLY listens on $iface,
    # never accidentally serves DHCP on the WAN side.
    cat > /etc/dnsmasq.d/myxon-lan.conf <<DNSCONF
# MYXON LAN DHCP — managed by install.sh
interface=${iface}
bind-interfaces
dhcp-range=${dhcp_start},${dhcp_end},12h
dhcp-option=option:router,${gw_ip}
dhcp-option=option:dns-server,8.8.8.8,8.8.4.4
# Log DHCP leases for debugging
log-dhcp
DNSCONF
    systemctl enable dnsmasq
    systemctl restart dnsmasq
    _cyan "DHCP: ${dhcp_start}–${dhcp_end} via ${iface} (gateway ${gw_ip})"

    # ── IP forwarding ──
    echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-myxon-forward.conf
    sysctl -q -w net.ipv4.ip_forward=1
    _cyan "IP forwarding: enabled"

    # ── iptables NAT rules ──
    # Idempotent: -C checks existence before -A to avoid duplicates on re-install.

    # NAT masquerade: PLC traffic leaving via WAN looks like Orange Pi's IP
    iptables -t nat -C POSTROUTING -o "$wan_iface" -j MASQUERADE 2>/dev/null \
        || iptables -t nat -A POSTROUTING -o "$wan_iface" -j MASQUERADE

    # Allow forwarding: LAN → WAN
    iptables -C FORWARD -i "$iface" -o "$wan_iface" -j ACCEPT 2>/dev/null \
        || iptables -A FORWARD -i "$iface" -o "$wan_iface" -j ACCEPT

    # Allow forwarding: established connections WAN → LAN (replies to PLC requests)
    iptables -C FORWARD -i "$wan_iface" -o "$iface" \
        -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null \
        || iptables -A FORWARD -i "$wan_iface" -o "$iface" \
           -m state --state RELATED,ESTABLISHED -j ACCEPT

    # Persist rules so they survive reboot
    netfilter-persistent save
    _cyan "NAT: ${iface} → ${wan_iface} (MASQUERADE)"

    _green "▶ LAN router ready. PLCs on ${prefix}.0/24 will get DHCP and internet via Orange Pi."
}

# ── 1. System packages ────────────────────────────────────────────────────────
_sep
_green "▶ Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv curl tar iproute2

# ── 2. frpc ───────────────────────────────────────────────────────────────────
if command -v frpc &>/dev/null; then
    _green "▶ frpc already installed: $(frpc --version 2>&1 | head -1)"
else
    _green "▶ Installing frpc $FRP_VERSION..."
    ARCH=$(uname -m)
    case "$ARCH" in
        aarch64|arm64) FRP_ARCH="arm64" ;;
        armv7l|armhf)  FRP_ARCH="arm"   ;;
        x86_64)        FRP_ARCH="amd64" ;;
        *)             _die "Unsupported architecture: $ARCH" ;;
    esac

    FRP_URL="https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_${FRP_ARCH}.tar.gz"
    FRP_TAR="/tmp/frp.tar.gz"

    curl -L --silent --show-error -o "$FRP_TAR" "$FRP_URL"
    tar -xzf "$FRP_TAR" -C /tmp
    cp "/tmp/frp_${FRP_VERSION}_linux_${FRP_ARCH}/frpc" /usr/local/bin/frpc
    chmod +x /usr/local/bin/frpc
    rm -rf "$FRP_TAR" "/tmp/frp_${FRP_VERSION}_linux_${FRP_ARCH}"
    _green "▶ frpc installed: $(frpc --version 2>&1 | head -1)"
fi

# ── 3. Agent files ────────────────────────────────────────────────────────────
_green "▶ Installing agent to $AGENT_DIR..."
mkdir -p "$AGENT_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# If install.sh is running from a local checkout — copy sibling files.
# If running from curl pipe (no BASH_SOURCE) — agent must be pre-installed or downloaded.
if [ -f "$SCRIPT_DIR/myxon_agent.py" ]; then
    for f in myxon_agent.py local_api.py requirements.txt; do
        [ -f "$SCRIPT_DIR/$f" ] && cp "$SCRIPT_DIR/$f" "$AGENT_DIR/$f"
    done
    _cyan "Agent files copied from $SCRIPT_DIR"
elif [ ! -f "$AGENT_DIR/myxon_agent.py" ]; then
    _die "myxon_agent.py not found. Run install.sh from the agent directory or pre-install agent files to $AGENT_DIR."
else
    _cyan "Agent files already present in $AGENT_DIR — skipping copy"
fi

# ── 4. Python venv ────────────────────────────────────────────────────────────
_green "▶ Setting up Python virtualenv..."
python3 -m venv "$AGENT_DIR/venv"
"$AGENT_DIR/venv/bin/pip" install --quiet --upgrade pip

if [ -f "$AGENT_DIR/requirements.txt" ]; then
    "$AGENT_DIR/venv/bin/pip" install --quiet -r "$AGENT_DIR/requirements.txt"
else
    "$AGENT_DIR/venv/bin/pip" install --quiet httpx fastapi uvicorn[standard]
fi

# ── 5. LAN router (optional) ─────────────────────────────────────────────────
_sep
if [[ -n "$LAN_IFACE" ]]; then
    _setup_lan_router "$LAN_IFACE" "$LAN_IP"
    # In router mode: always use lan-only scan so agent never scans WAN subnet
    SCAN_MODE="lan-only"
else
    _green "▶ Skipping LAN router setup (no --lan-iface specified)"
    _cyan "  Single-NIC mode: agent will scan the existing LAN via MYXON_SCAN_MODE=${SCAN_MODE}"
fi

# ── 5b. 4G WAN failover (optional) ───────────────────────────────────────────
_sep
if [[ -n "$BACKUP_MODEM" ]]; then
    _setup_wan_failover "$BACKUP_MODEM"
else
    _green "▶ Skipping 4G failover setup (no --backup-modem specified)"
fi

# ── 6. State directory ────────────────────────────────────────────────────────
mkdir -p "$MYXON_STATE_DIR"
chmod 700 "$MYXON_STATE_DIR"

# ── 7. Write agent.env ────────────────────────────────────────────────────────
_green "▶ Writing agent configuration..."

if [ "$ALREADY_ACTIVATED" -eq 1 ]; then
    # Device already activated — update server URL and scan mode, but don't
    # overwrite with activation code (device.json is the authority now)
    _warn "Updating agent.env without changing activation code (device already activated)"
    cat > "$AGENT_DIR/agent.env" <<ENVEOF
# MYXON Edge Agent — updated by install.sh $(date '+%Y-%m-%d %H:%M')
MYXON_CLOUD_URL=$CLOUD_URL
MYXON_SCAN_MODE=$SCAN_MODE
MYXON_HEARTBEAT_INTERVAL=15
MYXON_DISCOVERY_INTERVAL=60
MYXON_FRPC_BIN=/usr/local/bin/frpc
MYXON_DEVICE_STATE=$MYXON_STATE_DIR/device.json
ENVEOF
else
    # Fresh install — write activation code
    cat > "$AGENT_DIR/agent.env" <<ENVEOF
# MYXON Edge Agent — OEM activation-code flow
# Generated by install.sh $(date '+%Y-%m-%d %H:%M')
#
# On first boot, the agent calls POST /api/v0/agent/activate with MYXON_ACTIVATION_CODE.
# The server returns a serial number and frpc token, which are persisted to
# MYXON_DEVICE_STATE. On subsequent boots, MYXON_ACTIVATION_CODE is ignored
# (device.json takes priority). The code can only be used once.

MYXON_CLOUD_URL=$CLOUD_URL
MYXON_ACTIVATION_CODE=$ACTIVATION_CODE

# LAN scanning mode: auto | lan-only | all
MYXON_SCAN_MODE=$SCAN_MODE

# LAN interface (set when --lan-iface was used — Orange Pi as router/gateway).
# When set, the agent scans ONLY this interface, ignoring all others.
# Leave empty for auto-detection (single-NIC mode).
MYXON_LAN_IFACE=$LAN_IFACE

# GSM modem for local SMS delivery (set when --backup-modem was used).
# Agent uses mmcli (ModemManager CLI) first; falls back to AT commands on this port.
# Leave empty to disable local SMS (email-only notifications).
MYXON_MODEM_PORT=$BACKUP_MODEM

# Intervals (seconds)
MYXON_HEARTBEAT_INTERVAL=15
MYXON_DISCOVERY_INTERVAL=60
MYXON_FRPC_BIN=/usr/local/bin/frpc

# Path where activated device identity is persisted (serial + token)
# This file is created automatically on first successful activation.
MYXON_DEVICE_STATE=$MYXON_STATE_DIR/device.json
ENVEOF
fi

chmod 640 "$AGENT_DIR/agent.env"  # root:root, readable by root only
_cyan "agent.env written to $AGENT_DIR/agent.env"

# ── 8. systemd service ────────────────────────────────────────────────────────
_green "▶ Installing systemd service..."

cat > /etc/systemd/system/myxon-agent.service <<'SVCEOF'
[Unit]
Description=MYXON Edge Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/myxon-agent
EnvironmentFile=-/opt/myxon-agent/agent.env
ExecStart=/opt/myxon-agent/venv/bin/python myxon_agent.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=myxon-agent

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable myxon-agent
_cyan "myxon-agent service enabled"

# ── 9. Start ──────────────────────────────────────────────────────────────────
_green "▶ Starting myxon-agent..."
systemctl restart myxon-agent || {
    _warn "Service failed to start. Check logs: journalctl -u myxon-agent -n 50"
}

# Give agent a moment to attempt activation
sleep 3

# Report activation status
if [ -f "$MYXON_STATE_DIR/device.json" ]; then
    SERIAL=$(python3 -c "import json; d=json.load(open('$MYXON_STATE_DIR/device.json')); print(d.get('serial_number','?'))" 2>/dev/null || echo "?")
    echo ""
    _green "  ✓ Device activated successfully!"
    _cyan "  Serial: $SERIAL"
else
    echo ""
    _warn "Activation pending — device.json not yet created."
    _warn "The agent will retry automatically. Check logs:"
    _warn "  journalctl -u myxon-agent -f"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
_sep
echo ""
echo "  Installation complete. Useful commands:"
echo ""
echo "    journalctl -u myxon-agent -f           # Live logs"
echo "    systemctl status myxon-agent            # Service status"
echo "    cat $MYXON_STATE_DIR/device.json        # Activated device identity"
echo ""
_sep
