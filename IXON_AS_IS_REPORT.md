# IXON AS-IS Report (для концепции MYXON)

Дата: 28 March 2026
Статус: Черновик v1 (на основе открытых официальных материалов IXON)

## 1. Цель отчета
Зафиксировать текущее состояние (AS-IS) референсной системы IXON по направлениям:
- onboarding и регистрация устройств,
- UX передачи/привязки устройства,
- роли cloud/local интерфейсов,
- требования сети и безопасности,
- API-контур (edge и cloud),
- ограничения исследовательной выборки.

## 2. Использованные источники
1. IXrouter3 Installation Manual (PDF):
https://www.ixon.cloud/hubfs/ixrouter3-installation-manual.pdf

2. IXON Cloud Security Guide (PDF):
https://www.ixon.cloud/hubfs/IXON%20Cloud%20Security%20Guide.pdf

3. IXON Developer Documentation (portal):
https://developer.ixon.cloud/

4. IXrouter3 Router API:
https://developer.ixon.cloud/docs/router-api
https://developer.ixon.cloud/docs/router-api-login

5. IXON API prerequisites:
https://developer.ixon.cloud/docs/ixon-api-prerequisites

6. IXON Downloads (white papers / ebooks / guides):
https://www.ixon.cloud/downloads

7. Trust Center / security positioning:
https://trust.ixon.cloud/
https://www.ixon.cloud/knowledge-hub/trust-center

## 3. AS-IS: Onboarding и регистрация устройства
### 3.1 Базовый cloud-first сценарий
Подтвержденный путь ввода IXrouter3:
1. Создается аккаунт/компания в IXON Cloud.
2. Во Fleet Manager добавляется устройство.
3. Из cloud скачивается файл `router.conf`.
4. Файл переносится на USB-накопитель.
5. USB вставляется в IXrouter3.
6. Устройство регистрируется в аккаунте автоматически.

Источник: Installation Manual.

### 3.2 Локальный интерфейс как часть UX
Подтверждено наличие local UI:
- адрес: `http://IXrouter3.lan`,
- сценарии: базовая регистрация (если не зарегистрирован), сетевые настройки, firewall,
- пароль для входа берется с наклейки устройства.

Источник: Installation Manual.

### 3.3 Сигналы о статусе регистрации/привязки
По LED-поведениям из мануала подтверждается наличие статусов:
- ранее зарегистрирован,
- удален из cloud (требуется повторная регистрация),
- конфигурационные ошибки регистрации.

Вывод: lifecycle регистрации явно контролируется состояниями устройства, не только cloud UI.

## 4. AS-IS: UX transfer/claim (текущее понимание)
1. На физической наклейке устройства присутствуют:
- `Device ID`,
- одноразовый activation code/key,
- указание на transfer в cloud-аккаунт (через URL/QR).

2. Это формирует UX-модель:
- device pre-registered,
- account transfer / claim выполняется отдельно,
- activation code имеет one-time семантику.

3. Риск в многоуровневом канале продаж:
- если pre-registration сделан верхним дилером,
- а внедрение выполняет нижний дилер/интегратор/конечный клиент,
- возникают ручные процессы согласования владения и привязки.

Примечание: это аналитический вывод для UX (инференс), а не дословное заявление из документа.

## 5. AS-IS: Сеть и безопасность
### 5.1 Сетевая модель
Подтверждено:
- нет необходимости открывать inbound-порты на объекте,
- устройство работает через исходящие подключения.

Типовые outbound-порты, указанные в материалах:
- `443/TCP` (HTTPS),
- `1194/UDP` (VPN/OpenVPN),
- `8443/TCP`,
- `53/TCP+UDP` (DNS).

### 5.2 Каналы взаимодействия
Подтверждено разделение каналов:
- HTTPS: регистрация и управляющие операции,
- MQTT: конфигурация/события/обмен данными,
- VPN: удаленный защищенный доступ.

### 5.3 Compliance и governance
В Security Guide заявлены ISO/IEC сертификации и практики (2FA, least privilege, audit trail).
Также IXON позиционируется как managed cloud-модель.

## 6. AS-IS: API-контур
### 6.1 Local device API (IXrouter3)
Подтверждено:
- JSON-RPC 2.0 endpoint `/ubus`,
- null-session из 32 нулей ограничена логином и обзором,
- для расширенных вызовов нужен session token после login.

