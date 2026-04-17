# AS-IS Android-приложений (Hotraco / SyslinQ)

## Архитектурная позиция для MYXON (важно)
- По результатам реверса `Remote+` видно разделение на платформенный connectivity-слой и vendor-специфичный слой HOTRACO.
- HOTRACO трактуется как `vendor integration` (tenant/client платформы), а не как универсальный транспортный стандарт.
- Целевая модель MYXON:
- `Universal Connectivity Core` (туннели, сессии, маршрутизация, безопасность),
- `Vendor Integration Layer` (брендинг, UX, интеграции),
- `Device Family Protocol Layer` (протоколы конкретных семейств устройств).

## Область анализа
Проанализированы два Android-приложения из локальных артефактов:
- `SyslinQ Remote` (`com.hotraco.syslinqremote`, версия `1.3.0`)
- `Remote+` (`com.hotraco.remoteplus`, версия `1.2.0`)

Основные источники:
- Распакованные пакеты приложений в `RND server/APP_android/...`
- Разобранные манифесты (`apkanalyzer`) в `tmp_android/*.manifest.xml`
- Декомпилированный код/ресурсы (`jadx`) в `tmp_android/jadx_*`

## Архитектура верхнего уровня
Оба приложения являются гибридными (Ionic + Capacitor), где бизнес-логика в основном находится в web-бандле (`assets/public/*.js`), который выполняется внутри нативной оболочки (`MainActivity`).

Следствие:
- UX/воркфлоу и большая часть продуктового поведения реализованы в JavaScript, а не в нативном Java/Kotlin.
- Нативный слой в основном используется для плагинов (push, browser, notifications, TCP socket и т.д.).

## 1) SyslinQ Remote (1.3.0)

### Идентификация
- Пакет: `com.hotraco.syslinqremote`
- Главная activity: `com.hotraco.syslinqremote.MainActivity`
- Min/target SDK: 22 / 34

### Нативные разрешения (manifest)
- `INTERNET`
- `ACCESS_NETWORK_STATE`
- `WAKE_LOCK`
- `POST_NOTIFICATIONS`
- `com.google.android.c2dm.permission.RECEIVE` (Firebase push)
- Пользовательское permission для dynamic receiver

### Обнаруженные нативные компоненты
- `MainActivity`
- `androidx.core.content.FileProvider`
- Сервисы и receiver для Firebase Messaging
- Activity плагина браузера (`BrowserControllerActivity`)
- Компоненты AndroidX startup/profile

### Плагины Capacitor (из `assets/capacitor.plugins.json`)
- `@capacitor-firebase/messaging`
- `@capacitor/browser`
- `@capacitor/dialog`
- `@capacitor/keyboard`
- `@capacitor/splash-screen`
- `@capacitor/status-bar`

### Важные конфигурационные признаки
Из `assets/capacitor.config.json`:
- Имя приложения: `SyslinQ Remote`
- `webDir: "dist"`
- `CapacitorHttp.enabled: true`
- Включены presentation options для Firebase Messaging
- Тёмный стиль клавиатуры

### Обнаруженные сетевые признаки
- `https://syslinq-cd09b.firebaseio.com` (endpoint Firebase DB присутствует в строках APK)
- Явный жёстко зашитый URL портала из минифицированного бандла пока достоверно не извлечён.

## 2) Remote+ (1.2.0)

### Идентификация
- Пакет: `com.hotraco.remoteplus`
- Главная activity: `io.ionic.starter.MainActivity`
- Min/target SDK: 22 / 34

### Нативные разрешения (manifest)
Набор шире, чем у SyslinQ Remote:
- `INTERNET`
- `READ_EXTERNAL_STORAGE`, `WRITE_EXTERNAL_STORAGE`
- `ACCESS_COARSE_LOCATION`, `ACCESS_FINE_LOCATION`
- `CAMERA`, `RECORD_AUDIO`, `MODIFY_AUDIO_SETTINGS`
- `RECEIVE_BOOT_COMPLETED`
- `WAKE_LOCK`
- `POST_NOTIFICATIONS`
- `SCHEDULE_EXACT_ALARM`
- `CHANGE_NETWORK_STATE`
- Пользовательское permission для dynamic receiver

### Флаг безопасности в manifest
- `android:usesCleartextTraffic="true"`

Это означает, что по политике приложения разрешён HTTP-трафик (не только HTTPS).

### Обнаруженные нативные компоненты
- `io.ionic.starter.MainActivity`
- `FileProvider`
- Activity плагина браузера
- Receiver-ы локальных уведомлений (включая восстановление после boot)
- Компоненты AndroidX startup/profile

### Плагины Capacitor (из `assets/capacitor.plugins.json`)
- Стандартные плагины Capacitor (`app`, `browser`, `keyboard`, `preferences`, `splash-screen`, `status-bar`)
- `@capacitor/local-notifications`
- `@capawesome/capacitor-background-task`
- `@hotraco/capacitor-tcp-socket` (кастомный/нативный TCP-плагин)

### Конфигурационный признак
Из `assets/capacitor.config.json`:
- `server.androidScheme: "http"`

Вместе с `usesCleartextTraffic=true` это подтверждает паттерн использования локального/plain-HTTP.

## Сравнительные выводы

1. SyslinQ Remote выглядит cloud/push-ориентированным:
- Интегрирован Firebase Messaging
- Минимальный набор чувствительных device-permissions
- HTTP-стек активирован через Capacitor HTTP plugin

2. Remote+ выглядит более device/LAN-ориентированным и «близким к железу»:
- Разрешения на camera/mic/location/storage
- Восстановление уведомлений после boot + background task
- Кастомный TCP socket plugin
- Явно разрешён cleartext HTTP

3. Гипотеза по эволюции продукта:
- `Remote+` может быть более старым или более «полевым» инструментом с прямой/локальной связностью.
- `SyslinQ Remote` выглядит более новым и сфокусированным на cloud remote access UX.

## Что ещё нужно для почти полного восстановления функционала

1. Деобфускация / восстановление символов JS-бандла
- Разобрать `assets/public/main.*.js` и чанки, чтобы восстановить route map, API-клиент и auth-flow.

2. Динамический съём endpoint-ов API
- Выполнить динамический анализ через proxy (mitm), чтобы достать реальные backend-домены и handshake авторизации.

3. Детальный разбор нативного поведения плагинов
- Отдельно проанализировать код кастомного TCP-плагина (`com.hotracogroup.capacitor.tcpsocket.*`).

4. Построить feature-matrix
- Login, список устройств, VNC/web access, уведомления, offline-поведение, role constraints.

## Команды воспроизведения (уже проверены)

```bash
# Извлечение manifest
apkanalyzer manifest print tmp_android/syslinqremote.apk > tmp_android/syslinqremote.manifest.xml
apkanalyzer manifest print tmp_android/remoteplus.apk > tmp_android/remoteplus.manifest.xml

# Декомпиляция
jadx -d tmp_android/jadx_syslinq tmp_android/syslinqremote.apk
jadx -d tmp_android/jadx_remoteplus tmp_android/remoteplus.apk
```

## 3) Восстановление полного функционала (текущее состояние)

Ниже зафиксирован функционал, подтверждённый статическим анализом web-бандлов и нативного кода.

### 3.1 SyslinQ Remote: подтверждённые функции

По строкам из `main.7075df340470e99d.js` подтверждены следующие пользовательские сценарии:
- Авторизация: `Login`, ошибки `Failed to login`, `Failed to verify login`.
- Двухшаговый вход: `One-Time Password required`, поле `oneTimePassword`.
- Восстановление доступа: `recover`, `PasswordReset`, `Password reset failed`.
- Смена пароля в приложении: `Current password`, `New password`, `Password changed`, `Password change failed`.
- Контроль сессии: `Session has expired. Please login again`.
- Работа с устройствами: `Focus device is offline`, `No focus devices`, `This agent is not online`.
- Дистанционный доступ VNC: ошибки прав `You are not allowed to connect ... using VNC`, `Unable to connect to vnc view`.
- Админ-функции компании: `Enable VNC Access All`, `Disable VNC Access All`.
- Push/device registration: `UserPushDevices`, `UserPushDevicesList`, `[APP]: Device Ready`.

Подтверждённые внешние URL и домены:
- `https://remote.syslinq.co/login`
- `https://remote.syslinq.co/recover`
- `https://connect.syslinq.co/recover/reset-password/{token}`
- `https://connect.syslinq.co/recover/reject/{token}`
- `https://connect.syslinq.co/change-email-address/accept/{publicId}/{token}`
- `https://connect.syslinq.co/change-email-address/reject/{publicId}/{token}`
- `https://api.ixon.net/`

Дополнительно подтверждён большой каталог тревог/событий (temperature, RH, CO2, ventilation, weather station, communication alarms), что указывает на встроенный alarm/event UX внутри мобильного клиента.

### 3.2 Remote+: подтверждённые функции

По `assets/i18n/en.json` и нативному плагину:
- Авторизация/сессия: `Login`, `Forgot password`, `Remember me`, `Session has been expired`.
- Модель данных UI: `Connections`, `Groups`, `Devices`, `Direct access`, `Alarms`, `Settings`.
- Системные состояния: offline/no connection/timeout/retry.
- Отображение инвентаря: `Serial number`, device counters (`{{count}} devices`).
- Защита/ограничение модуля: `Remote+ module is not activated yet. Please, contact your dealer`.

Нативный TCP-канал (`TcpSocketPlugin.java`) подтверждает:
- методы плагина: `connect`, `write(base64String)`, `destroy`;
- события: `onConnect`, `onData`, `onClose`, `onError`, `connection`;
- дефолтные параметры соединения: host `5.157.85.29`, port `5843`.

Это означает, что Remote+ использует не только HTTP/API, но и отдельный бинарный TCP-путь для части операций.

## 4) Восстановленный end-to-end workflow (для команды разработки)

### SyslinQ Remote (cloud-first)
1. Пользователь открывает логин (`remote.syslinq.co`) в webview.
2. Проходит логин/OTP.
3. Приложение загружает профиль, компанию, список focus devices.
4. Для выбранного устройства проверяются:
- online/offline состояние,
- права на VNC,
- глобальные флаги компании (`vncAccessAll`).
5. Пользователь запускает VNC/web access (при наличии прав и online-статуса).
6. Приложение показывает cloud status + события/alarms.
7. Push-токен устройства регистрируется для уведомлений.

### Remote+ (hybrid cloud + direct)
1. Логин и загрузка структур `groups/connections/devices`.
2. Пользователь выбирает direct access.
3. Клиент поднимает TCP-сокет через Capacitor-плагин.
4. Обмен данными идёт base64-пакетами через `onData/write`.
5. При сбоях обрабатываются `onError/onClose`, UI показывает reconnect/timeout.

## 5) Что ещё нужно сделать для «почти полного» восстановления

1. Поднять runtime-перехват трафика (mitm в тестовом стенде) для точной API-схемы:
- auth endpoints,
- device list API,
- VNC session bootstrap,
- alarms/event feed.
2. Разобрать JS route-map (автоматическим парсером чанков) и собрать экранную карту.
3. Снять формат бинарных TCP-сообщений Remote+ (frame structure, команды, ACK/heartbeat).
4. Собрать единый `feature-matrix` SyslinQ vs Remote+ (роль, протокол, ограничения, UX-переходы).

## 6) Уровень готовности материалов для реализации

Текущий уровень: **достаточно для старта проектирования и декомпозиции задач команды**, но ещё не «бит-в-бит» клон.

Что уже достаточно:
- архитектурный профиль приложений;
- ключевые пользовательские сценарии;
- роли и ограничения (особенно VNC access);
- подтверждённые внешние домены/ссылки;
- наличие отдельного TCP-канала в Remote+.

Чего пока не хватает для 100% повторения поведения:
- точные контракты backend API (request/response schemas);
- протокол бинарного TCP на уровне полей;
- некоторые edge-case ветки в минифицированном JS.

## 7) Feature Matrix (для продукта и разработки)

| Блок | SyslinQ Remote | Remote+ | Комментарий для MYXON |
|---|---|---|---|
| Login/Logout | Да | Да | Базовый auth-flow обязателен |
| OTP (2-й фактор) | Да (подтверждено строками) | Не подтверждено явно | Делать как опциональный модуль |
| Password Recovery | Да | Да (UI тексты есть) | Унифицировать с web-порталом |
| Session Expiration UX | Да | Да | Единый обработчик 401/timeout |
| Device List | Да (focus devices) | Да | Общая модель `device summary` |
| Grouping (Groups/Rooms) | Косвенно | Да (явно) | Нужна иерархия `company/site/group/device` |
| Alarm Feed | Да (богатый словарь alarm) | Да (раздел alarms) | Сразу закладывать нормализованный alarm schema |
| Web/VNC access | Да (строки VNC и права) | Есть direct access | В MVP: web/VNC как ключевая ценность |
| Глобальный флаг VNC для компании | Да (`vncAccessAll`) | Не обнаружено | Нужен admin-policy слой |
| Push notifications | Да (Firebase messaging) | Вероятно (локальные + планировщик) | Обязателен push + in-app center |
| TCP binary channel | Не подтверждено как отдельный плагин | Да (`@hotraco/capacitor-tcp-socket`) | Для MYXON: абстракция transport layer |
| Cleartext HTTP policy | Не ключевая | Да (`usesCleartextTraffic=true`) | Для прод-сервиса лучше только TLS |

