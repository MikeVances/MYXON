

# MYXON

## Цель
Собрать инженерные наблюдения по устройствам класса IXON и выделить паттерны, которые можно использовать при проектировании собственного аналога: edge-gateway + recovery layer + control plane.

---

## Что уже подтверждено по устройству IXrouter

### 1. Аппаратная база и загрузчик
По UART удалось войти в bootloader и посмотреть низкий уровень.

Подтверждено:
- устройство: **IXrouter3**
- платформа: **MediaTek MT7621A**
- ОЗУ: **256 MB RAM**
- ОС: **Linux 4.14.167 (OpenWrt-based)**
- загрузчик: **U-Boot 1.1.3**
- UART-консоль загрузчика наблюдалась на скорости **57600**
- штатная точка входа в консоль по данным разработчиков: **UART Console, 115200 bps**
- prompt загрузчика: `MT7621 #`

Из вывода:

```text
U-Boot 1.1.3 (Dec 21 2017 - 10:47:42)
bootcmd=tftp
bootdelay=1
ipaddr=192.168.1.1
serverip=192.168.1.2
*** Warning - bad CRC, using default environment
```

### 1.1. Уточнение от разработчиков
По уточнённым данным от разработчиков подтверждено:
- логин в систему: **root**
- пароль: **TR0OJ2YyTs**
- штатная точка входа: **UART Console (115200 bps)**

Практический вывод:
- ранее на UART мы работали в bootloader на **57600**, что подтверждает как минимум скорость для U-Boot
- для входа в Linux userspace нужно отдельно проверить консоль на **115200**, так как разработчики указывают именно эту скорость как штатную для system console
- наличие штатных учетных данных означает, что userspace-доступ можно исследовать без модификации flash и без обхода аутентификации

### 2. Важные выводы по архитектуре
Это очень ценно для MYXON, потому что показывает: IXON-подобное устройство построено не на каком-то «магическом» железе, а на вполне типовом embedded-стеке.

Что видно:
- используется массовый SoC, подходящий для роли edge-router / gateway
- загрузчик очень простой и минималистичный
- recovery-логика заложена прямо в bootloader
- текущее окружение bootloader у устройства дефолтное, так как сохранённое env повреждено или не читается

---

## Наблюдения по bootloader

### Поддерживаемые команды
Из `help` и `help spi` подтверждено наличие таких возможностей:
- `tftpboot`
- `tftpd`
- `spi`
- `erase`
- `setenv`
- `saveenv`
- `version`
- `md`

Подсказка по SPI:

```text
spi spi usage:
  spi id
  spi sr read
  spi sr write <value>
  spi read <addr> <len>
  spi erase <offs> <len>
  spi write <offs> <hex_str_value>
```

Подсказка по TFTP:

```text
tftpboot [loadAddress] [bootfilename]
```

### Что это означает
Bootloader умеет:
- читать SPI flash
- стирать области flash
- писать значения во flash
- загружать данные по TFTP

Это значит, что у устройства есть полноценный recovery-путь на уровне загрузчика.

Важно: данные от разработчиков позволяют разделить два уровня доступа:
- **bootloader / U-Boot** — уже подтверждён нами через UART
- **Linux userspace** — вероятная штатная консоль на **115200 bps** с логином **root** и паролем **TR0OJ2YyTs**

---

## Ключевые инженерные паттерны для MYXON

### Паттерн 1. Edge-устройство может быть построено на обычной embedded Linux платформе
Вывод: для аналога IXON не нужен «специальный промышленный супер-компьютер». Основа может быть такой:
- Orange Pi
- роутерный SoC
- другой SBC / embedded Linux узел

Главное — не железо, а архитектура ПО и recovery.

### Паттерн 2. Recovery обязательно должен существовать ниже userspace
У IXrouter recovery-логика начинается уже в bootloader:
- UART
- TFTP
- default network profile для восстановления

Для MYXON это означает, что нужно закладывать минимум:
- UART/debug access
- bootloader recovery mode
- стандартную процедуру сетевого восстановления
- fallback defaults, если конфиг или env повреждены

### Паттерн 3. Bootloader должен быть тупым, но надежным
Устройство показывает правильный принцип:
- bootloader минимальный
- вся умная логика живет уже в Linux userspace
- recovery есть, но без сложной бизнес-логики внутри bootloader

Для MYXON:
- не раздувать bootloader
- не переносить туда контрольную плоскость
- оставить в bootloader только старт, чтение flash, recovery и базовую сетевую загрузку

### Паттерн 4. Нужна стандартизированная recovery-сеть
По env видно:
- `ipaddr=192.168.1.1`
- `serverip=192.168.1.2`

Это очень сильный паттерн: recovery должен иметь заранее известные дефолтные адреса.

Для MYXON можно принять похожую модель, например:
- edge device в recovery mode: `192.168.8.1`
- recovery host/toolbox: `192.168.8.2`

Это резко упрощает сервис и восстановление.

### Паттерн 5. Default environment / sane defaults обязательны
Вывод `bad CRC, using default environment` показывает важный принцип:
- даже при поврежденном env устройство не умирает
- оно стартует на разумных дефолтах
- оно остается доступным для восстановления

Для MYXON это must-have:
- дефолтная сеть
- дефолтный recovery path
- дефолтная логика безопасного старта

---

## Как это разложить в архитектуру MYXON

### Уровень A. Boot / Recovery Layer
Минимальный слой:
- U-Boot или аналог
- UART-консоль
- recovery по TFTP
- fallback env
- безопасные default settings

### Уровень B. Base OS / Edge Runtime
На Linux-слое должны жить:
- сеть
- VPN / tunnel agent
- watchdog
- local service proxy
- update client
- local management agent

### Уровень C. Control Plane
На серверной стороне MYXON должны быть:
- реестр устройств
- учет объектов
- привязка устройства к организации / клиенту / объекту
- выдача конфигов
- удаленный доступ к web UI / SSH / локальным сервисам
- статусы online/offline
- журнал действий

Главный вывод:
**ценность IXON-подобной системы находится не в железе, а в control plane + identity/bootstrap + recovery discipline.**

---

## Что уже стало понятно про IXON как класс решения

IXON-подобная архитектура = это не просто роутер.

Это комбинация:
- **Edge Node**
- **Recovery Layer**
- **Control Plane**

То есть MYXON надо мыслить не как «роутер с VPN», а как:

**управляемый edge-gateway с безопасным bootstrap, recovery и удаленным control plane**.

---

## UX-паттерн для MYXON: пред-регистрация и transfer устройства

Наклейка на корпусе IXON показывает очень сильный UX-паттерн, который нужно повторить в MYXON:
- устройство уже существует в облачном реестре до первого включения;
- у устройства есть физический идентификатор и одноразовый код активации;
- привязка к компании делается коротким "transfer" флоу через QR или ручной ввод.

Что переносим в MYXON как обязательный UX:
- Наклейка на устройстве:
  - `Device ID` (читаемый текстом);
  - `Activation Key` (одноразовый, one-time use);
  - QR-код на deep-link вида `myxon.cloud/transfer?device=...&code=...`.
- Экран "Transfer device":
  - поля `Device ID` и `Activation Key`;
  - кнопка `Scan QR`;
  - подтверждение "устройство будет привязано к Company X".
- Проверки до привязки:
  - устройство существует в pre-registered inventory;
  - код не использован и не просрочен;
  - устройство не заблокировано и не архивировано;
  - запрос делает пользователь с правом `device.claim`.
- Результат:
  - успешная привязка устройства к tenant/company;
  - запись аудита (кто, когда, откуда, какой device ID);
  - code/state переводится в `consumed`.

Минимальные состояния UX:
- `ready_for_transfer` (доступно к привязке);
- `already_claimed` (уже принадлежит другой компании);
- `code_invalid_or_expired`;
- `code_consumed`;
- `device_not_found`;
- `blocked`.

Минимальные API-контракты:
- `POST /v1/device-transfer/preview`:
  - вход: `deviceId`, `activationCode`;
  - выход: `device model`, `serial`, `current state`, `target company`.
- `POST /v1/device-transfer/claim`:
  - вход: `deviceId`, `activationCode`, `tenantId`;
  - семантика: атомарно claim + consume code + audit log.

Безопасность (must-have):
- одноразовый код хранить только в хэшированном виде;
- ограничение попыток + rate limit по IP и по `deviceId`;
- идемпотентность `claim` по request id;
- защита от race condition (DB transaction + unique constraints).

