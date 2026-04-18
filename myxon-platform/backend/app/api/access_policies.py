"""
AccessPolicy CRUD API.

Позволяет customer_admin (и выше) создавать и управлять политиками доступа —
гранулярными наборами разрешений, которые назначаются пользователям на площадки.

Routes:
  GET    /api/v0/access-policies        — список политик тенанта
  POST   /api/v0/access-policies        — создать политику
  GET    /api/v0/access-policies/{id}   — получить политику
  PATCH  /api/v0/access-policies/{id}   — обновить политику
  DELETE /api/v0/access-policies/{id}   — удалить политику (только если не назначена)
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.access_policy import AccessPolicy, DEFAULT_POLICIES
from app.models.device import Device
from app.models.user import User
from app.models.user_site_access import UserSiteAccess
from app.services.access_policy import get_site_policy, get_tenant_default_policy

router = APIRouter(prefix="/api/v0/access-policies", tags=["access-policies"])

# ── Roles that can manage policies ──
POLICY_MANAGERS = ("platform_admin", "partner_admin", "dealer_admin", "customer_admin")


# ── Schemas ──

class AccessPolicyCreate(BaseModel):
    name: str
    description: str | None = None
    allow_hmi: bool = True
    allow_vnc: bool = False
    allow_http: bool = False
    allow_alarms_view: bool = True
    allow_alarms_acknowledge: bool = True
    alarm_severity_filter: str = "all"   # "all" | "warning_and_above" | "critical_only"
    allow_audit_view: bool = False
    is_default: bool = False


class AccessPolicyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    allow_hmi: bool | None = None
    allow_vnc: bool | None = None
    allow_http: bool | None = None
    allow_alarms_view: bool | None = None
    allow_alarms_acknowledge: bool | None = None
    alarm_severity_filter: str | None = None
    allow_audit_view: bool | None = None
    is_default: bool | None = None


class AccessPolicyOut(BaseModel):
    id: str
    name: str
    description: str | None
    tenant_id: str
    allow_hmi: bool
    allow_vnc: bool
    allow_http: bool
    allow_alarms_view: bool
    allow_alarms_acknowledge: bool
    alarm_severity_filter: str
    allow_audit_view: bool
    is_default: bool

    model_config = {"from_attributes": True}


def _policy_to_out(p: AccessPolicy) -> AccessPolicyOut:
    return AccessPolicyOut(
        id=str(p.id),
        name=p.name,
        description=p.description,
        tenant_id=str(p.tenant_id),
        allow_hmi=p.allow_hmi,
        allow_vnc=p.allow_vnc,
        allow_http=p.allow_http,
        allow_alarms_view=p.allow_alarms_view,
        allow_alarms_acknowledge=p.allow_alarms_acknowledge,
        alarm_severity_filter=p.alarm_severity_filter,
        allow_audit_view=p.allow_audit_view,
        is_default=p.is_default,
    )


def _require_manager(user: User) -> None:
    if user.role not in POLICY_MANAGERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manage access policies",
        )


# ── Endpoints ──

@router.get("", response_model=list[AccessPolicyOut])
async def list_policies(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all AccessPolicies for the current tenant."""
    result = await db.execute(
        select(AccessPolicy)
        .where(AccessPolicy.tenant_id == user.tenant_id)
        .order_by(AccessPolicy.name)
    )
    policies = result.scalars().all()
    return [_policy_to_out(p) for p in policies]


