import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import generate_agent_token, hash_agent_token
from app.models.activation_code import ActivationCode
from app.models.audit import AuditEvent
from app.models.device import Device
from app.schemas.device import (
    AgentHeartbeatRequest,
    AgentHeartbeatResponse,
    AgentRegisterRequest,
    SmsPendingItem,
)
from app.services.notifications import get_pending_sms_for_device
from app.services.tunnel import allocate_tunnel_port

router = APIRouter(prefix="/api/v0/agent", tags=["agent"])


# ─── Schemas for activation-code flow ────────────────────────────────────────

class AgentActivateRequest(BaseModel):
    code: str                       # XXXX-XXXX-XXXX-XXXX — the one-time activation code
    metadata: dict | None = None    # Optional: firmware_version, model, published_resources, etc.


class AgentActivateResponse(BaseModel):
    accepted: bool
    device_id: str
    serial_number: str
    frpc_token: str                 # Always returned (first and only time)
    tunnel: dict


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

    # Collect pending SMS for this device (alarms not yet notified via GSM)
    sms_payloads = await get_pending_sms_for_device(db, device)
    pending_sms = [SmsPendingItem(**p) for p in sms_payloads]

    await db.commit()

    return AgentHeartbeatResponse(
        online=True,
        server_time=now,
        config_version=1,
        pending_sms=pending_sms,
    )


@router.post("/activate", response_model=AgentActivateResponse, status_code=status.HTTP_201_CREATED)
async def agent_activate(
    body: AgentActivateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Device self-registration via one-time activation code (no auth needed — code IS the secret).

    Steps:
      1. Validate code: exists, not expired, not yet used
      2. Generate unique serial number: MX-{YYYY}-{5-digit-seq}
      3. Create Device record (status=online, claim_state=claimed, tenant=dealer)
      4. Mark code as used (used_at=now, device_id=new device)
      5. Return device credentials (serial, frpc_token, tunnel config)

    Backward compatibility: existing /register endpoint (MYXON_SERIAL flow) is unchanged.
    """
    now = datetime.now(timezone.utc)

    # ── Step 1: Validate activation code ─────────────────────────────────────
    result = await db.execute(
        select(ActivationCode).where(ActivationCode.code == body.code)
    )
    act_code = result.scalar_one_or_none()

    if act_code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activation code not found. Check the code and try again.",
        )
    if act_code.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Activation code already used. Each code can only activate one device.",
        )
    if act_code.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Activation code has expired. Ask your dealer for a new code.",
        )

    # ── Step 2: Generate serial number ────────────────────────────────────────
    # Count existing devices to produce a monotonic sequence.
    # Format: MX-2026-00001, MX-2026-00002, ...
    # Note: not atomic — if two devices activate simultaneously, one will get
    # a duplicate constraint and should retry (extremely rare in practice).
    count_result = await db.execute(select(func.count()).select_from(Device))
    device_count = count_result.scalar() or 0
    year = now.year
    serial_number = f"MX-{year}-{device_count + 1:05d}"

    # ── Step 3: Create Device ─────────────────────────────────────────────────
    device = Device(
        id=uuid.uuid4(),
        serial_number=serial_number,
        # Use dealer-provided label or fall back to serial
        name=act_code.device_name or serial_number,
        status="online",
        # Device is immediately claimed by the dealer's tenant
        claim_state="claimed",
        tenant_id=act_code.tenant_id,
        last_seen_at=now,
    )

    # Apply metadata from agent if provided
    if body.metadata:
        device.firmware_version = body.metadata.get("firmware_version")
        device.hardware_info = body.metadata.get("hardware_info")
        device.model = body.metadata.get("model")

    # Issue frpc token — returned once, agent must persist it
    plain_token = generate_agent_token()
    device.agent_token_hash = hash_agent_token(plain_token)

    db.add(device)
    await db.flush()  # Populate device.id before allocating tunnel

    # ── Tunnel port allocation ─────────────────────────────────────────────────
    tunnel_port = await allocate_tunnel_port(db, device)

    # Enrich published_resources with assigned tunnel ports
    raw_resources: list[dict] = (body.metadata or {}).get("published_resources") or []
    if raw_resources and tunnel_port is not None:
        device.published_resources = [
            {**res, "remote_port": tunnel_port + offset}
            for offset, res in enumerate(raw_resources)
        ]
    elif raw_resources:
        device.published_resources = raw_resources

    # ── Step 4: Mark code as consumed ─────────────────────────────────────────
    act_code.used_at = now
    act_code.device_id = device.id

    # ── Audit event ───────────────────────────────────────────────────────────
    audit = AuditEvent(
        tenant_id=act_code.tenant_id,
        device_id=device.id,
        action="device.activated",
        details={
            "serial_number": serial_number,
            "activation_code_id": str(act_code.id),
            "device_name": act_code.device_name,
            "tunnel_port": tunnel_port,
        },
    )
    db.add(audit)

    return AgentActivateResponse(
        accepted=True,
        device_id=str(device.id),
        serial_number=serial_number,
        frpc_token=plain_token,  # Agent must store this — never returned again
        tunnel={
            "frps_host": settings.frps_host,
            "frps_port": settings.frps_bind_port,
            "assigned_port": tunnel_port,
            "subdomain": device.tunnel_subdomain,
        },
    )