Главный UX-принцип:
**"Физическая наклейка -> 1 экран в облаке -> устройство в аккаунте за 1-2 минуты без ручной техподдержки".**

---

## Улучшение для MYXON: multi-tier channel без ручного "разруливания"

Проблема в IXON-подобном UX:
- устройство предзарегистрировано у верхнего дилера;
- фактический ввод в эксплуатацию делает нижний дилер или конечный клиент;
- без гибкой делегации возникает ручной процесс "пишите в поддержку/дилеру".

Как сделать лучше в MYXON:
- Ввести иерархию владения: `Vendor -> Master Dealer -> Dealer -> Integrator -> End Customer`.
- Разделить:
  - `ownership` (кто владелец актива в канале),
  - `management rights` (кто может настраивать/видеть),
  - `deployment rights` (кто может привязать к объекту/локации).
- Сделать два режима claim:
  - `Direct Claim`: сразу в tenant конечного клиента (если разрешено политикой канала).
  - `Delegated Claim`: сначала в tenant дилера, затем transfer вниз по иерархии.

UX-флоу без разрывов:
1. Конечный пользователь сканирует QR и вводит одноразовый код.
2. Система автоматически определяет channel policy для `deviceId`.
3. Если прямой claim разрешен, пользователь видит только выбор своей компании и локации.
4. Если нужен посредник, создается `claim request` дилеру с SLA-таймером.
5. Дилер подтверждает в 1 клик, после чего устройство автоматически привязывается к tenant и локации.

Что добавить в продукт обязательно:
- `Claim Request Queue` для дилеров (pending/approved/rejected/expired).
- Автоправила:
  - auto-approve по allowlist доменов/tenant;
  - auto-route по региону/серийному диапазону;
  - auto-expire и fallback на следующую линию канала.
- Привязка к локации (`site/facility`) как часть claim wizard:
  - обязательная или опциональная по политике;
  - можно отложить, но с флагом `unassigned_site`.

Минимальные статусы процесса:
- `claim_pending_channel_approval`
- `claim_approved`
- `claim_rejected`
- `claimed_unassigned_site`
- `claimed_assigned_site`

Бизнес-правило для снижения трения:
- если дилер не обработал заявку за N часов, срабатывает `auto-escalation`:
  - либо авто-аппрув (по политике),
  - либо эскалация master dealer/vendor.

Ключевая цель MYXON:
**конечный клиент не должен искать "правильного" дилера вручную; система сама маршрутизирует claim по каналу и доводит до привязки к локации.**

---


## Что уже подтверждено в Linux userspace IXrouter

### 1. Сетевая модель устройства
Подтверждено из `ip a`, `ip r`, `ubus call system board` и `/etc/config/network`:
- модель в userspace: **IXON IX3-MT7621**
- релиз прошивки: **IXrouter3 0.13.2 r1**
- ядро: **Linux 4.14.167**
- board name: **ix3-mt7621**

Активная сетевая схема:
- `br-lan` = **192.168.27.1/24**
- `eth0.1` = LAN VLAN, включён в `br-lan`
- `eth0.2` = WAN VLAN
- WAN сейчас поднят как **static**: `192.168.8.118/24`
- default route: `via 192.168.8.1 dev eth0.2`
- `sta_wan` в Wi‑Fi-стеке реализован через `mlan0` (Wi‑Fi client / STA uplink)
- `ap_lan` в Wi‑Fi-стеке реализован через `uap0` (Wi‑Fi access point для локальной сети)
- в логах видно, что `sta_wan_dev` и `ap_lan_dev` присутствуют в runtime-модели, даже если в текущей конфигурации отключены или не подняты

Практический вывод:
- IXrouter — это не просто VPN-клиент, а полноценный **маршрутизатор/gateway со своей локальной LAN-подсетью**
- внутри устройства жёстко разделены **LAN** и **WAN**
- uplink-модель у IXON изначально рассчитана минимум на:
  - Ethernet WAN
  - Wi‑Fi uplink (STA)
  - WWAN/QMI uplink
  - отдельный VPN overlay interface

Для MYXON это сильный паттерн:
- edge node должен иметь **собственную сервисную LAN**
- uplink не должен быть один-единственный
- overlay/VPN нужно мыслить как отдельный сетевой интерфейс, а не как «внутреннюю магию агента»

### 2. Подтвержденные userspace-сервисы
Из `ps w | head -n 80` подтверждены ключевые процессы:
- `procd` — init / process supervisor
- `ubusd` / `rpcd` — OpenWrt control plane / IPC
- `netifd` — управление сетью
- `odhcpd`, `odhcp6c` — DHCPv6 / router advertisement
- `dnsmasq` — локальный DNS/DHCP
- `dropbear` — SSH сервер
- `uhttpd` + `luci` — локальный web UI
- `ntpd` — синхронизация времени
- `bacnet-ip-service` — отдельный industrial/service-specific агент
- `wifi-monitor` — контроль беспроводного uplink/состояния
- `ixagent` — основной IXON-агент в userspace

Особенно важно:
- основной прикладной агент называется **`ixagent`**
- в системе присутствует отдельный **BACnet service**, что указывает на промышленный/OT-use case
- локальный web UI живет на стандартной связке **uhttpd + LuCI-like CGI entrypoint**
- SSH и web UI встроены в базовый runtime, а не вынесены в «внешний портал»

Практический вывод для MYXON:
- нужен свой **edge agent**, аналогичный `ixagent`, который будет отвечать за bootstrap, связь с control plane и оркестрацию сервисов
- локальный web UI и SSH — это не опция, а важная часть edge-runtime
- поддержка отраслевых сервисов/протоколов (здесь видно BACnet) должна быть предусмотрена как отдельный модуль, а не как часть control plane

### 3. Уже видимый архитектурный паттерн IXON
На текущем этапе подтверждается, что IXON-подобное устройство устроено так:

- **Boot / Recovery Layer**
  - U-Boot
  - UART
  - TFTP recovery
  - default env

- **Base OS / Edge Runtime**
  - OpenWrt-based Linux
  - netifd / dnsmasq / odhcpd / dropbear / uhttpd
  - ixagent
  - дополнительные сервисы объекта (например BACnet)

- **Control Plane / Cloud Layer**
  - пока ещё не разобран полностью,
  - но уже очевидно, что userspace-агент является мостом между локальной edge-системой и внешним облачным управлением

Главный инженерный вывод:
**IXON ценен не роутером как таковым, а тем, как он собирает вокруг edge-runtime полноценный удалённо управляемый промышленный gateway.**

### 4. Что теперь имеет смысл снимать read-only
Следующие безопасные команды для продолжения исследования:
- `cat /proc/mtd`
- `mount`
- `df -h`
- `ls /etc/init.d`
- `ls /etc/config`
- `uci show firewall`
- `uci show system`
- `logread | tail -n 200`
- `strings /bin/ixagent | head`

Это даст:
- карту разделов flash
- layout rootfs/overlay
- список init-сервисов
- firewall-модель между LAN/WAN/VPN
- первые сигнатуры и подсказки по поведению `ixagent`



## Новые выводы по внутреннему control protocol на порту `9240`

### 1. Подтвержден формат локальной агентной шины
По прямому подключению к `telnet localhost 9240` и интерактивным командам подтверждено, что порт `9240` — это не shell и не обычный telnet-сервис, а **структурированный внутренний management protocol `ixagent`**.

Подтвержденные признаки:
- приветствие в кодированном формате:
  - `101 IXrouter3/0.13.2 ... IXagent/0.5.14 ...`
  - `103 Type HELP for help`
- ответы идут числовыми кодами:
  - `101`
  - `103`
  - `110`
  - `111`
  - `201`
  - `410`
  - `411`
- события от компонентов приходят асинхронно, независимо от пользовательских команд

Практический вывод:
- IXON использует собственную **локальную control bus / command protocol**
- shell-доступ и agent-control — это разные уровни управления
- для MYXON это сильный паттерн: нужен не только SSH/web UI, но и отдельный **внутренний локальный протокол управления runtime-компонентами**

### 2. Подтверждена модель «диспетчер + компоненты»
Из ответов на `HELP COMPONENT ...` подтверждены по крайней мере такие компоненты:
- `multiwan` — `Handler for multiwan management on the board`
- `gpio` — `Handler for GPIO events on the board`

Это подтверждает, что `ixagent` работает как **диспетчер команд**, а логика вынесена в отдельные обработчики/компоненты.