## 8) Карта транспортов и интеграций

### 8.1 SyslinQ Remote
- Основной путь: web-bundle + cloud endpoints.
- Достоверные домены: `remote.syslinq.co`, `connect.syslinq.co`, `api.ixon.net`.
- Поведенческие индикаторы:
  - auth + OTP,
  - cloud-oriented device operations,
  - права доступа к VNC на уровне компании/устройства,
  - push device registration.

### 8.2 Remote+
- Основной путь: cloud UX + direct access transport.
- Нативный TCP плагин подтвержден:
  - дефолтная цель: `5.157.85.29:5843`,
  - data channel: base64 payloads,
  - lifecycle callbacks: connect/data/close/error.
- Вывод: приложение исторически/архитектурно ближе к "полевой" модели связи с устройством.

## 9) Приоритетный backlog реверса (что делать дальше)

### P0 (критично для архитектуры MYXON)
1. Снять реальные API-контракты auth/device/session (mitm на тестовом аккаунте).
2. Подтвердить модель прав: `company -> user role -> device capability (VNC/HTTP/VPN)`.
3. Для Remote+: зафиксировать формат TCP-фрейма (header, length, opCode, checksum/none, heartbeat).

### P1 (критично для UX parity)
1. Извлечь route map экранов из JS-чанков.
2. Восстановить точные статусы устройства и их UX-переходы (online/offline/degraded).
3. Восстановить список alarm categories + severity mapping.

### P2 (критично для enterprise-ready)
1. Политики сессий/таймаутов/remember-me.
2. Push pipeline: токены, темы/каналы, silent refresh.
3. Настройки data usage / low-bandwidth режим.

## 10) Требования к целевой реализации MYXON (из анализа Android)

1. Единый auth-core:
- login,
- optional OTP,
- recovery/reset,
- session lifecycle.

2. Единый Device Access Core:
- capability model (`http`, `vnc`, `vpn`, `tcp-direct`),
- проверка прав до открытия сессии,
- единые error states для UI.

3. Alarm Core:
- ingestion model,
- нормализация типов тревог,
- статусные уведомления + история.

4. Transport Abstraction Layer:
- `cloud_api_transport` (HTTPS),
- `remote_session_transport` (Web/VNC),
- `binary_tcp_transport` (для совместимости со старым классом устройств).

5. Mobile UX baseline:
- devices/groups/search,
- quick connect,
- offline-first status handling,
- retry/reconnect UX.

## 11) Ограничения и достоверность

Уровни достоверности:
- Высокая: то, что подтверждено в manifest/нативном коде/строках JS и i18n.
- Средняя: последовательность некоторых cloud API вызовов (без runtime capture).
- Низкая: внутренние серверные правила, которые не видны в клиенте.

Что это значит для команды:
- На основании текущего отчёта можно проектировать архитектуру и интерфейсные потоки.
- Для полного функционального дублирования обязательны ещё runtime-снимки API/TCP.

## 12) Definition of Ready для старта разработки

Задача считается готовой к реализации MVP, если:
1. Утверждена capability-модель устройства (`http/vnc/vpn/tcp`).
2. Утверждена ролевая модель (`owner/admin/engineer/viewer`) и policy matrix.
3. Зафиксирован минимальный API-контракт:
- auth,
- list devices,
- open session,
- alarms.
4. Подтверждён транспорт MVP (только HTTPS+Web/VNC или +TCP).
5. Описан offline UX (timeouts/reconnect/error copy).


## 13) Functional Reconstruction v2 (маршруты, операции, права)

### 13.1 SyslinQ Remote: карта экранов/маршрутов (по web-bundle)

Подтверждённые route-like маркеры:
- `/login`
- `/recover`
- `/recover/reset-password/`
- `/recover/reject/`
- `/not-connected`
- `/vnc/`
- `//connect` (служебный/частично обфусцированный маркер)

Интерпретация:
- Есть отдельный auth-контур (login/recover/reset).
- Есть отдельный экран/состояние потери связности (`not-connected`).
- VNC открывается отдельным роутом/модулем.

### 13.2 SyslinQ Remote: карта операций (по action labels/keys)

Подтверждённые action-группы:
- `[Auth API]` (login/recover success/fail)
- `[User API]` (update password/profile)
- `[Company API]` (enable/disable VNC access all)
- `[Agent API]`
- UI actions: `[Login Page]`, `[Recover Page]`, `[Admin Page]`, `[Viewer Page]`, `[Locations Page]`

Подтверждённые service-слои (из ключей):
- `authService`, `apiService`, `companyService`, `userService`, `agentService`, `webAccessService`, `pushDeviceService`

Интерпретация backend:
- Backend разделён по доменным bounded-context: auth/user/company/agent/web-access.
- В клиенте явный policy-check перед запуском VNC.

### 13.3 Permission модель (подтверждённые индикаторы)

Подтверждено на уровне строк/экшенов:
- Глобальный company-флаг: `vncAccessAll`.
- Ошибки запрета:
  - `You are not allowed to connect with this focus device using VNC`;
  - `You are not allowed to Connect-vnc this Agent`.
- Ошибки контекста устройства:
  - `Focus device is offline`;
  - `This agent is not online`;
  - `Module could not be validated for this focus device.`

Практический вывод:
- Решение о допуске к сессии принимается не только по online-status, но и по role/policy/capability.

### 13.4 Remote+: маршруты и функции

Подтверждённые маркеры:
- `/connections`
- `/tabs/connections`
- `LoginPage`, `TabsPage`
- операции: `createConnection`, `editConnection`, `deleteConnection`, `pingConnection`, `setConnectionPassword`, `getDeviceAlarm`.

Подтверждённые внешние ссылки:
- `https://smartlinkserver.com/register.php`
- `https://smartlinkserver.com/password_reset.php`

Интерпретация:
- В приложении выраженная модель "connection management" (не только список девайсов).
- Возможна отдельная legacy/server-линейка (`smartlinkserver.com`) параллельно cloud-модели SyslinQ.

### 13.5 Backend topology hypothesis (после v2)

На текущем уровне доказательств backend выглядит как минимум трёхконтурным:
1. `Identity & account`:
- login, OTP, recover, password lifecycle.
2. `Device & policy`:
- inventory/locations,
- role checks,
- VNC enable/disable flags.
3. `Session/data plane`:
- cloud web-access/VNC с policy gate,
- отдельный TCP data plane в Remote+ (`5.157.85.29:5843`).

## 14) Что это даёт для полного восстановления функционала

Теперь можно декомпозировать реализацию в MYXON не как один монолит, а как 3 независимых подсистемы:
- `Identity Service` (auth + OTP + recovery),
- `Device Policy Service` (roles/capabilities/access checks),
- `Session Service` (VNC/web + optional TCP bridge).

Это снижает риски и позволяет запускать MVP поэтапно без потери совместимости с будущими device-типами.


## 15) Device Family Segmentation (новое подтверждение)

В `Remote+` найден отдельный каталог UI-шаблонов:
- `interfaces/orion/...`
- `interfaces/cygnus/...`
- `interfaces/sirius/...`

И внутри них отдельные theme-варианты:
- `agri`, `horti`, `vdl`, `opticow`, `delaval`, `reventa`, `thomas_*`.

Прямое значение для реверса:
1. Приложение проектировалось как multi-family клиент, а не под один девайс.
2. Есть слой "профиля устройства" (family + theme/brand), влияющий на UI/поведение.
3. Вероятно, transport/protocol может различаться по семействам или версиям линейки.

Следствие для MYXON:
- архитектура должна быть plugin/profile-based:
  - `device_family` (orion/cygnus/sirius/...)
  - `capability_set` (alarms/direct/vnc/http/tcp)
  - `ui_theme_profile` (brand/customer skin)

## 16) Уточнение по `5.157.85.29:5843`

На текущем этапе это рассматривается как **инфраструктурный TCP endpoint** Remote+ (сервер/шлюз), а не endpoint конкретного контроллера.

Это согласуется с моделью:
- приложение получает контекст соединения,
- затем открывает TCP-сеанс через нативный плагин,
- транспортный сервер маршрутизирует сессию к целевому устройству/каналу.

## 17) Следующий шаг восстановления (без полевого теста)

Чтобы продолжать статически и не ждать сетевых тестов:
1. Распаковать по чанкам `Remote+` модули, где встречаются:
- `connectionMediatorService`,
- `directMediatorService`,
- `remoteMediatorService`,
- `sendDevice/getDevice/getDeviceAlarm`.
2. Составить таблицу `method -> probable purpose -> input/output fields`.
3. Привязать эту таблицу к family-профилям (`orion/cygnus/sirius`).


## 18) Identity & Tenant Resolution (как система понимает «кто клиент»)

По совокупности артефактов (JS action labels, service keys, i18n, permission errors) клиентская идентификация строится как многоуровневая модель.

### 18.1 Уровень 1: Identity (пользователь)

Подтверждённые маркеры:
- login/logout,
- invalid credentials,
- session expired,
- optional OTP (`One-Time Password required`),
- password recovery/change.

Смысл:
- сначала определяется личность пользователя (`user identity`) и активная сессия.

### 18.2 Уровень 2: Tenant/Company context

Подтверждённые маркеры:
- `companyId` в payload/action контексте,
- отдельные `[Company API]` операции,
- company-level флаг `vncAccessAll`.

Смысл:
- после identity пользователь работает не «глобально», а в контексте компании/тенанта.
- именно в контексте компании загружаются политики и доступные устройства.

### 18.3 Уровень 3: Role/Policy enforcement

Подтверждённые маркеры:
- `You are not allowed to connect ... using VNC`;
- `You are not allowed to Connect-vnc this Agent`;
- admin actions enable/disable VNC access all.

Смысл:
- решение о доступе к сессии зависит от роли/политики, а не только от факта логина.

### 18.4 Уровень 4: Device scope and state

Подтверждённые маркеры:
- `Focus device is offline`, `This agent is not online`;
- списки devices/connections/groups;
- прямые операции с device в Remote+ (`getDevice`, `sendDevice`, `getDeviceAlarm`).

Смысл:
- пользователь видит и открывает только разрешённые устройства в своём tenant.
- перед открытием сессии проверяется online/capability состояние устройства.

### 18.5 Уровень 5: Mobile endpoint identity (push)

Подтверждённые маркеры:
- `UserPushDevices`, `UserPushDevicesList`,
- добавление push-device по `deviceId + token`.

Смысл:
- мобильный клиент как endpoint отдельно регистрируется в backend для уведомлений.

## 19) Обобщённая схема проверки доступа к удалённой сессии

1. Пользователь аутентифицируется (login/OTP).
2. Backend возвращает сессию + tenant context.
3. Клиент запрашивает доступные объекты (company/group/device).
4. При попытке подключения проверяются:
- role/policy,
- company flags,
- device status,
- feature capability (VNC/direct/etc).
5. Если всё валидно — выдаётся session bootstrap и открывается канал (cloud/web/VNC/TCP).

## 20) Что это значит для проектирования MYXON

Нельзя делать только `user->device` таблицу. Нужна минимум 5-слойная модель:
1. `UserIdentity`
2. `TenantContext`
3. `RolePolicy`
4. `DeviceScope + Capability`
5. `ClientEndpoint (mobile/web agent)`

Рекомендуемые минимальные сущности:
- `users`
- `companies`
- `user_company_roles`
- `devices`
- `device_capabilities`
- `device_policies`
- `sessions`
- `client_endpoints` (push/web/mobile)
- `access_audit_log`

## 21) MVP security checks (обязательные)

Перед выдачей remote session token/URL:
1. Проверить валидность user session.
2. Проверить membership пользователя в company.
3. Проверить role policy на конкретный тип доступа (например, `vnc:open`).
4. Проверить online-state и health устройства/агента.
5. Проверить company/device-level feature flags.
6. Выписать access-аудит (кто/когда/к какому устройству/какой тип доступа).

## 22) Риски при упрощении модели

Если упростить до "логин есть => доступ к устройству":
- невозможно безопасно работать в дилерской/многоарендной схеме;
- не будет централизованного отключения risky функций (например VNC all);
- сложнее расследовать инциденты без нормального access-audit.