### 6.2 Cloud API (APIv2)
Подтверждено:
- обязательные заголовки версии/приложения/авторизации/компании,
- идентификация сущностей через `publicId`,
- структура API пригодна для интеграций и automation сценариев.

## 7. Ограничения исследования
1. В текущем проходе не удалось полноценно извлечь часть статей с `support.ixon.cloud` из-за проблем рендера.
2. Поэтому детализация некоторых UX-сценариев transfer/approval может быть неполной.
3. Выводы отчета валидны как AS-IS v1 и требуют AS-IS v2 после выгрузки материалов support-базы.

## 8. Выводы для концепции MYXON
1. Сильная сторона IXON: быстрый bootstrap (cloud + USB + local fallback + label credentials).
2. Слабое место для multi-tier канала: возможный разрыв claim/ownership между уровнями дилеров.
3. Обязательный фокус MYXON:
- channel-aware claim orchestration,
- минимизация ручной эскалации,
- прозрачная привязка устройства к tenant и site в рамках одного UX-потока.

## 9. Что добавить в AS-IS v2
1. Таблица journey: `Шаг -> Актор -> Текущее поведение IXON -> Риск -> Возможность для MYXON`.
2. Детализация ролей канала: distributor/dealer/integrator/end-customer.
3. Карта состояний device claim/transfer (state machine).
4. Сводка экранов UX и текстов ошибок/подсказок.

## 10. Дополнение по статье Support: "Does my machine work with IXON Cloud?"
Источник:
https://support.ixon.cloud/s/article/Does-my-machine-work-with-IXON-Cloud

Что подтверждено по содержанию статьи (по скриншоту):
1. Базовый ответ IXON: если у машины есть Ethernet-порт, то в большинстве случаев она совместима.
2. Если Ethernet нет, возможен вариант через serial-to-USB кабель (только VPN).
3. Для удаленного доступа выделены отдельные режимы:
- VPN,
- HTTP EasyControl,
- VNC EasyControl,
- Live/Historical data + Alarms & Notifications.
4. По VPN прямо указано ограничение/особенность:
- IXON VPN на IXrouter включает весь L3-трафик, UDP broadcast и выбранный L2-трафик (примеры: Siemens PROFINET, B&R SNMP);
- для IXagent указана совместимость с L3 и L2 трафиком.
5. Для HTTP EasyControl и VNC EasyControl нужен совместимый HTTP/VNC сервер на машине.
6. Для Machine Data требуется совместимость с поддерживаемыми промышленными протоколами (например Modbus TCP или OPC UA).

UX-выводы для MYXON:
1. Нужен pre-check совместимости до покупки/внедрения:
- есть ли Ethernet,
- нужен ли VPN или EasyControl,
- поддерживаются ли протоколы данных.
2. Нужен onboarding-экран "Compatibility check" с ветвлением сценария:
- Remote access only,
- Remote access + Data,
- Data only.
3. Нужен явный "protocol capability matrix" в UI (что работает по VPN/L2/L3, что требует native-коннекторы).
4. Тексты в стиле "generally yes" удобны для маркетинга, но в продукте нужно давать детерминированный результат по чек-листу.

## 11. Login UX + Privacy UX (по portal.syslinq.co)
Источник (экран логина):
https://portal.syslinq.co/portal/login

Источник (текст privacy statement, предоставлен пользователем):
- заголовок компании/white-label: `Hotraco Agri b.v.`
- версия политики: `Version 1.1`
- дата: `8 November 2021`

### 11.1 Что подтверждено по UX логина
1. Экран минималистичный и одноцелевой:
- поле `E-mail address`,
- поле `Password`,
- чекбокс `Keep me logged in`,
- ссылка `Forgot password?`,
- primary CTA `Log in`,
- ссылка `Privacy statement`.
2. Присутствует white-label паттерн:
- tenant/company name отображается отдельно от платформенного бренда.
3. Политика приватности доступна прямо из login-screen (без входа в систему).

### 11.2 Что подтверждено по Privacy/Cookie политике
1. Описаны категории данных (IP, имя, email, дата/время визита, локация).
2. Указаны цели обработки:
- улучшение сайта,
- предоставление и мониторинг сервисов.
3. Указан регион хранения данных: страны EEA.
4. Описаны основания передачи третьим сторонам:
- контрактные обработчики,
- необходимость для оказания сервиса,
- требования закона.
5. Указаны категории обработчиков:
- IT hosting providers,
- IT monitoring providers.
6. Описаны права субъекта данных и privacy contact (`privacy@ixon.cloud`).
7. Cookie-блок заявляет обязательные функциональные cookies (без отключения).