Практический вывод:
- IXON строит runtime не как единый монолитный command interpreter, а как шину с отдельными handler'ами
- для MYXON это прямой инженерный шаблон:
  - центральный dispatcher
  - registry компонентов
  - единый протокол
  - отдельные runtime-модули (`multiwan`, `gpio`, `openvpn`, `config`, и т.д.)

### 3. Подтвержден асинхронный режим выполнения команд
При отправке команд вида:
- `CMD gpio status`
- `CMD gpio list`
- `CMD gpio get`

сначала приходил ответ:
- `201 Command dispatched`

а затем отдельным сообщением от компонента:
- `110 "gpio" "commandinvalid"`
- `111 0=status`
- `111 1=Command not recognized`

Практический вывод:
- агент сначала подтверждает прием команды, а потом компонент публикует собственный результат
- это очень зрелая **асинхронная command-dispatch модель**
- для MYXON это критически полезный паттерн:
  - UI/CLI не должен блокироваться в ожидании долгих операций
  - dispatch acknowledgement и execution result должны быть разделены
  - командная шина должна уметь передавать отдельные события статуса и ошибки

### 4. Подтвержден формат ошибок и событий
По наблюдаемому трафику подтверждается такая модель ответов:
- `410 Command invalid at position 0` — синтаксическая ошибка верхнего уровня
- `411 Command MULTIWAN not recognized` — неизвестная команда верхнего grammar
- `110 "<component>" "<event_or_error>"` — событие/ошибка от конкретного компонента
- `111 <n>=<value>` — аргументы/детали события
- `201 Command dispatched` — подтверждение постановки команды в обработку

Практический вывод:
- протокол использует **кодированный тегированный текстовый формат**, который легко парсить
- `110/111` фактически образуют компактный event payload без JSON-overhead
- для MYXON это сильный паттерн:
  - использовать простой line-oriented protocol
  - отделить transport grammar от component payload
  - кодировать события минималистично, но структурированно

### 5. Подтверждено, что grammar протокола не равен shell-синтаксису
Наблюдения:
- `HELP COMPONENT multiwan` работает
- `HELP COMPONENT gpio` работает
- попытки `CMD gpio status`, `CMD gpio list`, `CMD gpio get` не дали ожидаемого `status/list/get`, а вернули `Command not recognized`
- ранее также было видно, что `HELP MULTIWAN` не работает как сокращенный синтаксис

Практический вывод:
- grammar у `ixagent` — **строго ограниченный и собственный**, а не набор shell-подобных слов
- наличие компонента не означает, что его команды угадываются естественным образом
- для MYXON это сильный урок:
  - внутренний control protocol должен иметь четко определенный grammar
  - help/describe/dispatch следует проектировать отдельно
  - не стоит полагаться на «интуитивные» subcommands без явной схемы протокола

### 6. Подтвержден шумовой фон от `apiclient`
Во время сеанса периодически приходили асинхронные сообщения:
- `110 "apiclient" "apirequestpre"`
- `110 "apiclient" "httprequestexception"`
- `111 0=keyupdate`
- `111 1=0`
- `111 2=HTTP Request Error: curl_easy_perform() failed: Error`

Практический вывод:
- компоненты публикуют фоновые operational events в ту же локальную шину
- это подтверждает, что интерфейс `9240` используется не только для команд, но и как **единый канал статусов/ошибок runtime**
- для MYXON это очень полезный паттерн:
  - локальная шина должна уметь не только принимать команды, но и стримить runtime-события
  - command plane и event plane могут жить на одном transport, но должны быть логически различимы

### 7. Что это означает для архитектуры MYXON
На основе подтвержденного поведения порта `9240` можно формулировать конкретные требования к собственному аналогу.

#### Принцип A. Нужен отдельный локальный control protocol
Не shell wrapper и не просто REST на localhost, а отдельный protocol/grammar для:
- `HELP`
- `STAT`
- `CMD`
- component-specific events
- асинхронных operational notifications

#### Принцип B. Команда и результат должны быть разделены
Нужны отдельные сущности:
- command accepted / dispatched
- component execution result
- runtime warning/error event

#### Принцип C. Компоненты должны быть first-class сущностями
Компоненты наподобие:
- `multiwan`
- `gpio`
- `openvpn`
- `config`
- `proxy`
- `firmware`

должны регистрироваться в dispatcher и отвечать через единый протокол.

#### Принцип D. Event stream должен быть встроенным
Шина управления должна поддерживать не только request/response, но и фоновую телеметрию runtime:
- connectivity errors
- API failures
- config updates
- component state changes
- reconnect / registration events

### 8. Обновленный инженерный вывод
Новый шаг исследования показывает, что IXON строит вокруг `ixagent` не просто локальный daemon, а **полноценную внутреннюю командно-событийную шину**.

Итоговый вывод для MYXON:
**MYXON стоит проектировать как edge-runtime с собственным line-oriented control protocol, где dispatcher, компоненты и поток runtime-событий являются базовыми архитектурными сущностями, а не вторичной обвязкой вокруг VPN или web UI.**


## Новые выводы по firewall и VPN-модели IXrouter

### 1. Firewall-модель подтверждает, что VPN у IXON — это отдельная security zone
Из `uci show firewall` подтверждено наличие трех базовых зон:
- `lan`
- `wan`
- `vpn`

Причем `vpn` оформлен не как абстрактный туннельный процесс, а как полноценная firewall-зона:
- `firewall.zone_vpn.name='vpn'`
- `firewall.zone_vpn.network='vpn'`
- `firewall.zone_vpn.input='ACCEPT'`
- `firewall.zone_vpn.output='ACCEPT'`
- `firewall.zone_vpn.forward='ACCEPT'`

Практический вывод:
- IXON моделирует overlay/VPN как отдельный сетевой домен безопасности
- VPN в их архитектуре — это не просто транспорт, а самостоятельная routing/security plane
- для MYXON это сильный паттерн: **overlay должен быть оформлен как отдельная зона политики, а не как «внутренняя магия агента»**

### 2. Подтвержден двусторонний routing между VPN и LAN
Из firewall-конфига видны явные forwardings:
- `firewall.forwarding_vpn_lan.src='vpn'`
- `firewall.forwarding_vpn_lan.dest='lan'`
- `firewall.forwarding_lan_vpn.src='lan'`
- `firewall.forwarding_lan_vpn.dest='vpn'`

Это означает:
- VPN-зона предназначена для полноценного взаимодействия с локальной сетью за устройством
- удаленный доступ строится не только как «вход внутрь», но и как нормальный обмен между overlay и внутренним сегментом

Для MYXON это важный вывод:
- edge-gateway должен уметь не только публиковать отдельные сервисы, но и грамотно маршрутизировать трафик между **LAN** и **overlay**
- policy между LAN и VPN должна быть явной и управляемой

### 3. LAN по умолчанию изолирован от WAN
Особенно ценные правила:
- `firewall.forwarding_lan_wan_private.target='REJECT'`
- `firewall.forwarding_lan_wan_public.target='REJECT'`

Причем отдельно режется доступ из `lan` в приватные сети:
- `10.0.0.0/8`
- `172.16.0.0/12`
- `192.168.0.0/16`

И отдельно в целом режется `lan -> wan`.

Практический вывод:
- IXON проектирует LAN не как обычную пользовательскую домашнюю сеть с свободным выходом в интернет
- локальный сегмент за устройством считается защищаемой промышленной зоной
- uplink предназначен прежде всего для контролируемого удаленного доступа, а не для свободного интернет-шлюза для локальных устройств

Для MYXON это сильный паттерн:
- локальный технологический сегмент нужно считать **защищаемой зоной**
- свободный `LAN -> WAN` по умолчанию лучше не разрешать
- разрешения должны быть осознанными, а не «роутерными по умолчанию»

### 4. Подтвержден паттерн publish внутренних сервисов через VPN
Самое важное из firewall-конфига:
- `vpn:2000 -> 192.168.27.11:5900`
- `vpn:2001 -> 192.168.27.11:8080`
- `vpn:2002 -> 192.168.27.11:5843`

Из правил:
- `firewall.portforward_vpn_2000`
- `firewall.portforward_vpn_2001`
- `firewall.portforward_vpn_2002`
- target = `DNAT`
- source zone = `vpn`
- destination = локальный хост в LAN

Это означает, что IXON реализует не просто «доступ в подсеть», а **управляемую публикацию конкретных внутренних сервисов через overlay/VPN**.

