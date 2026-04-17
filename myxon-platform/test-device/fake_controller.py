"""
Fake HOTRACO Climate Controller — тестовый HMI.

Запускается в Docker-контейнере вместе с MYXON-агентом.
Имитирует веб-интерфейс промышленного контроллера климата:
  - Температура, влажность, CO2, скорость воздуха
  - Статус вентиляторов и нагревателей
  - Кнопка подтверждения аларма

Слушает на порту 8080 (HTTP, не бинарный TCP как реальный Remote+).
"""

import http.server
import json
import os
import random
import time

PORT = int(os.environ.get("CONTROLLER_PORT", 8080))

# Базовые значения — будут чуть варьироваться при каждом запросе
_BASE = {
    "temp_house":   22.4,
    "temp_outside": 8.1,
    "humidity":     63.0,
    "co2":          1240,
    "air_speed":    1.8,
}


def _jitter(val: float, pct: float = 0.03) -> float:
    """Добавить ±pct% случайного шума — имитация живых данных."""
    return round(val * (1 + random.uniform(-pct, pct)), 1)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MYXON — Fake Controller HMI</title>
<style>
  :root {{
    --bg:     #0d1117;
    --panel:  #161b22;
    --border: #30363d;
    --green:  #3fb950;
    --yellow: #d29922;
    --red:    #f85149;
    --blue:   #58a6ff;
    --text:   #e6edf3;
    --muted:  #8b949e;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    min-height: 100vh;
    padding: 24px;
  }}
  header {{
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 24px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 16px;
  }}
  header .dot {{
    width: 12px; height: 12px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 8px var(--green);
    animation: pulse 2s infinite;
  }}
  @keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50%       {{ opacity: 0.4; }}
  }}
  header h1 {{ font-size: 20px; font-weight: 600; }}
  header .serial {{ color: var(--muted); font-size: 13px; margin-left: auto; }}

  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }}
  .card {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
  }}
  .card .label {{ font-size: 12px; color: var(--muted); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; }}
  .card .value {{ font-size: 32px; font-weight: 700; font-variant-numeric: tabular-nums; }}
  .card .unit  {{ font-size: 14px; color: var(--muted); margin-left: 4px; }}

  .temp   {{ color: var(--yellow); }}
  .humid  {{ color: var(--blue); }}
  .co2    {{ color: #bc8cff; }}
  .wind   {{ color: var(--green); }}

  .status-row {{
    display: flex; gap: 12px; flex-wrap: wrap;
    margin-bottom: 24px;
  }}
  .badge {{
    display: flex; align-items: center; gap: 8px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
  }}
  .badge .led {{
    width: 8px; height: 8px;
    border-radius: 50%;
  }}
  .led-ok  {{ background: var(--green); box-shadow: 0 0 6px var(--green); }}
  .led-off {{ background: var(--muted); }}
  .led-err {{ background: var(--red); box-shadow: 0 0 6px var(--red); animation: pulse 1s infinite; }}

  .alarm-box {{
    background: #2d1b1b;
    border: 1px solid var(--red);
    border-radius: 8px;
    padding: 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 24px;
  }}
  .alarm-icon {{ font-size: 28px; }}
  .alarm-text {{ flex: 1; }}
  .alarm-text .alarm-title {{ font-weight: 600; color: var(--red); margin-bottom: 4px; }}
  .alarm-text .alarm-sub   {{ font-size: 13px; color: var(--muted); }}

  .btn-ack {{
    background: var(--red);
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity .15s;
    white-space: nowrap;
  }}
  .btn-ack:hover  {{ opacity: .85; }}
  .btn-ack:active {{ opacity: .65; }}

  .footer {{ font-size: 12px; color: var(--muted); margin-top: 24px; }}

  /* Toast */
  #toast {{
    position: fixed; bottom: 24px; right: 24px;
    background: var(--green); color: #000;
    padding: 12px 20px; border-radius: 6px;
    font-weight: 600; font-size: 14px;
    opacity: 0; transition: opacity .3s;
    pointer-events: none;
  }}
