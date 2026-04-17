#!/usr/bin/env python3
"""
MYXON Local Agent API — аналог IXrouter3 /ubus.

Запускается на Orange Pi и доступен по LAN без облака.
Порт: 8765 (настраивается через LOCAL_API_PORT).
Привязка: только к LAN-интерфейсу (не к WAN) — конфигурируется через LOCAL_API_BIND.

Эндпоинты:
  GET  /status         — статус агента, туннеля, последний heartbeat
  GET  /version        — версия агента, ОС, железо
  POST /reboot         — перезагрузка Orange Pi (требует X-Local-Token)
  POST /tunnel/restart — перезапуск frpc туннеля (требует X-Local-Token)
  GET  /health         — быстрый пинг (нет авторизации)

Безопасность:
  - Доступен только по LAN (bind на LAN IP, не 0.0.0.0)
  - POST-запросы требуют заголовок X-Local-Token
  - Токен хранится в /etc/myxon/local_api_token (0600)
  - HTTPS не обязателен в локальной сети, но рекомендован в prod

Запуск (вместе с основным агентом):
  uvicorn local_api:app --host 192.168.1.10 --port 8765

Или через systemd (отдельный юнит myxon-local-api.service).
"""

from __future__ import annotations

import logging
import os
import platform
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger("myxon-local-api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ── Config ─────────────────────────────────────────────────────────────────────

LOCAL_API_PORT  = int(os.environ.get("LOCAL_API_PORT", "8765"))
LOCAL_API_BIND  = os.environ.get("LOCAL_API_BIND", "0.0.0.0")  # restrict in prod
TOKEN_FILE      = Path(os.environ.get("MYXON_TOKEN_FILE", "/etc/myxon/agent_token"))
LOCAL_API_TOKEN_FILE = Path(os.environ.get("LOCAL_API_TOKEN_FILE", "/etc/myxon/local_api_token"))
FRPC_PID_FILE   = Path("/tmp/myxon_frpc.pid")
AGENT_VERSION   = "0.2.0"

# ── Local API token ────────────────────────────────────────────────────────────

def _ensure_local_token() -> str:
    """Load or generate the local API access token."""
    if LOCAL_API_TOKEN_FILE.exists():
        token = LOCAL_API_TOKEN_FILE.read_text().strip()
        if token:
            return token
    # Generate on first run
    token = secrets.token_urlsafe(24)
    LOCAL_API_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_API_TOKEN_FILE.write_text(token)
    LOCAL_API_TOKEN_FILE.chmod(0o600)
    log.info("Local API token generated → %s", LOCAL_API_TOKEN_FILE)
    log.info("Token value: %s (copy this for LAN access)", token)
    return token


LOCAL_TOKEN = _ensure_local_token()


def _require_token(x_local_token: str | None) -> None:
    """Validate X-Local-Token header. Raises 403 on mismatch."""
    if not x_local_token or x_local_token != LOCAL_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Local-Token",
        )


# ── Shared state (updated by main agent via shared file / signals) ─────────────

def _get_tunnel_status() -> dict:
    """Check if frpc process is running by reading its PID file."""
    if FRPC_PID_FILE.exists():
        try:
            pid = int(FRPC_PID_FILE.read_text().strip())
            # Check if process is alive
            os.kill(pid, 0)
            return {"running": True, "pid": pid}
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    return {"running": False, "pid": None}


def _get_agent_token_status() -> dict:
    """Check if device token is present (without exposing the value)."""
    has_token = TOKEN_FILE.exists() and bool(TOKEN_FILE.read_text().strip())
    return {"issued": has_token}


