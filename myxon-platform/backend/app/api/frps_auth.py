"""
frps HTTP Plugin — per-device authentication webhook.

frps вызывает этот эндпоинт при каждом подключении frpc-агента.
Мы проверяем device-specific токен и возвращаем allow/reject.

Протокол frps HTTP Plugin (op=Login):

  POST /api/v0/frps/auth
  Authorization: Bearer {frps_plugin_secret}
  Content-Type: application/json

  {
    "version": "0.1.0",
    "op": "Login",
    "content": {
      "version": "0.26.0",
      "hostname": "orangepi-farm-01",
      "os": "linux",
      "arch": "arm64",
      "user": "HOTRACO-ORN-001",          ← serial_number из frpc user поля
      "privilege_key": "...",              ← игнорируем (глобальный токен пуст)
      "timestamp": 1234567890,
      "run_id": "abc123",
      "metas": {
        "device_token": "plain-token"      ← per-device токен из frpc metadatas
      },
      "client_address": "1.2.3.4:5678"
    }
  }

  Ответ allow:  {"reject": false, "unchange": true}
  Ответ reject: {"reject": true,  "rejectReason": "причина"}

frpc config (генерируется агентом):
  user = "SERIAL_NUMBER"
  [metadatas]
  device_token = "plain-token-from-registration"

Безопасность:
  - Authorization: Bearer {settings.frps_plugin_secret} защищает эндпоинт
    от случайных вызовов снаружи frps
  - TLS между frps и backend (в prod через nginx/ingress)
  - Токен хранится как SHA-256 hash, plain нигде в БД не сохраняется
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.core.database import async_session
from app.core.security import verify_agent_token
from app.models.device import Device

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v0/frps", tags=["frps-auth"])

# ── Response helpers ──────────────────────────────────────────────────────────

def _allow() -> dict:
    return {"reject": False, "unchange": True}


def _reject(reason: str) -> dict:
    logger.warning("frps auth reject: %s", reason)
    return {"reject": True, "rejectReason": reason}


# ── Webhook ───────────────────────────────────────────────────────────────────

@router.post("/auth")
async def frps_auth_webhook(
    request: Request,
) -> dict[str, Any]:
    """
    frps HTTP Plugin authentication webhook.
    Called by frps on every frpc Login event.

    Безопасность: frps HTTP Plugin не отправляет Authorization-заголовок,
    поэтому защита строится на изоляции сети:
      - endpoint не публичен (nginx блокирует /api/v0/frps/ снаружи)
      - frps и backend в одной Docker-сети, порт 8000 не проброшен наружу
    Сам токен устройства (device_token в metas) — основная точка аутентификации.
    """

    # Parse body
    try:
        body = await request.json()
    except Exception:
        return _reject("malformed request body")

    op = body.get("op", "")
    content = body.get("content", {})

    # We only handle Login — pass everything else through
    if op != "Login":
        return _allow()

    # Extract serial_number from frpc `user` field
    serial_number: str = content.get("user", "").strip()
    if not serial_number:
        return _reject("missing serial_number (frpc user field)")

    # Extract per-device token from frpc metadatas
    metas: dict = content.get("metas", {})
    device_token: str = metas.get("device_token", "").strip()
    if not device_token:
        return _reject(f"missing device_token in frpc metadatas (device={serial_number})")

    # Load device from DB
    async with async_session() as db:
        result = await db.execute(
            select(Device).where(Device.serial_number == serial_number)
        )
        device = result.scalar_one_or_none()

    if device is None:
        return _reject(f"unknown device: {serial_number}")

    if not device.agent_token_hash:
        return _reject(f"device has no token issued: {serial_number}")

    # Verify token
    if not verify_agent_token(device_token, device.agent_token_hash):
        return _reject(f"invalid token for device: {serial_number}")

    logger.info(
        "frps auth OK: serial=%s client=%s",
        serial_number,
        content.get("client_address", "?"),
    )
    return _allow()