@router.post("", response_model=AccessPolicyOut, status_code=status.HTTP_201_CREATED)
async def create_policy(
    body: AccessPolicyCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new AccessPolicy for this tenant."""
    _require_manager(user)

    # Validate severity filter value
    valid_filters = ("all", "warning_and_above", "critical_only")
    if body.alarm_severity_filter not in valid_filters:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"alarm_severity_filter must be one of: {', '.join(valid_filters)}",
        )

    # If this is set as default, clear existing defaults
    if body.is_default:
        existing_defaults = await db.execute(
            select(AccessPolicy).where(
                AccessPolicy.tenant_id == user.tenant_id,
                AccessPolicy.is_default == True,  # noqa: E712
            )
        )
        for old in existing_defaults.scalars().all():
            old.is_default = False

    policy = AccessPolicy(
        tenant_id=user.tenant_id,
        name=body.name,
        description=body.description,
        allow_hmi=body.allow_hmi,
        allow_vnc=body.allow_vnc,
        allow_http=body.allow_http,
        allow_alarms_view=body.allow_alarms_view,
        allow_alarms_acknowledge=body.allow_alarms_acknowledge,
        alarm_severity_filter=body.alarm_severity_filter,
        allow_audit_view=body.allow_audit_view,
        is_default=body.is_default,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return _policy_to_out(policy)


@router.get("/effective", response_model=AccessPolicyOut | None)
async def get_effective_policy(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: str | None = None,
):
    """
    Return the effective AccessPolicy for the current user on a given device.

    Resolution order:
      1. User's per-site policy (via user_site_access) for the device's site
      2. Tenant-level default policy (is_default=True)
      3. null — no policy, fallback to role defaults

    Used by the frontend to conditionally show/hide UI elements (HMI, audit log…).
    """
    policy = None

    if device_id:
        # Load device to find site
        dev_result = await db.execute(
            select(Device).where(Device.id == uuid.UUID(device_id))
        )
        device = dev_result.scalar_one_or_none()
        if device and device.site_id:
            policy = await get_site_policy(db, user.id, device.site_id)

    if policy is None:
        policy = await get_tenant_default_policy(db, user.tenant_id)

    if policy is None:
        return None

    return _policy_to_out(policy)


@router.post("/seed-defaults", status_code=status.HTTP_201_CREATED)
async def seed_default_policies(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Seed the 4 default policies (Полный доступ, Инженер, Оператор, Наблюдатель)
    for this tenant. Idempotent — skips if a policy with the same name already exists.
    """
    _require_manager(user)

    created = []
    for template in DEFAULT_POLICIES:
        # Check if already exists
        exists = await db.execute(
            select(AccessPolicy).where(
                AccessPolicy.tenant_id == user.tenant_id,
                AccessPolicy.name == template["name"],
            )
        )
        if exists.scalar_one_or_none() is not None:
            continue

        policy = AccessPolicy(tenant_id=user.tenant_id, **template)
        db.add(policy)
        created.append(template["name"])

    await db.commit()
    return {"seeded": created}


@router.get("/{policy_id}", response_model=AccessPolicyOut)
async def get_policy(
    policy_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(AccessPolicy).where(
            AccessPolicy.id == uuid.UUID(policy_id),
            AccessPolicy.tenant_id == user.tenant_id,
        )
    )
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return _policy_to_out(policy)


@router.patch("/{policy_id}", response_model=AccessPolicyOut)
async def update_policy(
    policy_id: str,
    body: AccessPolicyUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _require_manager(user)

    result = await db.execute(
        select(AccessPolicy).where(
            AccessPolicy.id == uuid.UUID(policy_id),
            AccessPolicy.tenant_id == user.tenant_id,
        )
    )
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")

    if body.alarm_severity_filter is not None:
        valid_filters = ("all", "warning_and_above", "critical_only")
        if body.alarm_severity_filter not in valid_filters:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"alarm_severity_filter must be one of: {', '.join(valid_filters)}",
            )

    # If setting as default, clear existing defaults first
    if body.is_default:
        existing_defaults = await db.execute(
            select(AccessPolicy).where(
                AccessPolicy.tenant_id == user.tenant_id,
                AccessPolicy.is_default == True,  # noqa: E712
                AccessPolicy.id != uuid.UUID(policy_id),
            )
        )
        for old in existing_defaults.scalars().all():
            old.is_default = False

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(policy, field, value)

    await db.commit()
    await db.refresh(policy)
    return _policy_to_out(policy)


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _require_manager(user)

    result = await db.execute(
        select(AccessPolicy).where(
            AccessPolicy.id == uuid.UUID(policy_id),
            AccessPolicy.tenant_id == user.tenant_id,
        )
    )
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")

    # Prevent deleting if policy is assigned to any user-site
    assigned = await db.execute(
        select(UserSiteAccess).where(
            UserSiteAccess.access_policy_id == uuid.UUID(policy_id)
        ).limit(1)
    )
    if assigned.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete policy while it is assigned to users. "
                   "Remove assignments first.",
        )

    await db.delete(policy)
    await db.commit()
