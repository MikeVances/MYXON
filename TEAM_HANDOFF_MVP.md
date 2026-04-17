# TEAM HANDOFF MVP

> Обновлено: 04 April 2026 — приведено в соответствие с MYXON_PLATFORM_ARCHITECTURE.md v2

## Цель
Запустить MVP MYXON: промышленная IoT-платформа удалённого доступа к контроллерам в агросекторе,
где клиент самостоятельно управляет своими устройствами, а дилер получает комиссию без доступа к данным.

## In Scope (MVP)

- Orange Pi (Debian) как edge-агент с авто-дискавери контроллеров по LAN.
- frpc-тоннель как единственный путь к контроллеру (устройства за NAT, без публичного IP).
- Иерархия тенантов: `platform → partner → dealer → customer`.
- Мультиплощадочность: customer имеет N площадок (Sites), каждая — M устройств.
- Клиент **самостоятельно** активирует устройство через ClaimWizard (серийник с наклейки).
- RBAC: роли `customer_admin / customer_engineer / customer_viewer` внутри customer.
- Dealer видит только: online/offline, кол-во устройств. Данные клиента — закрыты.
- HMI контроллера (HOTRACO Remote+ port 5843) доступен из браузера через WS-бридж.
- AlarmPanel: аларми контроллера в портале.
- Журнал действий (audit log) и статусы online/offline.

## Out of Scope (после MVP)

- AI-ассистент ("Валентина Петровна").
- Встроенный мессенджер.
- Биллинг (Stripe Connect, settlement) — Этап 2.
- White-label branding — Этап 3.
- Временный access grant дилеру — Этап 3.
- Мобильное приложение.

## Ключевые архитектурные решения

Все принятые решения зафиксированы в: **`MYXON_PLATFORM_ARCHITECTURE.md`**

Ключевые:
1. Клиент платит MYXON напрямую (не через дилера).
2. Дилер не имеет доступа к данным клиента по умолчанию.
3. Orange Pi сам сканирует LAN и находит контроллер — ручной IP не нужен.
4. frpc-тоннель — PRIMARY путь к контроллеру (не прямой IP).
5. Selling chain (dealer_id, partner_id) ≠ Data access chain.

## Ключевые артефакты для команды

- `MYXON_PLATFORM_ARCHITECTURE.md` — **главный референс архитектуры**
- `MYXON_IMPLEMENTATION_PLAN.md` — рабочий план по workstreams
- `MVP_ACCEPTANCE_CHECKLIST.md` — критерии приёмки
- `SPRINT_0_1_PLAN.md` — план спринтов
- `myxon-platform/DEV_QUICKSTART.md` — как поднять dev-окружение
- `IXON_AS_IS_REPORT.md` — референс: как работает IXON (аналог)
- `REMOTE_PLUS_PROTOCOL_SPEC.md` — протокол HOTRACO Remote+

## Командная рамка

**Backend:**
- auth/devices/sites/agent/alarms/audit/ws_remote API
- Tenant isolation + RBAC (4 тира + роли внутри customer)
- Dealer data isolation (dealer видит только online/offline)
- ClaimWizard backend (SN validation → ownership transfer)

**Frontend:**
- Customer portal: список площадок/устройств, DeviceDashboard, AlarmPanel
- Dealer portal: создание клиентов, регистрация устройств
- ClaimWizard UI

**Edge/Agent:**
- `edge-agent/myxon_agent.py` — авто-дискавери LAN, регистрация, frpc-тоннель
- `edge-agent/setup-debian.sh` — установка на Orange Pi (Debian)
- `edge-agent/myxon-agent.service` — systemd unit

**DevOps:**
- `docker-compose.dev.yml` — PostgreSQL + Redis + FRPS
- `dev.sh` — единая команда для dev-старта
- Infra: TLS, observability, backup/restore

## Dev-старт (одна команда)

```bash
cd myxon-platform
./dev.sh
```

Детали: `myxon-platform/DEV_QUICKSTART.md`
