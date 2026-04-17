# REMOTE_PLUS Checklist Status (MYXON)

Источник чеклиста: `REMOTE_PLUS_PROTOCOL_SPEC.md` -> `## 12. Compatibility Checklist (for MYXON)`.

Важно по границам применимости:
- данный чеклист закрывает совместимость именно с HOTRACO/Remote+ стеком;
- для MYXON обязательно сохранять мультивендорную архитектуру (vendor adapters), чтобы поддерживать и другие типы контроллеров/протоколов.
- HOTRACO трактуется как vendor integration слой (tenant/client платформы), а не как универсальное ядро transport.

Архитектурная рамка для реализации:
- `Universal Connectivity Core`: туннель/сессии/маршрутизация/безопасность.
- `Vendor Integration Layer`: брендинг, UX, API-интеграции конкретного клиента (например HOTRACO).
- `Device Family Protocol Layer`: протоколы и декодеры конкретных семейств устройств.

## Статус выполнения

1. Exact framing (`@...*\\r`) + XOR checksum  
Статус: `Done`  
Реализация: `tools/remote_plus_proto/protocol.py` (`build_frame`, `parse_frame`, `checksum_xor`).

2. Command/address IDs  
Статус: `Done`  
Реализация: `tools/remote_plus_proto/protocol.py` (`CommandId`, `AddressId`, `SubCommand`).

3. `authData` packing  
Статус: `Done`  
Реализация: `tools/remote_plus_proto/protocol.py` (`pack_auth_data`).

4. Parser `ConfigurationRead` (9 полей)  
Статус: `Done`  
Реализация: `tools/remote_plus_proto/parsers.py` (`parse_configuration_read_response`).

5. Runtime commands (`CaptureScreenFast`, `SendKey`, `MainGroupRead`, `Close`)  
Статус: `Done`  
Что сделано:
- сборка кадра любой команды через `build_frame`
- декодеры screen payload для Orion/Cygnus/Sirius в `tools/remote_plus_proto/screen_decode.py`
- runtime socket loop + command dispatch: `tools/remote_plus_proto/runtime.py`
- CLI для стендового прогона runtime-запроса: `tools/remote_plus_tool.py` (`runtime-once`)

6. Fragmentation (`Repeat/Next`, block accumulation)  
Статус: `Done`  
Что сделано:
- транспортный reassembly по stream chunks -> frames: `tools/remote_plus_proto/reassembly.py`  
- stateful command-level accumulation с учетом `SUB`, `BLOCK`, `End`: `tools/remote_plus_proto/session_engine.py`.

7. Mapping layer UI family/branding отдельно от transport  
Статус: `Done`  
Что сделано:
- family-level screen decoders и keymaps зафиксированы в спецификации.
- отдельный catalog профилей: `tools/remote_plus_proto/device_profiles.json`
- schema профилей: `tools/remote_plus_proto/device_profiles.schema.json`
- Python mapping loader: `tools/remote_plus_proto/profiles.py`
- CLI доступ к mapping: `tools/remote_plus_tool.py` (`profile`)

8. Native TCP plugin semantics (Android bridge contract)  
Статус: `Done`  
Что подтверждено:
- методы плагина: `connect`, `write(base64String)`, `destroy`;
- события: `onConnect`, `onData`, `onError`, `onClose`, `connection`;
- receiver loop: chunk read `8192`, transport без message framing;
- дефолты соединения: `host=5.157.85.29`, `port=5843`, `localAddress=0.0.0.0`, `reuseAddress=true`;
- compatibility quirk: в `onConnection` поле `info.address` перезаписывается пустым объектом (не использовать как источник истины).

## CLI утилита

Инструмент:
- `tools/remote_plus_tool.py`

Примеры:

```bash
python3 tools/remote_plus_tool.py build-auth \
  --username demo \
  --hashed-password 0123456789ABCDEF
```

