# IXON API v2 — Анализ для MYXON

Дата: 04 April 2026
Цель: изучить архитектуру IXON APIv2 и выявить решения, которые нужно перенести в MYXON

Источники:
- [IXON Developer Documentation](https://developer.ixon.cloud/)
- [IXON API Prerequisites](https://developer.ixon.cloud/docs/ixon-api-prerequisites)
- [Manage users](https://developer.ixon.cloud/docs/manage-users)
- [Manage groups, users, roles and more](https://developer.ixon.cloud/docs/manage-groups-users-roles-and-more)
- [Manage devices](https://developer.ixon.cloud/docs/manage-devices)
- [Set up a VPN Connection](https://developer.ixon.cloud/docs/set-up-a-vpn-connection)
- [Migration of APIv1 to APIv2](https://developer.ixon.cloud/docs/migration-of-apiv1-to-apiv2)
- [Advanced RBAC article](https://www.ixon.cloud/news/advanced-role-based-access-control)

---

## 1. Общая архитектура API

### Как работает запрос

Каждый запрос к IXON APIv2 содержит **минимум 4 заголовка**:

```http
GET https://portal.ixon.cloud/api/agents
Api-Version: 2
Api-Application: <application_id>       ← ID стороннего приложения
Api-Company: <company_publicId>          ← в контексте какой компании
Authorization: Bearer <secretId>         ← токен пользователя
Content-Type: application/json
```

**Ключевые принципы:**
- `Api-Version: 2` — обязательный хедер версии
- `Api-Application` — каждое интегрирующее приложение имеет свой ID (не пользователь, а приложение). Это позволяет аудитировать "кто дёргал API".
- `Api-Company` — все сущности существуют в контексте компании; большинство запросов требуют этого хедера
- Токены получаются через `POST /api/access-tokens` (AccessTokenList endpoint)

### Паттерн именования эндпоинтов

IXON использует паттерн **List/Single**:
- `GET /api/agents` — список агентов (AgentList)
- `GET /api/agents/{publicId}` — один агент (Agent)
- `POST /api/agents` — создать (AgentList)
- `PATCH /api/agents/{publicId}` — изменить (Agent)
- `DELETE /api/agents/{publicId}` — удалить (Agent)

Pagination через поле `moreAfter` в ответе (курсорная, не offset).

### Универсальный идентификатор: publicId

Во всей системе IXON используется единый тип ID — `publicId`. Контекст определяет тип:
- в ответе с `type: "Company"` → это `companyId`
- в ответе с `type: "Agent"` → это `agentId`
- один и тот же механизм для users, groups, roles, alarms, data sources

---

## 2. Иерархия сущностей IXON

```
Company (верхний уровень изоляции)
├── User (принадлежит Company)
├── Group (контейнер пользователей + устройств)
│   ├── может быть вложенным: Group-of-Groups
│   └── примеры: Business Unit → Distributor → Customer
├── Agent (устройство / роутер)
│   └── AgentMembership (подписка Group → Agent)
├── Role (набор permissions + access categories)
└── AccessCategory (что именно доступно на устройстве)
```

### Агент (Agent) — ключевая сущность

Агент = IXrouter или IXagent (Orange Pi в нашем случае).

Поля агента:
- `publicId` — уникальный ID в системе
- `name` — человекочитаемое имя
- `deviceId` — MAC-адрес или серийный номер физического устройства
- `activeVpnSession` — текущая VPN-сессия (online/offline)
- `customFields` — расширяемые метаданные

**Активация устройства:**
```
POST /api/agents/activate
Body: { "publicId": "xxx", "name": "Machine 001" }
```
После активации — отдельный шаг: импорт конфигурации.

---

## 3. Модель доступа — самое важное для нас

### Три уровня управления доступом

```
User
  └── назначен → Role (что он может ДЕЛАТЬ)
                  ├── Permissions (глобальные: Manage devices, Manage users...)
                  └── Access Categories (что доступно НА КОНКРЕТНОМ устройстве)
                      ├── тип Alarm → видит аларми
                      ├── тип Page → видит страницы HMI
                      └── тип Service → VPN / VNC / HTTP / WebSocket

User
  └── добавлен в → Group (с КАКИМИ устройствами он работает)
                    └── подписана на → Agent(s) через AgentMembership
```

### Роль: Company-Wide vs Device-Specific

```json
// Company-Wide Role (как наш platform_admin / customer_admin)
{
  "permissions": ["COMPANY_WIDE_ROLE", "MANAGE_DEVICES", ...]
}

// Device-Specific Role (как наш customer_engineer)
{
  "permissions": ["VIEW_DATA", ...]  ← нет COMPANY_WIDE_ROLE
  // пользователь видит ТОЛЬКО устройства группы, в которую добавлен
}
```

Если `COMPANY_WIDE_ROLE` отсутствует в permissions → пользователь **обязан быть в группе** для доступа к устройствам.

### Access Category — ключевая концепция которой у нас нет

Access Category определяет **ЧТО именно** пользователь может делать на конкретном устройстве:

```
AccessCategory "Maintenance Engineer":
  - Service: VPN ✓
  - Service: VNC ✓
  - Service: HTTP ✓
  - Page: "Service Dashboard" ✓
  - Alarm: All alarms ✓

AccessCategory "Operator":
  - Service: HTTP ✓ (только HMI через браузер)
  - Page: "Production Dashboard" ✓
  - Alarm: Critical only ✓
  - Service: VPN ✗
  - Service: VNC ✗
```

Это позволяет один Role назначить разным людям, и они получают разный набор доступа к сервисам устройства в зависимости от Access Category своей роли.

### AgentMembership — подписка группы на устройство

Ключевой паттерн: **Group подписывается на Agent**, а не наоборот.

```
AgentMembership:
  group_id → agent_id
  (many-to-many: один агент может быть в нескольких группах)
```

Типы доступа:
1. **Company-wide**: роль с `COMPANY_WIDE_ROLE` → видит ВСЕ устройства компании
2. **Group-based**: роль без `COMPANY_WIDE_ROLE` → видит только устройства в своих группах
3. **Device-specific**: группа создаётся под конкретный агент (1 группа = 1 устройство)

---

## 4. Управление пользователями

### Инвайт (InviteList)

```
POST /api/invites
Body: {
  "data": {
    "email": "engineer@customer.ru",
    "role": { "publicId": "<role_id>" },
    "group": { "publicId": "<group_id>" }  // опционально
  }
}
```

Инвайт содержит:
- email приглашённого
- роль которую он получит
- группу в которую попадёт (опционально)

### Иерархические группы (Business Unit → Distributor → Customer)

```
Group "HOTRACO" (partner-level)
  └── Group "Агровент" (dealer-level)
       └── Group "ООО Бройлер Юг" (customer-level)
            └── Agent: Orange Pi #1
            └── Agent: Orange Pi #2
```

Пользователь с правами верхней группы видит всё дерево вниз. Пользователь в листовой группе — только своих агентов.

---

## 5. VPN-сессия (как они решили проблему доступа к устройству)

IXON использует **отдельный VPN Client API**, который запускается локально на компьютере пользователя:

```
Браузер → REST/WS → VPN Client (daemon, порт 9250) → VPN-туннель → IXrouter → Controller
```

Шаги для открытия сессии:
1. `GET /api/companies` → получить companyId
2. `GET /api/agents` → получить agentId нужного устройства
3. `POST /api/access-tokens` → получить Bearer токен для сессии
4. `POST localhost:9250/connect` (VPN Client API) → открыть туннель с нужным агентом

**MYXON отличается**: у нас frpc-тоннель постоянный (не per-session), и у клиента нет локального VPN-клиента — всё через браузер.

---

## 6. Что нам взять из IXON API v2

### ✅ Нужно взять сейчас (Этап 1)

#### A) Api-Application — токены для третьих сторон

У IXON каждое интегрирующееся приложение имеет свой ID. Это критично для:
- Аудита: "данные взяло приложение X, а не пользователь Y"
- Rate limiting per-application
- Возможности отозвать доступ конкретного приложения без сброса паролей

**Для MYXON:** добавить `Api-Application` хедер + таблицу `ApiApplication` (application_id, secret, owner_tenant_id, scopes).

#### B) Access Category вместо плоских ролей

Текущая модель MYXON: `customer_engineer` может делать всё. Но что если:
- Оператор видит только HMI через HTTP
- Инженер может открыть VNC
- Дежурный видит только аларми

**Для MYXON:** добавить `AccessPolicy` (или `AccessCategory`) как конфигурируемый набор разрешений:
```python
class AccessPolicy:
    allow_hmi: bool = True       # открыть HMI (HTTP/TCP прокси)
    allow_vnc: bool = False      # VNC-доступ
    allow_alarms: bool = True    # просмотр алармов
    allow_audit: bool = False    # просмотр аудит-лога
    alarm_severity_filter: str   # "all" | "critical" | "warning"
```

#### C) AgentMembership вместо UserSiteAccess

Текущая модель MYXON: `user → site`. Но нужно: `group → device`.

Переход к группам даёт:
- Один пользователь в нескольких группах (разные фермы, разные роли)
- Группа "Краснодарский регион" с несколькими площадками
- Dealers в группе верхнего уровня видят статус, не данные

#### D) Pagination через `nextPageToken` / `moreAfter`

Все List-эндпоинты IXON возвращают `moreAfter` для cursor-based пагинации. Нам нужно то же самое — сейчас список устройств вернёт всё сразу, что упадёт на 1000+ устройствах.

#### E) publicId как явное поле (не id)

IXON всегда возвращает `publicId` — это концептуально отделяет публичный идентификатор от внутреннего `id` (PK в БД). Это защита от случайного раскрытия внутренней структуры БД.

**Для MYXON:** сейчас мы возвращаем `id` (UUID из БД). Достаточно, но стоит переименовать в ответах в `publicId` для консистентности.

---

### ✅ Нужно взять в Этапе 2–3

#### F) Access Request (managed support access)

IXON имеет `ManageAccessRequest` — механизм временного доступа. Пользователь запрашивает доступ к устройству → владелец одобряет → access grant с TTL.

Это именно наш Этап 3: "Dealer запрашивает временный доступ к устройству клиента".

#### G) Hierarchical Groups для dealer-chain

Вместо flat `dealer_id` / `partner_id` на устройстве:
```
Group "HOTRACO" → contains Group "Агровент" → contains Group "ООО Птица"
                                                              → Agent #1, Agent #2
```

Это более гибко: дилер видит всё дерево вниз через иерархию групп.

---

## 7. Что IXON делает иначе — и почему мы правы

| Аспект | IXON | MYXON | Почему MYXON правильнее |
|--------|------|-------|------------------------|
| Подключение к устройству | VPN Client на PC пользователя | frpc-тоннель, браузерный бридж | Клиенту не нужно ставить ПО |
| Агент | IXrouter (hardware) | Orange Pi с Debian (open hardware) | Дешевле, гибче, доступно в РФ |
| Биллинг | Direct to IXON | Direct to MYXON, settlement to dealer | Клиент защищён от недобросовестного дилера |
| Авто-дискавери контроллеров | Ручная настройка IP | Автосканирование LAN | Проще для монтажника |
| Язык | Английский | Русский локализация | РФ-рынок |

---

## 8. Изменения в API MYXON по итогам анализа

### Немедленно (до production):

```
ДОБАВИТЬ:
POST   /api/v0/applications          — регистрация API-приложения (third-party integration)
GET    /api/v0/applications          — список приложений тенанта
DELETE /api/v0/applications/{id}     — отозвать доступ приложения

ПЕРЕРАБОТАТЬ:
GET /api/v0/devices → добавить cursor pagination (nextPageToken)
GET /api/v0/alarms  → добавить cursor pagination

ДОБАВИТЬ к ответам:
publicId (alias для id в JSON-ответах)
moreAfter / nextPageToken поле в List-ответах

В ХЕДЕРЫ:
X-Api-Version: 0 (наша версия, для будущей миграции)
X-Api-Application: <app_id> (для third-party интеграций)
```

### В Этапе 2 (группы и access policy):

```
POST /api/v0/groups                  — создать группу
POST /api/v0/groups/{id}/devices     — добавить устройство в группу (AgentMembership аналог)
POST /api/v0/groups/{id}/users       — добавить пользователя в группу

POST /api/v0/access-policies         — создать политику доступа к устройству
GET  /api/v0/access-policies         — список политик

# Заменяет плоский UserSiteAccess
```

---

## 9. Сводная таблица сущностей IXON → MYXON

| IXON сущность | MYXON аналог | Статус |
|---------------|--------------|--------|
| Company | Tenant (tier=customer) | ✅ Реализовано |
| Agent | Device | ✅ Реализовано |
| AgentMembership | UserSiteAccess (упрощённо) | ⚠️ Нужно расширить до групп |
| Group | — | ❌ Нет, нужно добавить |
| Role | User.role (плоский enum) | ⚠️ Нужно добавить AccessPolicy |
| AccessCategory | — | ❌ Нет, нужно добавить |
| Invite | Invite | ✅ Реализовано |
| AccessToken (Bearer) | JWT | ✅ Реализовано |
| ApiApplication | — | ❌ Нет (нужно для third-party) |
| VpnSession | AccessSession + WS бридж | ✅ Реализовано (через frpc) |
| ActiveVpnSession | Device.status (online/offline) | ✅ Реализовано |
| DataSource | — | 🔮 Этап 4 (telemetry) |
| AlarmList | Alarm | ✅ Реализовано |
| publicId | id (UUID) | ⚠️ Переименовать в ответах |

---

## 10. Архитектура хранения данных — гибридная БД

IXON использует **две базы данных одновременно**:

| Компонент | Тип | Что хранит | Зачем |
|-----------|-----|------------|-------|
| **MariaDB** (реляционная) | SQL | Имена, publicId, права доступа, конфигурации, связи "агент → датчик → пользователь" | Структура: "Станок №5 имеет датчик температуры, принадлежит группе X" |
| **InfluxDB** (time-series) | NoSQL | Сами измерения: "14:05:32 → температура 22.5°C" | Скорость: записывать миллионы точек в SQL-базу невозможно |

### Паттерн разделения:
- **SQL** → всё что структурировано: пользователи, устройства, политики, аларми (metadata)
- **InfluxDB** → временные ряды: показания датчиков, метрики, логи телеметрии

### Для MYXON:

Текущий статус: у нас только PostgreSQL. Это правильно для Этапа 1 (нет телеметрии).

Когда понадобится:
- Этап 4: DataSource / телеметрия (показания датчиков с контроллеров)
- Хранить в PostgreSQL временные ряды с интервалом <1 сек → не масштабируется

Варианты для Этапа 4:
1. **InfluxDB** — то же что IXON (open-source, python-influxdb-client)
2. **TimescaleDB** — расширение PostgreSQL (проще если уже на Postgres стеке)
3. **Clickhouse** — column-store, подходит для агрегаций по большим объёмам

**Рекомендация:** TimescaleDB (добавляется как PostgreSQL extension, не меняет стек).

---

## 11. Верифицированные архитектурные находки (апрель 2026)

Ниже — результаты проверки конкретных технических утверждений по официальным источникам IXON.

### 1. VPN Client API — localhost:9250 ✅ ПОДТВЕРЖДЕНО

**Точные данные:**
- VPN Client запускается как фоновый daemon (Linux/macOS) или Windows Service
- Поднимает локальный HTTPS-сервер строго на **порту 9250**
- Интерфейс доступен по `https://localhost:9250`

**Задокументированные эндпоинты:**

| Endpoint | Метод | Назначение |
|----------|-------|------------|
| `/connect` | POST | Поднять VPN-туннель |
| `/disconnect` | POST | Закрыть туннель |
| `/status` | GET | Текущий статус соединения |
| `/configuration` | GET | Конфигурация клиента |
| `/configuration` | POST | Сброс конфигурации |
| `wss://localhost:9250/` | WebSocket | Стриминг статуса в реальном времени |

**Для MYXON:** Наш `ws_remote.py` — аналог этого паттерна, только серверный (WebSocket-мост через frps). Если появится десктопный клиент, применяем ту же схему: daemon + `localhost:PORT` + REST + WS.

---

### 2. App Engine: UI Components + Cloud Functions ⚠️ ЧАСТИЧНО ПОДТВЕРЖДЕНО

**UI Components:**
- Фреймворки: **Vue.js** и **Svelte** (+ plain custom elements / vanilla JS)
- ❌ **React не поддерживается** — исходное утверждение неточное
- Файлы: `.js`, `.vue`, `.svelte` + `manifest.json` (width, height, target constraints)

**Cloud Functions:**
- Язык: **Python** ✅ — подтверждено
- Runtime: пакет `ixoncdkingress` предоставляет Context object
- Ingress обрабатывает коммуникацию между функцией и облаком

**Для MYXON:** App Engine — это "встроенный Zapier". Нам аналог не нужен в Этапе 1-2, но для Этапа 3 (интеграции с Telegram, 1С, ветеринарными системами) это правильный паттерн: Python cloud functions + event triggers.

---

### 3. Безопасность: сертификаты + шифрование ✅ ПОЛНОСТЬЮ ПОДТВЕРЖДЕНО

**Точные данные из Security Guide:**
- VPN: **single-use (одноразовые) сертификаты** ✅
- Шифрование туннеля: **AES-256-CBC + SHA512** ✅ (не просто AES-256)
- Мастер-ключи и CA хранятся в защищённом облаке, не на устройстве ✅

**Для MYXON:** Наш frps использует `token`-аутентификацию (статичный токен в конфиге агента). Это слабее, чем одноразовые сертификаты IXON. **В Этапе 2** нужно перейти на: агент получает временный токен через API при регистрации → frps проверяет его через webhook → токен инвалидируется после первого использования.

---

### 4. ISO 27001 ✅ ПОДТВЕРЖДЕНО (и сверх того)

IXON имеет **пять** сертификаций:
- **ISO 27001** — информационная безопасность
- **ISO 27017** — облачная безопасность
- **ISO 27701** — защита персональных данных (GDPR)
- **ISO 9001** — управление качеством
- **IEC 62443** — промышленная кибербезопасность (OT/ICS)
- Соответствие **NIS2** (Европейская директива по кибербезопасности)

Аудитор: DigiTrust (RvA accredited, Нидерланды).

**Для MYXON:** Долгосрочная цель — ISO 27001 для выхода на европейские рынки. IEC 62443 критичен для агропрома. Начинаем с документирования процессов уже сейчас.

---

### 5. IXrouter3 Local API ✅ ПОДТВЕРЖДЕНО

**Точные данные:**
- Протокол: **JSON-RPC 2.0** через HTTP POST на эндпоинт `/ubus`
- LAN IP по умолчанию: `192.168.140.1`
- Требует: firmware 3.19+
- Аутентификация: session ID (получается отдельным вызовом)

**Возможности через API:**
- Получить состояние роутера
- Чтение/запись конфигурации сети (WAN, LAN)
- **Перезагрузка** (reboot) — только с valid session
- Управление паролями

Также доступен **локальный веб-интерфейс** (Network → WAN/LAN).

**Для MYXON:** Наш Orange Pi + Debian не имеет аналогичного local API. В Этапе 2: добавить эндпоинт на агент для локального управления (network config, reboot, статус frpc-туннеля) — доступный по LAN без облака.

---

### 6. SecureEdge Pro: Docker на Edge ✅ ПОДТВЕРЖДЕНО

**Точные данные:**
- Продукт: **SecureEdge Pro** (не базовый IXrouter)
- Позиционирование: "2-in-1" — VPN-роутер + промышленный мини-ПК
- Полноценный Docker runtime на устройстве
- Маркетплейс: **40+ готовых приложений** (Grafana, TensorFlow, Snort IDS…)
- Sandbox isolation между контейнерами

**Use cases:**
- Real-time мониторинг процессов
- Edge ML/AI (TensorFlow)
- Локальная аналитика без облака
- Grafana dashboard прямо на объекте

**Для MYXON:** Orange Pi 5 (8 ядер ARM, 8–16 GB RAM) технически способен запускать Docker. В Этапе 3: предоставлять клиентам возможность деплоить кастомные контейнеры на их Edge-устройствах (Grafana локально, кастомные скрипты обработки данных). Это сильный differentiator.

---

### Сводная таблица верификации

| Утверждение | Статус | Уточнение |
|-------------|--------|-----------|
| VPN Client daemon на порту 9250 | ✅ | Точно, HTTPS, REST + WebSocket |
| App Engine: React + Svelte + Python | ⚠️ | Vue.js + Svelte (не React!) + Python ✅ |
| Одноразовые сертификаты + AES-256 | ✅ | AES-256-CBC + SHA512 |
| ISO 27001 | ✅ | + ISO 27017/27701, ISO 9001, IEC 62443 |
| IXrouter3 Local API (reboot, network) | ✅ | JSON-RPC 2.0 на /ubus, fw 3.19+ |
| Docker на Edge (SecureEdge) | ✅ | SecureEdge Pro, маркетплейс 40+ apps |

---

## 12. Приоритизированные доработки по итогам анализа

### P0 — Прямо сейчас:
- [x] AccessPolicy (Access Category) — ✅ реализовано в эту сессию

### P1 — Этап 1 (до первого клиента):
- [ ] Pagination (`nextPageToken`) в List-эндпоинтах
- [ ] `X-Api-Version` хедер во всех ответах

### P2 — Этап 2 (масштаб > 10 клиентов):
- [ ] Groups: заменить плоский UserSiteAccess на Group + GroupMembership
- [ ] AccessPolicy: конфигурируемый набор сервисов (HMI, VNC, алармы)
- [ ] ApiApplication: token для third-party интеграций

### P3 — Этап 3 (mature platform):
- [ ] AccessRequest: managed support access с TTL и аудитом
- [ ] Hierarchical Groups: dealer-chain через иерархию групп
- [ ] `publicId` vs `id` разделение в ответах API