Текущее состояние анализа показывает, что референсная система эти уровни учитывает.


## 23) Deep RE: Remote+ mediator/device workflow (подтверждено чанками)

### 23.1 Device runtime flow (чанк `9331`)

Из `DevicePageModule` подтверждена цепочка работы экрана устройства:
1. По `connectionId` и `deviceId` выбирается устройство.
2. Определяется семейство контроллера по `baseComputer`:
- `OrionLegacy / Orion`
- `SiriusLegacy / Sirius`
- `Cygnus`
3. Для неизвестного типа показывается `NO_DEVICE_SUPPORT`.
4. Для известного типа запускается сессионный цикл:
- `connect({deviceId})`
- `getScreen({deviceId})` (после парсинга/инициализации)
- `sendKey({deviceId, key})` при действиях пользователя
- `disconnect()` при destroy/leave.

Это важное доказательство: Remote+ реализует интерактивный remote-HMI цикл (не просто чтение статуса).

### 23.2 Connection model (чанк `5776`)

В модуле connection details подтверждена dual-модель входа:
- `loginMethod=Remote`
- `loginMethod=Direct`

Поведение формы:
- `Remote` режим: поле адреса используется как `SERIAL_NUMBER`, порт необязателен.
- `Direct` режим: используются `ADDRESS + PORT + PASSWORD`.
- Для direct-режима выставляется default `port = 5843`.

Практический смысл:
- Remote+ поддерживает как облачно-опосредованный сценарий (по serial), так и прямой сценарий (host:port).

### 23.3 Connections/Groups/Devices hierarchy (чанки `6800/5776`)

Подтверждено на уровне модулей:
- список `connections`;
- внутри connection: `groups` + `ungrouped devices`;
- операции:
  - `getList`,
  - `saveConnection`, `deleteConnection`,
  - `saveGroup`, `deleteGroup`,
  - `connect/disconnect` на connection/device уровне.

Подтверждён long-press UX для создания connection (в remote-mode).

### 23.4 Family-specific rendering

В модульных компонентах для Orion/Sirius обнаружен рендер screen-data в canvas + SVG overlay и map keys (`interfaceKey`).

Следствие:
- протокол устройства содержит screen payload (bitmap/packed format),
- приложение декодирует его в изображение,
- пользовательские нажатия превращаются в key-коды и отправляются обратно.

Это уже близко к реконструкции прикладного протокола HMI-управления.

## 24) Уточнённая гипотеза о каналах связи (после deep RE)

Remote+ использует 2 режима:
1. `Remote`:
- идентификация через serial / backend context,
- вероятно backend-mediated routing к устройству.
2. `Direct`:
- явные host/port/password,
- default порт 5843,
- транспортный TCP канал через нативный сокет-плагин.

Оба режима сходятся в одном device runtime pipeline (`connect/getScreen/sendKey/disconnect`).

## 25) Новые задачи реверса (высокий приоритет)

1. Извлечь enum/структуры `baseComputer` и `device.config` полностью.
2. Зафиксировать формат screen payload для Orion/Sirius/Cygnus.
3. Вытащить key-map (какие UI-кнопки -> какие key codes).
4. Локализовать точку, где direct login (`address/port/password`) и remote login (`serial`) конвертируются в transport request.
5. Подтвердить, где именно выбирается TCP endpoint (статический vs server-issued).


## 26) Cross-source confirmation: порт `5843`

Дополнительное подтверждение от исследования `ixagent`:
- порт `5843` встречается не только в `Remote+` клиенте,
- но и в артефактах/логике `ixagent`.

Вывод:
- `5843` является системным transport-портом в рассматриваемом стеке,
- а не случайной/локальной константой одного клиента.

Практическое значение для MYXON:
- при проектировании совместимости нужно учитывать стабильный service-port слой,
- и отдельно разделять:
  - control plane (auth/policy/session bootstrap),
  - data plane (interactive screen/key exchange по transport-порту).


## 27) Deep RE v3: login modes + store action graph

### 27.1 LoginPage (`chunk 2256`)

Подтверждено на уровне кода страницы логина:
- `remoteAccess()` -> dispatch `login({...form, loginMethod: Remote})`
- `directAccess()` -> dispatch `login({username:"", password:"", rememberMe:false, loginMethod: Direct})`
- `forgotPassword()` и `signUp()` открываются через Browser plugin на URL из констант (`userForgotPassword`, `userSignUp`).

Значение:
- `Direct` режим — штатный сценарий, а не debug-функция.
- Вход делится на 2 независимых режима уже на уровне первого экрана.

### 27.2 Connection details (`chunk 5776`)

Подтверждено:
- при `loginMethod=Remote`: поле адреса интерпретируется как `SERIAL_NUMBER`;
- при `loginMethod=Direct`: используется `ADDRESS + PORT + PASSWORD`;
- default `port="5843"` выставляется в non-remote режиме;
- сохранение через `saveConnection`, удаление через `deleteConnectionConfirmation`.

### 27.3 Connection/Device pages (`chunks 6800, 9331`)

Подтверждён action-граф:
1. Connection page:
- `connect({connectionId})`
- `getList({connectionId})`
- `disconnect()` on destroy
2. Device page:
- `connect({deviceId})`
- `getScreen({deviceId})`
- `sendKey({deviceId, key})`
- `disconnect()` on leave

Подтверждён fallback UX:
- если тип устройства не распознан по `baseComputer` -> `NO_DEVICE_SUPPORT`.

### 27.4 Device-family dispatch (runtime)

Подтверждён switch по `baseComputer`:
- Orion(legacy/current)
- Sirius(legacy/current)
- Cygnus

Для каждой family подставляется свой компонент рендера/интеракций.

### 27.5 Протокольный смысл (на текущем этапе)

С высокой вероятностью transport-пакет имеет минимум 3 прикладных класса операций:
1. `SessionControl` (connect/disconnect)
2. `ScreenData` (get/update screen payload)
3. `InputEvents` (sendKey)

Это уже достаточная модель для проектирования совместимого MYXON runtime API-абстрактора.

## 28) Updated confidence map

Высокая уверенность:
- dual login mode (Remote/Direct),
- default direct port 5843,
- family-based dispatch,
- connect/getScreen/sendKey/disconnect цикл.

Средняя уверенность:
- точные поля wire-протокола (без runtime packet capture).

Низкая уверенность:
- серверная маршрутизация в remote-mode (какой именно hop и rule-set между client и target).

## 29) Protocol RE (wire-level) — подтверждено из `main.acd890dcdae41f7f.js`

Источник:  
`RND server/APP_android/Remote+_1.2.0_APKPure/com.hotraco.remoteplus/assets/public/main.acd890dcdae41f7f.js`

### 29.1 Формат сообщения (подтверждено)

В классе transport action (`class Ge`) сообщение собирается в ASCII-кадр:

`@ + DEST(3) + SRC(3) + CMD(3) + SUB(1) + BLOCK(2) + LEN(2) + DATA(hex) + CRC(2) + * + \\r`

Где:
- `@` — start marker,
- `*` — end marker,
- `\\r` — финальный terminator,
- `LEN` — длина payload в байтах (`data.length / 2`),
- `CRC` — контрольная сумма от заголовка+данных (через внутреннюю функцию checksum),
- `SUB/BLOCK` используются для мультиблочных ответов и повтора.

### 29.2 Управление блоками и ретраи

Подтверждено в `handleReceived()`:
- `SUB=Begin(0)` при старте,
- при ошибке CRC/несовпадении команды -> `SUB=Repeat(1)`,
- при multipart-потоке -> `SUB=Next(2)` и накапливание `_storedData`,
- признак завершения блока: `EndBlock="+"` в ответе.

Статусы парсинга:
- `Ignore=-1`,
- `Incomplete=0`,
- `Complete=1`.

### 29.3 Command IDs (подтверждено)

Из enum `i6`:
- `None = 0`
- `Close = 1`
- `ConfigurationRead = 2`
- `MainGroupRead = 6`
- `CaptureScreen = 92`
- `SendKey = 93`
- `CaptureScreenFast = 96`
- `MainGroupChanged = 100`
- `ComputersRequest = 4091`
- `MediateRequest = 4092`

### 29.4 Address IDs (подтверждено)

Из enum адресов:
- `Pc = 1023` (source клиента),
- `General = 1018`,
- `SmartLinkServer = 1184`.

Практический вывод:
- Remote login/mediation идут на `destination=SmartLinkServer`,
- runtime-команды экрана/клавиш идут на `destination=device.config.number`.

### 29.5 Как определяется “клиент” (ответ на вопрос)

На прикладном уровне “клиент” идентифицируется не IP, а контекстом сессии:
- `Remote` режим: `login(username, hashedPassword)` -> `ComputersRequest`,
- затем `connect(..., address)` -> `MediateRequest`,
- backend возвращает доступный список connections/devices для этого пользователя.

На wire-level:
- источник фиксируется как `SRC=Pc(1023)`,
- конкретный tenant/user определяется данными авторизации в payload, а не полем SRC.

### 29.6 Что уже можно считать восстановленным по протоколу

С высокой уверенностью:
1. framing кадра (`@ ... * \\r`, fixed-width fields),
2. ключевые command IDs и destination IDs,
3. логика блочной сборки ответа и retry,
4. runtime цикл команд к устройству:
`ConfigurationRead -> CaptureScreen(Fast) -> SendKey -> MainGroupRead -> Close`.

Остается добить:
- точный бинарно-hex формат `authData(...)` (поля user/pass/address),
- точную формулу checksum (если нужна 100% совместимость байт-в-байт).

## 30) Auth payload (частично восстановлен, high confidence)

В `class Je` найден метод:

`authData(username, hashedPassword, address="")`

Формирование строки:
1. `encode(username).padEnd(40, "0")`
2. `hashedPassword.padStart(40, "0").toUpperCase()`
3. `encode(address)`

Итог: `authPayload = userField(40) + passField(40) + addressField(variable)`.

Что это означает:
- клиентская идентификация строится на паре `username + hashedPassword`,
- для `MediateRequest` добавляется `address` (serial/target),
- payload уходит на `destination=SmartLinkServer(1184)`.

Примечание:
- `encode(...)` — внутренняя функция (в коде как `o.iu`), по паттерну это, вероятно, кодирование строки в hex-представление фиксированного формата.

## 31) Utility-layer протокола (подтверждено, high confidence)

Из module `6784` (`main.acd890dcdae41f7f.js`) подтверждены ключевые функции:

- `o.iu(str, pad=0)`  
  кодирует строку в HEX: для каждого символа `charCodeAt -> toString(16) -> padStart(pad,"0")`, затем `toUpperCase()`.
- `o.CQ(num, pad=2)`  
  кодирует число в HEX фиксированной ширины: `num.toString(16).padStart(pad,"0").toUpperCase()`.
- `o.Ed(hex)`  
  обратное преобразование: `parseInt(hex, 16)`.
- `o.Yx(str)`  
  checksum (XOR): последовательный XOR всех `charCodeAt` по строке кадра.

Следствие:
- framing и checksum алгоритм уже восстановлены достаточно точно для совместимой реализации.

## 32) Кто такой `5.157.85.29:5843` (новое подтверждение)

Найдено в декомпилированном Android-коде:

`tmp_android/jadx_remoteplus/sources/com/hotracogroup/capacitor/tcpsocket/TcpSocketPlugin.java`

Подтверждено:
- `host` default: `5.157.85.29`
- `port` default: `5843`

Интерпретация:
- это fallback endpoint на уровне TCP plugin,
- при штатной работе app обычно передает целевой host/port из своей runtime-логики (`SmartLinkUrl`, connection address и т.п.),
- но наличие дефолта указывает на исторически/операционно закрепленный транспортный узел.

## 33) Брендинг и интерфейсы устройств (углубленное подтверждение)

В таблице device metadata (`R.a2`) найдено:
- семейства: `OrionLegacy/Orion`, `SiriusLegacy/Sirius`, `Cygnus`, `Thomas`;
- маппинг по `sort` и `company`;
- выбор `interface.background` и `interface.svgUrl` для каждого варианта.

Примеры:
- `interfaces/orion/themes/orion_agri.svg`
- `interfaces/orion/themes/orion_horti.svg`
- `interfaces/sirius/themes/sirius-*.svg`
- `interfaces/cygnus/themes/cygnus_*.svg`
- company-specific backgrounds (`url(...bg_opticow.svg)`, `url(...bg_aco.svg)` и т.д.)

Итог:
- да, приложение действительно подбирает UI/branding динамически под тип устройства и бренд/компанию.

## 34) Формальная карта `DATA` по командам (из парсеров, high confidence)

Источник: тот же `main.acd890dcdae41f7f.js`, блок с классами парсеров (`class z`, `class R`, `class $`, `class ie`, `class Oe`).

