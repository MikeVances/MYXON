# SPRINT 0-1 PLAN

> Обновлено: 04 April 2026 — приведено в соответствие с MYXON_PLATFORM_ARCHITECTURE.md v2

---

## ✅ Sprint 0 — ВЫПОЛНЕНО (инфра + каркас)

1. ~~Поднять окружение: PostgreSQL + Redis + FRPS (Docker) + Backend + Frontend.~~
   → `docker-compose.dev.yml` + `./dev.sh` готовы
2. ~~Миграции БД (Alembic) + seed-данные.~~
3. ~~Скелет API: `auth`, `devices`, `sites`, `agent`, `alarms`, `audit`, `ws_remote`.~~
4. ~~Базовый портал: login + список устройств + DeviceDashboard + AlarmPanel.~~
5. ~~Edge Agent: авто-дискавери LAN, регистрация, frpc-тоннель, heartbeat.~~
6. ~~Архитектурный документ: `MYXON_PLATFORM_ARCHITECTURE.md`.~~

---

## Sprint 1 — Онбординг (текущий приоритет)

### Backend
1. Тиры тенантов: добавить поле `tenant_type` (platform/partner/dealer/customer) в модель `Tenant`.
2. Selling chain: добавить `dealer_id`, `partner_id` на модель `Device`.
3. Site-scoped users: таблица `UserSiteAccess` (user_id → site_id).
4. Dealer API: эндпоинты для регистрации серийников и создания customer-инвайтов.
5. ClaimWizard API: `POST /api/v0/devices/claim` (SN → привязка к customer + site).
6. Customer invite: `POST /api/v0/auth/invite` (дилер создаёт инвайт для клиента).
7. Dealer data isolation: middleware/guard — dealer не получает данные клиента.

### Frontend
1. Dealer portal: страница создания клиента + регистрации устройства по серийнику.
2. ClaimWizard UI: ввод серийника → подтверждение → выбор площадки.
3. Customer signup: регистрация по инвайт-ссылке от дилера.
4. Site selector: пользователь customer_engineer видит только свои площадки.

### E2E-сценарий Sprint 1
```
Дилер регистрирует SN → создаёт инвайт для клиента
→ Клиент регистрируется по инвайту
→ Клиент: ClaimWizard → вводит SN → устройство привязано к его площадке
→ Orange Pi включается → агент находит контроллер → пробивает тоннель
→ Клиент открывает DeviceDashboard → видит HMI контроллера
→ Аларми контроллера → AlarmPanel → клиент подтверждает
```

## Exit Criteria Sprint 1
- Дилер может зарегистрировать устройство и создать клиента.
- Клиент самостоятельно активирует устройство через ClaimWizard.
- Dealer НЕ видит аларм-детали и HMI клиента.
- Закрыт `MVP_ACCEPTANCE_CHECKLIST.md` минимум на 80%.

---

## Sprint 2 — Hardening + Биллинг-основа

1. Reliability: disconnect/reconnect/offline SLA тест.
2. Security checks: token misuse, cross-tenant access attempts.
3. UX: ошибочные состояния (offline, invalid SN, expired invite).
4. Billing-модели: Plan, Subscription (без Stripe в этом спринте).
5. Grace period логика: suspended status при неоплате.
6. Operational readiness: alerts/runbooks/backups.

## Exit Criteria Sprint 2
- Go-live readiness review passed.
- `MVP_ACCEPTANCE_CHECKLIST.md` закрыт на 100%.
