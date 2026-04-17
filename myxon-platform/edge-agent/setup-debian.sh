#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# MYXON Edge Agent — установка на Debian (Orange Pi и другие SBC)
#
# Интерактивный мастер установки:
#   1. Выбор режима работы (пассивный / роутер)
#   2. Ввод серийника и URL сервера
#   3. Установка агента + Local API
#   4. Опционально — WiFi точка доступа (телефон как монитор)
#   5. systemd-сервисы в автозапуск
#
# Запуск (на Orange Pi, от root или через sudo):
#   scp -r edge-agent/ user@orangepi:/tmp/myxon-agent
#   ssh user@orangepi
#   cd /tmp/myxon-agent && sudo bash setup-debian.sh
#
# Неинтерактивный запуск (CI / предконфигурированный образ):
#   MYXON_SERIAL=HOTRACO-ORN-001 \
#   MYXON_CLOUD_URL=http://10.0.1.5:8000 \
#   MYXON_MODE=passive \
#   MYXON_WIFI_AP=no \
#     sudo -E bash setup-debian.sh --non-interactive
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

AGENT_DIR=/opt/myxon-agent
FRP_VERSION=0.61.0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Helpers ───────────────────────────────────────────────────────────────────
log()     { echo -e "\033[1;32m▶ $*\033[0m"; }
info()    { echo -e "  \033[0;36m$*\033[0m"; }
warn()    { echo -e "\033[1;33m⚠ $*\033[0m"; }
die()     { echo -e "\033[1;31m✖ $*\033[0m"; exit 1; }
sep()     { echo -e "\033[0;90m────────────────────────────────────────────────────\033[0m"; }
bold()    { echo -e "\033[1m$*\033[0m"; }

ask() {
    # ask VARNAME "Question" "default"
    local var="$1" prompt="$2" default="${3:-}"
    local answer
    if [ -n "$default" ]; then
        read -r -p "  $prompt [$default]: " answer
        echo "${answer:-$default}"
    else
        while true; do
            read -r -p "  $prompt: " answer
            [ -n "$answer" ] && break
            echo "  (обязательное поле, введите значение)"
        done
        echo "$answer"
    fi
}

ask_yn() {
    # ask_yn "Question" y|n  → returns 0 for yes, 1 for no
    local prompt="$1" default="${2:-n}"
    local answer
    local hint
    [ "$default" = "y" ] && hint="[Y/n]" || hint="[y/N]"
    read -r -p "  $prompt $hint: " answer
    answer="${answer:-$default}"
    [[ "$answer" =~ ^[Yy] ]]
}

[ "$(id -u)" -eq 0 ] || die "Run as root: sudo bash setup-debian.sh"

# Non-interactive flag
NON_INTERACTIVE=0
for arg in "$@"; do
    [ "$arg" = "--non-interactive" ] && NON_INTERACTIVE=1
done

# ── Welcome ───────────────────────────────────────────────────────────────────
echo ""
bold "  ╔═══════════════════════════════════════════╗"
bold "  ║        MYXON Edge Agent Installer         ║"
bold "  ╚═══════════════════════════════════════════╝"
echo ""
echo "  Установит агент, Local API и опционально WiFi AP"
echo "  на этот Orange Pi / Debian-устройство."
echo ""

# ── Step 1: Mode ──────────────────────────────────────────────────────────────
sep
bold "  Шаг 1. Режим работы"
echo ""
echo "  passive  — Orange Pi вставлен в существующую LAN фермы (камеры, контроллеры)."
echo "             Один Ethernet-порт. Агент сканирует ту же подсеть."
echo "             ✓ Самый частый случай."
echo ""
echo "  gateway  — Orange Pi — роутер между WAN и LAN контроллеров."
echo "             Два сетевых порта (WAN eth0, LAN eth1)."
echo "             Агент сканирует только LAN-порт, не WAN."
echo ""

if [ "$NON_INTERACTIVE" -eq 1 ]; then
    DEPLOY_MODE="${MYXON_MODE:-passive}"
    log "Режим: $DEPLOY_MODE (из MYXON_MODE)"
else
    DEPLOY_MODE_RAW=$(ask DEPLOY_MODE "Выберите режим (passive/gateway)" "passive")
    DEPLOY_MODE="${DEPLOY_MODE_RAW,,}"
    [[ "$DEPLOY_MODE" =~ ^(passive|gateway)$ ]] || DEPLOY_MODE="passive"
fi

case "$DEPLOY_MODE" in
    passive)
        SCAN_MODE_VAL="auto"
        info "Выбран passive → MYXON_SCAN_MODE=auto (сканирует LAN фермы, fallback на WAN-подсеть)"
        ;;
    gateway)
        SCAN_MODE_VAL="lan-only"
        info "Выбран gateway → MYXON_SCAN_MODE=lan-only (только LAN-порт)"
        ;;
