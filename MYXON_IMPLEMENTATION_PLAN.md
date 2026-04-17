# MYXON Implementation Plan (Team Execution Document)

Дата: 29 March 2026
Обновлено: 04 April 2026 — приведено в соответствие с MYXON_PLATFORM_ARCHITECTURE.md
Статус: Draft v2
Назначение: рабочий план реализации платформы MYXON для инженерной команды (без кода в этом документе)

> ⚠️ **Справочный документ по архитектуре:** `MYXON_PLATFORM_ARCHITECTURE.md`
> Все решения по иерархии тенантов, биллингу и доступу к данным — там.

---

## 1. Mission and Scope

### 1.1 Mission
Построить промышленную IoT-платформу удалённого доступа к контроллерам
(климат, вентиляция, кормление) в агросекторе, где:

- устройство за NAT подключается исходящим frpc-тоннелем к облаку;
- клиент (птицефабрика) самостоятельно активирует своё устройство;
- инженер получает доступ к HMI/PLC через браузер без установки спецПО;
- дилер получает комиссию, но **не имеет доступа к данным клиента**;
- клиент платит MYXON напрямую — сервис гарантирован независимо от дилера.

### 1.2 MVP Scope (In)

1. **Device onboarding** — дилер регистрирует серийник, клиент активирует устройство сам (ClaimWizard).
2. **Agent connectivity** — Orange Pi с Debian, frpc-тоннель, авто-дискавери контроллеров по LAN.
3. **Device inventory + status** — online/offline для всех уровней иерархии.
4. **Web access (HMI)** — прямой TCP через frpc-тоннель → контроллер (HOTRACO Remote+ port 5843).
5. **4-tier RBAC** — `platform_admin / partner / dealer / customer` + роли внутри customer.
6. **Мультиплощадочность** — один customer = несколько Sites, один Site = несколько устройств.
7. **Аудит-лог** — по ключевым действиям (claim, access, alarm).
8. **Alarm-панель** — отображение алармов контроллера в портале.

### 1.3 Out of Scope (MVP)
1. Полноценный встроенный мессенджер.
2. ИИ-ассистент "Валентина Петровна".
3. Глубокая аналитика machine data.
4. Полная enterprise-SSO матрица.
5. Биллинг (Этап 2) — только учёт подписок без Stripe в MVP.
6. White-label branding (Этап 3).

---

## 2. Иерархия участников (ключевое)

```
platform_admin
└── partner  (HOTRACO — white-label, каталог устройств)
    └── dealer  (Агровент — региональный интегратор)
        └── customer  (ООО Бройлер — конечный клиент)
            ├── site: Площадка А (Краснодар)
            │   └── device: Orange Pi #1
            └── site: Площадка Б (Ростов)
                └── device: Orange Pi #2
```

**Принцип разделения:**
- `selling chain` (dealer_id, partner_id на Device) = финансовая принадлежность
- `data access` = только сам customer и platform_admin по умолчанию

Подробнее: `MYXON_PLATFORM_ARCHITECTURE.md` §2–5.

---

## 3. System Workstreams

### 3.1 Edge Agent Layer
Цель: Orange Pi сам обнаруживает контроллеры и устанавливает тоннель.

Задачи:
1. Авто-дискавери — сканирование LAN-интерфейса (не WAN), поиск по портам 5843/5900/80.
2. Регистрация на сервере: SN, firmware version, hardware info, список найденных ресурсов.
3. Heartbeat/keepalive и модель online/offline (<=60 сек детекция).
4. frpc-тоннель: конфиг генерируется автоматически по данным от сервера.
5. Периодическое пересканирование LAN (reconnect/rediscovery).
6. Безопасное хранение секретов (`agent.env` как EnvironmentFile в systemd).

Топология:
```
Контроллер (port 5843)
  → LAN → Orange Pi (Debian, frpc)
    → интернет → MYXON Server (FRPS)
      → Backend → браузер клиента
```

**Orange Pi НЕ нуждается** в знании IP контроллера — он сканирует LAN сам.
**Orange Pi нуждается** только в белом адресе MYXON-сервера.

Результат: агент стабильно появляется в control plane и держит тоннель.

### 3.2 Connectivity Layer
Цель: туннелирование и маршрутизация доступа к устройствам.