</style>
</head>
<body>

<header>
  <div class="dot"></div>
  <h1>Климат — Птичник №3</h1>
  <span class="serial">SN: {serial} &nbsp;|&nbsp; MYXON Test Device</span>
</header>

<div class="grid">
  <div class="card">
    <div class="label">Температура (корпус)</div>
    <span class="value temp" id="temp">{temp_house}</span>
    <span class="unit">°C</span>
  </div>
  <div class="card">
    <div class="label">Температура (улица)</div>
    <span class="value temp" id="temp_out">{temp_outside}</span>
    <span class="unit">°C</span>
  </div>
  <div class="card">
    <div class="label">Влажность</div>
    <span class="value humid" id="humid">{humidity}</span>
    <span class="unit">%</span>
  </div>
  <div class="card">
    <div class="label">CO₂</div>
    <span class="value co2" id="co2">{co2}</span>
    <span class="unit">ppm</span>
  </div>
  <div class="card">
    <div class="label">Скорость воздуха</div>
    <span class="value wind" id="wind">{air_speed}</span>
    <span class="unit">м/с</span>
  </div>
</div>

<div class="status-row">
  <div class="badge"><div class="led led-ok"></div> Вентилятор 1</div>
  <div class="badge"><div class="led led-ok"></div> Вентилятор 2</div>
  <div class="badge"><div class="led led-off"></div> Нагреватель</div>
  <div class="badge"><div class="led led-ok"></div> Охлаждение</div>
  <div class="badge"><div class="led led-err" id="alarm-led"></div> Аларм CO₂</div>
</div>

<div class="alarm-box" id="alarm-box">
  <div class="alarm-icon">⚠️</div>
  <div class="alarm-text">
    <div class="alarm-title">АЛАРМ: CO₂ выше нормы</div>
    <div class="alarm-sub">Порог превышен &gt; 1200 ppm · {ts}</div>
  </div>
  <button class="btn-ack" onclick="ackAlarm()">ПОДТВЕРДИТЬ</button>
</div>

<div class="footer">
  Данные обновляются каждые 3 сек &nbsp;·&nbsp; Fake controller v1.0 &nbsp;·&nbsp;
  Tunnel OK via MYXON Agent
</div>

<div id="toast">✓ Аларм подтверждён</div>

<script>
// Автоматически обновляем данные с сервера каждые 3 секунды
async function refresh() {{
  try {{
    const r = await fetch('/data');
    const d = await r.json();
    document.getElementById('temp').textContent    = d.temp_house;
    document.getElementById('temp_out').textContent = d.temp_outside;
    document.getElementById('humid').textContent   = d.humidity;
    document.getElementById('co2').textContent     = d.co2;
    document.getElementById('wind').textContent    = d.air_speed;
  }} catch(e) {{ /* ignore */ }}
}}
setInterval(refresh, 3000);

function ackAlarm() {{
  document.getElementById('alarm-box').style.display = 'none';
  document.getElementById('alarm-led').className = 'led led-off';
  const t = document.getElementById('toast');
  t.style.opacity = '1';
  setTimeout(() => t.style.opacity = '0', 2500);
}}
</script>
</body>
</html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Тихий логгинг — только ошибки
        pass

    def do_GET(self):
        if self.path == "/data":
            # JSON endpoint для автообновления
            data = {k: _jitter(v) for k, v in _BASE.items()}
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path in ("/", "/index.html"):
            data = {k: _jitter(v) for k, v in _BASE.items()}
            data["serial"] = os.environ.get("MYXON_SERIAL", "MX-TEST-001")
            data["ts"] = time.strftime("%H:%M:%S")
            html = HTML_TEMPLATE.format(**data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Fake controller listening on :{PORT}", flush=True)
    server.serve_forever()