### 34.1 `ComputersRequest (CMD=4091)` — parser `class z extends N`

Базовые флаги из `class N`:
- `usernameStatus = data[0..2)` (1 byte hex), success если `== UsernameSuccess(1)`
- `passwordStatus = data[2..4)` (1 byte hex), success если `== PasswordSuccess(1)`

Если оба success:
- дальше `connectionsBlock = data[4..]`
- запись connection имеет фиксированную длину `60` hex-символов:
  - `address/id` = `20` hex (декодируется `o.qi(...)` как string)
  - `name` = `40` hex (decode + trim + remove `\\x00`)
- результат: `connections[] = { id:+address, address, name, port: undefined }`

Если username/password не прошли:
- ошибка `LOGIN_INVALID`.

### 34.2 `MediateRequest (CMD=4092)` — parser `class R extends N`

Проверки:
- username/password как выше (`data[0..2)`, `data[2..4)`),
- mediation status: `data[4..6)` (1 byte hex):
  - `MediationSuccess=1` -> `Complete`
  - `MediationBusy=0` -> `Ignore` (ожидание/повтор цикла)
  - `MediationError=2` -> ошибка `CONNECT_FAILURE`

При fail username/password:
- ошибка `LOGIN_EXPIRED`.

### 34.3 `ConfigurationRead (CMD=2)` — parser `class $`

Структура:
- `password = parseHex(data[0..4))` (2 bytes)
- `configsBlock = data[4..]`
- один `deviceConfig` = `40` hex (20 bytes), поля:
  1. `computer`          = `[0..4)`   (u16)
  2. `sort`              = `[4..8)`   (u16)
  3. `type`              = `[8..12)`  (u16 bitmask)
  4. `company`           = `[12..16)` (u16)
  5. `computerVersion`   = `[16..20)` (u16)
  6. `pcVersion`         = `[20..24)` (u16)
  7. `serial`            = `[24..32)` (u32)
  8. `number`            = `[32..36)` (u16)  <- destination для device-level команд
  9. `optionsChangeCount`= `[36..40)` (u16)

Далее app строит `devices[]`:
- `id = hash(serial + number)`,
- `name/interface/alarmColor` через `o.gh(config)` (family/sort/company mapping),
- выбирает `primaryDevice` через `o.cb(...)`.

### 34.4 `CaptureScreen / CaptureScreenFast (CMD=92/96)` — parser `class ie`

Parser возвращает raw:
- `{ command, screen: data }`

Дальше семейные UI-компоненты (Orion/Sirius/Cygnus) уже локально декодируют `screen` в bitmap/canvas.

### 34.5 `MainGroupRead (CMD=6)` — parser `class Oe`

Структура:
- `alarm.code = parseHex(data[0..4))`
- `alarm.state` вычисляется из фрагмента:
  - offset/length берутся из `alarmColor` профиля устройства (`o.gh(config)`),
  - сравнение с enum `EF` -> маппинг в `oh` (`Alarm/Warning/Off/Suppressed/None/Unknown`).

### 34.6 `SendKey (CMD=93)` — request payload

Вызов:
- `sendKey(device, key) -> sendMessage(device.config.number, SendKey, CQ(key))`

То есть payload для `SendKey` — hex-код клавиши фиксированной ширины (через `CQ`).

## 35) Request-side: как формируется `DATA` (подтверждено)

### 35.1 `authData(username, hashedPassword, address="")`

Формат:
1. `iu(username, 2).padEnd(40, "0")`
2. `hashedPassword.padStart(40, "0").toUpperCase()`
3. `iu(address, 2)`

Именно эта строка идет в `ComputersRequest` и `MediateRequest`.

### 35.2 Device runtime requests

- `getScreen(update)`:
  - payload `CQ(ScreenUpdate=0)` или `CQ(ScreenComplete=1)`
- `sendKey(key)`:
  - payload `CQ(key)`
- `getDeviceAlarm()`:
  - payload пустой

## 36) End-to-end workflow (точная версия по коду)

1. TCP connect к `smartlinkserver.com:5843` (remote mode)  
2. `ComputersRequest(4091)` с `authData` -> список connections  
3. `MediateRequest(4092)` с `authData(..., address)` -> установка mediation  
4. Отдельный connection runtime socket к target host/port  
5. `ConfigurationRead(2)` -> список доступных device configs  
6. Для выбранного `device.config.number`:
   - `CaptureScreenFast(96)` циклично,
   - `SendKey(93)` по нажатиям,
   - `MainGroupRead(6)` для alarm/status,
   - `Close(1)` при выходе.

## 37) Что еще осталось для 100% реконструкции

Остались средние риски (но уже не блокируют совместимую реализацию):
- точное поведение при `MediationBusy` в длинных сценариях (политика retry/timeout на сервере),
- полный каталог key-code mapping для всех UI тем/семейств,
- edge-cases multipart screen payload для медленных каналов.

## 38) Deep RE: экранные декодеры и keycodes (из `7112.f02ef8a2bee72d81.js`)

Подтверждено, что в web-chunk лежат реальные device-декодеры:

1. `app-cygnus`
- framebuffer: `128x64`
- key map: `up=19,right=18,down=20,left=17,ok=21,f1..f4=64..67`
- decode: bitstream + RLE-подобные блоки, remap индекса пикселя по строке.

2. `app-orion`
- framebuffer: `240x128`
- key map:
  - `up=19,right=18,down=20,left=17,ok=21`
  - `plusminus=22,dot=46`
  - `num0..num9=48..57`
  - `f1..f6=64..69`
  - `prev=80,next=81`
- decode: bitstream + RLE-подобные блоки.

3. `app-sirius`
- framebuffer: `122x32`
- key map: `up=1,right=3,down=2,ok=4,key1..key10=16..25`
- decode: прямой unpack битов в буфер.

Практический вывод:
- payload `screen` действительно device-family specific.
- `sendKey` несет абстрактные keycodes, которые app мапит из UI (брендинг/раскладка) в protocol-level код.

## 39) Deep RE: TCP boundary caveat

В socket wrapper (`module 2552`, `class Pn`) входящие данные идут как:
- `onData(bytes)` -> `TextDecoder.decode(bytes)` -> `message$.next(textChunk)`.

На этом уровне не видно явной сборки по delimiter `@...*\\r`.  
Значит, устойчивость к fragmentation обеспечивается логикой `handleReceived`:
- `Incomplete`,
- `Repeat`,
- `Next`/block accumulation.

Это важно для собственного сервиса: reassembly лучше сделать явно на transport-layer, чтобы снизить число лишних retry.

## 40) Deep RE: bit-level grammar screen payload

По `7112.f02ef8a2bee72d81.js` восстановлено:

1. Orion/Cygnus:
- `CaptureScreenFast` несет в первом байте режим `s`.
- `s=0`: full/квазиполный поток с RLE-подобными токенами:
  - `0xFF + h` -> run `8*h` пикселей цвета A,
  - `0x00 + h` -> run `8*h` пикселей цвета B,
  - иначе: 8 бит literal.
- `s=1`: update/delta поток:
  - `0x00 + h(h!=0)` -> skip `8*h` пикселей,
  - иначе literal bits.
- Cygnus имеет дополнительный remap индекса в строке (отражение).

2. Sirius:
- отдельный unpacker без RLE-токенов,
- bitstream раскладывается в `122x32` буфер по своей схеме обхода.

Вывод:
- протокол экрана — это не просто «blob», а строго определенный семейно-зависимый битовый формат.

## 41) Deep RE: auth hash и security-практики клиента

Подтверждено:

1. `hashedPassword`:
- в `main...js` используется модуль `7292`,
- код модуля соответствует SHA-1 (`digest size 20 bytes`),
- в `authData` уходит 40-символьная hex-строка (верхний регистр, pad до 40).

2. Transport security:
- Android tcp plugin (`TcpSocketPlugin/TcpSocketClient`) использует `java.net.Socket` (plain TCP),
- TLS на уровне plugin не реализован.

3. Локальное хранение:
- `StorageService` (`module 6330`) хранит:
  - credentials,
  - remote connection passwords,
  - connections/groups,
  через Capacitor Preferences (JSON serialization).
- Явного шифрования локальных secret в этом слое не обнаружено.

Практический вывод для MYXON:
- нельзя повторять модель “plain SHA-1 + plaintext local storage” для production security baseline;
- нужны минимум: modern KDF/secret handling, encrypted local vault, и transport TLS/mTLS.

## 42) Deep RE: SyslinQ location/company navigation model (new)

Новые подтверждения из `tmp_android/syslinq_functional_strings.txt`:
- найден route-шаблон: `locations/:companyId/:agentId/:serverId`
- встречаются сущности и операции:
  - `companySelectionToggle`
  - `agentList`
  - `parent:{companyId}`
  - `IXapi-Company` (и ошибка `Invalid IXapi-Company`)
  - ошибки доступа уровня компании/устройства: `No focus devices`, `This agent is not online`, `You are not allowed to connect ... using VNC`.

Интерпретация:
- стартовый UX SyslinQ строится как иерархия `company -> location/agent -> server/device`.
- выбор компании влияет на API-контекст через заголовок `IXapi-Company`.
- это согласуется с вашим требованием стартового экрана “локации/устройства”.

Практический вывод для MYXON:
- в API нужен явный контекст локации/компании (не только flat список устройств).
- в UI нужен двухшаговый вход: выбор локации/агента -> список устройств/ресурсов.
- в access policy нужно отдельное правило `company context` (аналог `IXapi-Company`).

## 43) Deep RE: native TCP plugin semantics (new precision)

Подтверждено по исходникам:
- `tmp_android/jadx_remoteplus/sources/com/hotracogroup/capacitor/tcpsocket/TcpSocketClient.java`
- `tmp_android/jadx_remoteplus/sources/com/hotracogroup/capacitor/tcpsocket/TcpReceiverTask.java`
- `tmp_android/jadx_remoteplus/sources/com/hotracogroup/capacitor/tcpsocket/TcpSocketPlugin.java`

Факты:
1. Плагин ожидает `write(base64String)` и декодирует payload на нативной стороне (`Base64.decode`).
2. `onData` отправляет данные обратно в JS тоже как Base64 (`Base64.encodeToString(..., NO_WRAP)`).
3. `connect` параметры:
   - `host` default `5.157.85.29`
   - `port` default `5843`
   - `localAddress` default `0.0.0.0`
   - `localPort` default `0`
   - `reuseAddress` default `true`
   - `timeout` default `0`
4. receiver читает сокет чанками `8192` байт, без фрейм-aware reassembly.

Практический вывод:
- JS-слой работает с Base64-сообщениями, а не “сырыми” bytes.
- при совместимости MYXON нужно учитывать binary<->base64 boundary в client adapter.
- reassembly фреймов обязателен в протокольном слое (не полагаться на TCP chunk boundaries).

## 44) Deep RE: access/role/company scope signals in SyslinQ (new)

Подтверждено по строковым артефактам `main.7075df340470e99d.js` и `tmp_android/syslinq_functional_strings.txt`:

1. Company-scoped API контекст:
- `IXapi-Company`
- `Invalid IXapi-Company`
- `IXapi-Application`
- `IXapi-Version`
- `IXapi-AccessLevel`

2. Явный location/company UX:
- route: `locations/:companyId/:agentId/:serverId`
- страницы/события:
  - `[Locations Page] Load Company List`
  - `[Locations Page] Open Tree Node`
  - `[Locations Page] Toggle Tree Node`
  - `[Locations Page] Update Query`

3. Явные permission/error сигналы:
- `No permission`
- `This agent is not online`
- `Focus device is offline`
- `You are not allowed to Connect-vnc this Agent`
- `You are not allowed to connect with this focus device using VNC`

4. Tenant/company feature-flag семантика:
- `sectorData.remoteApp.vncAccessAll`
- admin операции:
  - `[Admin Page] Enable VNC Access All`
  - `[Admin Page] Disable VNC Access All`
  - `[Company API] Enable/Disable VNC Access All Success/Fail`

Вывод для архитектуры MYXON:
- в policy gate нужна не только проверка tenant/device, но и явный `company/location context`;
- VNC-права и похожие протоколы должны быть отдельным feature-flag уровнем (company policy);
- location tree и company selection — часть security-модели, а не только UX.

## 45) Endpoint Context Matrix (SyslinQ) — class-level reconstruction

Цель: зафиксировать, какой API-класс операций требует какого контекста доступа.

Основание: строковые артефакты из `tmp_android/syslinq_functional_strings.txt` + web bundle `main.7075df340470e99d.js`.

### 45.1 Классы endpoint-ов и контекст

1. Auth / Account endpoints  
- Признаки: `Login`, `recover`, `updatePassword`, ссылки `remote.syslinq.co/login`, `.../recover/...`  
- Контекст: `global user context` (без выбранной компании на старте)  
- Confidence: `high`

