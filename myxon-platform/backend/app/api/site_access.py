"""
Site Access API — управление доступом пользователей к площадкам.

Позволяет customer_admin:
  - Видеть список пользователей своего тенанта
  - Назначать/изменять доступ пользователя к конкретной площадке
  - Задавать AccessPolicy для этого доступа
  - Удалять доступ

Endpoints:
  GET  /api/v0/sites/{site_id}/access         — список доступа на площадке
  PUT  /api/v0/sites/{site_id}/access/{user_id} — назначить/обновить доступ
  DELETE /api/v0/sites/{site_id}/access/{user_id} — убрать доступ

  GET  /api/v0/users                           — пользователи тенанта (для дропдауна)
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
from app.models.access_policy import AccessPolicy
from app.models.site import Site
from app.models.user import User
from app.models.user_site_access import UserSiteAccess

router = APIRouter(tags=["site-access"])

MANAGER_ROLES = ("customer_admin", "superadmin", "admin", "platform_admin")


# ── Schemas ────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str

    model_config = {"from_attributes": True}


class SiteAccessOut(BaseModel):
    id: str
    user_id: str
    user_email: str
    user_full_name: str
    site_id: str
    role: str
    access_policy_id: str | None = None
    access_policy_name: str | None = None


class SiteAccessUpsert(BaseModel):
    role: str = "customer_viewer"
    access_policy_id: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _require_site_owned(db: AsyncSession, site_id: uuid.UUID, tenant_id: uuid.UUID) -> Site:
    result = await db.execute(
        select(Site).where(Site.id == site_id, Site.tenant_id == tenant_id)
    )
    site = result.scalar_one_or_none()
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return site


# ── Users list ─────────────────────────────────────────────────────────────────

@router.get("/api/v0/users", response_model=list[UserOut])
async def list_tenant_users(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all users in the current tenant. Requires customer_admin+."""
    if user.role not in MANAGER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")

    result = await db.execute(
        select(User)
        .where(User.tenant_id == user.tenant_id, User.is_active == True)
        .order_by(User.full_name)
    )
    users = result.scalars().all()
    return [UserOut(id=str(u.id), email=u.email, full_name=u.full_name, role=u.role) for u in users]


# ── Site access CRUD ───────────────────────────────────────────────────────────

@router.get("/api/v0/sites/{site_id}/access", response_model=list[SiteAccessOut])
async def list_site_access(
    site_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all user→site access entries for this site."""
    if user.role not in MANAGER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")

    await _require_site_owned(db, site_id, user.tenant_id)

    result = await db.execute(
        select(UserSiteAccess, User)
        .join(User, User.id == UserSiteAccess.user_id)
        .where(UserSiteAccess.site_id == site_id)
        .order_by(User.full_name)
    )
    rows = result.all()

    out = []
    for access, member in rows:
        policy_name = None
        if access.access_policy:
            policy_name = access.access_policy.name
        out.append(SiteAccessOut(
            id=str(access.id),
            user_id=str(access.user_id),
            user_email=member.email,
            user_full_name=member.full_name,
            site_id=str(access.site_id),
            role=access.role,
            access_policy_id=str(access.access_policy_id) if access.access_policy_id else None,
            access_policy_name=policy_name,
        ))
    return out


@router.put("/api/v0/sites/{site_id}/access/{target_user_id}", response_model=SiteAccessOut)
async def upsert_site_access(
    site_id: uuid.UUID,
    target_user_id: uuid.UUID,
    body: SiteAccessUpsert,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Assign or update a user's access to this site (upsert). Requires customer_admin+."""
    if user.role not in MANAGER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")

    await _require_site_owned(db, site_id, user.tenant_id)

    # Verify target user belongs to same tenant
    target_result = await db.execute(
        select(User).where(User.id == target_user_id, User.tenant_id == user.tenant_id)
    )
    target = target_result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in your tenant")

    # Validate policy if provided
    policy_id = uuid.UUID(body.access_policy_id) if body.access_policy_id else None
    policy_name = None
    if policy_id:
        policy_result = await db.execute(
            select(AccessPolicy).where(
                AccessPolicy.id == policy_id,
                AccessPolicy.tenant_id == user.tenant_id,
            )
        )
        policy = policy_result.scalar_one_or_none()
        if policy is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AccessPolicy not found")
        policy_name = policy.name

    # Upsert
    existing_result = await db.execute(
        select(UserSiteAccess).where(
            UserSiteAccess.user_id == target_user_id,
            UserSiteAccess.site_id == site_id,
        )
    )
    access = existing_result.scalar_one_or_none()

    if access is None:
        access = UserSiteAccess(
            user_id=target_user_id,
            site_id=site_id,
            role=body.role,
            access_policy_id=policy_id,
        )
        db.add(access)
    else:
        access.role = body.role
        access.access_policy_id = policy_id

    await db.flush()

    return SiteAccessOut(
        id=str(access.id),
        user_id=str(access.user_id),
        user_email=target.email,
        user_full_name=target.full_name,
        site_id=str(access.site_id),
        role=access.role,
        access_policy_id=str(access.access_policy_id) if access.access_policy_id else None,
        access_policy_name=policy_name,
    )


@router.delete("/api/v0/sites/{site_id}/access/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site_access(
    site_id: uuid.UUID,
    target_user_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Remove a user's access to this site."""
    if user.role not in MANAGER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")

    await _require_site_owned(db, site_id, user.tenant_id)

    result = await db.execute(
        select(UserSiteAccess).where(
            UserSiteAccess.user_id == target_user_id,
            UserSiteAccess.site_id == site_id,
        )
    )
    access = result.scalar_one_or_none()
    if access is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access record not found")

    await db.delete(access)