esac

# ── Step 2: Cloud config ──────────────────────────────────────────────────────
sep
bold "  Шаг 2. Настройка подключения к облаку"
echo ""

if [ "$NON_INTERACTIVE" -eq 1 ]; then
    SERIAL="${MYXON_SERIAL:?MYXON_SERIAL is required in non-interactive mode}"
    CLOUD_URL="${MYXON_CLOUD_URL:?MYXON_CLOUD_URL is required in non-interactive mode}"
else
    SERIAL=$(ask SERIAL "Серийный номер устройства (напр. HOTRACO-ORN-001)" "")
    CLOUD_URL=$(ask CLOUD_URL "URL MYXON сервера (напр. http://10.0.1.5:8000)" "")
fi
info "Serial   : $SERIAL"
info "Cloud URL: $CLOUD_URL"

# ── Step 3: WiFi AP ───────────────────────────────────────────────────────────
sep
bold "  Шаг 3. WiFi точка доступа (опционально)"
echo ""
echo "  Поднять wlan0 как WiFi AP? Фермер подключает телефон"
echo "  и видит статус устройства без интернета."
echo ""

SETUP_WIFI=0
AP_SSID_VAL=""
AP_PASS_VAL=""

if [ "$NON_INTERACTIVE" -eq 1 ]; then
    [[ "${MYXON_WIFI_AP:-no}" =~ ^[Yy] ]] && SETUP_WIFI=1
else
    # Check if wlan0 exists before offering the option
    if ip link show wlan0 &>/dev/null; then
        if ask_yn "Настроить WiFi AP на wlan0?" "n"; then
            SETUP_WIFI=1
            AP_SSID_VAL=$(ask AP_SSID "SSID сети" "MYXON-${SERIAL}")
            AP_PASS_VAL=$(ask AP_PASS "Пароль (мин. 8 символов)" "myxon1234")
        fi
    else
        warn "wlan0 не найден — WiFi AP недоступен на этом устройстве."
    fi
fi

if [ "$SETUP_WIFI" -eq 1 ] && [ -z "$AP_SSID_VAL" ]; then
    AP_SSID_VAL="${MYXON_WIFI_SSID:-MYXON-${SERIAL}}"
    AP_PASS_VAL="${MYXON_WIFI_PASS:-myxon1234}"
fi

# ── Confirm ───────────────────────────────────────────────────────────────────
sep
bold "  Итоговая конфигурация"
echo ""
echo "  Режим           : $DEPLOY_MODE (SCAN_MODE=$SCAN_MODE_VAL)"
echo "  Серийник        : $SERIAL"
echo "  Сервер          : $CLOUD_URL"
if [ "$SETUP_WIFI" -eq 1 ]; then
    echo "  WiFi AP         : ДА  SSID=$AP_SSID_VAL"
else
    echo "  WiFi AP         : нет"
fi
echo ""

if [ "$NON_INTERACTIVE" -eq 0 ]; then
    ask_yn "Продолжить установку?" "y" || { echo "  Отменено."; exit 0; }
fi

echo ""

# ── 1. System packages ────────────────────────────────────────────────────────
log "Обновление пакетов и установка зависимостей..."
apt-get update -q
apt-get install -y -q python3 python3-pip python3-venv curl tar iproute2

# ── 2. frpc ───────────────────────────────────────────────────────────────────
if command -v frpc &>/dev/null; then
    log "frpc уже установлен: $(frpc --version)"
else
    ARCH=$(uname -m)
    case "$ARCH" in
      aarch64|arm64) FRP_ARCH="arm64" ;;
      armv7l|armhf)  FRP_ARCH="arm"   ;;
      x86_64)        FRP_ARCH="amd64" ;;
      *)             die "Неизвестная архитектура: $ARCH" ;;
    esac

    FRP_URL="https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_${FRP_ARCH}.tar.gz"
    FRP_TAR="/tmp/frp.tar.gz"

    log "Загрузка frpc для $ARCH..."
    curl -L --progress-bar -o "$FRP_TAR" "$FRP_URL"
    tar -xzf "$FRP_TAR" -C /tmp
    cp "/tmp/frp_${FRP_VERSION}_linux_${FRP_ARCH}/frpc" /usr/local/bin/frpc
    chmod +x /usr/local/bin/frpc
    rm -rf "$FRP_TAR" "/tmp/frp_${FRP_VERSION}_linux_${FRP_ARCH}"
    log "frpc установлен: $(frpc --version)"
fi

# ── 3. Agent files ────────────────────────────────────────────────────────────
log "Установка агента в $AGENT_DIR..."
mkdir -p "$AGENT_DIR"

# Copy all agent Python files
for f in myxon_agent.py local_api.py; do
    [ -f "$SCRIPT_DIR/$f" ] && cp "$SCRIPT_DIR/$f" "$AGENT_DIR/$f"