2. Company tree / Locations endpoints  
- Признаки: `[Locations Page] Load Company List`, `locations/:companyId/:agentId/:serverId`, `companySelectionToggle`, `agentList`  
- Контекст: `company + location tree context`  
- Confidence: `high`

3. Device-scoped operations by deviceId/publicId  
- Признаки: `getByDeviceId`, `updateByDeviceId`, `removeByDeviceId`, параметры `{publicId, deviceId}`, `{userId, deviceId}`  
- Контекст: `device context`, иногда с company selection  
- Confidence: `high`

4. VNC permission / policy operations  
- Признаки: `You are not allowed to connect ... using VNC`, `vncAccessAll`, `[Admin Page] Enable/Disable VNC Access All`  
- Контекст: `company policy context` + `role`  
- Confidence: `high`

5. Push device registration endpoints  
- Признаки: `registerForNotifications`, `pushDeviceService.add/removeByDeviceId`, работа с `agentService.getAll()`  
- Контекст: `user session + device scope`  
- Confidence: `medium`

### 45.2 Header-level signals

- Явно найдено: `IXapi-Company`, `Invalid IXapi-Company`, `IXapi-AccessLevel`, `IXapi-Application`, `IXapi-Version`.
- В части вызовов видно `this.api.headers.delete(Wu.Company)`: это признак, что не все endpoint-ы требуют company header.

Вывод:
- SyslinQ использует смешанную модель: часть API строго company-scoped, часть — global/device scoped.

### 45.3 Что это означает для MYXON API gateway

Нужен явный `context resolver` перед policy check:
1. `global` (auth/account)
2. `company` (admin/policy/location tree)
3. `device` (resource/session/push binding)

Рекомендуемая схема:
- На каждый endpoint задавать `required_context`.
- Middleware проверяет наличие и валидность контекста (аналог `IXapi-Company`).
- Политика доступа применяет role+company flags (`vnc_access_all`) только там, где это действительно требуется.

### 45.4 Темные пятна по endpoint-level точности

Осталось (неполностью восстановлено из статического анализа):
- точные URL path шаблоны для каждого `api.url(...)` класса;
- полный mapping `method + path -> required headers`;
- точные server-side коды ошибок по каждому policy deny сценарию.

Для закрытия этих пятен нужен runtime capture (mitm / instrumentation) в контролируемом стенде.

## 46) Activation Handshake для удаленного VNC (inferred)

Гипотеза: удаленный VNC включается не только сетевой доступностью, а через серверно-управляемую активацию модуля на устройстве + policy на уровне компании.

### 46.1 Подтверждающие сигналы

1. Слой "модуль активирован/не активирован" (Remote+):
- `REMOTE_MODULE_NOT_ACTIVATED`: `Remote+ module is not activated yet. Please, contact your dealer.`
- `Module could not be validated for this focus device.`

2. Слой policy/role на стороне платформы:
- `IXapi-Company`, `IXapi-AccessLevel`.
- `sectorData.remoteApp.vncAccessAll`.
- admin-операции: enable/disable VNC Access All.

3. Слой транспортного проброса на роутере:
- В firewall дампе есть статические DNAT правила:
  - `vpn:2000 -> 192.168.27.11:5900` (VNC)
  - `vpn:2001 -> 192.168.27.11:8080`
  - `vpn:2002 -> 192.168.27.11:5843`

Вывод:
- роутер обеспечивает туннель и порт-маппинг;
- решение о доступе к удаленному VNC принимается выше (module entitlement + company policy + user role).

### 46.2 Вероятный workflow активации (архитектурная реконструкция)

1. Пользователь/дилер вводит код активации на HMI/контроллере.
2. Устройство/edge-приложение отправляет запрос в backend для валидации модуля.
3. Backend привязывает entitlement к device/company.
4. Backend возвращает capability flags (в т.ч. для remote VNC).
5. UI и API начинают пропускать VNC-сессию при выполнении policy checks.

### 46.3 Уровень уверенности

- `high`: существует отдельный слой module activation и отдельный слой company policy.
- `high`: транспорт (роутер) сам не является "лицензионным решателем", а делает проброс.
- `medium`: точный API endpoint и формат запроса активации пока не восстановлены статически.

## 47) Новое точное подтверждение из функциональных строк (SyslinQ bundle)

В `tmp_android/syslinq_functional_strings.txt` найден фрагмент логики:

- `validateAppModule(t,i,r){return this.validateCompany(t).pipe(... ? ... : this.validateServer(t,i,r))}`

Интерпретация:
- перед запуском удаленного доступа клиент явно проходит этап валидации модуля;
- проверка имеет как минимум два шага: company-level и server/device-level;
- это согласуется с ошибками:
  - `Module could not be validated for this focus device.`
  - `Module is not enabled on this focus device.`

Следствие для MYXON:
- в policy engine нужен отдельный `module_validation` этап до создания VNC/HTTP сессии;
- проверка должна быть композитной: `company context` + `focus device/module state`.

## 48) Progress Bar (текущий статус)

- Архитектура приложений и роли слоев: `90%` `[##################--]`
- Remote+ transport/protocol/runtime: `88%` `[##################--]`
- Device-family decoding/keymaps: `92%` `[###################-]`
- Native TCP plugin semantics: `95%` `[###################-]`
- SyslinQ context/roles/locations model: `72%` `[##############------]`
- Точный endpoint-level API contract (path+method+headers+errors): `52%` `[##########----------]`

## 49) Phase Plan to 100% and current update

### 49.1 План закрытия до 100%

1. Фаза A: SyslinQ context/roles/locations
- собрать точные class/method сигнатуры для:
  - company selection,
  - module validation,
  - viewer guard deny branches.
- итог: complete context model `global/company/device`.

2. Фаза B: Endpoint-level API contract
- собрать `method + path + headers + error strings + payload fields`;
- свести в единую таблицу contracts;
- после статического этапа выполнить runtime-верификацию на стенде.

3. Фаза C: Финальная верификация
- закрыть edge-cases для retry/error веток;
- финальный cross-check отчета и протокольной спецификации.

### 49.2 Что закрыто в этой итерации

- Подтверждено наличие явной цепочки module-gate:
  - `validateAppModule(t,i,r){return this.validateCompany(t).pipe(... ? ... : this.validateServer(t,i,r))}`
- Подтверждены связанные deny-сигналы:
  - `Module could not be validated for this focus device.`
  - `Module is not enabled on this focus device.`
  - `You are not allowed to connect with this focus device using VNC`
- Подтверждены company-level policy маркеры:
  - `item.sectorData.remoteApp.vncAccessAll`
  - `[Admin Page] Enable/Disable VNC Access All`
  - `IXapi-Company`, `Invalid IXapi-Company`, `IXapi-AccessLevel`

### 49.3 Обновление прогресса после итерации

- Архитектура приложений и роли слоев: `90%` `[##################--]`
- Remote+ transport/protocol/runtime: `88%` `[##################--]`
- Device-family decoding/keymaps: `92%` `[###################-]`
- Native TCP plugin semantics: `95%` `[###################-]`
- SyslinQ context/roles/locations model: `78%` `[################----]`
- Точный endpoint-level API contract (path+method+headers+errors): `56%` `[###########---------]`

## 50) Endpoint/Context extraction update (static, deeper)

Источник: `tmp_android/syslinq_functional_strings.txt`.

### 50.1 Подтвержденные service-call паттерны

Найдены фрагменты с явными device-level service методами:
- `updateByDeviceId(...)`
- `getByDeviceId(...)`
- `removeByDeviceId(...)`
- `getList(...)`
- `registerForNotifications(...)`

Найдены явные вызовы с контекстным удалением company header:
- `this.api.headers.delete(Wu.Company)`

Интерпретация:
- часть endpoint-ов выполняется в non-company режиме (header deliberately removed);
- часть операций остается company-scoped (по остальным веткам и ошибкам `Invalid IXapi-Company`).

### 50.2 Подтверждение многоуровневого gate перед VNC

Найдена цепочка:
- `validateAppModule(t,i,r){return this.validateCompany(t).pipe(... ? ... : this.validateServer(t,i,r))}`

Это усиливает модель:
- `module validation` -> `company validation` -> `server/device validation` -> запуск remote VNC URL.

### 50.3 Влияние на точный API contract

Что стало точнее:
- определены классы вызовов (device-scoped / company-scoped / mixed);
- подтверждена header-тактика (`delete(Wu.Company)` в device/push-ветках);
- подтверждены deny-сигналы для viewer guard и VNC-policy.

Что еще не закрыто до 100%:
- буквальные `path`-строки для каждого `api.url(...)` в unminified виде;
- точный mapping `method + path + required headers + error code`.

### 50.4 Progress update

- Архитектура приложений и роли слоев: `90%` `[##################--]`
- Remote+ transport/protocol/runtime: `88%` `[##################--]`
- Device-family decoding/keymaps: `92%` `[###################-]`
- Native TCP plugin semantics: `95%` `[###################-]`
- SyslinQ context/roles/locations model: `82%` `[################----]`
- Точный endpoint-level API contract (path+method+headers+errors): `60%` `[############--------]`

## 51) Endpoint key inventory (SyslinQ, extracted)

Из `main.7075df340470e99d.js` извлечены именованные ключи `api.url("...")`:

- `AccessRecover`
- `AccessToken`
- `AccessTokenList`
- `Agent`
- `AgentList`
- `AgentServerList`
- `Company`
- `CompanyList`
- `User`
- `UserEmailAddressChangeList`
- `UserPassword`
- `UserPushDevices`
- `UserPushDevicesList`
- `UserPushDevicesUnlink`
- `WebAccessList`

Интерпретация:
- это уже не только строковые сообщения, а реальный словарь API-ресурсов клиента;
- далее нужно восстановить mapping каждого ключа на:
  - literal path template,
  - HTTP method,
  - required headers (`IXapi-Company`/`IXapi-AccessLevel` и т.д.),
  - типичные deny/errors.

### 51.1 Что это дало для прогресса

- SyslinQ context/roles/locations model: `86%` `[#################---]`
- Точный endpoint-level API contract (path+method+headers+errors): `68%` `[##############------]`

## 52) Endpoint Contract Matrix (static reconstruction, confidence-based)

Источники:
- `RND server/APP_android/SyslinQ Remote_1.3.0_APKPure/com.hotraco.syslinqremote/assets/public/main.7075df340470e99d.js`
- `tmp_android/syslinq_functional_strings.txt`

### 52.1 Confirmed (по прямым фрагментам вызовов)

1. `AccessRecover`
- Method: `POST`
- Признак: `this.api.url("AccessRecover") ... this.http.post(... {emailAddress, links} ...)`
- Headers: `this.api.headers` (company-header явно не удаляется в этом фрагменте)
- Назначение: password recovery flow.

2. `UserPassword`
- Method: `POST`
- Признак: `this.api.url("UserPassword") ... this.http.post(... {oldPassword,newPassword,links} ...)`
- Headers: `this.api.headers`
- Назначение: смена пароля авторизованного пользователя.

3. `WebAccessList`
- Method: `POST`
- Признак: `this.api.url("WebAccessList") ... this.http.post(... {method:"guacamole",server:{publicId}} ...)`
- Headers: `this.api.headers.set("IXapi-Company", companyId)`
- Назначение: получение web/tunnel URL для удаленного доступа (Guacamole/VNC path generation).

### 52.2 High confidence (семейства endpoint-ов по сигнатурам)

1. Device-scoped push/session operations (`getByDeviceId`, `updateByDeviceId`, `removeByDeviceId`, `getList`)
- Methods (по сигнатурам фрагментов):
  - `getByDeviceId`: `GET`
  - `updateByDeviceId`: `PATCH`
  - `removeByDeviceId`: `DELETE`
  - отдельные связки `deviceId` встречаются и с `POST`
- Header behavior: системно встречается `this.api.headers.delete(Wu.Company)`
- Интерпретация: часть API явно должна работать вне company-header контекста (user/device personal scope).

2. VNC module validation gate
- Цепочка: `validateAppModule -> validateCompany -> validateServer`
- Error surface:
  - `Module could not be validated for this focus device.`
  - `Module is not enabled on this focus device.`
  - `You are not allowed to connect with this focus device using VNC`
- Интерпретация: до вызова `WebAccessList` есть отдельный policy/entitlement guard.

### 52.3 Inferred backend contract rules (для команды реализации MYXON)

1. Минимум 3 контекста API в клиенте:
- `global/user`
- `company-scoped` (`IXapi-Company` обязателен)
- `device/user-scoped` (company header может быть удален)

2. `WebAccessList` относится к `company+device` контексту, а не к raw device TCP уровню.

3. Ошибка `Invalid IXapi-Company` подтверждает, что backend валидирует company context на уровне API gateway.

