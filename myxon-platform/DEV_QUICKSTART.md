# MYXON Platform — быстрый старт (dev)

## Архитектура

```
Контроллер (порт 5843)
    ↓ LAN
Orange Pi [Debian]
    ├── авто-дискавери → находит контроллер сам
    ├── frpc → тоннель к серверу
    └── heartbeat каждые 15 сек
         ↓ internet / LAN
MYXON Сервер (Mac / VPS)
    ├── FRPS      :7000  ← принимает тоннели от агентов
    ├── Backend   :8000
    └── Frontend  :3000
                    ↑
             Браузер пользователя
```

Агент **сам** сканирует LAN-интерфейс Orange Pi, находит контроллеры по известным портам (5843 для HOTRACO Remote+), и пробрасывает их через тоннель. Никакого ручного указания IP.

---

## Часть 1 — Сервер (Mac)

```bash
cd myxon-platform
./dev.sh
```

Поднимает PostgreSQL + Redis + FRPS, запускает backend и frontend с hot-reload.

| Сервис | URL |
|--------|-----|
| Frontend | http://localhost:3000 |
| Backend / Swagger | http://localhost:8000/docs |
| FRPS dashboard | http://localhost:7500 |

**Тестовые пользователи:**

| Email | Пароль | Роль |
|-------|--------|------|
| admin@myxon.local | admin123 | admin |
| engineer@myxon.local | engineer123 | engineer |
| viewer@myxon.local | viewer123 | viewer |

---

## Часть 2 — Orange Pi (агент)

### Подготовить конфиг (на Mac)

```bash
cd edge-agent
cp agent.env.example agent.env
```

Изменить **только две строки**:

```env
# IP Mac'а в локальной сети (для dev) или публичный адрес сервера (для prod)
MYXON_CLOUD_URL=http://192.168.1.YYY:8000

# Серийник — один из демо-серийников из seed
MYXON_SERIAL=HOTRACO-ORN-001
```

Всё остальное агент определяет сам: сканирует LAN, находит контроллер, строит тоннель.

### Скопировать и установить на Orange Pi

```bash
# Скопировать папку агента
scp -r edge-agent/ user@<orange-pi-ip>:/tmp/myxon-agent

# Установить (один раз)
ssh user@<orange-pi-ip> "cd /tmp/myxon-agent && sudo bash setup-debian.sh"
```

Скрипт установит Python, скачает frpc для arm64/armv7 и зарегистрирует systemd-сервис.

### Запустить

```bash
ssh user@<orange-pi-ip> "sudo systemctl start myxon-agent"
```

### Проверить логи

```bash
ssh user@<orange-pi-ip> "journalctl -u myxon-agent -f"
```

Ожидаемый вывод:
```
MYXON Agent v0.2 starting
  serial : HOTRACO-ORN-001
  server : http://192.168.1.YYY:8000
Discovery: scanning 192.168.1.0/24 (254 hosts) on iface eth0
Discovery: found HOTRACO Remote+ at 192.168.1.100:5843
Registered. device_id=... tunnel_port=10001
frpc started (PID 1234)
Heartbeat OK (uptime 15s)
```

---

## Часть 3 — Браузер

1. Открыть `http://localhost:3000`
2. Войти: `admin@myxon.local` / `admin123`
3. **ClaimWizard** → ввести серийник `HOTRACO-ORN-001` → подтвердить
4. Открыть устройство → секция **Direct HMI** → экран контроллера живьём

---

## Остановка

```bash
# Сервер (Mac)
Ctrl+C

# Агент (Orange Pi)
sudo systemctl stop myxon-agent
```