### 11.3 Выводы для MYXON (UX и доверие)
1. На login-экране MYXON нужен такой же "минимальный trust package":
- понятный вход,
- восстановление доступа,
- прозрачная ссылка на privacy до авторизации.
2. White-label должен быть first-class:
- название клиента/дилера + бренд платформы одновременно.
3. В privacy-документации MYXON стоит улучшить относительно референса:
- явная матрица ролей данных (controller/processor) для multi-tenant channel,
- retention schedule по типам данных,
- changelog версий policy.

## 12. Logged-in Device UX + VNC flow (по скриншотам portal.ixon.cloud)
Контекст:
- ссылка device web access: `.../portal/devices/{deviceId}/web-access/vnc/{resourceId}`
- пользователь уже авторизован в tenant-branded портале (SyslinQ).

### 12.1 Что подтверждено по списку устройств
1. Есть централизованный экран `Devices` с поиском и фильтром сверху.
2. Карточки устройств показывают:
- имя устройства,
- online/offline индикатор,
- быстрые action-кнопки (`Connect`, целевые web resources).
3. Offline-устройства видны в том же списке, но действия визуально disabled.

### 12.2 Что подтверждено по странице конкретного устройства
На device dashboard одновременно видны:
1. `VPN` блок:
- индикатор доступности,
- primary action `VPN connect`.
2. `Web Access` блок:
- список опубликованных endpoint-ресурсов (иконки VNC/HTTP),
- запуск удаленного доступа из того же экрана.
3. Карточка устройства:
- `Status`,
- `Serial number`,
- `Firmware`,
- `Hardware`,
- `Customer`.
4. `Cloud connection status` с вкладками:
- `Status`,
- `Logbook`,
- `VPN data usage`.
5. `Event log`:
- поля `Who / When / What`,
- фиксируются действия типа:
  - `Changed the configuration`,
  - `Pulled the device to this company`,
  - события подключений VNC/HTTP.
6. `Service logbook` как отдельная зона заметок/сервисных записей.

### 12.3 Поведение online/offline
1. Для offline устройства:
- VPN/WebAccess действия недоступны или неактивны,
- в cloud status у соединений показывается `Last active`.

## 13. Идентификация устройства в IXON Agent (по реверсу + конфигам)
Основание:
- реверс-функции из `ixagent` (декомпиляция),
- конфиги из `firmware_dump` и `ixon_dump_full`,
- LLM-выводы в `reverse_agent/memory/llm_analysis_latest.json`.

### 13.1 Уровень 1: локальная идентичность устройства (system identity)
Подтверждено в коде:
1. Агент читает метаданные устройства из:
- `/proc/ixrouter` (ключи вида `version`, `wan`, `serial`),
- `/etc/banner`,
- `/etc/openwrt_version`,
- `/etc/openwrt_release`.
2. Ключи из `/proc/ixrouter` приводятся к нижнему регистру перед сопоставлением (каноникализация ключей).
3. На старте формируется строка `agentName` с включением OpenWrt/IXagent-версии (в декомпиляции видны фрагменты вроде `OpenWRT/` и `IXagent/0.5.14`).

Практический смысл:
- устройство получает стабильный локальный "паспорт" (версии, serial, канал/wan-атрибуты),
- эти поля пригодны для телеметрии, UI и первичной инвентаризации.

### 13.2 Уровень 2: cloud-идентичность агента (credential identity)
Подтверждено по конфигам:
1. Используются предзаданные идентификаторы и секреты:
- `agent_public_id`,
- `agent_shared_secret`,
- `application_public_id`,
- `application_shared_secret`,
- `agent_key_pair`,
- root keys (доверенные ключи/якоря).
2. В конфиге указан cloud entrypoint (`https://...:443`), что указывает на outbound-auth модель.

Практический смысл:
- облако идентифицирует агент не по IP/MAC, а по криптографическим/учетным артефактам,
- это соответствует pre-provisioned onboarding модели.

### 13.3 Уровень 3: идентификация опубликованных сервисов "за агентом"
Подтверждено по сетевым правилам:
1. Есть `vpn` интерфейс (`tap+`) и forwarding `vpn <-> lan`.
2. Есть DNAT/redirect правила из VPN-зоны к локальным host:port.

