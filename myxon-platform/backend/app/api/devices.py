import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.pagination import PagedOut, decode_cursor, encode_cursor
from app.models.audit import AuditEvent
from app.models.device import AccessSession, Device
from app.models.user import User
from app.schemas.device import (
    AccessSessionCreate,
    AccessSessionOut,
    DeviceClaimPreview,
    DeviceClaimRequest,
    DeviceClaimResponse,
    DeviceOut,
    DeviceRegisterRequest,
    DeviceRegisterResponse,
)

router = APIRouter(prefix="/api/v0/devices", tags=["devices"])

# Roles that belong to the dealer tier (can register devices, NOT access customer data)
DEALER_ROLES = ("dealer_admin", "dealer_engineer")
# Roles that can claim/access devices (customer tier)
CUSTOMER_ROLES = ("customer_admin", "customer_engineer", "customer_viewer")
# Backward-compat: old superadmin/admin roles
ADMIN_ROLES = ("superadmin", "admin", "platform_admin")


def _device_to_out(d: Device) -> DeviceOut:
    return DeviceOut(
        id=str(d.id),
        serial_number=d.serial_number,
        name=d.name,
        model=d.model,
        firmware_version=d.firmware_version,
        status=d.status,
        claim_state=d.claim_state,
        last_seen_at=d.last_seen_at,
        tenant_id=str(d.tenant_id) if d.tenant_id else None,
        site_id=str(d.site_id) if d.site_id else None,
        dealer_id=str(d.dealer_id) if d.dealer_id else None,
        partner_id=str(d.partner_id) if d.partner_id else None,
        vendor_id=d.vendor_id,
        device_family=d.device_family,
        device_capabilities=d.device_capabilities,
        published_resources=d.published_resources,
    )


def _dealer_device_to_out(d: Device) -> DeviceOut:
    """Stripped-down view for dealers: no customer data, only status."""
    return DeviceOut(
        id=str(d.id),
        serial_number=d.serial_number,
        name=d.serial_number,  # dealers see SN, not customer-assigned name
        model=d.model,
        firmware_version=None,      # dealer doesn't need firmware details
        status=d.status,            # online/offline — for billing/support
        claim_state=d.claim_state,
        last_seen_at=d.last_seen_at,
        tenant_id=None,             # NEVER expose customer tenant to dealer
        site_id=None,               # NEVER expose customer site to dealer
        dealer_id=str(d.dealer_id) if d.dealer_id else None,
        partner_id=str(d.partner_id) if d.partner_id else None,
        vendor_id=d.vendor_id,
        device_family=d.device_family,
        device_capabilities=None,   # not needed for dealer view
        published_resources=None,   # NEVER expose customer resources to dealer
    )


# ---------------------------------------------------------------------------
# Dealer: Register device (before shipping to customer)
# ---------------------------------------------------------------------------