Задачи:
1. FRPS в Docker, порт 7000 (тоннели) + 7500 (dashboard).
2. Backend назначает `tunnel_port` при регистрации агента.
3. WS-бридж (`/api/v0/ws/{device_id}`) проксирует TCP через `frps_host:tunnel_port`.
4. Первичный путь — всегда frpc-тоннель; прямой IP — только dev-fallback.
5. Health checks туннельных эндпоинтов.

Результат: доступ к HMI контроллера из браузера через frpc-тоннель.

### 3.3 Clientless Access Layer
Цель: web-доступ к HMI контроллера (HOTRACO Remote+ binary TCP).

Задачи:
1. WS-бридж на backend (WebSocket → TCP к tunnel_port).
2. Генерация временных access-сессий.
3. Browser session controls (open/close/timeout).
4. Аудит: who/when/what/resource.

Результат: оператор открывает экран контроллера из портала.

### 3.4 Control Plane Backend
Цель: ядро платформы, API, бизнес-правила.

Задачи:
1. Доменные модели:
   - `Tenant` (с типом: platform/partner/dealer/customer)
   - `User` (с ролью: customer_admin/customer_engineer/customer_viewer)
   - `Device` (с полями: dealer_id, partner_id, tunnel_port, status)
   - `Site` (площадка клиента)
   - `UserSiteAccess` (user → [site_id])
   - `Alarm`, `AuditEvent`, `AccessGrant`

2. API:
   - auth (JWT)
   - devices (list/details/claim/status)
   - sites (CRUD)
   - agent (register/heartbeat)
   - alarms (list/acknowledge)
   - audit (read-only)
   - ws_remote (WebSocket бридж)

3. Tenant isolation + RBAC enforcement.
4. Dealer data isolation: dealer видит только online/offline и количество устройств.

Результат: единое API-ядро для портала/агента/интеграций.

### 3.5 Portal UX Layer
Цель: рабочий продуктовый интерфейс для всей иерархии участников.

Задачи:
1. **Customer portal** (основной): список площадок, устройств, DeviceDashboard, AlarmPanel.
2. **Dealer portal**: создание клиентов, регистрация устройств по серийнику.
3. **ClaimWizard**: клиент вводит серийник с наклейки → устройство привязывается к его аккаунту.
4. Login + белый экран ошибок (offline, invalid SN, expired).
5. Мультиплощадочность: пользователь видит только назначенные ему площадки.

Результат: UX, покрывающий цикл: регистрация SN → онбординг клиента → активация → доступ → аудит.

### 3.6 Provisioning & Identity
Цель: корректный lifecycle устройства от дилера до клиента.

Воркфлоу:
```
1. Дилер прошивает Orange Pi (setup-debian.sh)
2. Дилер регистрирует серийник в dealer-портале MYXON
3. Orange Pi отправляется клиенту (серийник — на наклейке)
4. Orange Pi включается → агент стартует → пробивает тоннель → статус "online, unclaimed"
5. Клиент регистрируется в MYXON портале (по инвайту от дилера)
6. Клиент: ClaimWizard → вводит серийник → подтверждает → устройство привязано
7. Клиент указывает площадку → подписка активируется
```

**Важно:** клиент — единственный владелец устройства. Дилер не активирует за клиента.

Задачи:
1. Device registration endpoint для dealer-портала.
2. ClaimWizard: SN validation → ownership transfer → site assignment.
3. Invite flow: дилер создаёт customer + отправляет инвайт.
4. Статусная машина устройства: `registered → unclaimed → claimed → active → suspended`.

Результат: полный lifecycle от прошивки до активации клиентом.

### 3.7 Security & Compliance
Цель: безопасный baseline для production.

Задачи:
1. TLS everywhere on external perimeter.
2. Agent token policy (issue/rotate/revoke).
3. RBAC hard boundaries, dealer data isolation.
4. Audit retention policy.
5. Privacy baseline (GDPR-совместимость, dealer не видит данные клиента).
6. Temporary access grant (Этап 3): клиент → временный доступ поддержке → все действия логируются.

Результат: минимально достаточный security/compliance контур.

### 3.8 Ops/SRE
Цель: эксплуатационная готовность.