Практический смысл:
- IXON различает:
  - сам edge-agent (доверенный узел),
  - ресурсы/машины за ним (публикуемые endpoint'ы VNC/HTTP/др. через mapping).

### 13.4 Что уверенно подтверждено и что пока гипотеза
Подтверждено (high confidence):
1. Парсинг локальных identity-источников (`/proc/ixrouter`, banner, OpenWrt release/version).
2. Каноникализация ключей (`tolower`) перед логикой сопоставления.
3. Наличие pre-provisioned cloud credentials/keys в конфиге.
4. VPN/LAN связка и порт-маппинг для удаленного доступа к локальным ресурсам.

Пока не подтверждено полностью (medium/low confidence):
1. Точный формат подписи каждого API-запроса (полная canonical string и HMAC/EVP sequence во всех ветках кода).
2. Полный server-side workflow claim/ownership на стороне IXON Cloud (это вне бинаря edge-агента).

### 13.5 Вывод для MYXON
Для совместимого UX и архитектуры MYXON нужно закладывать такую же трехуровневую модель идентификации:
1. `Device System Identity` (serial/version/hardware/network metadata),
2. `Agent Cloud Identity` (public_id + secrets + key material),
3. `Published Resource Identity` (какие локальные сервисы и куда маппятся).

И отдельным этапом в MVP спланировать подтверждение auth-пайплайна через:
- более глубокий реверс crypto-path,
- controlled runtime-трассировку handshake/requests.

## 14. Workflow простым языком (для неразработчика)
Ниже тот же процесс без технических терминов.

### 14.1 Как устройство "появляется" в системе
1. На заводе/у поставщика роутеру заранее дают "паспорт" (ID и ключи).
2. Роутер ставят на объект и включают.
3. Он сам выходит в интернет и связывается с облаком IXON.
4. Облако проверяет, что это "свой" роутер (по его ID/ключам), и привязывает к аккаунту компании.

Итог:
- роутер не нужно "ловить" снаружи по белому IP,
- он сам инициирует безопасное подключение к облаку.

### 14.2 Как IXON понимает, что это именно этот роутер
IXON смотрит сразу на несколько вещей:
1. Данные самого устройства (серийник, версия, модель, сетевые признаки).
2. Секретные ключи/идентификаторы, зашитые для облака.
3. Список "машин за роутером", которые он публикует для удаленного доступа (например VNC/HTTP).

Итог:
- система отличает и сам роутер, и конкретные сервисы за ним.

### 14.3 Как инженер подключается к оборудованию
1. Инженер входит в веб-портал IXON.
2. Видит список устройств (online/offline).
3. Выбирает нужное устройство и нужный тип доступа (например VNC).
4. Портал открывает соединение через облако и роутер к локальной машине на объекте.

Итог:
- инженер работает через браузер,
- на объекте обычно не нужно открывать входящие порты "в интернет".

### 14.4 Что важно для бизнеса (не только для ИТ)
1. Ускоряется запуск объектов: меньше ручной сетевой настройки.
2. Легче поддержка: доступ к машине из одного портала.
3. Проще контроль: видно кто, когда и к какому устройству подключался.
4. В дилерской цепочке нужен прозрачный процесс передачи владения устройством (claim/transfer), иначе возникают задержки и ручные согласования.

### 14.5 Как это перевести в MYXON
Простая целевая логика для пользователя:
1. "Добавить устройство" -> скан QR/ввод кода.
2. "Привязать к компании и объекту" -> 2-3 шага мастера.
3. "Проверить связь" -> статус online и тест доступа.
4. "Подключиться" -> кнопка VNC/HTTP без сложной сетевой настройки.

Главная идея:
MYXON должен быть понятен как "удаленный доступ к машине в 3 клика", а вся сложная сеть и безопасность должны оставаться внутри платформы.
2. Для online устройства:
- доступны подключения VPN и Web Access,
- показываются активные cloud endpoints (пример: региональные серверы).

### 12.4 UX вокруг VPN клиента (desktop dependency)
Подтвержден error-flow:
- модальное окно `VPN Client` с сообщением `No installation found`.
- предлагаются действия:
  - `Try again`,
  - `Download installer`.

Вывод: UX учитывает отсутствие локального VPN-клиента и содержит встроенный recovery-путь без выхода из контекста устройства.

### 12.5 VNC web session UX
Подтверждено:
1. VNC запускается в браузере как отдельная web-сессия.
2. Есть базовые действия сессии (масштаб/панель/закрытие).
3. Есть экранная клавиатура/комбинации клавиш (для удаленного HMI/PLC UI).
4. Пользователь работает с реальным HMI-экраном машины без отдельного native VNC клиента.

### 12.6 UX-выводы для MYXON
1. Нужен unified device workspace:
- статусы соединений,
- web-access endpoints,
- журнал действий и сервис-лог в одном месте.
2. Нужны явные `online/offline` состояния с деградацией действий, а не только ошибка по клику.
3. Для VPN обязателен guided dependency flow (`client missing -> installer -> retry`).
4. Для Web Access/VNC нужен browser-native запуск и системный audit след (кто/когда/к какому ресурсу подключался).
5. Событие вида `Pulled the device to this company` критично для канального UX:
- это подтверждает, что transfer/claim операции должны быть явно видимы в event timeline.

## 13. RND server evidence map (локальные материалы проекта)
Контекст:
- изучены материалы в директории `RND server` репозитория MYXON;
- цель: выделить подтвержденные факты для AS-IS IXON и UX/архитектуры MYXON.

### 13.1 Карта источников (что реально полезно)
1. Логи устройства:
- `RND server/logs/17086062.log`
- `RND server/logs/17086062-20241116T064119Z.log`
2. Android-артефакты:
- `RND server/Приложения андроид/SyslinQ Remote_1.3.0_APKPure/*`
- `RND server/Приложения андроид/Remote+_1.2.0_APKPure/*`
3. Desktop-интеграция:
- `RND server/Novus/Ixon.dll`
- `RND server/Novus/Api 2.dll`
- `RND server/Novus/Api.txt` (по факту DLL, не текст)
4. UX/веб-референсы:
- `RND server/Novnc.html`
- `RND server/account~configuration~login~overview.272054c6.js`
- `RND server/In.jpeg`, `RND server/Out.jpeg`, `RND server/nat_overview-toster.png`

### 13.2 Подтвержденные факты из логов IXrouter/IXagent
1. Версии стека (на момент логов):
- IXrouter3 `0.17.1 r1`,
- ixagent `0.5.18`,
- OpenVPN `2.4.5`,
- OpenSSL `1.0.2u`.
2. Подтверждена VPN-зона и правила форвардинга в LAN:
- `vpn:2000 -> 192.168.27.11:5900` (VNC),
- `vpn:2010 -> 192.168.27.11:5843`,
- `vpn:2020 -> 192.168.27.11:8080`.
3. Подтверждена модель `vpn <-> lan` forwarding на уровне firewall/config.
4. В логах присутствуют USB/hotplug события и сообщения типа `no upgrade on USB device`.

Вывод:
- референсная архитектура не ограничивается "просто VPN", а включает publish локальных сервисов через управляемые VPN-порты.

### 13.3 Подтвержденные факты из Android-пакетов
1. `SyslinQ Remote 1.3.0`:
- package: `com.hotraco.syslinqremote`,
- гибридное приложение на Capacitor (`webDir: dist`),
- подключены push-notifications (Firebase Messaging),
- app ориентирован на удаленный доступ/операции в облаке.
2. В web bundle приложения присутствует Guacamole/noVNC стек (browser VNC session).
3. `Remote+ 1.2.0`:
- package: `com.hotraco.remoteplus`,
- также Capacitor,
- больше device-level разрешений (camera/audio/location/storage),
- есть TCP socket plugin (`@hotraco/capacitor-tcp-socket`).

Вывод:
- remote UX поддерживается не только web-порталом, но и mobile-гибридом с встроенными web/VNC-компонентами.

### 13.4 Подтвержденные факты из desktop-интеграции (Novus DLL)
По строкам в `Ixon.dll`/`Api 2.dll` видны доменные сущности и API-поведение:
1. Токен-флоу:
- `GetAccessToken`, `DeleteAccessToken`, `loginToken`, `accessToken`.
2. Бизнес-сущности:
- `IxonDevice`, `IxonLocation`, `IxonCompany`.
3. Методы интеграции:
- `GetIxonDevicesForLocation`,
- `GetLocationsWithDevices`,
- `UpdateIxonDevicesUrls`.

Вывод:
- в референсе явно используется модель `auth -> locations -> devices -> access URLs`, полезная для будущей MYXON domain model.

### 13.5 Состояние папки "Проект к реализации"
1. Внутри есть каркас `client/server/src`, но ключевые `.js/.json/.md` файлы в основном пустые (`0 bytes`).
2. Для текущего AS-IS исследования эти файлы не несут содержательных продуктовых данных.

### 13.6 Итоговые выводы для MYXON (по локальным материалам)
1. Обязателен unified device workspace:
- статус устройства,
- VPN/Web access действия,
- cloud connection status,
- event/audit log,
- service logbook.
2. Для web access нужны first-class сценарии VNC/HTTP через браузер, без обязательного native VNC-клиента.
3. Для VPN нужен UX с обработкой отсутствия локального VPN-клиента и встроенным recovery (`download installer -> retry`).
4. Для multi-tier канала transfer/claim события должны быть видимы в timeline и в аудит-логе.

## 14. Strategic constraints before implementation (учесть обязательно)
Источник: внутреннее саммари проекта (предоставлено пользователем).

### 14.1 Целевой контур продукта
1. Продуктовая цель:
- российская платформа удаленного доступа к промышленному оборудованию (аналог IXON),
- browser-first доступ без установки клиентского ПО у инженера,
- работа при NAT и без белого IP на объектах.
2. Базовые режимы:
- `DirectVPN` (полный сетевой доступ),
- `EasyControl` (быстрый VNC/HTTP доступ через web).

### 14.2 Архитектурный baseline для MVP
1. Edge/agent:
- OpenWRT/Linux агент,
- исходящее подключение к облаку,
- FRPC как транспортный клиент.
2. Cloud core:
- сервер в РФ с белым IP,
- FRPS + backend + PostgreSQL,
- Nginx как reverse proxy и TLS termination.
3. Clientless access:
- Apache Guacamole/guacd для VNC/HTTP/RDP/SSH в браузере.

### 14.3 Сетевые и региональные требования (РФ)
1. Транспорт по умолчанию:
- FRP через WebSocket на `443` для устойчивости к DPI/блокировкам.
2. Адресация:
- приоритет пути `https://portal.<domain>/device/<sn>` (стабильнее в РФ),
- поддомены как вторичный/опциональный режим.
3. DNS-риски:
- минимизировать зависимость от динамических поддоменов,
- использовать контролируемую DNS-стратегию (TTL/резолверы/мониторинг резолвинга).

### 14.4 Identity, onboarding и channel model
1. White-label onboarding:
- уникальные `SN + Activation Key`,
- QR-код на активацию,
- привязка устройства к tenant через flow claim/transfer.
2. Роли:
- `SuperAdmin`, `Dealer`, `Customer`, `Engineer`.
3. Канальные требования:
- дилерская передача вниз по цепочке,
- аудит всех операций transfer/claim.

### 14.5 Security baseline (обязательный минимум)
1. Токенизация агентов (`SN + secret/token`), отказ при неверном токене.
2. TLS end-to-end на внешнем периметре.
3. RBAC и изоляция устройств между tenant-пользователями.
4. 2FA/SSO как целевая траектория (например Keycloak на следующих этапах).

### 14.6 MVP scope and acceptance criteria (фикс)
MVP должен подтверждать:
1. Агент за NAT стабильно подключается к серверу.
2. Строгая tenant-изоляция: пользователь A не видит устройства пользователя B.
3. HMI/контроллер открывается в браузере без доп. ПО.
4. Устройство появляется в админке по SN со статусом online/offline.
5. Неверный токен агента отклоняется.
6. Статус offline фиксируется не позже ~1 минуты после потери связи.
7. Внешний доступ работает через HTTPS/443 с валидным сертификатом.

### 14.7 Deployment model
1. SaaS-режим (РФ cloud) для стандартных клиентов.
2. On-Prem (Docker stack) для холдингов с требованием data-perimeter.
3. Лицензионный контроль для on-prem без вывода эксплуатационных данных наружу.

### 14.8 Риски, которые нельзя игнорировать
1. DNS/резолвинг динамических доменов.
2. DPI/блокировки VPN-протоколов.
3. Канальные конфликты ownership/claim.
4. Рост рисков безопасности при масштабировании без раннего audit+RBAC.

### 14.9 Decision note
Эти ограничения и решения считаются входными рамками перед стартом разработки и должны использоваться как обязательные допущения при проектировании TO-BE архитектуры MYXON.
