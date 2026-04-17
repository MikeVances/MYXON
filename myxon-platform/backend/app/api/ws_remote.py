"""
WebSocket endpoint for Remote+ HMI bridge.

Connects browser to device via Remote+ TCP protocol bridge.
The frontend sends JSON commands; this endpoint translates them
to Remote+ TCP frames and streams screen data back.

Route: WS /api/v0/ws/remote/{device_id}
Auth:  JWT token passed as query parameter ?token=...
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
from app.services.remote_plus_bridge import RemotePlusBridgeSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ws-remote"])


async def _authenticate_ws(token: str) -> User | None:
    """Validate JWT from WebSocket query param."""
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


@router.websocket("/api/v0/ws/remote/{device_id}")
async def ws_remote_plus(websocket: WebSocket, device_id: str):
    """
    WebSocket bridge for Remote+ HMI control.

    Query params:
      - token: JWT access token
      - dest: device destination address (from ConfigurationRead)
      - resource_id: published resource ID (for policy check)
    """
    # Extract auth token
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    # Authenticate
    user = await _authenticate_ws(token)
    if user is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Load device
    device = await _get_device(device_id)
    if device is None:
        await websocket.close(code=4004, reason="Device not found")
        return

    # Load AccessPolicy for this user on this site (if device is claimed to a site)
    access_policy = None
    async with async_session() as db:
        if device.site_id is not None:
            access_policy = await get_site_policy(db, user.id, device.site_id)
        if access_policy is None and device.tenant_id is not None:
            # Fall back to tenant default policy
            access_policy = await get_tenant_default_policy(db, device.tenant_id)

    # Policy check
    resource_id = websocket.query_params.get("resource_id", "screen")
    policy = check_access(
        user=user, device=device,
        protocol="hmi", resource_id=resource_id,
        policy=access_policy,
    )
    if not policy.allowed:
        await websocket.close(code=4003, reason=policy.denied_reason or "Access denied")
        return

    # Accept WebSocket
    await websocket.accept()

    device_dest = int(websocket.query_params.get("dest", "0"))

    # ── Resolve TCP target ─────────────────────────────────────────────────
    # Mode 1 (tunnel): FRPS reverse tunnel — primary for production.
    #   Router runs frpc, which connects to frps and exposes the controller.
    #   Backend connects to frps_host:tunnel_port to reach the controller.
    #
    # Mode 2 (direct): known IP in published_resources — fallback for
    #   same-network dev/test when no tunnel is set up.
    tcp_host: str | None = None
    tcp_port: int | None = None

    # Primary: FRPS tunnel (router → frpc → frps → backend)
    if device.tunnel_port is not None:
        tcp_host = settings.frps_host
        tcp_port = device.tunnel_port
        logger.info("Tunnel connect: %s:%d", tcp_host, tcp_port)

    # Fallback: direct IP from published_resources (same-LAN only)
    if tcp_host is None:
        req_resource = websocket.query_params.get("resource_id", "remote-plus")
        resources: list[dict] = device.published_resources or []
        for res in resources:
            if res.get("host") and res.get("port") and (
                res.get("id") == req_resource
                or res.get("protocol") in ("tcp", "remote-plus")
            ):
                tcp_host = res["host"]
                tcp_port = int(res["port"])
                logger.info("Direct connect (no tunnel): %s:%d", tcp_host, tcp_port)
                break

    if tcp_host is None:
        await websocket.send_json({
            "type": "error",
            "message": "Device unreachable: no tunnel and no direct address configured",
        })
        await websocket.close()
        return

    # Create bridge session
    bridge = RemotePlusBridgeSession(
        host=tcp_host,
        port=tcp_port,
        device_dest=device_dest,
    )

    connected = await bridge.connect()
    if not connected:
        await websocket.send_json({"type": "error", "message": f"Failed to connect to device at {tcp_host}:{tcp_port}"})
        await websocket.close()
        return

    await websocket.send_json({"type": "connected", "host": tcp_host, "port": tcp_port})

    logger.info(
        "WS bridge opened: user=%s device=%s dest=%d target=%s:%d",
        user.email, device.serial_number, device_dest, tcp_host, tcp_port,
    )

    # ── Bidirectional relay ──

    async def ws_to_tcp():
        """Read JSON commands from WebSocket, send as TCP frames."""
        try:
            while True:
                msg = await websocket.receive_json()
                msg_type = msg.get("type")

                if msg_type == "screen_request":
                    mode = msg.get("mode", 0)
                    await bridge.send_command(96, format(mode, "X").zfill(2))

                elif msg_type == "send_key":
                    key_code = msg.get("key_code", 0)
                    await bridge.send_command(93, format(key_code, "X").zfill(2))

                elif msg_type == "config_read":
                    await bridge.send_command(2)

                elif msg_type == "main_group_read":
                    await bridge.send_command(6)

                elif msg_type == "close":
                    break

        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.warning("WS→TCP relay error: %s", exc)

    async def tcp_to_ws():
        """Read TCP frames from device, send as JSON to WebSocket."""
        try:
            while True:
                msg = await bridge.recv_message()
                if msg is None:
                    # Try again — could be timeout with no data
                    await asyncio.sleep(0.05)
                    continue

                cmd = msg["cmd"]
                payload = msg["payload_hex"]

                if cmd == 96 or cmd == 92:
                    # Screen data
                    await websocket.send_json({
                        "type": "screen_data",
                        "command": cmd,
                        "hex": payload,
                    })
                elif cmd == 2:
                    # Configuration read — parse inline
                    await websocket.send_json({
                        "type": "config",
                        "hex": payload,
                    })
                elif cmd == 6:
                    # Main group read
                    await websocket.send_json({
                        "type": "main_group",
                        "hex": payload,
                    })
                elif cmd == 100:
                    # MainGroupChanged — notification
                    await websocket.send_json({
                        "type": "main_group_changed",
                        "hex": payload,
                    })
                else:
                    await websocket.send_json({
                        "type": "frame",
                        "cmd": cmd,
                        "hex": payload,
                    })

        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.warning("TCP→WS relay error: %s", exc)

    try:
        # Run both directions concurrently
        done, pending = await asyncio.wait(
            [
                asyncio.create_task(ws_to_tcp()),
                asyncio.create_task(tcp_to_ws()),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    finally:
        await bridge.close()
        try:
            await websocket.send_json({"type": "closed"})
        except Exception:
            pass
        logger.info(
            "WS bridge closed: device=%s",
            device.serial_number,
        )