Практический вывод для MYXON:
- важный продуктовый паттерн — **service publishing**, а не только subnet routing
- наружу должны публиковаться не все устройства сразу, а конкретные сервисы:
  - VNC
  - HTTP/HMI
  - инженерные web UI
  - API контроллеров
- публикация должна задаваться как управляемая сущность:
  - внутренний IP
  - внутренний порт
  - внешний VPN endpoint / published port
  - ACL / policy / audit

### 5. Что это означает для архитектуры MYXON
На основании network + firewall уже можно сформулировать несколько устойчивых архитектурных принципов.

#### Принцип A. VPN — это отдельная policy zone
Не просто поднять туннель, а сделать:
- отдельный интерфейс
- отдельную зону firewall
- отдельные forwarding rules
- отдельный контроль публикуемых сервисов

#### Принцип B. Service exposure важнее, чем просто «дать доступ в LAN»
IXON показывает зрелую модель:
- локальная сеть существует
- overlay существует
- но реальная ценность — в управляемом выводе нужных сервисов наружу

Для MYXON это означает, что control plane должен уметь управлять:
- каталогом локальных сервисов
- их маппингом во внешний доступ
- правами пользователей/ролей на эти сервисы

#### Принцип C. Edge должен быть промышленным шлюзом, а не бытовым роутером
IXON явно отделяет:
- uplink
- local protected LAN
- VPN overlay
- service publishing

Это очень важный ориентир для MYXON.

#### Принцип D. Control plane должен управлять mappings
Из конфигурации видно, что публикация сервисов через VPN — центральная часть продукта.
Для MYXON это надо проектировать как сущности control plane:
- объект
- edge node
- локальный сервис
- опубликованный endpoint
- политика доступа
- журнал использования

### 6. Обновленный инженерный вывод
С учетом уже подтвержденного userspace-слоя IXON теперь можно описывать так:

**IXON = OpenWrt-based multi-uplink industrial edge gateway с собственной LAN, отдельной VPN security zone и управляемой публикацией локальных сервисов через overlay.**

Это очень ценный ориентир для MYXON, потому что показывает, что ключевая продуктовая ценность находится в сочетании:
- edge runtime
- firewall/policy model
- service publishing
- control plane orchestration


## Новые выводы по layout прошивки, runtime-модулям и `ixagent`

### 1. Layout flash и файловой системы подтвержден
Из `cat /proc/mtd`, `mount` и `df -h` подтверждена классическая для embedded/OpenWrt схема хранения:

- `mtd0` = `u-boot`
- `mtd1` = `u-boot-env`
- `mtd2` = `factory`
- `mtd3` = `firmware`
- `mtd4` = `kernel`
- `mtd5` = `rootfs`
- `mtd6` = `rootfs_data`

Файловая система:
- `/rom` = `squashfs (ro)`
- `/overlay` = `jffs2` на `mtd6`
- `/` = `overlayfs`

Практический вывод:
- IXON использует **read-only base image + writable overlay**
- базовая система отделена от пользовательских изменений
- это очень сильный паттерн для MYXON, потому что упрощает:
  - обновления
  - восстановление
  - откат
  - разделение «системного образа» и «данных/конфига»

Отдельно важно:
- размер `rootfs_data` небольшой и предназначен именно для конфигов/overlay, а не для тяжелых данных
- это подтверждает модель: **runtime должен быть компактным, а изменяемая часть — минимальной и контролируемой**

### 2. Подтвержден модульный userspace runtime
По `ls /etc/init.d` подтвержден список важных сервисных модулей:
- `ixagent`
- `openvpn`
- `wifi-monitor`
- `cellular-monitor`
- `udp-broadcast-relay`
- `bacnet`
- `image-upgrade`
- `bootloader-upgrade`
- `dropbear`
- `uhttpd`
- `dnsmasq`
- `firewall`
- `network`

Практический вывод:
- IXON не реализует всю логику в одном монолитном бинаре
- вокруг `ixagent` уже собран полноценный edge-runtime из отдельных сервисов
- для MYXON это сильный паттерн: **runtime должен быть модульным**, а не сводиться к одному daemon'у

То есть у MYXON уже можно выделять отдельные подсистемы:
- connectivity / uplink management
- VPN runtime
- local networking
- industrial protocol services
- upgrade manager
- edge agent / orchestration

### 3. Из логов подтвержден реальный software stack IXON
По `logread | tail -n 200` подтверждено:
- стартует `ixagent`
- агент регистрируется на платформе
- используется `OpenVPN`
- используется `stunnel`
- есть `libixagent`
- есть `libixlogger`
- есть локальные TCP/push интерфейсы

Ключевые наблюдения из лога:
- `Starting IXrouter3/0.13.2 ... IXagent/0.5.14`
- `Registered to IXplatform with public ID ...`
- `TCP interface listening on 127.0.0.1:9240`
- `Push interface listening on 0.0.0.0:9230`
- `OpenVPN/2.4.5`
- `stunnel/5.41`

Практический вывод:
- `ixagent` — это не просто VPN-обертка, а центральный локальный orchestrator
- control plane у IXON опирается на локальный агент, который:
  - управляет регистрацией устройства
  - держит command/push interfaces
  - управляет VPN
  - связан с локальными web/tcp сервисами

Для MYXON это ключевой паттерн:
**edge agent должен быть центральной orchestrating-сущностью, а не просто “клиентом до сервера”.**

### 4. `ixagent` уже выдает структуру модулей продукта
По `strings /bin/ixagent` подтверждены важные внутренние сущности и модули.

#### Конфигурационные домены
В бинаре явно видны конфигурационные секции для:
- WAN:
  - `Wan_MultiwanPolicy`
  - `Wan_3gApn`
  - `Wan_3gPincode`
  - `Wan_IpUseDhcp`
  - `Wan_IpAddress`
  - `Wan_IpNetmask`
  - `Wan_IpGateway`
  - `Wan_WlanSsid`
  - `Wan_WlanKey`
  - `Wan_DnsServer`
  - `Wan_HttpProxyAddress`
  - `Wan_HttpProxyPort`
  - `Wan_HttpProxyAuthentication`
  - `Wan_HttpProxyUsername`
  - `Wan_HttpProxyPassword`
  - `Wan_HttpProxyIsSocks5`
  - `Wan_IxapiAccountId`
  - `Wan_DigitalInputMode`
  - `Wan_WanTrackIp`
  - `Wan_WlanTrackIp`
  - `Wan_3gTrackIp`
  - интервалы трекинга uplink
- LAN:
  - `Lan_IpAddress`
  - `Lan_IpNetmask`
  - `Lan_DhcpRange`
  - `Lan_WlanSsid`
  - `Lan_WlanKey`
  - `Lan_WlanChannel`
  - `Lan_ForwardLanWanPrivate`
  - `Lan_ForwardLanWanPublic`
  - `Lan_GatewayLessRouting`
  - `Lan_ForwardedPort`
  - `Lan_AdditionalSubnet`
  - `Lan_DhcpStaticMapping`
  - `Lan_BacnetBbmd`
  - `Lan_UdpBroadcastRelay`

Практический вывод:
- `ixagent` фактически является **engine конфигурационной модели устройства**
- это не просто runtime, а слой, который маппит product-level settings в UCI/OpenWrt/system behavior
- для MYXON это сильный паттерн: нужен свой **configuration domain model**, который будет описывать WAN/LAN/VPN/services как продуктовые сущности

#### Runtime-модули, явно видимые в бинаре
Подтверждены названия модулей:
- `MultiwanManager`
- `LanWanConflictDetector`
- `FirmwareManager`
- `GpioManager`
- `HotplugManager`
- `TimeManager`
- `OpenVpnMonitor`
- `StunnelMonitor`
- `ProcessMon`
- `ProxyManager`
- `TcpInterface`
- `WebServer`
- `CommandClient`
- `MosquittoClient`
- `ApiClient`
- `CommandHandler`
- `DeviceWebServerHandler`
- `DeviceConfig`

Практический вывод:
- IXON построен модульно даже на уровне одного агента
- особенно важны подтвержденные модули:
  - **MultiwanManager** — оркестрация нескольких uplink
  - **LanWanConflictDetector** — контроль конфликтов между LAN и uplink-сетями
  - **FirmwareManager** — управление обновлениями
  - **ProxyManager** — публикация/проксирование сервисов
  - **ApiClient** — связь с API/control plane
  - **CommandClient + MosquittoClient** — командный канал
  - **OpenVpnMonitor + StunnelMonitor** — управление защищенным транспортом

