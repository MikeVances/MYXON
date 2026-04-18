"""
WebSocket → Guacamole VNC proxy.

Поток данных:
  Browser (guacamole-common-js)
    ↕ WebSocket (subprotocol: guacamole)
  /api/v0/ws/vnc/{device_id}  ← этот файл
    ↕ TCP (guacamole protocol)
  guacd :4822
    ↕ VNC protocol
  frpc tunnel → device VNC server (port 5900)

Рукопожатие (handshake) с перехватом:
  1. Backend → guacd:   select,3,vnc;
  2. guacd  → backend:  args,8.hostname,4.port,...;
  3. backend → browser: args (forwarded as-is)
  4. browser → backend: connect,0.,0.,0.,...;   (пустые значения)
  5. backend → guacd:   connect (с реальными host:port из туннеля)
  6. guacd  → backend:  ready,<id>;
  7. backend → browser: ready (forwarded)
  8. Далее — чистый прокси в обе стороны.

Причина перехвата connect: браузер не знает реальный адрес VNC-сервера
(он закрыт за frpc туннелем). Backend подставляет корректные значения.
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session
from app.core.security import decode_token
from app.models.device import Device
from app.models.user import User
from app.services.access_policy import check_access, get_site_policy, get_tenant_default_policy

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ws-vnc"])


# ── Guacamole protocol helpers ──────────────────────────────────────────────────

def _guac_element(value: str) -> str:
    """Encode single guacamole element: n.value"""
    return f"{len(value)}.{value}"


def _guac_encode(*elements: str) -> str:
    """Encode a full guacamole instruction: e1,e2,...;"""
    return ",".join(_guac_element(e) for e in elements) + ";"


def _guac_decode(instruction: str) -> list[str]:
    """
    Decode guacamole instruction into list of values.
    '4.args,8.hostname,4.port;' → ['args', 'hostname', 'port']
    """
    elements = []
    for part in instruction.rstrip(";").split(","):
        if "." not in part:
            continue
        dot = part.index(".")
        try:
            length = int(part[:dot])
        except ValueError:
            continue
        elements.append(part[dot + 1 : dot + 1 + length])
    return elements


async def _tcp_read_instruction(reader: asyncio.StreamReader, buf: bytearray) -> str:
    """
    Read one complete guacamole instruction from TCP stream.
    Handles partial TCP reads by accumulating in buf.
    Returns the instruction string including the terminating ';'.
    """
    while b";" not in buf:
        chunk = await asyncio.wait_for(reader.read(4096), timeout=10.0)
        if not chunk:
            raise ConnectionError("guacd disconnected during handshake")
        buf.extend(chunk)

    idx = buf.index(b";")
    instruction = buf[: idx + 1].decode(errors="replace")
    del buf[: idx + 1]  # consume from buffer
    return instruction


# ── Auth helpers ────────────────────────────────────────────────────────────────

async def _authenticate_ws(token: str) -> User | None:
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


async def _get_device(device_id: str) -> Device | None:
    async with async_session() as db:
        result = await db.execute(
            select(Device).where(Device.id == uuid.UUID(device_id))
        )
        return result.scalar_one_or_none()


# ── WebSocket endpoint ──────────────────────────────────────────────────────────

@router.websocket("/api/v0/ws/vnc/{device_id}")
async def ws_vnc(websocket: WebSocket, device_id: str):
    """
    WebSocket → guacd → VNC bridge.

    Query params:
      token       — JWT access token
    Subprotocol:  guacamole
    """
    # ── Auth ──
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    user = await _authenticate_ws(token)
    if user is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # ── Device ──
    try:
        device = await _get_device(device_id)
    except Exception:
        await websocket.close(code=4004, reason="Invalid device id")
        return

    if device is None:
        await websocket.close(code=4004, reason="Device not found")
        return

    # ── Access policy ──
    access_policy = None
    async with async_session() as db:
        if device.site_id is not None:
            access_policy = await get_site_policy(db, user.id, device.site_id)
        if access_policy is None and device.tenant_id is not None:
            access_policy = await get_tenant_default_policy(db, device.tenant_id)

    policy_result = check_access(
        user=user,
        device=device,
        protocol="vnc",
        resource_id="vnc",
        policy=access_policy,
    )
    if not policy_result.allowed:
        await websocket.close(
            code=4003, reason=policy_result.denied_reason or "Access denied"
        )
        return

    # ── Find VNC tunnel port from published_resources ──
    vnc_remote_port: int | None = None
    for res in device.published_resources or []:
        if res.get("protocol") == "vnc" and res.get("remote_port"):
            vnc_remote_port = int(res["remote_port"])
            break

    if vnc_remote_port is None:
        await websocket.close(code=4005, reason="Device has no VNC tunnel configured")
        return

    # ── Connect to guacd ──
    try:
        reader, writer = await asyncio.open_connection(
            settings.guacd_host, settings.guacd_port
        )
    except Exception as exc:
        logger.error("Cannot connect to guacd at %s:%d — %s", settings.guacd_host, settings.guacd_port, exc)
        # Accept WS so we can send a proper error
        await websocket.accept(subprotocol="guacamole")
        # guacamole error instruction: error,<message>,<status_code>;
        # Status 516 = UPSTREAM_ERROR
        await websocket.send_text(_guac_encode("error", "guacd unavailable", "516"))
        await websocket.close()
        return

    # Accept WebSocket with guacamole subprotocol
    await websocket.accept(subprotocol="guacamole")

    tcp_buf = bytearray()

    try:
        # ── Handshake: step 1 — backend tells guacd to use VNC ──
        writer.write(_guac_encode("select", "vnc").encode())
        await writer.drain()

        # ── Handshake: step 2 — guacd replies with expected params ──
        args_raw = await _tcp_read_instruction(reader, tcp_buf)
        args_elements = _guac_decode(args_raw)
        # args_elements = ["args", "hostname", "port", "password", ...]
        param_names = args_elements[1:]  # skip the "args" opcode

        # Forward args to browser — guacamole-common-js expects to see this
        await websocket.send_text(args_raw)
        logger.debug("guacd VNC args params: %s", param_names)

        # ── Handshake: step 3 — browser sends connect with (empty) values ──
        connect_raw = await websocket.receive_text()
        connect_elements = _guac_decode(connect_raw)
        # connect_elements = ["connect", "", "", "", ...]
        connect_values = list(connect_elements[1:])  # skip "connect" opcode

        # Pad values list if browser sent fewer elements than guacd expects
        while len(connect_values) < len(param_names):
            connect_values.append("")

        # Inject real VNC tunnel address — browser doesn't know this
        for idx, name in enumerate(param_names):
            if idx >= len(connect_values):
                break
            if name == "hostname":
                connect_values[idx] = settings.frps_host
            elif name == "port":
                connect_values[idx] = str(vnc_remote_port)

        patched_connect = _guac_encode("connect", *connect_values)
        writer.write(patched_connect.encode())
        await writer.drain()

        logger.info(
            "VNC session: user=%s device=%s tunnel=%s:%d",
            user.email,
            device.serial_number,
            settings.frps_host,
            vnc_remote_port,
        )

        # ── Handshake: step 4 — guacd sends ready (or error) ──
        ready_raw = await _tcp_read_instruction(reader, tcp_buf)
        ready_elements = _guac_decode(ready_raw)

        if ready_elements and ready_elements[0] == "error":
            err_msg = ready_elements[1] if len(ready_elements) > 1 else "VNC connection refused"
            logger.error("guacd VNC error: %s", err_msg)
            await websocket.send_text(ready_raw)  # forward error to browser
            await websocket.close()
            return

        # Forward ready to browser — guacamole-common-js transitions to CONNECTED
        await websocket.send_text(ready_raw)

        # Flush any leftover bytes guacd sent during handshake
        if tcp_buf:
            await websocket.send_text(tcp_buf.decode(errors="replace"))
            tcp_buf.clear()

        # ── Proxy phase — pure bidirectional relay ──────────────────────────────
        # At this point the guacamole-common-js client is in CONNECTED state.
        # Both sides speak the same guacamole text protocol: display instructions
        # from guacd → browser, mouse/keyboard instructions browser → guacd.

        async def ws_to_tcp() -> None:
            """Forward WebSocket text frames to guacd TCP."""
            try:
                while True:
                    data = await websocket.receive_text()
                    writer.write(data.encode())
                    await writer.drain()
            except (WebSocketDisconnect, Exception):
                pass

        async def tcp_to_ws() -> None:
            """Forward guacd TCP bytes to browser WebSocket."""
            try:
                while True:
                    data = await reader.read(65536)
                    if not data:
                        break
                    await websocket.send_text(data.decode(errors="replace"))
            except Exception:
                pass

        done, pending = await asyncio.wait(
            [
                asyncio.create_task(ws_to_tcp()),
                asyncio.create_task(tcp_to_ws()),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        pass
    except asyncio.TimeoutError:
        logger.error("VNC handshake timed out for device %s", device.serial_number)
    except Exception as exc:
        logger.exception("VNC proxy error for device %s: %s", device.serial_number, exc)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        logger.info(
            "VNC session closed: user=%s device=%s",
            user.email,
            device.serial_number,
        )
