# REMOTE_PLUS_PROTOCOL_SPEC

## 1. Scope

Документ описывает прикладной протокол Remote+ (по результатам статического reverse engineering Android app `Remote+_1.2.0`).

Важно:
- текущий протокол и runtime-паттерны относятся к стеку HOTRACO/SyslinQ (вендор-специфичная реализация на базе IXON);
- это не универсальный промышленный стандарт для всех вендоров;
- для MYXON этот документ используется как один из vendor adapters, а не как единственная модель.

Архитектурная интерпретация для MYXON:
- HOTRACO выступает как клиент/интегратор платформенного connectivity-слоя (IXON-like), а не как определение ядра;
- роутерный transport, tunnel-механика и серверный routing должны проектироваться как универсальный слой;
- vendor-специфика (брендинг, UX, семейства устройств, keymaps, device behavior) должна жить в отдельном слое адаптеров.

Статус:
- High confidence: framing, command IDs, ключевые payload форматы, runtime workflow.
- High confidence: retry/timeout семантика (`MediationBusy`, `Incomplete`, resend loop).

---

## 2. Transport

- Базовый транспорт: TCP socket.
- Основной endpoint (remote mode): `smartlinkserver.com:5843`.
- В нативном TCP plugin найден fallback:
  - host: `5.157.85.29`
  - port: `5843`

Подтверждено по Android plugin (`TcpSocketPlugin/TcpSocketClient/TcpReceiverTask`):
- plain TCP (`java.net.Socket`), без TLS-обертки на plugin-уровне.
- чтение из сокета чанками `8192` bytes.
- default plugin timeout = `0` (если не передан), но app layer обычно передает `20000`.
- bind перед connect: `localAddress` (default `0.0.0.0`) и `localPort` (default `0`).
- bridge между JS и native идет через Base64:
  - `write(base64String)` -> native decode,
  - `onData` -> JS получает Base64-строку.

---

## 3. Frame Format

Сообщение формируется как ASCII-кадр:

`@ + DEST(3hex) + SRC(3hex) + CMD(3hex) + SUB(1hex) + BLOCK(2hex) + LEN(2hex) + DATA(hex) + CRC(2hex) + * + \r`

Где:
- `@` — start marker
- `DEST` — destination ID
- `SRC` — source ID
- `CMD` — command ID
- `SUB` — sub-command/fragment control
- `BLOCK` — block counter
- `LEN` — длина payload в байтах
- `DATA` — hex payload
- `CRC` — XOR checksum по символам строки до CRC
- `*` — end marker
- `\r` — terminator

---

## 4. Utility Functions (confirmed)

- `iu(str, pad=0)`:
  - string -> hex uppercase (charCode per symbol, `padStart(pad,"0")`)
- `CQ(num, pad=2)`:
  - number -> hex uppercase fixed width
- `Ed(hex)`:
  - `parseInt(hex,16)`
- `Yx(str)`:
  - XOR checksum по `charCodeAt` всей строки

---

## 5. Enums

### 5.1 Command IDs (`CMD`)

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

### 5.2 Address IDs

- `Pc = 1023`
- `General = 1018`
- `SmartLinkServer = 1184`

### 5.3 Sub-command (`SUB`)

- `Begin = 0`
- `Repeat = 1`
- `Next = 2`
- `End = 5`

### 5.4 Parse status

- `Ignore = -1`
- `Incomplete = 0`
- `Complete = 1`

### 5.5 Login/mediation status values

- `UsernameSuccess = 1`, `UsernameError = 0`
- `PasswordSuccess = 1`, `PasswordError = 0`
- `MediationSuccess = 1`, `MediationBusy = 0`, `MediationError = 2`

---

## 6. Request Payloads

### 6.1 `ComputersRequest (4091)`

`DATA = authData(username, hashedPassword, "")`

`authData`:
1. `iu(username,2).padEnd(40,"0")`
2. `hashedPassword.padStart(40,"0").toUpperCase()`
3. `iu(address,2)` (в этом случае пусто)

`hashedPassword` в app считается как SHA-1(password):
- модуль `7292` реализует SHA-1 digest (`_digestsize=20`),
- на уровень `authData` подается hex-строка длиной 40 символов.

### 6.2 `MediateRequest (4092)`

`DATA = authData(username, hashedPassword, address)`

### 6.3 `ConfigurationRead (2)`

`DATA = ""` (пустой payload)

### 6.4 `CaptureScreen/CaptureScreenFast (92/96)`

`DATA = CQ(mode)`:
- `ScreenUpdate = 0`
- `ScreenComplete = 1`