```bash
python3 tools/remote_plus_tool.py build-frame \
  --cmd 4091 \
  --payload-hex "<HEX_PAYLOAD>"
```

```bash
python3 tools/remote_plus_tool.py parse-response \
  --kind config \
  --data-hex "<HEX_DATA>"
```

```bash
python3 tools/remote_plus_tool.py decode-screen \
  --family orion \
  --screen-hex "<HEX_SCREEN>" \
  --fast \
  --out /tmp/orion.pgm
```

## Traceability: Spec -> Code Coverage

Ниже матрица соответствия разделов `REMOTE_PLUS_PROTOCOL_SPEC.md` текущей реализации.

| Spec section | Статус | Реализация |
|---|---|---|
| `§3 Frame Format` | Covered | `tools/remote_plus_proto/protocol.py` (`build_frame`, `parse_frame`) |
| `§4 Utility Functions` | Covered | `protocol.py` (`encode_hex_int`, `encode_ascii_hex`, `decode_ascii_hex`, `checksum_xor`) |
| `§5 Enums` | Covered | `protocol.py` (`CommandId`, `AddressId`, `SubCommand`, `ParseStatus`) |
| `§6.1/6.2 authData` | Covered | `protocol.py` (`pack_auth_data`) |
| `§7.1 ComputersRequest parser` | Covered | `tools/remote_plus_proto/parsers.py` (`parse_computers_response`) |
| `§7.2 MediateRequest parser` | Covered | `parsers.py` (`parse_mediate_response`) |
| `§7.3 ConfigurationRead parser` | Covered | `parsers.py` (`parse_configuration_read_response`) |
| `§7.4 Screen decoders` | Covered | `tools/remote_plus_proto/screen_decode.py` (`decode_orion/cygnus/sirius`) |
| `§7.5 MainGroupRead parser` | Covered | `parsers.py` (`parse_main_group_response`) |
| `§8 Fragmentation` | Covered | `tools/remote_plus_proto/reassembly.py`, `tools/remote_plus_proto/session_engine.py` |
| `§10 Runtime state machine` | Covered | `tools/remote_plus_proto/runtime.py` + CLI `runtime-once` |
| `§14 Keycode appendix` | Covered | `tools/remote_plus_proto/device_profiles.json` + `profiles.py` |
| `§15 Decoder implementation notes` | Covered | `screen_decode.py`, `device_profiles.*` |
| Android TCP bridge semantics | Covered | зафиксировано в `ANDROID_APPS_AS_IS_REPORT.md` §62 |

## Остаточные задачи (не реверс, а production-hardening)

1. Добавить unit/integration тесты на:
- CRC mismatch -> `Repeat`;
- block accumulation (`Begin/Next/End`);
- edge-cases `CaptureScreenFast` (dirty/incomplete chunks).

2. Добавить replay/pcap-like fixtures:
- эталонные raw chunks и expected parsed messages;
- эталонные screen payload samples для Orion/Cygnus/Sirius.

3. Ввести строгие runtime guardrails:
- backoff policy на reconnect;
- retry budget и circuit breaker;
- structured logs/metrics (`cmd`, `sub`, `block`, `retry_count`, `latency_ms`).

4. Закрыть compatibility caveat по `onConnection.info.address`:
- не использовать поле как source of truth;
- опираться на `onConnect` + локальный runtime state.

## Verification (code-level)

Добавлен автотест-пакет:
- `tests/test_remote_plus_proto.py`

Покрытые зоны:
- framing/CRC/parse (`protocol.py`);
- auth packing;
- response parsers (`computers`, `mediate`, `configuration`, `main-group`);
- stream reassembly;
- session accumulation (`BEGIN/NEXT/END`);
- screen decoders (`orion/cygnus/sirius`);
- profiles loader/resolver.

Локальный прогон:

```bash
python3 -m unittest -v tests/test_remote_plus_proto.py
```

Результат: `13 passed`.