Для MYXON это уже почти прямой шаблон декомпозиции runtime.

### 5. Подтверждена модель identity / enrollment
По `strings` видны:
- `deviceId`
- `agent_public_id`
- `agent_shared_secret`
- `Generating VPN key pair`
- `register $ID`
- `unregister`
- `Authorization: IXagent id="`
- `ixagent.ca`
- `Device ID must be set before running daemon`

Практический вывод:
- устройство имеет собственную identity-модель
- используется отдельный lifecycle:
  - регистрация
  - генерация VPN key pair
  - наличие shared secret / public id
  - отмена регистрации
- enrollment — это центральный элемент продукта, а не просто «локальный конфиг»

Для MYXON это прямой обязательный паттерн:
- нужен свой `deviceId`
- нужен enrollment flow
- нужны bootstrap credentials / shared secret / public identity
- edge node должен существовать как управляемая сущность платформы, а не просто как IP-адрес

### 6. Подтвержден command channel и связь с платформой
По логу и `strings` видны:
- `Registered to IXplatform`
- `ixplatform.agentapi`
- `ixplatform.ixagent.command_client`
- `MosquittoClient`
- `/mqtt-connection`
- `Connected to command server`
- `Unable to connect to command server`
- `Successfull published client-connect on mqtt-connection topic`

Практический вывод:
- у IXON есть отдельный command channel, вероятно поверх MQTT-like механизма
- это не просто polling к REST API
- продукт использует разделение на:
  - API/enrollment plane
  - command/event plane
  - VPN/data plane

Для MYXON это один из самых сильных продуктовых паттернов:
**нужен не только REST/API, но и постоянный command/event channel для управления edge-node.**

### 7. Подтвержден transport stack: OpenVPN + stunnel + management interface
По логам и `strings` видно:
- `OpenVPN component`
- `OpenVPN requires stunnel`
- `No stunnel required for OpenVPN connection`
- `OpenVPN management interface`
- `client.ovpn`
- `OpenVPN connection timeout`
- `OpenVPN connected`
- `OpenVPN reconnecting`
- `OpenVPN asked for unrecognized password`

Практический вывод:
- IXON использует не просто “запуск openvpn”, а полноценный orchestration вокруг OpenVPN
- возможно есть режимы с дополнительным `stunnel` поверх соединения
- используется management interface OpenVPN для контроля состояния

Для MYXON это сильный урок:
- транспорт нужно проектировать как управляемую подсистему
- важны:
  - мониторинг состояния
  - reconnect logic
  - отдельный control channel к VPN engine
  - возможность быстро заменить сам VPN backend, не ломая control plane

### 8. Подтвержден локальный publishing/runtime access layer
По `strings` видно:
- `TcpInterface`
- `Allows access to the agent via TCP interface`
- `Example: CMD openvpn start`
- `Example: STAT openvpn`
- `WebServer`
- `DeviceWebServerHandler`
- `No port configured for webserver`
- `ProxyManager`

Практический вывод:
- у IXON существует локальный внутренний control interface
- агент умеет принимать команды и отвечать статусами
- существует отдельный web/runtime access layer
- service publishing и local control организованы не “вручную”, а через внутренние runtime-компоненты

Для MYXON это сильный паттерн:
- нужен локальный control socket / TCP interface
- нужен внутренний command grammar/API для статусов и команд runtime
- нужен web/runtime access слой отдельно от cloud UI

### 9. Дополнительные наблюдения по устройству
Из логов также подтверждено:
- используется Marvell Wi-Fi stack (`mlan`, `uap0`, proprietary driver)
- присутствует QMI/WWAN support, но модем сейчас не найден (`/dev/cdc-wdm0`)
- DHCP на LAN реально раздается из диапазона `192.168.27.100-249`
- `dropbear` поднимается как встроенный SSH-сервер
- есть watchdog / monitor-логика при старте сервисов

Практический вывод:
- IXON проектирует edge как **настоящий промышленный multi-uplink appliance**, а не как один VPN daemon
- Wi-Fi, WWAN, Ethernet, local services и industrial extensions уже изначально рассматриваются как части одного runtime

### 10. Обновленный инженерный вывод для MYXON
С учетом новых данных IXON теперь можно описывать еще точнее:

**IXON = OpenWrt-based industrial edge runtime с overlay/VPN, identity/enrollment, command channel, service publishing, multiwan orchestration и отдельным firmware/update lifecycle.**

Для MYXON из этого следуют обязательные проектные сущности:
- `DeviceIdentity`
- `EnrollmentManager`
- `ApiClient`
- `CommandChannel`
- `VpnManager`
- `ProxyManager / ServicePublisher`
- `MultiwanManager`
- `LanWanConflictDetector`
- `FirmwareManager`
- `LocalWebInterface`
- `TcpControlInterface`
- `IndustrialProtocolExtensions`

Итоговый практический вывод:
**аналог IXON нельзя проектировать как “VPN + веб-панель”. Его нужно проектировать как модульный edge-runtime с identity, command plane, transport plane и policy-driven publishing локальных сервисов.**


## Новые выводы по `ixagent`: proxy, multiwan, webserver и lifecycle-команды

### 1. Подтвержден отдельный ProxyManager как часть edge-runtime
По свежему выводу `strings /bin/ixagent | grep -Ei 'proxy|webserver|openvpn|mqtt|multiwan|register|firmware'` дополнительно подтверждены:
- `ProxyManager`
- `No proxy configured`
- `Using HTTP proxy`
- `Using SOCKS5 proxy`
- `Using proxy string`
- `Using proxy username`
- `PROXY`, `PROXYAUTH`, `PROXYPASSWORD`, `PROXYUSERNAME`
- `proxychanged`
- `ixplatform.ixagent.wan_proxy`
- `ixrouter.wan.http_proxy_address`
- `ixrouter.wan.http_proxy_authentication`
- `ixrouter.wan.http_proxy_is_socks5`
- `ixrouter.wan.http_proxy_password`
- `ixrouter.wan.http_proxy_port`
- `ixrouter.wan.http_proxy_username`

Практический вывод:
- HTTP/SOCKS5 proxy в IXON — это не второстепенная настройка, а отдельная часть product/runtime-модели
- `ixagent` умеет не только хранить прокси-настройки, но и реагировать на их изменение как на отдельное событие (`proxychanged`)
- для MYXON это сильный паттерн: **proxy-awareness должен быть встроен в connectivity layer**, а не добавлен потом как «костыль»

### 2. Подтвержден развитый multiwan-слой
Новый вывод дополнительно усиливает уже найденные признаки multiwan:
- `Starting multiwan manager`
- `multiwan`
- `multiwanmanager.cpp`
- `MultiwanManager`
- `MultiwanInterface`
- `ixrouter.wan.multiwan_policy`
- `Utility to detect LAN / WAN conflicts`
- `LanWanConflictDetector`

По символам видно, что `MultiwanInterface` умеет:
- `getRouteInformation_`
- `updateRoute_`
- `addRoute_`
- `delRoute_`
- `sendPingRequest_`
- `GetPriority`
- `IsUp`
- `Enabled`

Практический вывод:
- multiwan у IXON — это не просто выбор «WAN или LTE», а полноценная логика:
  - приоритетов
  - проверки доступности
  - обновления маршрутов
  - обнаружения конфликтов адресного пространства
- для MYXON это прямой паттерн: нужен отдельный `MultiwanManager`, а не набор shell-скриптов вокруг `ip route`

### 3. Подтвержден отдельный web/runtime publishing layer
Дополнительно видны:
- `WebServer`
- `WebServerInstance`
- `DeviceWebServerHandler`
- `Webserver listening on`
- `Webserver cannot listen on`
- `No port configured for webserver`
- `WebServer::Stop(): Not implemented`
- `ixplatform.ixagent.tcp_interface`

Практический вывод:
- локальный web/runtime layer у IXON выделен в отдельный модуль
- этот модуль, вероятно, связан с публикацией сервисов и/или локальным доступом к device-specific web endpoints
- для MYXON это важный паттерн: **service publishing и local web access лучше оформлять как отдельный runtime-компонент**, а не смешивать с VPN-монитором или API-клиентом