### 6.5 `SendKey (93)`

`DATA = CQ(keyCode)`

### 6.6 `MainGroupRead (6)`

`DATA = ""`

---

## 7. Response Payloads

### 7.1 `ComputersRequest` response

Первые байты:
- `[0..2)` username status
- `[2..4)` password status

Далее `connectionsBlock = data[4..]`, каждая запись 60 hex:
- `[0..20)` address/id (hex string -> decode)
- `[20..60)` name (hex string -> decode/trim/remove null)

Результат: `connections[] = { id:+address, address, name, port: undefined }`

### 7.2 `MediateRequest` response

- username/password статусы как выше
- mediation status: `[4..6)`

Интерпретация:
- `MediationSuccess` -> `Complete`
- `MediationBusy` -> `Ignore`
- `MediationError` -> error `CONNECT_FAILURE`

### 7.3 `ConfigurationRead` response

- `password = data[0..4)` (u16)
- далее записи `deviceConfig`, каждая 40 hex (20 bytes):
  1. `computer` `[0..4)` u16
  2. `sort` `[4..8)` u16
  3. `type` `[8..12)` u16 bitmask
  4. `company` `[12..16)` u16
  5. `computerVersion` `[16..20)` u16
  6. `pcVersion` `[20..24)` u16
  7. `serial` `[24..32)` u32
  8. `number` `[32..36)` u16
  9. `optionsChangeCount` `[36..40)` u16

### 7.4 `CaptureScreen/CaptureScreenFast` response

- parser возвращает raw: `{ command, screen: data }`
- декодирование `screen` выполняют family-specific UI-компоненты (Orion/Sirius/Cygnus).

### 7.4.1 Family decoder details (from `7112.f02ef8a2bee72d81.js`)

Общее:
- UI-компонент получает `screenData={data, command}`.
- при `command == CaptureScreenFast` первый байт payload читается как режим (`s`).

#### Cygnus (`app-cygnus`)
- размер: `128x64`
- key map:
  - `up=19`, `right=18`, `down=20`, `left=17`, `ok=21`
  - `f1=64`, `f2=65`, `f3=66`, `f4=67`
- декодер: битовый поток + RLE-подобные блоки, с remap индекса пикселя внутри строки.

#### Orion (`app-orion`)
- размер: `240x128`
- key map:
  - navigation: `up=19`, `right=18`, `down=20`, `left=17`, `ok=21`
  - symbols: `plusminus=22`, `dot=46`
  - numeric: `num0..num9 = 48..57`
  - function: `f1..f6 = 64..69`
  - paging: `prev=80`, `next=81`
- декодер: битовый поток + RLE-подобные блоки (без cygnus-remap).

#### Sirius (`app-sirius`)
- размер: `122x32`
- key map:
  - `up=1`, `right=3`, `down=2`, `ok=4`
  - `key1..key10 = 16..25`
- декодер: последовательный unpack битов в framebuffer.

### 7.4.2 Bit-level grammar (Orion/Cygnus)

`CaptureScreenFast`:
- первый байт payload: `s` (`00` или `01`).
- для `CaptureScreen` (full) `s` по коду остается `0` (де-факто full decode path).

Итерация идет по байтовым токенам `l` (hex byte), начиная с конца framebuffer (`r = pixels.length - 1`).

Режим `s == 0`:
- `l == 0xFF`:
  - следующий байт `h`
  - записать `8*h` пикселей в цвет A (в Orion: black, в Cygnus: white)
- `l == 0x00`:
  - следующий байт `h`
  - записать `8*h` пикселей в цвет B (в Orion: white, в Cygnus: black)
- иначе:
  - распаковать 8 бит `l` (MSB->LSB), каждый бит = 1/0 -> цвет A/B

Режим `s == 1` (delta/update):
- `l == 0x00`:
  - следующий байт `h`
  - если `h == 0x00`:
    - special literal block: распаковать 8 бит текущего `l` (то есть нулевого байта) по условию в коде.
  - иначе:
    - skip `8*h` пикселей (без записи)
- иначе:
  - распаковать 8 бит как в full режиме.

Примечание:
- Cygnus использует remap индекса пикселя по формуле отражения внутри строки:
  - `v = r - (r % width) + width - (r % width) - 1`
- Orion пишет линейно в `pixels[r]`.

### 7.4.3 Bit-level grammar (Sirius)