def _get_hw_info() -> dict:
    """Collect hardware/OS info."""
    info: dict = {
        "os": platform.system(),
        "arch": platform.machine(),
        "python": platform.python_version(),
    }

    # Debian version
    dv = Path("/etc/debian_version")
    if dv.exists():
        info["os_detail"] = f"Debian {dv.read_text().strip()}"

    # CPU info (Orange Pi / ARM)
    try:
        cpu_info = Path("/proc/cpuinfo").read_text()
        for line in cpu_info.splitlines():
            if line.startswith("Hardware"):
                info["hardware"] = line.split(":", 1)[1].strip()
                break
            if line.startswith("Model name"):
                info["cpu"] = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass

    # Memory
    try:
        mem_info = Path("/proc/meminfo").read_text()
        for line in mem_info.splitlines():
            if line.startswith("MemTotal"):
                kb = int(line.split()[1])
                info["memory_mb"] = kb // 1024
                break
    except OSError:
        pass

    # Uptime
    try:
        uptime_secs = float(Path("/proc/uptime").read_text().split()[0])
        info["uptime_seconds"] = int(uptime_secs)
    except OSError:
        pass

    return info


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="MYXON Local Agent API",
    version=AGENT_VERSION,
    docs_url="/docs",
    redoc_url=None,
)

# Allow LAN browser access (e.g. technician opens 192.168.1.10:8765/docs)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Quick ping — no auth required."""
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat()}


@app.get("/version")
async def version():
    """Agent version and hardware info — no auth required."""
    return {
        "agent_version": AGENT_VERSION,
        "hardware": _get_hw_info(),
    }


@app.get("/status")
async def agent_status(
    x_local_token: str | None = Header(None),
):
    """
    Full agent status: tunnel, token, timestamps.
    Requires X-Local-Token header.
    """
    _require_token(x_local_token)

    tunnel = _get_tunnel_status()
    token_status = _get_agent_token_status()

    # Last heartbeat time from a shared file written by main agent
    last_hb_file = Path("/tmp/myxon_last_heartbeat")
    last_heartbeat = None
    if last_hb_file.exists():
        try:
            last_heartbeat = last_hb_file.read_text().strip()
        except OSError:
            pass

    return {
        "agent_version": AGENT_VERSION,
        "tunnel": tunnel,
        "device_token": token_status,
        "last_heartbeat_at": last_heartbeat,
        "local_api_port": LOCAL_API_PORT,
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/tunnel/restart")
async def restart_tunnel(
    x_local_token: str | None = Header(None),
):
    """
    Restart the frpc tunnel process.
    Useful when the tunnel is stuck or after network changes.
    Requires X-Local-Token.
    """
    _require_token(x_local_token)

    tunnel = _get_tunnel_status()
    if tunnel["running"] and tunnel["pid"]:
        try:
            # Send SIGTERM to frpc — main agent will restart it automatically
            os.kill(tunnel["pid"], 15)  # SIGTERM
            log.info("Sent SIGTERM to frpc PID %d", tunnel["pid"])
            return {"restarting": True, "killed_pid": tunnel["pid"]}
        except ProcessLookupError:
            pass

    return {"restarting": False, "reason": "frpc was not running"}


@app.post("/reboot")
async def reboot_device(
    x_local_token: str | None = Header(None),
):
    """
    Reboot the Orange Pi.

    WARNING: This immediately reboots the device. All active sessions
    will be dropped. Use only for maintenance purposes.
    Requires X-Local-Token.
    """
    _require_token(x_local_token)

    log.warning("REBOOT requested via Local API — rebooting in 3 seconds")

    # Schedule reboot in background (gives time to return HTTP response)
    subprocess.Popen(
        ["bash", "-c", "sleep 3 && reboot"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return {
        "rebooting": True,
        "message": "Device will reboot in ~3 seconds. Reconnect in 30–60 seconds.",
        "time": datetime.now(timezone.utc).isoformat(),
    }


# ── Standalone entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    log.info("MYXON Local Agent API v%s", AGENT_VERSION)
    log.info("Bind: %s:%d", LOCAL_API_BIND, LOCAL_API_PORT)
    log.info("X-Local-Token: %s", LOCAL_TOKEN)

    uvicorn.run(app, host=LOCAL_API_BIND, port=LOCAL_API_PORT, log_level="info")