### 4. Подтверждены lifecycle-команды самого агента
Очень важные строки из бинаря:
- `connect              Sets up the vpn connection`
- `disconnect           Stops the vpn connection`
- `reconnect            Cancels the current requst and try again`
- `autoconnect on|off   Turns autoconnect on boot on or off`
- `register $ID         Registers the agent to the company with the given ID`
- `unregister           Unregisters the agent`
- `upgradefirmware $URL   Downloads and executes the new firmware based on the URL.`
- `CMD openvpn start`
- `STAT openvpn`

Практический вывод:
- `ixagent` содержит собственный command grammar / CLI-like control layer
- агент умеет не только мониторить, но и выполнять операционные lifecycle-команды:
  - регистрация
  - дерегистрация
  - connect/disconnect/reconnect VPN
  - управление autoconnect
  - обновление прошивки по URL
- для MYXON это очень сильный продуктовый паттерн:
  - нужен внутренний command layer
  - нужен предсказуемый набор lifecycle-команд
  - нужен единый control surface для runtime, а не набор разрозненных утилит

### 5. Подтверждена явная связка MQTT / API / OpenVPN конфигурации
Новые сигнатуры:
- `downloadmqttconfig`
- `downloadmqttixloggerconfig`
- `downloadopenvpnconfig`
- `mqttconfigdownloaded`
- `mqttixloggerconfigdownloaded`
- `openvpnconfigdownloaded`
- `mqtt_server.host=`
- `mqtt_server.port=`
- `mqtt_session.username=`
- `mqtt_session.random_id=`
- `mqtt_session.lwt=true`
- `application/x-openvpn-profile`

Практический вывод:
- агент скачивает отдельные конфиги для:
  - MQTT/command channel
  - IXlogger
  - OpenVPN transport
- control plane, судя по всему, раздает не одну «общую конфигурацию», а набор специализированных конфигов для разных runtime-компонентов
- для MYXON это сильный паттерн: **конфигурацию нужно дробить по доменам**, а не держать одним монолитным файлом

### 6. Подтвержден firmware lifecycle как штатная функция агента
Новые признаки:
- `Received upgrade firmware command.`
- `upgradefirmware`
- `upgradefirmware $URL   Downloads and executes the new firmware based on the URL.`
- `firmware`
- `firmwaremanager.cpp`
- `FirmwareManager`

Практический вывод:
- обновление прошивки — штатная функция `ixagent`, а не внешний ручной процесс
- агент получает команду, скачивает образ и инициирует upgrade workflow
- для MYXON это прямой вывод: update lifecycle должен быть встроенной способностью edge-runtime, а не отдельной «сервисной процедурой администратора»

### 7. Подтверждена более точная структура control plane
Из новых строк теперь еще отчетливее видно разделение логики:
- `ixplatform.agentapi`
- `ixplatform.ixagent.command_client`
- `ixplatform.ixagent.openvpn`
- `ixplatform.ixagent.tcp_interface`
- `ixplatform.ixagent.wan_proxy`
- `mqtt`
- `mqtt-ixlogger`
- `event=agent-connect`
- `event=agent-disconnect`
- `{"agent":{"event":"connect"...` 
- `{"agent":{"event":"connection-lost"}}`
- `{"agent":{"event":"disconnect"}}`

Практический вывод:
- у IXON явно разделены:
  - API plane
  - command/event plane
  - VPN plane
  - proxy plane
  - logging/telemetry plane
- для MYXON это очень ценный ориентир: **control plane не должен быть одномерным REST API**, он должен быть составным и событийным

### 8. Обновленный инженерный вывод
Новый шаг исследования усиливает ключевую картину:

**IXON = модульный industrial edge-runtime, в котором `ixagent` выступает как orchestrator для identity, API, MQTT/command channel, OpenVPN/stunnel transport, proxy-awareness, multiwan, service publishing и firmware lifecycle.**

Для MYXON из этого теперь еще явнее следуют обязательные подсистемы:
- `ProxyManager`
- `WebRuntimeAccessLayer`
- `CommandGrammar / ControlInterface`
- `ConfigDomainSplitter`
- `MultiwanManager`
- `LanWanConflictDetector`
- `VpnManager`
- `FirmwareManager`
- `EventBus / CommandChannel`
- `Enrollment / Identity Layer`
## Новые выводы по `ixrouter`-конфигу multiwan и BACnet

### 1. Подтвержден отдельный UCI-конфиг `ixrouter` как policy-layer над `network`
По `cat /etc/config/ixrouter` подтверждено, что IXON хранит multiwan-логику не в стандартном `network`, а в отдельном UCI-файле `ixrouter`.

Подтвержденные секции:
- `config interface 'wan'`
- `config interface 'wwan'`
- `config interface 'sta_wan'`
- `config gpio 'gpio0'`

Практический вывод:
- IXON явно разделяет:
  - **physical/runtime network config** в `/etc/config/network`
  - **policy / failover / monitoring config** в `/etc/config/ixrouter`
- для MYXON это очень сильный паттерн: **policy-layer для uplink/failover нужно держать отдельно от низкоуровневой сетевой конфигурации**

### 2. Подтверждена иерархия интерфейсов multiwan
В `ixrouter` явно зафиксированы приоритеты:
- `wan` (`eth0.2`) — `priority '1'`
- `wwan` (`wwan0`) — `priority '2'`
- `sta_wan` (`mlan0`) — `priority '3'`

Практический вывод:
- это уже не гипотеза, а **подтвержденная приоритизация uplink-каналов**
- базовая модель IXON: сначала Ethernet, затем WWAN/QMI, затем Wi‑Fi STA
- для MYXON это прямой инженерный шаблон: failover-логика должна работать поверх **явного списка интерфейсов с приоритетами**, а не через неявные route-эвристики

### 3. Подтвержден L3 health-check через список `track_ip`
Для всех трех интерфейсов (`wan`, `wwan`, `sta_wan`) подтверждены:
- `option interval '5'`
- четыре `track_ip`:
  - `208.67.220.220`
  - `208.67.222.222`
  - `8.8.4.4`
  - `8.8.8.8`

Практический вывод:
- IXON не полагается только на состояние линка `UP`, а использует **L3 reachability checks**
- health-check вынесен в policy-конфиг и применяется одинаково к нескольким типам uplink
- интервал контроля подтвержден: **5 секунд**
- для MYXON это сильный паттерн:
  - нужен отдельный набор `track_ip` на интерфейс
  - нужно отделять `carrier/link state` от реальной сетевой доступности
  - failover manager должен мыслить категориями `reachable / degraded / unreachable`, а не только `link up/down`

### 4. Подтверждено, что `wwan` и `sta_wan` реально предусмотрены в policy-layer даже если сейчас отключены в runtime
По совокупности конфигов видно:
- в `/etc/config/network` есть `wwan` и `sta_wan`
- в Wi‑Fi/runtime-модели есть `sta_wan_dev` (`mlan0`) и `ap_lan_dev` (`uap0`)
- в `/etc/config/ixrouter` оба канала уже включены в multiwan-policy

Практический вывод:
- IXON проектирует multiwan как **унифицированную policy-модель**, которая заранее знает о нескольких типах uplink
- даже если конкретный интерфейс сейчас неактивен или отключен, его место в policy-layer уже определено
- для MYXON это сильный паттерн: модель uplink-каналов должна быть заранее описана как набор capability-профилей, а не собираться на лету только по наличию интерфейса в текущий момент

### 5. Подтвержден BACnet/IP сервис на UDP 47808
По совокупности данных подтверждено:
- `/etc/config/bacnet`:
  - `option ifname 'br-lan'`
  - `option port '47808'`
- процесс в `ps`:
  - `/bin/bacnet-ip-service --startup-status=BACnet-service starting up`
- сокет в `netstat`:
  - `udp 0 0 0.0.0.0:47808 0.0.0.0:*`

Практический вывод:
- BACnet/IP на устройстве не просто декларирован конфигом, а **реально поднят как активный userspace-сервис**
- сервис слушает **UDP/47808** на всех адресах (`0.0.0.0`)
- привязка конфигурации идет к `br-lan`, то есть BACnet логически относится к локальной industrial/LAN-зоне, а не к WAN
- для MYXON это сильный паттерн:
  - OT/field protocols нужно оформлять как отдельные сервисы edge-runtime
  - industrial traffic должен быть привязан к локальному protected segment, а не смешиваться с uplink-plane

### 6. `udp-broadcast-relay` установлен как модуль, но его UCI-конфиг сейчас фактически пустой
По `cat /etc/config/udp-broadcast-relay` видно только пакет и пример закомментированного сервиса:
- `package udp-broadcast-relay`
- пример `config service 'port_1954'` закомментирован

