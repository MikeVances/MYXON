#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# MYXON Platform — VPS Installer / Updater
#
# ПЕРВЫЙ ЗАПУСК (чистый VPS, Debian 12 / Ubuntu 22.04+):
#   git clone https://github.com/MikeVances/MYXON.git && cd MYXON/myxon-platform
#   sudo bash deploy.sh --domain myxon.yourcompany.com --email admin@yourcompany.com
#
# Что делает скрипт:
#   1. Устанавливает Docker + Compose plugin (если нет)
#   2. Генерирует .env с криптостойкими случайными паролями (если нет)
#   3. Включает Docker в systemd (автозапуск при ребуте)
#   4. Создаёт myxon-platform.service — платформа поднимается после ребута
#   5. Собирает и запускает контейнеры
#   6. Запускает Alembic migrations (через entrypoint backend-а)
#   7. Запускает bootstrap (первый admin-пользователь)
#   8. (Если --tls) получает TLS-сертификат через Let's Encrypt
#
# ОБНОВЛЕНИЕ КОДА (после git pull):
#   sudo bash deploy.sh --update
#
# ФЛАГИ:
#   --domain <domain>   Домен или IP VPS (обязателен при первом запуске)
#   --email  <email>    Email администратора (по умолчанию: admin@<domain>)
#   --tls               Получить сертификат Let's Encrypt (нужен реальный домен)
#   --update            Только пересборка backend/frontend и перезапуск
#   --reset-db          Удалить БД и начать заново (ОСТОРОЖНО: необратимо)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Цвета ─────────────────────────────────────────────────────────────────────
_green() { echo -e "\033[1;32m▶ $*\033[0m"; }
_cyan()  { echo -e "  \033[0;36m$*\033[0m"; }
_warn()  { echo -e "\033[1;33m⚠ $*\033[0m" >&2; }
_die()   { echo -e "\033[1;31m✖ $*\033[0m" >&2; exit 1; }
_sep()   { echo -e "\033[0;90m────────────────────────────────────────────────\033[0m"; }

# ── Аргументы ─────────────────────────────────────────────────────────────────
DOMAIN="${MYXON_DOMAIN:-}"
ADMIN_EMAIL_ARG="${MYXON_ADMIN_EMAIL:-}"
MODE="full"
TLS=0
RESET_DB=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain)   DOMAIN="$2";         shift 2 ;;
        --email)    ADMIN_EMAIL_ARG="$2"; shift 2 ;;
        --tls)      TLS=1;                shift   ;;
        --update)   MODE="update";        shift   ;;
        --reset-db) RESET_DB=1;           shift   ;;
        *) _die "Неизвестный аргумент: $1" ;;
    esac
done

COMPOSE="docker compose -f docker-compose.prod.yml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Права ─────────────────────────────────────────────────────────────────────
[ "$(id -u)" -eq 0 ] || _die "Запусти с правами root: sudo bash deploy.sh [аргументы]"

# ─────────────────────────────────────────────────────────────────────────────
# РЕЖИМ ОБНОВЛЕНИЯ — только пересборка и перезапуск
# ─────────────────────────────────────────────────────────────────────────────
if [ "$MODE" = "update" ]; then
    _green "Режим обновления..."
    [ -f ".env" ] || _die ".env не найден — запусти полный деплой сначала"
    _cyan "Пересборка образов..."
    $COMPOSE build --pull backend frontend
    _cyan "Перезапуск контейнеров..."
    $COMPOSE up -d --no-deps backend frontend nginx
    _green "Обновление завершено!"
    echo ""
    _cyan "Логи: $COMPOSE logs -f backend"
    exit 0
fi

# ─────────────────────────────────────────────────────────────────────────────
# ПОЛНЫЙ ДЕПЛОЙ
# ─────────────────────────────────────────────────────────────────────────────

[[ -n "$DOMAIN" ]] || _die \
    "Укажи домен/IP: sudo bash deploy.sh --domain myxon.yourcompany.com"

# Определяем протокол и URL
if [[ $TLS -eq 1 ]]; then
    APP_BASE_URL="https://${DOMAIN}"
else
    APP_BASE_URL="http://${DOMAIN}"
fi

ADMIN_EMAIL="${ADMIN_EMAIL_ARG:-admin@${DOMAIN}}"

echo ""
_green "  ╔═══════════════════════════════════════════╗"
_green "  ║     MYXON Platform — VPS Installer       ║"
_green "  ╚═══════════════════════════════════════════╝"
echo ""
_cyan "Домен    : $DOMAIN"
_cyan "URL      : $APP_BASE_URL"
_cyan "Admin    : $ADMIN_EMAIL"
_cyan "TLS      : $([ $TLS -eq 1 ] && echo "Let's Encrypt" || echo "нет (HTTP)")"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Шаг 1: Установка Docker
# ─────────────────────────────────────────────────────────────────────────────
_sep
_green "Шаг 1/7: Docker..."

if ! command -v docker &>/dev/null; then
    _cyan "Docker не найден — устанавливаю..."
    apt-get update -qq
    apt-get install -y -qq curl ca-certificates gnupg lsb-release

    # Официальный скрипт установки Docker (Debian/Ubuntu)
    curl -fsSL https://get.docker.com | bash

    _cyan "Docker установлен: $(docker --version)"