Алгоритм:
- обрабатываются байты payload по порядку.
- каждый байт распаковывается на 8 бит (LSB-first по фактической проверке `l>>c` при `c=0..7` в цикле с инкрементом позиции).
- запись в `pixels[e + s*width]`, где:
  - `s` инкрементируется до `screenHeight`,
  - затем `s=0`, `e++`.

Цвета:
- bit=1 -> black
- bit=0 -> white

Отличие от Orion/Cygnus:
- нет явных RLE-token веток `0xFF/0x00`.

### 7.5 `MainGroupRead` response

- `alarm.code = data[0..4)`
- `alarm.state` вычисляется из смещения `alarmColor.startIndex/length` (из device profile).

---

## 8. Fragmentation / Retry Behavior

Клиент при обработке frame:
- если command mismatch + `CMD=None` -> error `UNKNOWN_ERROR`
- если command mismatch + `CMD=MainGroupChanged` -> `Ignore`
- если CRC mismatch или несоответствие -> `SUB=Repeat`, статус `Incomplete`
- если маркер блока `+` (`EndBlock`) -> накопление блока, `SUB=Next`, `Incomplete`
- если блок завершен корректно -> parse payload -> `Complete`

Клиентский timeout: `20s` (в app constants).

### 8.1 TCP boundary caveat

В socket wrapper (`class Pn`, module `2552`) входящий data path:
- `onData(bytes) -> TextDecoder.decode(bytes) -> message$.next(textChunk)`.

На этом уровне явной сборки по границе `@...*\\r` нет.  
Следствие:
- целостность кадра обеспечивается выше (`handleReceived` + `Incomplete/Repeat`),
- при TCP fragmentation возрастает число retry/Incomplete циклов.

---

## 9. Device/UI Mapping

Из конфигурации app:
- family IDs: `OrionLegacy/Orion`, `SiriusLegacy/Sirius`, `Cygnus`, `Thomas`
- branding/UX определяется через `computer + sort + company`
- выбираются:
  - `name`
  - `interface.background`
  - `interface.svgUrl`
  - `alarmColor` offsets

Следствие: один протокол, но разные UI-темы и декодеры экрана по семейству устройств.

---

## 10. End-to-End State Machine (Remote mode)

1. TCP connect to server (`smartlinkserver.com:5843`)
2. `ComputersRequest` -> список connections
3. `MediateRequest` -> mediation grant/deny/busy
4. Runtime connection/socket for selected target
5. `ConfigurationRead` -> список devices
6. For selected device:
   - loop `CaptureScreenFast`
   - on input `SendKey`
   - optional `MainGroupRead`
7. `Close` on disconnect

---

## 11. Error Model (observed)

- `LOGIN_INVALID` (username/password fail на `ComputersRequest`)
- `LOGIN_EXPIRED` (auth fail на mediation/дальнейших шагах)
- `CONNECT_FAILURE` (`MediationError`)
- `REQUEST_TIMEOUT` (клиентский timeout)
- `UNKNOWN_ERROR` (`CMD=None` при mismatch)
- `REMOTE_MODULE_NOT_ACTIVATED` (если не найден `primaryDevice` после конфигурации)

---

## 12. Compatibility Checklist (for MYXON)

Минимум для wire-compatible прототипа:
1. Реализовать exact framing (`@...*\r`) и XOR checksum.
2. Поддержать command/address IDs как в таблицах.
3. Реализовать `authData` packing (username/pass/address).
4. Реализовать parser `ConfigurationRead` с 9-польным deviceConfig.
5. Реализовать runtime команды `CaptureScreenFast`, `SendKey`, `MainGroupRead`, `Close`.
6. Поддержать fragmentation (`Repeat/Next`, block accumulation).
7. Ввести mapping layer для UI family/branding отдельно от transport.

Требование к архитектуре реализации:
- transport/core и vendor/device логика не должны смешиваться в одном модуле;
- совместимость с Remote+ реализуется как `vendor=hotraco` adapter поверх универсального ядра.

Текущие реализованные артефакты:
- `tools/remote_plus_proto/protocol.py`
- `tools/remote_plus_proto/parsers.py`
- `tools/remote_plus_proto/reassembly.py`
- `tools/remote_plus_proto/session_engine.py`
- `tools/remote_plus_proto/screen_decode.py`
- `tools/remote_plus_proto/runtime.py`
- `tools/remote_plus_proto/device_profiles.json`
- `tools/remote_plus_proto/device_profiles.schema.json`
- `tools/remote_plus_proto/profiles.py`
- `tools/remote_plus_tool.py`
- `REMOTE_PLUS_CHECKLIST_STATUS.md`