done

# virtualenv with required packages
log "Создание Python venv..."
python3 -m venv "$AGENT_DIR/venv"
"$AGENT_DIR/venv/bin/pip" install --quiet --upgrade pip
"$AGENT_DIR/venv/bin/pip" install --quiet httpx fastapi uvicorn[standard]

# ── 4. Write agent.env ────────────────────────────────────────────────────────
log "Запись конфигурации → $AGENT_DIR/agent.env"

# Don't overwrite an existing config unless --non-interactive (preserves token)
if [ -f "$AGENT_DIR/agent.env" ] && [ "$NON_INTERACTIVE" -eq 0 ]; then
    if ! ask_yn "agent.env уже есть. Перезаписать?" "n"; then
        warn "agent.env оставлен без изменений."
    else
        _write_env=1
    fi
else
    _write_env=1
fi

if [ "${_write_env:-0}" -eq 1 ]; then
    cat > "$AGENT_DIR/agent.env" <<ENVEOF
# MYXON Edge Agent — сгенерировано setup-debian.sh $(date '+%Y-%m-%d %H:%M')
MYXON_CLOUD_URL=$CLOUD_URL
MYXON_SERIAL=$SERIAL

# Режим сканирования LAN: auto | lan-only | all
MYXON_SCAN_MODE=$SCAN_MODE_VAL

# Интервалы (секунды)
MYXON_HEARTBEAT_INTERVAL=15
MYXON_DISCOVERY_INTERVAL=60
MYXON_FRPC_BIN=/usr/local/bin/frpc
ENVEOF
    info "agent.env записан"
fi

# ── 5. /etc/myxon directory ───────────────────────────────────────────────────
mkdir -p /etc/myxon
chmod 700 /etc/myxon

# ── 6. systemd: myxon-agent ───────────────────────────────────────────────────
log "Установка systemd-сервиса myxon-agent..."
if [ -f "$SCRIPT_DIR/myxon-agent.service" ]; then
    cp "$SCRIPT_DIR/myxon-agent.service" /etc/systemd/system/
else
    # Generate inline if service file not present
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
EnvironmentFile=-/etc/myxon/agent.env
ExecStart=/opt/myxon-agent/venv/bin/python myxon_agent.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF
fi

# ── 7. systemd: myxon-local-api ───────────────────────────────────────────────
log "Установка systemd-сервиса myxon-local-api..."
if [ -f "$SCRIPT_DIR/myxon-local-api.service" ]; then
    cp "$SCRIPT_DIR/myxon-local-api.service" /etc/systemd/system/
else
    cat > /etc/systemd/system/myxon-local-api.service <<SVCEOF
[Unit]
Description=MYXON Local Agent API
After=network.target myxon-agent.service
Wants=myxon-agent.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/myxon-agent
EnvironmentFile=-/etc/myxon/agent.env
Environment=LOCAL_API_BIND=0.0.0.0
Environment=LOCAL_API_PORT=8765
ExecStart=/opt/myxon-agent/venv/bin/python local_api.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF
fi

systemctl daemon-reload
systemctl enable myxon-agent myxon-local-api

# ── 8. WiFi AP ────────────────────────────────────────────────────────────────
if [ "$SETUP_WIFI" -eq 1 ]; then
    log "Настройка WiFi AP..."
    AP_SSID="$AP_SSID_VAL" AP_PASS="$AP_PASS_VAL" bash "$SCRIPT_DIR/setup-wifi-ap.sh"
fi

# ── 9. Start services ─────────────────────────────────────────────────────────
log "Запуск сервисов..."
systemctl start myxon-agent   || warn "myxon-agent не запустился (check: journalctl -u myxon-agent)"
systemctl start myxon-local-api || warn "myxon-local-api не запустился (check: journalctl -u myxon-local-api)"

# ── Done ──────────────────────────────────────────────────────────────────────
sep
echo ""
bold "  Установка завершена!"
echo ""
echo "  Статус сервисов:"
echo "    sudo systemctl status myxon-agent"
echo "    sudo systemctl status myxon-local-api"
echo ""
echo "  Логи в реальном времени:"
echo "    journalctl -u myxon-agent -f"
echo "    journalctl -u myxon-local-api -f"
echo ""
echo "  Local API (из LAN):"
echo "    curl http://$(hostname -I | awk '{print $1}'):8765/health"
echo "    # Токен доступа после первого запуска:"
echo "    cat /etc/myxon/local_api_token"
echo ""
if [ "$SETUP_WIFI" -eq 1 ]; then
    echo "  WiFi AP:"
    echo "    SSID: $AP_SSID_VAL"
    echo "    URL : http://192.168.42.1:8765"
    echo ""
fi
echo "  Конфигурация: $AGENT_DIR/agent.env"
sep