Задачи:
1. Environments: dev (`./dev.sh`) / stage / prod.
2. CI/CD pipeline базового уровня.
3. Metrics/logs/alerts dashboards.
4. Backups and restore drill.
5. Runbooks (connectivity incident, auth incident, tunnel incident).

Результат: система готова к поддержке после запуска.

---

## 4. Delivery Phases

### Этап 1 — Онбординг (текущий приоритет)
- [ ] Тиры тенантов: `platform / partner / dealer / customer`
- [ ] Selling chain на Device: `dealer_id`, `partner_id`
- [ ] Site-scoped пользователи (user → [site_id])
- [ ] Dealer UI: создать клиента, зарегистрировать устройство по серийнику
- [ ] Customer signup: регистрация по инвайту от дилера
- [ ] ClaimWizard: клиент активирует устройство сам

### Этап 2 — Биллинг
- [ ] Модели: Plan, Subscription, LedgerEntry, Settlement
- [ ] Stripe Connect интеграция (Destination Charges)
- [ ] Webhook обработка платежей
- [ ] Grace period / suspension логика (7 дней read-only → 7 дней offline)
- [ ] Settlement dashboard для дилера и партнёра

### Этап 3 — Зрелость платформы
- [ ] Временный access grant (поддержка дилера по запросу клиента)
- [ ] White-label branding per partner
- [ ] Multi-domain tenant resolution (app.hotraco.com → partner resolution)
- [ ] Мобильное приложение
- [ ] Аналитика и отчёты по тенантам

---

## 5. Team Model and Ownership

Минимальный состав:
1. Tech Lead / Architect.
2. Backend Engineer x2.
3. Frontend Engineer x1-2.
4. Edge/Network Engineer x1.
5. DevOps/SRE x1.
6. QA Engineer x1.
7. Product/UX owner x1.

Ownership matrix:
1. Architecture/API: Tech Lead.
2. Backend domain + RBAC + tenant isolation: Backend team.
3. Portal UX + ClaimWizard + Dealer UI: Frontend + Product/UX.
4. Agent/tunnel reliability + auto-discovery: Edge/Network + SRE.
5. Release readiness: SRE + QA + Tech Lead.

---

## 6. Critical Dependencies

1. API contracts frozen → перед активной FE/agent интеграцией.
2. Tenant model frozen → перед dealer UI и claim UX.
3. Connectivity layer stable → перед E2E тестированием HMI.
4. RBAC + data isolation → перед UAT (иначе тесты недостоверны).

---

## 7. Major Risks and Mitigations

1. DNS/резолвинг в РФ: путь `/device/<sn>` как основной режим, мониторинг DNS.
2. DPI/блокировки: WS over 443, fallback transport strategy.
3. Dealer expectations: чёткие контрактные ограничения — dealer не получает доступ к данным.
4. Security drift: security gate в конце каждой фазы.
5. Stripe/международные платежи: рассмотреть российские альтернативы (ЮKassa, CloudPayments).

---

## 8. Принятые решения (ADR-summary)

| # | Решение | Статус |
|---|---------|--------|
| 1 | Клиент платит MYXON напрямую, не дилеру | ✅ Принято |
| 2 | Дилер не имеет доступа к данным клиента по умолчанию | ✅ Принято |
| 3 | Selling chain ≠ Data access chain | ✅ Принято |
| 4 | Клиент активирует устройство самостоятельно (ClaimWizard) | ✅ Принято |
| 5 | Orange Pi = агент с авто-дискавери контроллеров (нет ручного IP) | ✅ Принято |
| 6 | frpc/frps тоннель — основной и единственный путь к контроллеру | ✅ Принято |
| 7 | Stripe Connect для биллинга (Этап 2) | ✅ Принято |

Полный ADR: `MYXON_PLATFORM_ARCHITECTURE.md` §11.

---

## 9. Immediate next actions

1. ~~Kickoff по workstreams~~ → выполнено в текущей сессии.
2. ~~Поднять dev-среду~~ → `./dev.sh` готов.
3. ~~Edge Agent реализован~~ → `edge-agent/myxon_agent.py` с авто-дискавери.
4. **Следующий шаг — Этап 1:** добавить тиры тенантов (dealer, partner, customer) в модели и API.
5. Реализовать dealer-портал (создание клиентов + регистрация устройств).
6. Реализовать ClaimWizard (frontend + backend).
