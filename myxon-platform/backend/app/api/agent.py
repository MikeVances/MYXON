from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import generate_agent_token, hash_agent_token
from app.models.audit import AuditEvent
from app.models.device import Device
from app.schemas.device import (
    AgentHeartbeatRequest,
    AgentHeartbeatResponse,
    AgentRegisterRequest,
)
from app.services.tunnel import allocate_tunnel_port

router = APIRouter(prefix="/api/v0/agent", tags=["agent"])


@router.post("/register")
async def agent_register(
    body: AgentRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Agent self-registration on first boot."""
    result = await db.execute(
        select(Device).where(Device.serial_number == body.serial_number)
    )
    device = result.scalar_one_or_none()

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not pre-registered. Contact administrator.",
        )

    # Update device metadata from agent
    if body.metadata:
        device.firmware_version = body.metadata.get("firmware_version", device.firmware_version)
        device.hardware_info = body.metadata.get("hardware_info", device.hardware_info)
        device.model = body.metadata.get("model", device.model)

    device.status = "online"
    device.last_seen_at = datetime.now(timezone.utc)

    # Issue per-device frps token on first registration (or if revoked)
    plain_token: str | None = None
    if not device.agent_token_hash:
        plain_token = generate_agent_token()
        device.agent_token_hash = hash_agent_token(plain_token)

    # Allocate tunnel port from pool
    tunnel_port = await allocate_tunnel_port(db, device)

    # Annotate each published resource with its remotePort on frps.
    # The agent uses `assigned_port + offset` for each resource in order.
    # Storing this here means /devices/{id}/sessions can look up the correct
    # frps port for proxying without guessing.
    raw_resources: list[dict] = (body.metadata or {}).get("published_resources") or []
    if raw_resources and tunnel_port is not None:
        enriched: list[dict] = []
        for offset, res in enumerate(raw_resources):
            enriched.append({**res, "remote_port": tunnel_port + offset})
        device.published_resources = enriched
    elif raw_resources:
        device.published_resources = raw_resources

    # Audit (no tenant_id required for pre-registered unclaimed devices)
    if device.tenant_id:
        audit = AuditEvent(
            tenant_id=device.tenant_id,
            device_id=device.id,
            action="device.registered",
            details={
                "agent_public_id": body.agent_public_id,
                "metadata": body.metadata,
                "tunnel_port": tunnel_port,
            },
        )
        db.add(audit)

    response: dict = {
        "accepted": True,
        "device_id": str(device.id),
        "config_version": 1,
        "tunnel": {
            "frps_host": settings.frps_host,
            "frps_port": settings.frps_bind_port,
            "assigned_port": tunnel_port,
            "subdomain": device.tunnel_subdomain,
        },
    }

    # Return plain token only when freshly issued — agent must persist it locally.
    # Subsequent registrations (reconnects) will NOT include the token again.
    # To rotate: use POST /api/v0/agent/rotate-token.
    if plain_token:
        response["frpc_token"] = plain_token

    return response


@router.post("/rotate-token")
async def rotate_agent_token(
    body: AgentRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Rotate the frpc token for a device.
    Called by the agent on demand (e.g. after suspected compromise).
    Returns a new plain token — agent must persist and use it immediately.
    The old token is invalidated.
    """
    result = await db.execute(
        select(Device).where(Device.serial_number == body.serial_number)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    plain_token = generate_agent_token()
    device.agent_token_hash = hash_agent_token(plain_token)
    await db.commit()

    return {"rotated": True, "frpc_token": plain_token}


@router.post("/heartbeat", response_model=AgentHeartbeatResponse)
async def agent_heartbeat(
    body: AgentHeartbeatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Periodic heartbeat from edge agent."""
    result = await db.execute(
        select(Device).where(Device.id == body.device_id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown device")

    now = datetime.now(timezone.utc)
    was_offline = device.status == "offline"

    device.status = "online"
    device.last_seen_at = now

    if body.metrics:
        # Store latest metrics (could go to Redis for real-time, DB for history)
        pass

    # If device came back online, emit audit event
    if was_offline and device.tenant_id:
        audit = AuditEvent(
            tenant_id=device.tenant_id,
            device_id=device.id,
            action="device.online",
            details={"tunnel_state": body.tunnel_state},
        )
        db.add(audit)

    return AgentHeartbeatResponse(online=True, server_time=now, config_version=1)