Дополнительные требования совместимости (из deep RE Android):
- учитывать JS/native boundary (base64 payload в mobile bridge);
- учитывать company/location context в верхнем API слое (в экосистеме SyslinQ это выражено через `IXapi-Company` и маршруты вида `locations/:companyId/:agentId/:serverId`).
- учитывать company feature flags для протоколов доступа (например, семантика `vncAccessAll` в SyslinQ/Hotraco экосистеме).

---

## 13. Gaps / TODO

Транспортные/протокольные gap'ы для Remote+ закрыты статическим анализом кода приложения.

Подтверждено по runtime-коду (`class Je.createAction` + enum constants):
- при `status=Ignore` (включая `MediationBusy`) клиент не завершает request, а продолжает polling;
- при `status=Incomplete` клиент явно делает resend того же frame (`socket.send(Ut.toSend())`);
- между циклами применяется задержка `Delay=250ms`;
- общий таймаут запроса `Timeout=20000ms`, после чего ошибка `REQUEST_TIMEOUT`.

Остаются только не-блокирующие расширения (не мешают wire/runtime совместимости):
- полный key-code catalog для всех брендов/тем (база уже есть для Orion/Cygnus/Sirius);
- дополнительные edge-cases экранных payload на «грязной» сети (для robustness-тестов).

---

## 14. Keycode Appendix (current extraction)

### 14.1 Orion

- `up=19`, `right=18`, `down=20`, `left=17`, `ok=21`
- `plusminus=22`, `dot=46`
- `num0..num9 = 48..57`
- `f1=64`, `f2=65`, `f3=66`, `f4=67`, `f5=68`, `f6=69`
- `prev=80`, `next=81`

### 14.2 Cygnus

- `up=19`, `right=18`, `down=20`, `left=17`, `ok=21`
- `f1=64`, `f2=65`, `f3=66`, `f4=67`

### 14.3 Sirius

- `up=1`, `right=3`, `down=2`, `ok=4`
- `key1..key10 = 16..25`

---

## 15. Decoder Implementation Notes (for MYXON)

1. Делайте отдельные декодеры на family level (`orion`, `cygnus`, `sirius`), не пытайтесь одним универсальным unpacker.
2. Для Orion/Cygnus обязательно различайте:
   - full path (`s=0`)
   - delta path (`s=1`) со skip-семантикой.
3. Для Cygnus сохраните remap формулу строки, иначе картинка будет зеркалиться/ломаться.
4. На transport слое держите reassembly буфер по delimiter `\r`, даже если legacy-клиент полагается на retry.
5. Проектируйте MYXON как мультивендорную платформу: HOTRACO/Remote+ должен быть изолирован в отдельном адаптере (`vendor=hotraco`), с независимыми адаптерами для других производителей.

---

## 16. Target Layering (Core / Vendor / Device)

### 16.1 Universal Connectivity Core
- Edge identity/onboarding.
- Tunnel/session transport.
- Routing, authN/authZ, multi-tenant boundaries.
- Unified observability/logging.
- Policy enforcement hooks для company/location context (включая deny-reasons и audit).

### 16.2 Vendor Integration Layer
- Tenant-level integrations (например, HOTRACO).
- Branding and UX policy.
- Vendor API adapters and provisioning rules.

### 16.3 Device Family Protocol Layer
- Device protocol handlers (Orion/Cygnus/Sirius и др.).
- Frame/payload codecs, keymaps, screen decoders.
- Capability matrix per family/model.

Ключевой принцип:
- изменения в одном вендор-адаптере не должны требовать изменения transport/core.

---

## 17. Activation and Entitlement Gate (inferred)

Наблюдение по связке Android apps + firmware dump:
- удаленный VNC проходит через многоуровневый gate, а не только через online-состояние устройства.

Подтвержденные уровни:
1. `Module activation`:
- в клиентских строках есть явный признак неактивированного модуля (`REMOTE_MODULE_NOT_ACTIVATED`) и ошибки валидации модуля на focus device.

2. `Company policy`:
- обнаружены `IXapi-Company`, `IXapi-AccessLevel`, `vncAccessAll` и admin-операции по включению/выключению VNC policy.

3. `Transport reachability`:
- в дампе роутера есть DNAT для VNC/HTTP/vendor-port (`2000->5900`, `2001->8080`, `2002->5843`), что подтверждает роль туннеля/проброса.

Инженерный вывод для MYXON:
- transport слой должен быть отделен от entitlement/policy;
- даже при доступном туннеле сессия VNC должна открываться только после policy check:
`module_enabled && company_policy_allows && user_role_allows`.