else
    _cyan "Docker уже установлен: $(docker --version)"
fi

# Docker Compose plugin
if ! docker compose version &>/dev/null; then
    _cyan "Устанавливаю Docker Compose plugin..."
    apt-get install -y -qq docker-compose-plugin
fi
_cyan "Docker Compose: $(docker compose version --short)"

# Включаем автозапуск Docker при ребуте VPS
systemctl enable docker
systemctl start docker
_cyan "Docker systemd: enabled + running"

# ─────────────────────────────────────────────────────────────────────────────
# Шаг 2: Генерация .env
# ─────────────────────────────────────────────────────────────────────────────
_sep
_green "Шаг 2/7: Конфигурация (.env)..."

if [ -f ".env" ]; then
    _warn ".env уже существует — не перезаписываю"
    _cyan "Обновляю SERVER_HOST и APP_BASE_URL..."
    # Обновляем только хост/URL если изменился домен
    sed -i "s|^SERVER_HOST=.*|SERVER_HOST=${DOMAIN}|" .env
    sed -i "s|^APP_BASE_URL=.*|APP_BASE_URL=${APP_BASE_URL}|" .env
else
    _cyan "Генерирую .env с безопасными случайными паролями..."

    # Генерация криптостойких значений
    DB_PASSWORD=$(openssl rand -hex 24)
    REDIS_PASSWORD=$(openssl rand -hex 24)
    SECRET_KEY=$(openssl rand -hex 48)
    ADMIN_PASSWORD=$(openssl rand -base64 12 | tr -d /+= | head -c 16)
    FRPS_PLUGIN_SECRET=$(openssl rand -hex 32)

    cat > .env <<ENVEOF
# ─── MYXON Platform — Production Config ──────────────────────────────────────
# Сгенерировано автоматически: $(date '+%Y-%m-%d %H:%M')
# Не коммить этот файл в git — он содержит секреты!

# ─── Server ──────────────────────────────────────────────────────────────────
SERVER_HOST=${DOMAIN}
APP_BASE_URL=${APP_BASE_URL}

# ─── Database ─────────────────────────────────────────────────────────────────
DB_PASSWORD=${DB_PASSWORD}

# ─── Redis ────────────────────────────────────────────────────────────────────
REDIS_PASSWORD=${REDIS_PASSWORD}

# ─── Auth (JWT) ───────────────────────────────────────────────────────────────
SECRET_KEY=${SECRET_KEY}

# ─── First admin user ─────────────────────────────────────────────────────────
# Используется один раз при bootstrap. После создания можно изменить пароль в UI.
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASSWORD}

# ─── FRPS ─────────────────────────────────────────────────────────────────────
FRPS_BIND_PORT=7000
TUNNEL_PORT_START=10000
TUNNEL_PORT_END=10100
# Секрет для проверки запросов от frps к backend (frps → /api/v0/frps/auth)
FRPS_PLUGIN_SECRET=${FRPS_PLUGIN_SECRET}

# ─── Email notifications (SMTP) ───────────────────────────────────────────────
# Оставь SMTP_HOST пустым чтобы отключить email-уведомления об авариях.
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@${DOMAIN}
SMTP_USE_TLS=true

# ─── App settings ─────────────────────────────────────────────────────────────
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=info
UVICORN_WORKERS=2
ENVEOF

    chmod 600 .env
    _cyan ".env создан (права 600)"
    echo ""
    _warn "СОХРАНИ ЭТИ ДАННЫЕ:"
    _warn "  Admin email:    ${ADMIN_EMAIL}"
    _warn "  Admin password: ${ADMIN_PASSWORD}"
    _warn "  (пароль виден только один раз, хранится в .env)"
    echo ""
fi

# ─────────────────────────────────────────────────────────────────────────────
# Шаг 3: Обновление frps.toml с FRPS_PLUGIN_SECRET из .env
# ─────────────────────────────────────────────────────────────────────────────
# frps.toml не поддерживает env vars напрямую — подставляем при деплое
source <(grep -E "^FRPS_PLUGIN_SECRET=" .env)

# Добавляем secret в backend переменные окружения (docker-compose уже читает .env)
# Ничего дополнительного не нужно — docker-compose.prod.yml передаёт его как
# FRPS_PLUGIN_SECRET через environment: секцию (добавим ниже если нужно)

# ─────────────────────────────────────────────────────────────────────────────
# Шаг 4: systemd unit — платформа поднимается после ребута VPS
# ─────────────────────────────────────────────────────────────────────────────
_sep
_green "Шаг 3/7: Systemd unit (myxon-platform.service)..."

cat > /etc/systemd/system/myxon-platform.service <<SVCEOF
[Unit]
Description=MYXON Platform (Docker Compose)
# Стартуем после того как Docker daemon готов и сеть поднялась
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${SCRIPT_DIR}
# При старте — поднять все контейнеры
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d --remove-orphans
# При остановке — graceful shutdown
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
# При перезапуске через systemctl restart — полный down + up
ExecReload=/usr/bin/docker compose -f docker-compose.prod.yml up -d --remove-orphans

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable myxon-platform
_cyan "myxon-platform.service: enabled"
_cyan "После ребута VPS платформа поднимается автоматически"

