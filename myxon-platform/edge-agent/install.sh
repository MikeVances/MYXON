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
# Или с локальным файлом:
#
#   bash install.sh --code A3F1-B2E4-C9D7-0F56 --server https://myxon.example.com
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
#   5. Регистрирует и запускает systemd-сервис
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

while [[ $# -gt 0 ]]; do
    case "$1" in
        --code)   ACTIVATION_CODE="$2"; shift 2 ;;
        --server) CLOUD_URL="$2";       shift 2 ;;
        --scan)   SCAN_MODE="$2";       shift 2 ;;
        *) _die "Unknown argument: $1. Usage: install.sh --code XXXX-XXXX-XXXX-XXXX --server https://myxon.example.com" ;;
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

# ── 5. State directory ────────────────────────────────────────────────────────
mkdir -p "$MYXON_STATE_DIR"
chmod 700 "$MYXON_STATE_DIR"

# ── 6. Write agent.env ────────────────────────────────────────────────────────
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

# ── 7. systemd service ────────────────────────────────────────────────────────
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

# ── 8. Start ──────────────────────────────────────────────────────────────────
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
