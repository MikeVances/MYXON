#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# MYXON Platform — деплой на VPS (Debian/Ubuntu)
#
# Запуск:
#   git clone ... && cd myxon-platform
#   cp .env.example .env && nano .env    # заполнить CHANGE_ME
#   bash deploy.sh
#
# При повторном деплое (обновление кода):
#   git pull && bash deploy.sh --update
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

MODE="${1:-full}"   # full | update

log()  { echo -e "\033[1;32m▶ $*\033[0m"; }
warn() { echo -e "\033[1;33m⚠ $*\033[0m"; }
die()  { echo -e "\033[1;31m✖ $*\033[0m"; exit 1; }

# ── Проверки ──────────────────────────────────────────────────────────────────
[ -f ".env" ] || die ".env не найден. Скопируй: cp .env.example .env && nano .env"
grep -q "CHANGE_ME" .env && die ".env содержит незаполненные значения CHANGE_ME"

command -v docker >/dev/null || die "Docker не установлен"
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin не установлен"

COMPOSE="docker compose -f docker-compose.prod.yml"

# ── Update mode: пересборка и перезапуск ──────────────────────────────────────
if [ "$MODE" = "--update" ]; then
    log "Режим обновления..."
    $COMPOSE build --pull backend frontend
    $COMPOSE up -d --no-deps backend frontend nginx
    log "Обновление завершено"
    exit 0
fi

# ── Full deploy ───────────────────────────────────────────────────────────────

log "Шаг 1/5: Сборка образов..."
$COMPOSE build --pull

log "Шаг 2/5: Запуск БД и Redis..."
$COMPOSE up -d db redis
echo "  Ждём готовности PostgreSQL..."
timeout 60 bash -c 'until docker compose -f docker-compose.prod.yml exec -T db pg_isready -U myxon 2>/dev/null; do sleep 2; done'
log "  PostgreSQL готов ✓"

log "Шаг 3/5: Запуск backend (migrations запускаются автоматически в entrypoint)..."
$COMPOSE up -d backend
echo "  Ждём старта backend..."
timeout 60 bash -c 'until curl -sf http://localhost:8000/health 2>/dev/null; do sleep 3; done'
log "  Backend готов ✓"

log "Шаг 4/5: Запуск всех сервисов..."
$COMPOSE up -d

log "Шаг 5/5: Bootstrap (создание тенантов и первого admin)..."
if $COMPOSE exec -T backend python -m scripts.bootstrap; then
    log "Bootstrap выполнен ✓"
else
    warn "Bootstrap пропущен (данные уже существуют)"
fi

# ── Финальная проверка ────────────────────────────────────────────────────────
echo ""
log "Проверка сервисов..."
$COMPOSE ps

echo ""
log "Деплой завершён!"
echo ""

# Читаем SERVER_HOST из .env
source <(grep -E "^SERVER_HOST=" .env)
source <(grep -E "^APP_BASE_URL=" .env)
source <(grep -E "^ADMIN_EMAIL=" .env 2>/dev/null || echo "ADMIN_EMAIL=admin@myxon.local")

echo "  ┌─────────────────────────────────────────────────────────┐"
echo "  │  Платформа:   ${APP_BASE_URL}"
echo "  │  API:         ${APP_BASE_URL}/api/v0/"
echo "  │  frps:        ${SERVER_HOST}:7000  (для Orange Pi)"
echo "  │  Admin:       ${ADMIN_EMAIL}"
echo "  └─────────────────────────────────────────────────────────┘"
echo ""
echo "  Следующие шаги:"
echo "  1. Открой ${APP_BASE_URL} в браузере"
echo "  2. На Orange Pi отредактируй agent.env:"
echo "     MYXON_CLOUD_URL=${APP_BASE_URL}"
echo "     MYXON_FRPS_HOST=${SERVER_HOST}"
echo "  3. Запусти агент: sudo systemctl start myxon-agent"
echo "  4. Устройство должно появиться в браузере через 15–30 сек"
echo ""
echo "  Логи:  docker compose -f docker-compose.prod.yml logs -f backend"