# ─────────────────────────────────────────────────────────────────────────────
# Шаг 5: Reset DB (если --reset-db)
# ─────────────────────────────────────────────────────────────────────────────
if [ $RESET_DB -eq 1 ]; then
    _sep
    _warn "СБРОС БД — все данные будут удалены!"
    read -r -p "Подтверди (введи 'yes'): " confirm
    [ "$confirm" = "yes" ] || _die "Прервано"
    $COMPOSE down -v
    _cyan "Volumes удалены"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Шаг 6: Сборка и запуск
# ─────────────────────────────────────────────────────────────────────────────
_sep
_green "Шаг 4/7: Сборка Docker-образов..."
$COMPOSE build --pull

_sep
_green "Шаг 5/7: Запуск БД и Redis..."
$COMPOSE up -d db redis

_cyan "Ожидание PostgreSQL..."
timeout 90 bash -c \
    'until docker compose -f docker-compose.prod.yml exec -T db pg_isready -U myxon 2>/dev/null; do sleep 2; done' \
    || _die "PostgreSQL не запустился за 90 секунд"
_cyan "PostgreSQL готов ✓"

_sep
_green "Шаг 6/7: Запуск всех сервисов..."
# entrypoint.sh запускает 'alembic upgrade head' перед стартом uvicorn
$COMPOSE up -d

_cyan "Ожидание backend (migrations + startup)..."
timeout 120 bash -c \
    'until curl -sf http://localhost:8000/health 2>/dev/null | grep -q ok; do sleep 3; done' \
    || _die "Backend не ответил за 120 секунд. Проверь: docker compose -f docker-compose.prod.yml logs backend"
_cyan "Backend готов ✓"

# ─────────────────────────────────────────────────────────────────────────────
# Шаг 7: Bootstrap — первый admin-пользователь
# ─────────────────────────────────────────────────────────────────────────────
_sep
_green "Шаг 7/7: Bootstrap (первый admin-пользователь)..."

if $COMPOSE exec -T backend python -m scripts.bootstrap 2>&1 | tee /tmp/myxon_bootstrap.log; then
    _cyan "Bootstrap выполнен ✓"
else
    if grep -q "already exists\|уже существует\|duplicate" /tmp/myxon_bootstrap.log 2>/dev/null; then
        _cyan "Bootstrap пропущен — admin уже создан ранее"
    else
        _warn "Bootstrap завершился с предупреждением. Лог: /tmp/myxon_bootstrap.log"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# TLS — Let's Encrypt (если --tls)
# ─────────────────────────────────────────────────────────────────────────────
if [ $TLS -eq 1 ]; then
    _sep
    _green "TLS: Получение сертификата Let's Encrypt..."
    source <(grep -E "^ADMIN_EMAIL=" .env)

    # Убеждаемся что certbot-папка существует
    mkdir -p infra/nginx/certs

    $COMPOSE run --rm certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email "${ADMIN_EMAIL}" \
        --agree-tos \
        --no-eff-email \
        -d "${DOMAIN}"

    _cyan "Сертификат получен ✓"
    _cyan "Перезапуск nginx с TLS..."
    $COMPOSE restart nginx

    # Авто-обновление сертификата запускается через certbot в docker-compose (profile: certbot)
    # Уже настроен в docker-compose.prod.yml: sleep 12h + certbot renew
fi

# ─────────────────────────────────────────────────────────────────────────────
# Финальный отчёт
# ─────────────────────────────────────────────────────────────────────────────
_sep
echo ""
_green "Деплой завершён!"
echo ""

source <(grep -E "^ADMIN_EMAIL=" .env)
source <(grep -E "^ADMIN_PASSWORD=" .env 2>/dev/null || echo "ADMIN_PASSWORD=см .env")

echo "  ┌──────────────────────────────────────────────────────────────┐"
echo "  │  Платформа:    ${APP_BASE_URL}"
echo "  │  API:          ${APP_BASE_URL}/api/v0/"
echo "  │  Документация: ${APP_BASE_URL}/docs"
echo "  │"
echo "  │  Admin email:  ${ADMIN_EMAIL}"
echo "  │  Admin pass:   ${ADMIN_PASSWORD}"
echo "  │"
echo "  │  frps (агент): ${DOMAIN}:7000"
echo "  └──────────────────────────────────────────────────────────────┘"
echo ""
echo "  Для Orange Pi / edge agent:"
echo "    MYXON_CLOUD_URL=${APP_BASE_URL}"
echo "    MYXON_FRPS_HOST=${DOMAIN}"
echo ""
echo "  Полезные команды:"
echo "    $COMPOSE ps                    # статус контейнеров"
echo "    $COMPOSE logs -f backend       # логи бэкенда"
echo "    $COMPOSE logs -f               # все логи"
echo "    sudo bash deploy.sh --update   # обновление кода"
echo "    systemctl status myxon-platform # статус systemd unit"
echo ""
_sep