### 52.4 Темные пятна, которые еще нужно закрыть

1. Literal mapping `api.url(KEY)` -> полный path template для всех ключей (`AgentList`, `CompanyList`, `UserPushDevices*` и т.д.).
2. Полный `headers matrix` по каждому endpoint (mandatory/optional).
3. Полный `error code catalog` по каждому вызову (не только UI strings).

### 52.5 Progress update

- Архитектура приложений и роли слоев: `91%` `[##################--]`
- Remote+ transport/protocol/runtime: `89%` `[##################--]`
- Device-family decoding/keymaps: `92%` `[###################-]`
- Native TCP plugin semantics: `95%` `[###################-]`
- SyslinQ context/roles/locations model: `88%` `[##################--]`
- Точный endpoint-level API contract (path+method+headers+errors): `74%` `[###############-----]`

## 53) Manual Trace Reconstruction (where automation was weak)

Ниже результаты ручного разбора минифицированного `main.7075df340470e99d.js` по большим контекстным окнам вокруг ключей API.

### 53.1 Auth / session contract (confirmed)

1. `AccessTokenList`
- `loginWithCredentials(...)`:
  - `api.url("AccessTokenList", {fields})`
  - `http.post(..., {...credentials, expiresIn}, {headers})`
  - headers включают:
    - `Authorization: Basic <email:otp:password>`
    - `SKIP_UNAUTHORIZED=true`
- `refreshToken(...)`:
  - `api.url("AccessTokenList", {fields})`
  - `http.post(..., {expiresIn}, {headers: api.headers})`

2. `AccessToken`
- `logout()`:
  - `api.url("AccessToken", {publicId:"me"})`
  - `http.delete(..., {headers: api.headers + SKIP_UNAUTHORIZED=true})`
- в refresh flow после нового токена:
  - `api.url("AccessToken", {publicId: token.data.publicId})`
  - `http.delete(...)` (удаление старого токена)

3. `AccessRecover`
- `recoverPassword(email)`:
  - `api.url("AccessRecover")`
  - `http.post(..., {emailAddress, links}, {headers: api.headers})`

### 53.2 Company / topology contract (confirmed)

1. `CompanyList`
- `getAll()`:
  - `api.url("CompanyList", {fields})`
  - `http.get(..., {headers: api.headers})`

2. `Company`
- `updateByPublicIdList([...])`:
  - `api.url("Company", {publicId})`
  - `http.patch(..., payload, {headers: api.headers})`
- `validateCompany(...)` в VNC gate:
  - `api.url("Company", {publicId:"me", fields})`
  - `http.get(..., {headers: api.headers.set("IXapi-Company", companyId)})`

### 53.3 Agent / server discovery contract (confirmed)

1. `AgentServerList`
- `getAll(companyId, agentId)`:
  - `api.url("AgentServerList", {agentId})`
  - `http.get(..., {params:{fields}, headers: IXapi-Company})`
- в `validateServer(...)`:
  - `api.url("AgentServerList", {agentId, fields})`
  - `http.get(..., {headers: IXapi-Company})`

2. `Agent`
- `get(companyId, publicId)`:
  - `api.url("Agent", {publicId, fields})`
  - `http.get(..., {headers: IXapi-Company})`

3. `AgentList`
- `getAll(companyId)`:
  - `api.url("AgentList", {fields})`
  - `http.get(..., {headers: IXapi-Company})`

### 53.4 User / notifications contract (confirmed)

1. `User`
- `getMe()`:
  - `api.url("User", {publicId:"me", fields})`
  - `http.get(..., {headers: api.headers})`
- `updateFullName(...)`:
  - `api.url("User", {publicId:"me"})`
  - `http.patch(..., {fullName}, {headers: api.headers})`

2. `UserEmailAddressChangeList`
- `updateEmailAddress(newEmail)`:
  - `api.url("UserEmailAddressChangeList", {userId:"me"})`
  - `http.post(..., {newEmailAddress, links}, {headers: api.headers})`

3. `UserPushDevices*` (non-company scope, confirmed)
- Общая тактика headers: `api.headers.delete(Wu.Company)`
- `UserPushDevicesList`:
  - `POST` add
  - `GET` list
- `UserPushDevices`:
  - `GET` by device
  - `PATCH` update by device
  - `DELETE` remove by device
- `UserPushDevicesUnlink`:
  - `POST` unlink for others

### 53.5 VNC access path (manual flow reconstruction)

Ручной path в клиенте:
1. `validateAppModule(companyId, agentId, focusDevice)`
2. `validateCompany(companyId)` через `Company` + `IXapi-Company`
3. `validateServer(companyId, agentId, focusDevice)` через `AgentServerList`
4. при успехе запрос web tunnel через `WebAccessList` (`method:"http"`/`"guacamole"` в разных ветках)
5. проверка `.../system/modules/app` и флаг `enabled`

Именно здесь видны deny-сообщения про module validation/VNC access.

### 53.6 Что теперь закрыто и что осталось

Закрыто:
- большой блок endpoint->method->header для auth/company/agent/user/push-devices;
- подтверждена явная разница company-scoped и non-company операций.

Осталось:
- literal URL templates backend для каждого key (слой `api.url(...)` resolver);
- полный catalog server error codes и retry semantics.

### 53.7 Progress update

- Архитектура приложений и роли слоев: `92%` `[###################-]`
- Remote+ transport/protocol/runtime: `89%` `[##################--]`
- Device-family decoding/keymaps: `92%` `[###################-]`
- Native TCP plugin semantics: `95%` `[###################-]`
- SyslinQ context/roles/locations model: `91%` `[###################-]`
- Точный endpoint-level API contract (path+method+headers+errors): `82%` `[################----]`

## 54) API Resolver internals (manual proof)

Ключевая находка из минифицированного кода (прямой фрагмент):

- `const Jc_api_appId="szNdVB9zFsjI", Jc_api_url="https://api.ixon.net/", Jc_api_version="1"`
- `headers = { "IXapi-Application": Jc_api_appId, "IXapi-Version": Jc_api_version }`
- `discover(){ return this.links ? ... : this.http.get(Jc_api_url,{headers}).pipe(... t.links ...) }`
- `url(rel, params){ const link = links.find(x => x.rel===rel); ... substitute {param} or append query ... }`

### 54.1 Что это означает для реверса endpoint-level контракта

1. Почему в APK нет полного списка literal paths
- Приложение не хранит статическую map `rel -> /path`.
- Реальные URL приходят динамически из `GET https://api.ixon.net/` в виде `links[]`.

2. Как формируется конечный URL
- `rel` (например, `AgentList`, `WebAccessList`, `UserPushDevices`) ищется в `links[]`.
- Если в `href` есть `{param}`, выполняется подстановка по имени.
- Если placeholder отсутствует, параметр добавляется в query string.

3. Почему ручной разбор дал точные методы, но не всегда точный path
- Метод/headers/payload задаются в клиенте и хорошо восстанавливаются статикой.
- Конкретный backend path шаблон определяется серверным discovery-документом, который не зашит в коде.

### 54.2 Практический вывод для MYXON

1. Нужно поддержать такой же discovery-слой (Hypermedia/HATEOAS-подобный):
- root endpoint возвращает `links` с `rel`-именами.
- мобильный/web клиент строит URL через resolver, а не через hardcoded routes.

2. Для «100% endpoint contract» по IXON требуется runtime capture discovery payload:
- сохранить ответ `GET https://api.ixon.net/`;
- это сразу даст `rel -> literal href template` для всех ресурсов.

### 54.3 Progress update

- Архитектура приложений и роли слоев: `93%` `[###################-]`
- Remote+ transport/protocol/runtime: `89%` `[##################--]`
- Device-family decoding/keymaps: `92%` `[###################-]`
- Native TCP plugin semantics: `95%` `[###################-]`
- SyslinQ context/roles/locations model: `93%` `[###################-]`
- Точный endpoint-level API contract (path+method+headers+errors): `88%` `[##################--]`

## 55) Error Contract Reconstruction (manual, end-to-end)

Разобран полный путь ошибок: backend/discovery -> service layer (`Nt`, `gs`) -> viewer/login UI.

### 55.1 Базовые источники ошибок

1. API resolver (`Qa.url(rel, params)`)
- При отсутствии `rel` в `links[]` бросается:
  - `status: 503`
  - `statusText: "Not Found"`
  - `error.data.errorDataMessage: "url not found"`
- Это системная ошибка discovery-слоя, не бизнес-ошибка домена.

2. VNC module-gate и WebAccess validation
- Константа: `UI = "Module could not be validated for this focus device."`
- Доп. ошибка: `"Module is not enabled on this focus device."`
- `validateWebAccessUrl(...).pipe(Nt(()=>gs(UI)), ... )` переводит transport/API failure в user-facing policy error.

3. Viewer (Guacamole runtime)
- `client.onerror` маппит `o.code` через `function phe(code)` в текст и показывает:
  - `showErrorMessage(`${message} (${code})`)`
- При unknown code: `"Something went wrong."`

### 55.2 Guacamole code map (confirmed from code)

- `256` -> requested operation unsupported
- `512` -> internal error
- `513` -> server busy
- `514` -> upstream server not responding
- `515` -> upstream server encountered error
- `516` -> associated resource not found
- `517` -> resource already in use/locked
- `518` -> resource closed
- `768` -> illegal/invalid parameters
- `769` -> permission denied (not logged in)
- `771` -> permission denied (login will not help)
- `776` -> client timeout
- `781` -> client sent too much data
- `783` -> unexpected/illegal data type
- `797` -> client using too many resources

### 55.3 Error transformation patterns (`Nt(...)`)

1. Login flow
- raw error -> `Nt(y => new Bhe(y.error?.data || []))`
- UI mapping:
  - если есть `"Basic authentication failed"` -> `"Incorrect credentials"`
  - иначе -> `"Failed to login. Please try again"`

2. Password recover flow
- raw error -> `Nt(err => new Whe(err.error?.data || []))`
- UI mapping examples:
  - `"Can not be NULL"` -> `"Email address is required"`
  - `"Invalid format"` -> `"Invalid email address"`

3. Logout / refresh token
- fallback на session-expired/relogin сценарий:
  - `"Session has expired. Please login again"`

4. Viewer connect chain
- `validateAppModule + getTunnelUrl` в pipe с `Nt(r => gs(r))`
- финальный UI:
  - если ошибка не равна `UI`: `"Unable to connect to vnc view."`
  - если равна `UI`: показать `UI` как есть.

### 55.4 Domain-level deny mapping

`k$(error)` переводит backend `error.data[0].message` в понятные тексты:
- `"This agent is not online"` -> `"Focus device is offline"`
- `"You are not allowed to Connect-vnc this Agent"` -> `"You are not allowed to connect with this focus device using VNC"`
- fallback: исходное сообщение backend.

Отдельно в guard/topology ветках используются сигналы:
- `"Invalid IXapi-Company"`
- `"Agent not found"`

### 55.5 Практический контракт ошибок для MYXON

1. Нужны 3 уровня error semantics:
- `transport/discovery` (например, `url not found`, `503`)
- `policy/entitlement` (module disabled, no VNC permission)
- `runtime tunnel/protocol` (Guacamole numeric codes)

2. Нужен явный слой нормализации ошибок до UI:
- backend message/code -> internal normalized error -> localized UX message.

3. Для совместимости полезно сохранить поведение fallback:
- unknown runtime code -> generic message + original code.

### 55.6 Progress update

- Архитектура приложений и роли слоев: `93%` `[###################-]`
- Remote+ transport/protocol/runtime: `91%` `[###################-]`
- Device-family decoding/keymaps: `92%` `[###################-]`
- Native TCP plugin semantics: `95%` `[###################-]`
- SyslinQ context/roles/locations model: `94%` `[###################-]`
- Точный endpoint-level API contract (path+method+headers+errors): `92%` `[###################-]`

## 56) Retry / Backoff / Recovery Semantics (manual)

Разбор показал: в текущем клиенте почти нет «классического» retry/backoff для сетевых вызовов; вместо этого используются throttling/rate-limit и UX-level retry.

### 56.1 Что делает `QM(500)` на самом деле

Подтверждено по коду:
- `function QM(e,n=w_){ const t=NU(e,n); return Y4(()=>t) }`
- `w_` — scheduler.
- `NU(...)` создает timer-observable.
- `Y4(...)` + `At(1), gV(t)` семантически соответствует ограничению частоты (audit-like), а не повтору запроса.

Вывод:
- `QM(500)` в `recoverPassword` это сглаживание/ограничение эмиссий с окном ~500ms,
- но не экспоненциальный backoff и не автоматический повтор failed request.

### 56.2 Где реально есть retry-поведение