@router.post("/register", response_model=DeviceRegisterResponse)
async def register_device(
    body: DeviceRegisterRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Dealer pre-registers a device serial number. Device will be unclaimed until customer activates."""
    if user.role not in DEALER_ROLES + ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only dealer accounts can register devices",
        )

    # Check for duplicate serial
    existing = await db.execute(
        select(Device).where(Device.serial_number == body.serial_number)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device with serial {body.serial_number!r} already registered",
        )

    device = Device(
        serial_number=body.serial_number,
        name=body.serial_number,
        model=body.model,
        vendor_id=body.vendor_id,
        device_family=body.device_family,
        status="pre_registered",
        claim_state="ready_for_transfer",
        dealer_id=user.tenant_id,  # Selling chain: this dealer registered it
    )
    db.add(device)

    audit = AuditEvent(
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="device.registered",
        details={"serial_number": body.serial_number, "model": body.model},
    )
    db.add(audit)
    await db.flush()

    return DeviceRegisterResponse(
        device_id=str(device.id),
        serial_number=device.serial_number,
        status="pre_registered",
        message=f"Device {body.serial_number} registered. Customer can now claim it.",
    )


# ---------------------------------------------------------------------------
# Dealer: List own devices (status only, no customer data)
# ---------------------------------------------------------------------------

@router.get("/dealer", response_model=PagedOut[DeviceOut])
async def list_dealer_devices(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Dealer sees status of devices they registered. NO customer data. Cursor-paginated."""
    if user.role not in DEALER_ROLES + ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dealers only")

    query = select(Device).where(Device.dealer_id == user.tenant_id)

    c = decode_cursor(cursor)
    if c:
        # keyset: (serial_number, id) both ASC
        query = query.where(
            or_(
                Device.serial_number > c["after_serial"],
                and_(
                    Device.serial_number == c["after_serial"],
                    Device.id > uuid.UUID(c["after_id"]),
                ),
            )
        )

    query = query.order_by(Device.serial_number, Device.id).limit(limit + 1)
    result = await db.execute(query)
    devices = result.scalars().all()

    next_cursor = None
    if len(devices) > limit:
        last = devices[limit - 1]
        next_cursor = encode_cursor({"after_serial": last.serial_number, "after_id": str(last.id)})
        devices = devices[:limit]

    return PagedOut(items=[_dealer_device_to_out(d) for d in devices], next_cursor=next_cursor)


# ---------------------------------------------------------------------------
# Customer: List own devices
# ---------------------------------------------------------------------------

@router.get("", response_model=PagedOut[DeviceOut])
async def list_devices(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    site_id: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    """List devices for the current customer tenant. Cursor-paginated."""
    if user.role in DEALER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Use /devices/dealer endpoint to list your registered devices",
        )

    query = select(Device).where(Device.tenant_id == user.tenant_id)
    if site_id:
        query = query.where(Device.site_id == uuid.UUID(site_id))

    c = decode_cursor(cursor)
    if c:
        # keyset: (name, id) both ASC
        query = query.where(
            or_(
                Device.name > c["after_name"],
                and_(
                    Device.name == c["after_name"],
                    Device.id > uuid.UUID(c["after_id"]),
                ),
            )
        )

    query = query.order_by(Device.name, Device.id).limit(limit + 1)
    result = await db.execute(query)
    devices = result.scalars().all()

    next_cursor = None
    if len(devices) > limit:
        last = devices[limit - 1]
        next_cursor = encode_cursor({"after_name": last.name, "after_id": str(last.id)})
        devices = devices[:limit]

    return PagedOut(items=[_device_to_out(d) for d in devices], next_cursor=next_cursor)


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(
    device_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if user.role in DEALER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dealers cannot access device details")

    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.tenant_id == user.tenant_id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return _device_to_out(device)


# ---------------------------------------------------------------------------
# Customer: Claim device (ClaimWizard — serial number only)
# ---------------------------------------------------------------------------

@router.post("/claim/preview", response_model=DeviceClaimPreview)
async def claim_preview(
    body: DeviceClaimRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if user.role in DEALER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dealers cannot claim devices")

    result = await db.execute(
        select(Device).where(Device.serial_number == body.serial_number)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    return DeviceClaimPreview(
        serial_number=device.serial_number,
        model=device.model,
        claim_state=device.claim_state,
        current_tenant=str(device.tenant_id) if device.tenant_id else None,
    )


@router.post("/claim", response_model=DeviceClaimResponse)
async def claim_device(
    body: DeviceClaimRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Customer self-activates device by entering the serial number from the label.
    No activation code required — serial number is sufficient.
    """
    if user.role in DEALER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dealers cannot claim devices")

    result = await db.execute(
        select(Device).where(Device.serial_number == body.serial_number)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    if device.claim_state != "ready_for_transfer":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device cannot be claimed (state: {device.claim_state})",
        )

    # Claim — transfer ownership to customer tenant
    device.tenant_id = user.tenant_id
    device.claim_state = "claimed"
    if body.site_id:
        device.site_id = uuid.UUID(body.site_id)

    audit = AuditEvent(
        tenant_id=user.tenant_id,
        actor_id=user.id,
        device_id=device.id,
        action="device.claimed",
        details={"serial_number": device.serial_number, "site_id": body.site_id},
    )
    db.add(audit)

    return DeviceClaimResponse(
        device_id=str(device.id),
        claim_status="claimed",
        message=f"Device {device.serial_number} activated successfully",
    )


# ---------------------------------------------------------------------------
# Access Sessions (customer engineers and above)
# ---------------------------------------------------------------------------

@router.post("/{device_id}/sessions", response_model=AccessSessionOut)
async def create_access_session(
    device_id: uuid.UUID,
    body: AccessSessionCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if user.role in DEALER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dealers cannot open HMI sessions")

    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.tenant_id == user.tenant_id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    # 5-layer access policy check
    from app.services.access_policy import check_access
    policy = check_access(
        user=user,
        device=device,
        protocol=body.protocol,
        resource_id=body.resource_id,
    )
    if not policy.allowed:
        status_code = (
            status.HTTP_403_FORBIDDEN
            if policy.layer in ("role", "tenant", "company_flags")
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=policy.denied_reason)

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=body.ttl_minutes)

    # Look up the resource from published_resources.
    # remote_port is the frps-side port (stored during registration in agent.py).
    # Fallback: if remote_port is missing (older agent), derive from tunnel_port.
    resource_port: int | None = None
    resource_found: dict | None = None
    if device.published_resources:
        for offset, res in enumerate(device.published_resources):
            if res.get("id") == body.resource_id:
                resource_found = res
                # Prefer the explicit remote_port stored at registration time
                resource_port = res.get("remote_port") or (
                    (device.tunnel_port + offset) if device.tunnel_port else res.get("port")
                )
                break

    # Validate that the requested protocol matches the resource's declared protocol.
    # Prevents e.g. opening a VNC guacamole session on an HTTP-only resource.
    if resource_found is not None:
        declared_protocol = resource_found.get("protocol")
        if declared_protocol and declared_protocol != body.protocol:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Resource '{body.resource_id}' uses protocol '{declared_protocol}', "
                    f"but '{body.protocol}' was requested"
                ),
            )

    from app.services.guacamole import create_guacamole_connection
    try:
        guac_conn = create_guacamole_connection(
            device_serial=device.serial_number,
            resource_id=body.resource_id,
            protocol=body.protocol,
            tunnel_port=device.tunnel_port,
            resource_port=resource_port,
            ttl_minutes=body.ttl_minutes,
        )
        access_url = guac_conn.access_url
    except ValueError:
        access_url = (
            f"/guacamole/#/client/{device.serial_number}-{body.resource_id}"
            f"?protocol={body.protocol}"
        )

    session = AccessSession(
        device_id=device.id,
        user_id=user.id,
        resource_id=body.resource_id,
        protocol=body.protocol,
        access_url=access_url,
        expires_at=expires_at,
    )
    db.add(session)

    audit = AuditEvent(
        tenant_id=user.tenant_id,
        actor_id=user.id,
        device_id=device.id,
        action="session.opened",
        details={"resource_id": body.resource_id, "protocol": body.protocol},
        resource=body.resource_id,
    )
    db.add(audit)
    await db.flush()

    return AccessSessionOut(
        id=str(session.id),
        device_id=str(session.device_id),
        resource_id=session.resource_id,
        protocol=session.protocol,
        access_url=session.access_url,
        status=session.status,
        expires_at=session.expires_at,
    )