Практический вывод:
- модуль `udp-broadcast-relay` присутствует в системе, но в текущем конфиге его UCI-настройка **не активирована явными сервисами**
- следовательно, сам факт наличия relay-компонента подтвержден, но **текущая активная схема его использования остается гипотезой**
- для MYXON это хороший урок: в документации и reverse notes нужно отдельно разделять:
  - установленный capability/module
  - реально активированную operational-config

### 7. Что это означает для архитектуры MYXON
На основании этих данных уже можно зафиксировать несколько очень сильных проектных принципов.

#### Принцип A. Network config и policy config должны быть разделены
- `network` отвечает за интерфейсы и адресацию
- `ixrouter` отвечает за policy, priority и reachability monitoring

#### Принцип B. Multiwan нужно строить вокруг policy engine
Нужны отдельные сущности:
- interface profile
- priority
- health-check targets
- check interval
- runtime state
- failover decision

#### Принцип C. Industrial services должны быть first-class runtime-модулями
BACnet в IXON — это отдельный userspace-сервис, а не побочный эффект общего VPN/роутерного стека.

#### Принцип D. Installed capability != active operational use
Наличие `udp-broadcast-relay` в системе еще не означает подтвержденную активную relay-схему. Для MYXON это нужно явно учитывать в инженерной документации.

### 8. Обновленный инженерный вывод
Новый шаг исследования подтверждает, что IXON строит edge-runtime не только как transport appliance, но и как **policy-driven multiwan gateway с отдельным industrial service layer**.

Итоговый вывод для MYXON:
**MYXON стоит проектировать как edge-runtime, в котором low-level network config, uplink policy/failover logic и industrial protocol services разделены на отдельные слои и управляются независимыми runtime-компонентами.**

## Что еще нужно исследовать дальше

### 1. Карта SPI flash и разделов
Нужно понять:
- где лежит bootloader
- где kernel
- где rootfs
- где config/env
- есть ли разделение base image и пользовательских данных

### 2. Userspace-сервисы IXrouter
Нужно добраться до Linux userspace или снять firmware, чтобы понять:
- какие сервисы стартуют
- как устроен агент
- как делается bootstrap в облако
- как хранится конфиг устройства
- подтвердить вход в Linux userspace через UART на 115200 bps с учетными данными root / TR0OJ2YyTs
- снять перечень сервисов и сетевых агентов уже из штатной shell-сессии

### 3. Механизм обновления
Нужно выяснить:
- есть ли A/B update
- есть ли резервный образ
- как отделяются прошивка и конфиг
- как переживается сбой обновления

### 4. Модель идентичности устройства
Для MYXON это особенно важно:
- bootstrap token
- enrollment flow
- привязка устройства к организации и объекту
- ротация credentials
- безопасная переинициализация

### 5. Проксирование локальных сервисов
Нужно понять и воспроизвести паттерны доступа к:
- локальным web UI
- SSH
- подсетям за edge node
- локальным внутренним IP:port

---

## Практическое состояние на сейчас

Что уже есть у нас самих и можно использовать как базу для MYXON:
- Orange Pi как edge node
- Tailscale как транспортный слой
- subnet router для публикации локальных подсетей
- hardening SSH (вход только по ключу)
- базовая модель удаленного доступа к локальным сетям и устройствам
- опыт инвентаризации камер, роутеров и edge-узлов в реальной сети

То есть фундамент под собственный аналог уже частично собран.

---

## Следующие инженерные шаги по MYXON

1. Продолжать вести разделение Confirmed / Hypothesis и поддерживать его при каждом новом шаге реверс-анализа
2. Проверить поведение и grammar интерфейса `9230` как отдельного push/event канала
3. Выяснить, как именно читается и применяется `PASS` в локальном control protocol `ixagent`
4. Выяснить точный grammar `config dump` и других команд компонента `config`
5. Добрать команды и статусы конкретных компонентов (`multiwan`, `gpio`, `openvpn`, `apiclient`)
6. Уточнить, есть ли реальная активная relay-логика для UDP broadcast помимо установленного модуля `udp-broadcast-relay`
7. Отделить в концепции MYXON: edge boot/recovery, edge runtime, control plane
8. Описать bootstrap / enrollment flow для собственного устройства
9. Спроектировать recovery-стандарт и дефолтную recovery-сеть
10. Подготовить первый архитектурный черновик MYXON как mini-IXON
11. После этого перейти к прототипу собственного dispatcher/eventbus для MYXON

---



## Дополнительные подтвержденные выводы, которые стоит зафиксировать

### 1. Отдельный push/interface на порту `9230`
Помимо локального control protocol на `127.0.0.1:9240`, подтвержден второй интерфейс `ixagent`:
- `0.0.0.0:9230`
- при подключении отвечает строкой вида `HELO IXrouter3/0.13.2 ... IXagent/0.5.14 ...`

Практический вывод:
- у IXON есть не один, а минимум **два прикладных интерфейса агента**:
  - `9240` — command/control bus
  - `9230` — отдельный push/event-oriented interface
- для MYXON это сильный архитектурный паттерн: **command plane и push/event plane лучше разделять**, даже если они реализованы внутри одного агента

### 2. Локальный MQTT broker не подтвержден
На устройстве не обнаружены:
- `mosquitto`
- `mosquitto_sub`
- `mosquitto_pub`
- слушающие порты `1883/8883`

При этом в `ixagent` подтверждены:
- `MosquittoClient`
- `mqtt_server.host=`
- `mqtt_server.port=`
- `mqtt_session.username=`
- `mqtt_session.random_id=`
- `mqtt_session.lwt=true`

Практический вывод:
- MQTT у IXON, вероятнее всего, используется в режиме **встроенного клиентского command/event channel**, а не как локальный broker на edge-устройстве
- для MYXON это полезный ориентир: **event-driven control plane не требует локального брокера на каждом edge-узле**, если агент сам умеет держать постоянный клиентский канал к платформе

### 3. Immutable base + overlay + tmpfs — ключевой паттерн edge-runtime
Дополнительно подтверждено по `df -h`, что:
- `/rom` полностью занят и является **read-only squashfs**
- `/overlay` хранит изменяемую часть системы
- `/tmp` представляет собой достаточно большой **RAM-backed workspace**

Практический вывод:
- IXON проектирует runtime как:
  - **immutable base image**
  - **малый writable overlay**
  - **временную рабочую область в RAM**
- для MYXON это нужно считать не удобством, а базовым инженерным принципом

### 4. Что уже можно считать Confirmed и что пока остается Hypothesis
Для инженерной дисциплины важно явно разделять уровни уверенности.

#### Confirmed
Подтверждено наблюдениями:
- модульный userspace runtime вокруг `ixagent`
- отдельный local control protocol на `9240`
- отдельный push/interface на `9230`
- line-oriented кодированный протокол (`101/103/110/111/201/410/411`)
- асинхронная модель dispatch + component event
- отдельные runtime-модули: `multiwan`, `gpio`, `openvpn`, `config`, `proxy`, `firmware`
- OpenVPN/stunnel orchestration
- identity/enrollment-модель (`deviceId`, `agent_public_id`, `agent_shared_secret`)
- service publishing через VPN-zone
- multi-uplink runtime с признаками route/priority/failover logic

#### Hypothesis
Пока требует дополнительных подтверждений:
- точная grammar команды `PASS`
- точная grammar `config dump`
- полный набор команд конкретных компонентов `multiwan` / `gpio`
- точная роль `9230` как push/event channel и его handshake
- детали MQTT topic model и формата exchange с платформой
- точный state machine и hysteresis-логика `multiwan`

Практический вывод:
- архитектуру MYXON нужно собирать, опираясь прежде всего на **Confirmed patterns**
- `Hypothesis` использовать как направление дальнейшей разведки, но не как уже доказанную реализацию



## Новые выводы по `ixrouter`-конфигу multiwan и BACnet

### 1. Подтвержден отдельный UCI-конфиг `ixrouter` как policy-layer над `network`
По `cat /etc/config/ixrouter` подтверждено, что IXON хранит multiwan-логику не в стандартном `network`, а в отдельном UCI-файле `ixrouter`.

Подтвержденные секции:
- `config interface 'wan'`
- `config interface 'wwan'`
- `config interface 'sta_wan'`
- `config gpio 'gpio0'`

Практический вывод:
- IXON явно разделяет:
  - **physical/runtime network config** в `/etc/config/network`
  - **policy / failover / monitoring config** в `/etc/config/ixrouter`