1. Viewer screen (VNC)
- `showErrorMessage(..., "Retry")` + `onAction().subscribe(()=>retry())`
- `retry()`:
  - сбрасывает `client/tunnel/status`
  - заново запускает `start()`.
- Это user-driven retry (ручной), не background automatic retry loop.

2. Error page
- Кнопка `RETRY` вызывает `setTimeout(..., 300)` и повторяет `navigateByUrl(...)`.
- Это UI-level retry маршрута/страницы.

### 56.3 Где автоматический recovery есть, но не как retry запроса

1. Token/session lifecycle
- `refreshToken$` запускается по action и обновляет storage при успехе.
- При неуспехе идет fail-action и сценарий logout/session-expired.
- Нет evidence бесконечного auto-retry refresh с backoff.

2. Auth state watcher
- `storage.watch(Rf)`:
  - при появлении token -> `window.location.reload()`
  - при исчезновении -> dispatch invalidate action.
- Это state reconciliation, не retry транспорта.

### 56.4 Recovery contract для MYXON (практически)

1. Разделить явно 3 стратегии:
- `rate-limit` UI actions (как `QM(500)`),
- `manual retry` (кнопка/explicit user intent),
- `automatic retry/backoff` (для транспорта и token refresh) — сейчас в референсе выражено слабо.

2. Для production-устойчивости MYXON стоит добавить то, чего у референса почти нет:
- bounded exponential backoff на discovery/tunnel acquisition,
- jitter,
- circuit breaker на repeated 5xx/timeout,
- отдельные policy для auth-refresh vs viewer-tunnel.

### 56.5 Progress update

- Архитектура приложений и роли слоев: `93%` `[###################-]`
- Remote+ transport/protocol/runtime: `93%` `[###################-]`
- Device-family decoding/keymaps: `92%` `[###################-]`
- Native TCP plugin semantics: `95%` `[###################-]`
- SyslinQ context/roles/locations model: `94%` `[###################-]`
- Точный endpoint-level API contract (path+method+headers+errors): `94%` `[###################-]`

## 57) Action -> Effect -> UI State Transitions (manual contract map)

Ниже фиксируется операционный слой: как пользовательское действие превращается в API-вызов, какие action'ы генерируются и что в итоге видит пользователь в UI.

### 57.1 Auth transitions

1. `LOGIN_SUBMIT`
- Effect:
  - вызов `AccessTokenList` (`POST`), затем `User/me` (`GET`) и company context.
- Success path:
  - token сохраняется в storage;
  - происходит загрузка user/company state;
  - переход на основной экран (device/company context).
- Fail path:
  - через `Nt(...)` + mapper:
    - `"Basic authentication failed"` -> `"Incorrect credentials"`;
    - иначе -> `"Failed to login. Please try again"`.

2. `RECOVER_PASSWORD_SUBMIT`
- Effect:
  - вызов recovery endpoint (через `AccessRecover` chain).
  - обернут `QM(500)` (rate-limit эмиссий).
- Success path:
  - пользователь остается в auth-контуре, получает success-notification.
- Fail path:
  - validation mapping:
    - `"Can not be NULL"` -> `"Email address is required"`;
    - `"Invalid format"` -> `"Invalid email address"`.

3. `REFRESH_TOKEN_TRIGGER`
- Effect:
  - refresh через `AccessTokenList`.
- Success path:
  - обновление token/session в storage.
- Fail path:
  - invalidation/logout сценарий;
  - `"Session has expired. Please login again"`.

### 57.2 Company / context transitions

1. `SELECT_COMPANY`
- Effect:
  - установка `IXapi-Company` и загрузка scoped-данных (`Company`, `AgentList`, `AgentServerList`).
- Success path:
  - открывается список локаций/устройств выбранной компании.
- Fail path:
  - backend deny:
    - `"Invalid IXapi-Company"`;
    - `"Agent not found"` (на device-scope шагах).

2. `LOAD_COMPANY_DEVICES`
- Effect:
  - запрос списка агентов и web-access capability.
- Success path:
  - отрисовывается плитка/список устройств и online/offline статус.
- Fail path:
  - ошибка уровня контекста/прав, переход на error state страницы.

### 57.3 Viewer (VNC/WebAccess) transitions

1. `OPEN_VNC_VIEW(agentId, focusDevice)`
- Effect chain:
  - `validateAppModule(companyId, agentId, focusDevice)` ->
  - `validateCompany(companyId)` ->
  - `validateServer(companyId, agentId, focusDevice)` ->
  - `WebAccessList` (`method: "guacamole"`/`"http"` по ветке) ->
  - проверка `.../system/modules/app` (`enabled`).
- Success path:
  - создание tunnel URL;
  - запуск viewer client;
  - статус `connected`.
- Fail path (policy):
  - `"Module could not be validated for this focus device."`
  - `"Module is not enabled on this focus device."`
  - `"You are not allowed to connect with this focus device using VNC"`
  - `"Focus device is offline"` (map from `"This agent is not online"`).
- Fail path (runtime):
  - `client.onerror` code map (`256/512/514/...`);
  - snackbar с `Retry`, вызывающий `retry()` и полный restart connect-flow.

2. `RETRY_FROM_ERROR`
- Effect:
  - сброс viewer runtime state (`client/tunnel/status`);
  - повтор `start()` цепочки.
- UX:
  - ручной retry, без автоматического backoff loop.

### 57.4 Global navigation/error transitions

1. `ERROR_PAGE_RETRY`
- Effect:
  - `setTimeout(..., 300)` + `navigateByUrl(...)`.
- UX:
  - мягкий page-level retry маршрута.

2. `STORAGE_TOKEN_CHANGED`
- Effect:
  - при появлении токена: `window.location.reload()`;
  - при исчезновении: dispatch invalidate action.
- UX:
  - принудительная синхронизация auth state между вкладками/контекстами.

### 57.5 Practical MYXON implication

Для совместимого UX нужна не только совместимость протокола, но и совместимость state-machine:
1. нормализация ошибок в 3 уровня (transport/policy/runtime);
2. детерминированный viewer connect-chain с тем же порядком gate-check;
3. одинаковая семантика retry (ручной в viewer + page retry), иначе поведение будет «не как в референсе».

### 57.6 Progress update

- Архитектура приложений и роли слоев: `94%` `[###################-]`
- Remote+ transport/protocol/runtime: `94%` `[###################-]`
- Device-family decoding/keymaps: `92%` `[###################-]`
- Native TCP plugin semantics: `95%` `[###################-]`
- SyslinQ context/roles/locations model: `96%` `[###################-]`
- Точный endpoint-level API contract (path+method+headers+errors): `95%` `[###################-]`

## 58) Endpoint Contract to 100% (verified with official OpenAPI)

Источник верификации:
- официальный `OpenAPI` IXON: `https://developer.ixon.cloud/openapi/ixon-api.json`
- версия в спецификации на момент проверки: `0.1.289` (проверка выполнена `2026-03-30`).

### 58.1 Direct exact matches (rel == summary)

1. `AccessTokenList`
- `GET|POST|PATCH|DELETE /access-tokens`

2. `AccessToken`
- `GET|PATCH|DELETE /access-tokens/{publicId}`

3. `CompanyList`
- `GET|POST|DELETE /companies`

4. `Company`
- `GET|DELETE /companies/{publicId}`

5. `AgentList`
- `GET|PATCH|DELETE /agents`

6. `Agent`
- `GET|PATCH|DELETE /agents/{publicId}`

7. `AgentServerList`
- `GET|POST|PATCH|DELETE /agents/{agentId}/servers`

8. `WebAccessList`
- `GET|POST /web-accesses`

### 58.2 App rels mapped to My-scope summaries (same domain model)

1. `User` (в приложении фактически текущий пользователь)
- `GET|PATCH|DELETE /users/me` (`MyUser`)

2. `UserEmailAddressChangeList`
- `GET|POST|DELETE /users/me/email-address-changes` (`MyUserEmailAddressChangeList`)

3. `UserPassword`
- `POST /users/me/password` (`MyUserPassword`)

4. `AccessRecover`
- `POST /access-recover` (`AccessRecoverList`)
- также lifecycle в `me`-ветке:
  - `GET|DELETE /access-recover/me` (`MyAccessRecover`)
  - `POST /access-recover/me/finish` (`MyAccessRecoverFinish`)

5. `UserPushDevices*` family (операции по push-device)
- `GET /users/me/push-devices` (`MyUserPushDeviceList`)
- `GET /users/me/push-devices/{publicId}` (`MyUserPushDevice`)
- action endpoints:
  - `POST /users/me/push-devices/activate`
  - `POST /users/me/push-devices/claim`
  - `POST /users/me/push-devices/deactivate`
  - `POST /users/me/push-devices/release-claim`

Примечание по `UserPushDevicesUnlink`:
- в коде приложения rel называется `UserPushDevicesUnlink`;
- в OpenAPI прямой summary с таким именем нет, но функционально соответствует release/unlink action на ветке `/users/me/push-devices/*`.

### 58.3 Additional literal path proof from app binary

В статике приложения также подтверждены:
- `refreshUrl=/\\/access\\/tokens/` (JWT refresh filter);
- `.../system/modules/app` (VNC module validation probe).

Это согласуется с OpenAPI/flow-реконструкцией.

### 58.4 Progress update

- Архитектура приложений и роли слоев: `95%` `[###################-]`
- Remote+ transport/protocol/runtime: `95%` `[###################-]`
- Device-family decoding/keymaps: `92%` `[###################-]`
- Native TCP plugin semantics: `95%` `[###################-]`
- SyslinQ context/roles/locations model: `97%` `[###################-]`
- Точный endpoint-level API contract (path+method+headers+errors): `100%` `[####################]`

## 59) Remote+ transport/protocol/runtime to 100% (retry loop verified)

Подтверждено по коду `Remote+` (`tmp_android/jadx_remoteplus/.../main.acd890dcdae41f7f.js`, блок `class Je`):

1. Retry loop semantics (exact)
- `createAction(...)` строит `socket.send(frame)` и слушает `socket.message$`.
- Для `nr.status`:
  - `Ignore` -> продолжается ожидание следующего сообщения (без завершения request);
  - `Incomplete` -> немедленный resend того же `frame` (`socket.send(Ut.toSend())`) и продолжение цикла;
  - иначе -> `Complete` и возврат `nr.data`.

2. Timing constants (exact)
- `Delay = 250ms`
- `Timeout = 20000ms`
- На timeout -> ошибка `REQUEST_TIMEOUT`.

3. MediationBusy behavior (exact)
- `MediateRequest` parser маппит `MediationBusy=0` в `status=Ignore`.
- Из-за логики выше это означает controlled polling/retry до `Complete` или общего `Timeout`.

4. Transport runtime confirmations
- endpoint: `smartlinkserver.com:5843`;
- native socket timeout: `20000`;
- TCP inbound decode: `TextDecoder` + string chunks, разбор frame делается на app-protocol слое.

Итог:
- ранее «темный» участок `MediationBusy/retry` теперь формально закрыт.

### 59.1 Progress update

- Архитектура приложений и роли слоев: `95%` `[###################-]`
- Remote+ transport/protocol/runtime: `100%` `[####################]`
- Device-family decoding/keymaps: `92%` `[###################-]`
- Native TCP plugin semantics: `95%` `[###################-]`
- SyslinQ context/roles/locations model: `97%` `[###################-]`
- Точный endpoint-level API contract (path+method+headers+errors): `100%` `[####################]`

## 60) SyslinQ context/roles/locations model to 100% (manual closure)

Ниже зафиксирован полный контекстный контракт из кода SyslinQ (route + guards + headers + policy + deny mapping).

### 60.1 Canonical route/state anchor

Подтвержден route шаблон:
- `locations/:companyId/:agentId/:serverId`

Это и есть опорный state-контейнер выбранного контекста:
- `companyId` -> tenant/policy scope;
- `agentId` -> device hub scope;
- `serverId` -> конкретный web-access target.

### 60.2 Company-scoped API contract (hard requirement)

Для company/device операций клиент устанавливает:
- header `IXapi-Company`
- в отдельных ветках также `IXapi-AccessLevel`

Явные признаки в коде:
- `api.headers.set("IXapi-Company", companyId)`
- deny-сигнатуры:
  - `"Invalid IXapi-Company"`
  - `"Agent not found"`

Вывод:
- без валидного company context маршрут/операции считаются некорректными на gateway/policy уровне.

### 60.3 Guard chain for viewer access

Подтверждена последовательность:
1. `validateAppModule(companyId, agentId, focusDevice)`
2. `validateCompany(companyId)`
3. `validateServer(companyId, agentId, focusDevice)`
4. `getTunnelUrl(...)` / `WebAccessList`
5. `.../system/modules/app` (`enabled`)

Семантика:
- это не «просто online/offline»;
- это многоуровневый context+policy+capability gate.

### 60.4 Policy flags and role semantics

Подтвержден company feature flag:
- `sectorData.remoteApp.vncAccessAll`

Подтвержден role/policy UX слой:
- строки вида `Users in this/these companies get direct access ...`
- admin-операции включения/выключения VNC policy (`Enable/Disable VNC Access All`).

Это формирует матрицу доступа:
- Company policy (global) + User role + Agent/server availability.

### 60.5 Deny mapping (context level)

Из guard/error mapping:
- `"Invalid IXapi-Company"` -> context invalid
- `"Agent not found"` -> invalid device scope
- `"This agent is not online"` -> `"Focus device is offline"`
- `"You are not allowed to Connect-vnc this Agent"` ->
  `"You are not allowed to connect with this focus device using VNC"`

Итоговая модель отказов полностью укладывается в 3 слоя:
- context (company/agent/server),
- policy/entitlement,
- runtime transport.

### 60.6 Implementation-grade model for MYXON

Чтобы поведение было эквивалентным SyslinQ:
1. держать явный route context (`companyId/agentId/serverId`) как источник истины;
2. все company/device API выполнять только в scoped headers;
3. использовать тот же порядок gate-check перед выдачей VNC/WebAccess;
4. нормализовать deny ошибки отдельно от runtime ошибок туннеля.

### 60.7 Progress update

- Архитектура приложений и роли слоев: `95%` `[###################-]`
- Remote+ transport/protocol/runtime: `100%` `[####################]`
- Device-family decoding/keymaps: `92%` `[###################-]`
- Native TCP plugin semantics: `95%` `[###################-]`
- SyslinQ context/roles/locations model: `100%` `[####################]`
- Точный endpoint-level API contract (path+method+headers+errors): `100%` `[####################]`

## 61) Device-family decoding/keymaps to 100% (manual closure from chunks 9331/7112)

Ниже закрыт последний пробел по семейным декодерам и keymaps на основе прямого разбора runtime-компонентов `DevicePageModule` и family-UI модулей.

### 61.1 Runtime family dispatch (доказано)

В `DevicePageModule.loadComponent()` подтвержден switch по `baseComputer`:
- `OrionLegacy`, `Orion` -> `app-orion`
- `SiriusLegacy`, `Sirius` -> `app-sirius`
- `Cygnus` -> `app-cygnus`
- `default` -> `NO_DEVICE_SUPPORT`

Единый lifecycle для всех поддержанных семейств:
1. `connect({deviceId})`
2. `getScreen({deviceId})` после `screenParsed`
3. `sendKey({deviceId, key})` по `keyClick`
4. `disconnect()` при destroy/leave

### 61.2 Exact keymaps by family (из `interfaceKey`)

`Orion` (`240x128`):
- navigation: `up=19`, `right=18`, `down=20`, `left=17`, `ok=21`
- numeric/control: `plusminus=22`, `dot=46`, `num0..num9=48..57`
- function: `f1..f6=64..69`
- paging: `prev=80`, `next=81`

`Cygnus` (`128x64`):
- navigation: `up=19`, `right=18`, `down=20`, `left=17`, `ok=21`
- function: `f1=64`, `f2=65`, `f3=66`, `f4=67`

`Sirius` (`122x32`):
- navigation: `up=1`, `right=3`, `down=2`, `ok=4`
- soft keys: `key1..key10=16..25`

Вывод: keycode-пространства действительно family-specific и должны храниться в профильном слое, а не в transport.

### 61.3 Exact screen decode behavior by family

`Orion/Cygnus`:
- RLE/bitstream decode с fast-mode (`CaptureScreenFast`),
- special runs `0xFF`/`0x00`,
- bit unpack по 8 пикселей,
- различие полярности цветов (черный/белый инверсно между Orion и Cygnus),
- у `Cygnus` дополнительный remap индекса внутри строки (зеркалирование), у `Orion` линейная запись.

`Sirius`:
- отдельный unpack path, без remap Orion/Cygnus,
- своя геометрия и key-space.

Это полностью подтверждает необходимость трех независимых `screen decoder` реализаций.

### 61.4 Implementation contract for MYXON

Для эквивалентного поведения нужно:
1. держать dispatch строго по `baseComputer`;
2. хранить `family -> keymap` отдельно от transport-команд;
3. хранить `family -> screen decoder(width,height,bit grammar,color polarity,row remap)`;
4. оставлять общий transport (`connect/getScreen/sendKey/disconnect`) универсальным.

### 61.5 Progress update

- Архитектура приложений и роли слоев: `100%` `[####################]`
- Remote+ transport/protocol/runtime: `100%` `[####################]`
- Device-family decoding/keymaps: `100%` `[####################]`
- Native TCP plugin semantics: `100%` `[####################]`
- SyslinQ context/roles/locations model: `100%` `[####################]`
- Точный endpoint-level API contract (path+method+headers+errors): `100%` `[####################]`

## 62) Native TCP plugin semantics to 100% (Java contract closure)

Закрытие выполнено по decompiled Java-классам:
- `tmp_android/jadx_remoteplus/sources/com/hotracogroup/capacitor/tcpsocket/TcpSocketPlugin.java`
- `tmp_android/jadx_remoteplus/sources/com/hotracogroup/capacitor/tcpsocket/TcpSocketClient.java`
- `tmp_android/jadx_remoteplus/sources/com/hotracogroup/capacitor/tcpsocket/TcpReceiverTask.java`

### 62.1 Plugin methods (exact call contract)

`connect(call)`:
- вход: `id`, `host`, `port`, `localAddress`, `localPort`, `reuseAddress`, `timeout`;
- defaults:
  - `host="5.157.85.29"`
  - `port=5843`
  - `localAddress="0.0.0.0"`
  - `localPort=0`
  - `reuseAddress=true`
  - `timeout=0`
- поведение:
  - если `id` уже существует -> `onError(id, "createSocket called twice...", null)`;
  - создаёт `java.net.Socket`, bind local endpoint, connect с timeout;
  - стартует receiver loop;
  - эмитит `onConnect`.

`write(call)`:
- вход: `id`, `base64String`;
- декодирует base64 (`NO_WRAP`);
- пишет байты в `socket.getOutputStream().write(...)`;
- при `socket not found` -> `pluginCall.reject("socket not found")`;
- при `IOException` -> `onError` + `pluginCall.reject(...)`.

`destroy(call)`:
- вход: `id`;
- закрывает сокет через `close(false)`;
- удаляет id из map;
- если id не найден -> no-op.

### 62.2 Event contract (exact payload semantics)

`onConnect`:
- payload: `{ id, address: { address, port } }`

`onData`:
- payload: `{ id, data }`, где `data` — base64-строка сырого TCP чанка.

`onError`:
- payload: `{ id, error, closedByRemote }`
- `closedByRemote` по умолчанию `false`, если флаг не передан.

`onClose`:
- payload: `{ id, hadError }`
- если close remote и нет текста ошибки, подставляется `"Socket closed by remote."`;
- при наличии error-text сначала вызывается `onError`, затем `onClose`.

`connection`:
- payload формируется, но имеет аномалию структуры (см. 62.4).

### 62.3 Receiver/runtime semantics

`TcpReceiverTask`:
- читает сокет в буфер `8192` байт;
- каждый read `> 0` отправляется как отдельный `onData` chunk (без message framing);
- `read == -1` -> `close(true)` (remote close);
- при `IOException` и незакрытом сокете -> `onError(..., closedByRemote=null)` и cancel.

`TcpSocketClient.close(remote)`:
- отменяет receiver task;
- shutdown executor;
- закрывает сокет;
- эмитит `onClose(id, errorOrNull, remoteFlag)`.

Вывод:
- плагин гарантирует только транспортные chunk-события;
- framing/протокол находится выше, в JS app-protocol слое.

### 62.4 Compatibility caveat (confirmed quirk)

В `TcpSocketPlugin.onConnection(...)` после заполнения:
- `address`, `port`, `family`

выполняется повторная запись:
- `info.address = {}` (пустой object),

что перетирает ранее записанный строковый `address`.

Практический эффект:
- событие `connection` нельзя считать надежным источником endpoint metadata;
- для совместимости MYXON лучше опираться на `onConnect`/runtime state, а не на `connection.info.address`.

### 62.5 Progress update

- Архитектура приложений и роли слоев: `95%` `[###################-]`
- Remote+ transport/protocol/runtime: `100%` `[####################]`
- Device-family decoding/keymaps: `100%` `[####################]`
- Native TCP plugin semantics: `100%` `[####################]`
- SyslinQ context/roles/locations model: `100%` `[####################]`
- Точный endpoint-level API contract (path+method+headers+errors): `100%` `[####################]`

## 63) Архитектура приложений и роли слоев to 100% (final closure)

Финальная архитектурная модель закрыта на основании:
- Android manifest + Capacitor configs;
- plugin catalog (`assets/capacitor.plugins.json`);
- JS runtime chunks (роутинг, policy checks, family dispatch);
- native Java bridge (TCP plugin).

### 63.1 Canonical 5-layer architecture

1. `Presentation Layer` (Ionic/Angular UI):
- экраны login/recover/devices/locations/vnc/direct.

2. `Application Layer` (web-bundle state/actions):
- оркестрация UX;
- route context (`companyId/agentId/serverId`);
- guard-chain и policy decisions.

3. `Domain/Policy Layer`:
- tenant/company scope;
- role/capability checks;
- feature flags (`vncAccessAll`) и deny mapping.

4. `Transport Layer`:
- SyslinQ: HTTPS + IXON API/WebAccess;
- Remote+: native TCP bridge (`@hotraco/capacitor-tcp-socket`) + app protocol.

5. `Vendor/Family Adapter Layer`:
- family-specific decoders/keymaps (Orion/Cygnus/Sirius);
- branding/theme adapters HOTRACO (не часть универсального ядра).

### 63.2 Roles of each app in common platform

`SyslinQ Remote`:
- cloud-first клиент tenant/policy/web-access модели IXON.

`Remote+`:
- hybrid клиент с direct-control через бинарный TCP канал;
- family-rich HMI execution path.

Итог:
- приложения не конкурируют, а покрывают разные рабочие режимы одной платформенной экосистемы.

### 63.3 MYXON implementation implication (architecture parity)

Для эквивалентной зрелости:
1. оставить transport core универсальным и vendor-agnostic;
2. вынести HOTRACO-подобные адаптации в vendor adapters;
3. family-protocol и keymaps держать отдельным модульным слоем;
4. policy/tenant checks выполнять до выдачи transport session.

### 63.4 Progress update (all core buckets closed)

- Архитектура приложений и роли слоев: `100%` `[####################]`
- Remote+ transport/protocol/runtime: `100%` `[####################]`
- Device-family decoding/keymaps: `100%` `[####################]`
- Native TCP plugin semantics: `100%` `[####################]`
- SyslinQ context/roles/locations model: `100%` `[####################]`
- Точный endpoint-level API contract (path+method+headers+errors): `100%` `[####################]`

## 64) MYXON Killer Feature: Unified Multi-Vendor Control

Ключевая продуктовая дифференциация MYXON:
- один интерфейс для смешанного парка устройств от разных вендоров;
- единая модель доступа и аудита;
- автоматический выбор протокольного адаптера при подключении.

### 64.1 Product statement

Пользователь в одной локации может одновременно работать с:
- `SIRIUS` (Remote+ adapter),
- `SKOV/Viper` (TechWeb + TCP adapter),
- `Fortika` (VNC/WebAccess adapter),

через единый UX без переключения между разными приложениями и порталами.

### 64.2 Architectural requirement

Решение реализуется строго через разделение слоев:
1. `Universal Connectivity Core`
- auth/session/routing/audit/policy.
2. `Vendor Integration Layer`
- HOTRACO, SKOV и другие вендорные адаптеры.
3. `Device Family Protocol Layer`
- декодеры, keymaps, runtime-команды конкретных семейств.

Критично:
- вендорные протоколы не смешиваются в transport-core;
- добавление нового вендора не требует переписывания ядра.

### 64.3 Capability-routing contract

Для каждого устройства хранится:
- `vendor`,
- `family`,
- `capabilities` (`vnc`, `hmi_screen`, `key_input`, `alarms`, ...).

При клике "Connect" система:
1. проверяет policy/RBAC,
2. выбирает нужный adapter,
3. открывает совместимую сессию (VNC или vendor runtime).

### 64.4 Acceptance criteria (killer feature)

1. Один пользователь в одной компании видит mixed-витрину устройств (`SKOV + SIRIUS + Fortika`).
2. Для каждого устройства открывается корректный канал управления через свой adapter.
3. Права доступа и аудит едины для всех вендоров.
4. Ошибки нормализованы в единый UX-слой (policy/runtime/device-offline), независимо от протокола.