- для MYXON это очень сильный паттерн: **policy-layer для uplink/failover нужно держать отдельно от низкоуровневой сетевой конфигурации**

### 2. Подтверждена иерархия интерфейсов multiwan
В `ixrouter` явно зафиксированы приоритеты:
- `wan` (`eth0.2`) — `priority '1'`
- `wwan` (`wwan0`) — `priority '2'`
- `sta_wan` (`mlan0`) — `priority '3'`

Практический вывод:
- это уже не гипотеза, а **подтвержденная приоритизация uplink-каналов**
- базовая модель IXON: сначала Ethernet, затем WWAN/QMI, затем Wi-Fi STA
- для MYXON это прямой инженерный шаблон: failover-логика должна работать поверх **явного списка интерфейсов с приоритетами**, а не через неявные route-эвристики

### 3. Подтвержден L3 health-check через список `track_ip`
Для всех трех интерфейсов (`wan`, `wwan`, `sta_wan`) подтверждены:
- `option interval '5'`
- четыре `track_ip`:
  - `208.67.220.220`
  - `208.67.222.222`
  - `8.8.4.4`
  - `8.8.8.8`

Практический вывод:
- IXON не полагается только на состояние линка `UP`, а использует **L3 reachability checks**
- health-check вынесен в policy-конфиг и применяется одинаково к нескольким типам uplink
- интервал контроля подтвержден: **5 секунд**
- для MYXON это сильный паттерн:
  - нужен отдельный набор `track_ip` на интерфейс
  - нужно отделять `carrier/link state` от реальной сетевой доступности
  - failover manager должен мыслить категориями `reachable / degraded / unreachable`, а не только `link up/down`

### 4. Подтверждено, что `wwan` и `sta_wan` реально предусмотрены в policy-layer даже если сейчас отключены в runtime
По совокупности конфигов видно:
- в `/etc/config/network` есть `wwan` и `sta_wan`
- в `/etc/config/wireless` есть `sta_wan_dev` (`mlan0`) и `ap_lan_dev` (`uap0`)
- в `/etc/config/ixrouter` оба канала уже включены в multiwan-policy

Практический вывод:
- IXON проектирует multiwan как **унифицированную policy-модель**, которая заранее знает о нескольких типах uplink
- даже если конкретный интерфейс сейчас неактивен или отключен, его место в policy-layer уже определено
- для MYXON это сильный паттерн: модель uplink-каналов должна быть заранее описана как набор capability-профилей, а не собираться на лету только по наличию интерфейса в текущий момент

### 5. Подтвержден BACnet/IP сервис на UDP 47808
По совокупности данных подтверждено:
- `/etc/config/bacnet`:
  - `option ifname 'br-lan'`
  - `option port '47808'`
- процесс в `ps`:
  - `/bin/bacnet-ip-service --startup-status=BACnet-service starting up`
- сокет в `netstat`:
  - `udp 0 0 0.0.0.0:47808 0.0.0.0:*`

Практический вывод:
- BACnet/IP на устройстве не просто декларирован конфигом, а **реально поднят как активный userspace-сервис**
- сервис слушает **UDP/47808** на всех адресах (`0.0.0.0`)
- привязка конфигурации идет к `br-lan`, то есть BACnet логически относится к локальной industrial/LAN-зоне, а не к WAN
- для MYXON это сильный паттерн:
  - OT/field protocols нужно оформлять как отдельные сервисы edge-runtime
  - industrial traffic должен быть привязан к локальному protected segment, а не смешиваться с uplink-plane

### 6. `udp-broadcast-relay` установлен как модуль, но его UCI-конфиг сейчас фактически пустой
По `cat /etc/config/udp-broadcast-relay` видно только пакет и пример закомментированного сервиса:
- `package udp-broadcast-relay`
- пример `config service 'port_1954'` закомментирован

Практический вывод:
- модуль `udp-broadcast-relay` присутствует в системе, но в текущем конфиге его UCI-настройка **не активирована явными сервисами**
- следовательно, сам факт наличия relay-компонента подтвержден, но **текущая активная схема его использования остается гипотезой**
- для MYXON это хороший урок: в документации и reverse notes нужно отдельно разделять:
  - установленный capability/module
  - реально активированную operational-config

### 7. Что это означает для архитектуры MYXON
На основании этих данных уже можно зафиксировать несколько очень сильных проектных принципов.

#### Принцип A. Network config и policy config должны быть разделены
- `network` отвечает за интерфейсы и адресацию
- `ixrouter` отвечает за policy, priority и reachability monitoring

#### Принцип B. Multiwan нужно строить вокруг policy engine
Нужны отдельные сущности:
- interface profile
- priority
- health-check targets
- check interval
- runtime state
- failover decision

#### Принцип C. Industrial services должны быть first-class runtime-модулями
BACnet в IXON — это отдельный userspace-сервис, а не побочный эффект общего VPN/роутерного стека.

#### Принцип D. Installed capability != active operational use
Наличие `udp-broadcast-relay` в системе еще не означает подтвержденную активную relay-схему. Для MYXON это нужно явно учитывать в инженерной документации.

### 8. Обновленный инженерный вывод
Новый шаг исследования подтверждает, что IXON строит edge-runtime не только как transport appliance, но и как **policy-driven multiwan gateway с отдельным industrial service layer**.

Итоговый вывод для MYXON:
**MYXON стоит проектировать как edge-runtime, в котором low-level network config, uplink policy/failover logic и industrial protocol services разделены на отдельные слои и управляются независимыми runtime-компонентами.**

## Локальный дамп устройства (подтверждено 28 March 2026)
В репозитории подготовлен и заполнен отдельный каталог полного локального среза файловой системы устройства:
- `ixon_dump_full` (порядка `52M` по `du -sh`)

Пометка по составу папки `ixon_dump_full`:
- присутствуют ключевые каталоги runtime:
  - `bin`
  - `etc`
  - `lib`
  - `sbin`
  - `usr`
  - `www`
  - `root`
- также присутствуют:
  - `rom`
  - `overlay`
- отсутствует:
  - `home` (на текущем дампе не найден)

Критично для реверса `ixagent`:
- найден `bin/ixagent`
- найден `etc/init.d/ixagent`
- найден `etc/ixon/ixagent.conf`
- найдены package-метаданные `usr/lib/opkg/info/ixagent.*`

## Следующие инженерные шаги по MYXON
1. Зафиксировать в проекте разделение на Confirmed / Hypothesis и поддерживать его при каждом новом шаге реверс-анализа
2. Проверить поведение и grammar интерфейса `9230` как отдельного push/event канала
3. Снять read-only данные о системе: `uname`, `/etc/openwrt_release`, `/proc/mtd`, `ps`, `netstat/ss`, `init/services`
4. Безопасно разобраться с картой SPI flash и разделов firmware/config
5. Отделить в концепции MYXON: edge boot/recovery, edge runtime, control plane
6. Описать bootstrap / enrollment flow для собственного устройства
7. Спроектировать recovery-стандарт и дефолтную recovery-сеть
8. Подготовить первый архитектурный черновик MYXON как mini-IXON
9. После этого перейти к прототипу собственного dispatcher/eventbus для MYXON

1. Продолжать вести разделение Confirmed / Hypothesis и поддерживать его при каждом новом шаге реверс-анализа
2. Проверить поведение и grammar интерфейса `9230` как отдельного push/event канала
3. Выяснить, как именно читается и применяется `PASS` в локальном control protocol `ixagent`
4. Выяснить точный grammar `config dump` и других команд компонента `config`
5. Добрать команды и статусы конкретных компонентов (`multiwan`, `gpio`, `openvpn`, `apiclient`)
6. Уточнить, есть ли реальная активная relay-логика для UDP broadcast помимо установленного модуля `udp-broadcast-relay`
7. Отделить в концепции MYXON: edge boot/recovery, edge runtime, control plane
8. Описать bootstrap / enrollment flow для собственного устройства
9. Спроектировать recovery-стандарт и дефолтную recovery-сеть
10. Подготовить первый архитектурный черновик MYXON как mini-IXON
11. После этого перейти к прототипу собственного dispatcher/eventbus для MYXON

## Черновой тезис проекта

**MYXON = собственный управляемый edge-access gateway для объектов, построенный по схеме Edge Node + Recovery Layer + Control Plane, с упором на безопасный bootstrap, удаленный доступ и повторяемое восстановление.**
