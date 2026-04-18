"""
Notification contacts and rules API.

All endpoints are scoped to the caller's tenant (extracted from JWT).
Admin role required for write operations.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.notification import NotificationContact, NotificationRule
from app.models.user import User

router = APIRouter(prefix="/api/v0/notifications", tags=["notifications"])


# ── Auth helpers ──────────────────────────────────────────────────────────────

async def _get_admin_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require admin or superadmin role."""
    if current_user.role not in ("admin", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to manage notifications.",
        )
    return current_user


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ContactOut(BaseModel):
    id: str
    name: str
    phone: str | None
    email: str | None
    channels: list[str]
    active: bool

    model_config = {"from_attributes": True}


class ContactCreate(BaseModel):
    name: str
    phone: str | None = None
    email: str | None = None
    channels: list[str] = ["sms", "email"]
    active: bool = True


class ContactUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    channels: list[str] | None = None
    active: bool | None = None


class RuleOut(BaseModel):
    id: str
    contact_id: str
    contact_name: str
    contact_phone: str | None
    contact_email: str | None
    contact_channels: list[str]
    scope_type: str
    scope_id: str
    min_severity: str
    categories: list[str]
    active: bool
    notes: str | None

    model_config = {"from_attributes": True}


class RuleCreate(BaseModel):
    contact_id: str
    scope_type: str        # "tenant" | "site" | "device"
    scope_id: str          # UUID of the tenant/site/device
    min_severity: str = "alarm"
    categories: list[str] = []
    active: bool = True
    notes: str | None = None


class RuleUpdate(BaseModel):
    contact_id: str | None = None
    scope_type: str | None = None
    scope_id: str | None = None
    min_severity: str | None = None
    categories: list[str] | None = None
    active: bool | None = None
    notes: str | None = None


# ── Contacts CRUD ─────────────────────────────────────────────────────────────

@router.get("/contacts", response_model=list[ContactOut])
async def list_contacts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all notification contacts for the caller's tenant."""
    result = await db.execute(
        select(NotificationContact).where(
            NotificationContact.tenant_id == current_user.tenant_id
        ).order_by(NotificationContact.created_at)
    )
    contacts = result.scalars().all()
    return [
        ContactOut(
            id=str(c.id),
            name=c.name,
            phone=c.phone,
            email=c.email,
            channels=c.channels or [],
            active=c.active,
        )
        for c in contacts
    ]


@router.post("/contacts", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
async def create_contact(
    body: ContactCreate,
    current_user: Annotated[User, Depends(_get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new notification contact."""
    if not body.phone and not body.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of phone or email must be provided.",
        )
    contact = NotificationContact(
        tenant_id=current_user.tenant_id,
        name=body.name,
        phone=body.phone,
        email=body.email,
        channels=body.channels,
        active=body.active,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return ContactOut(
        id=str(contact.id),
        name=contact.name,
        phone=contact.phone,
        email=contact.email,
        channels=contact.channels or [],
        active=contact.active,
    )


@router.put("/contacts/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: str,
    body: ContactUpdate,
    current_user: Annotated[User, Depends(_get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(NotificationContact).where(
            NotificationContact.id == uuid.UUID(contact_id),
            NotificationContact.tenant_id == current_user.tenant_id,
        )
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    if body.name is not None:     contact.name = body.name
    if body.phone is not None:    contact.phone = body.phone
    if body.email is not None:    contact.email = body.email
    if body.channels is not None: contact.channels = body.channels
    if body.active is not None:   contact.active = body.active

    await db.commit()
    await db.refresh(contact)
    return ContactOut(
        id=str(contact.id),
        name=contact.name,
        phone=contact.phone,
        email=contact.email,
        channels=contact.channels or [],
        active=contact.active,
    )


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: str,
    current_user: Annotated[User, Depends(_get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(NotificationContact).where(
            NotificationContact.id == uuid.UUID(contact_id),
            NotificationContact.tenant_id == current_user.tenant_id,
        )
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    await db.delete(contact)
    await db.commit()


# ── Rules CRUD ────────────────────────────────────────────────────────────────

def _rule_to_out(rule: NotificationRule) -> RuleOut:
    c = rule.contact
    return RuleOut(
        id=str(rule.id),
        contact_id=str(rule.contact_id),
        contact_name=c.name if c else "?",
        contact_phone=c.phone if c else None,
        contact_email=c.email if c else None,
        contact_channels=c.channels if c else [],
        scope_type=rule.scope_type,
        scope_id=str(rule.scope_id),
        min_severity=rule.min_severity,
        categories=rule.categories or [],
        active=rule.active,
        notes=rule.notes,
    )


@router.get("/rules", response_model=list[RuleOut])
async def list_rules(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(NotificationRule).where(
            NotificationRule.tenant_id == current_user.tenant_id
        ).order_by(NotificationRule.created_at)
    )
    return [_rule_to_out(r) for r in result.scalars().all()]


@router.post("/rules", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: RuleCreate,
    current_user: Annotated[User, Depends(_get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Verify contact belongs to same tenant
    contact_result = await db.execute(
        select(NotificationContact).where(
            NotificationContact.id == uuid.UUID(body.contact_id),
            NotificationContact.tenant_id == current_user.tenant_id,
        )
    )
    if contact_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Contact not found in your tenant")

    if body.scope_type not in ("tenant", "site", "device"):
        raise HTTPException(status_code=422, detail="scope_type must be: tenant | site | device")
    if body.min_severity not in ("warning", "alarm"):
        raise HTTPException(status_code=422, detail="min_severity must be: warning | alarm")

    rule = NotificationRule(
        tenant_id=current_user.tenant_id,
        contact_id=uuid.UUID(body.contact_id),
        scope_type=body.scope_type,
        scope_id=uuid.UUID(body.scope_id),
        min_severity=body.min_severity,
        categories=body.categories,
        active=body.active,
        notes=body.notes,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return _rule_to_out(rule)


@router.put("/rules/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: str,
    body: RuleUpdate,
    current_user: Annotated[User, Depends(_get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(NotificationRule).where(
            NotificationRule.id == uuid.UUID(rule_id),
            NotificationRule.tenant_id == current_user.tenant_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    if body.contact_id is not None:  rule.contact_id  = uuid.UUID(body.contact_id)
    if body.scope_type is not None:  rule.scope_type  = body.scope_type
    if body.scope_id is not None:    rule.scope_id    = uuid.UUID(body.scope_id)
    if body.min_severity is not None: rule.min_severity = body.min_severity
    if body.categories is not None:  rule.categories  = body.categories
    if body.active is not None:      rule.active      = body.active
    if body.notes is not None:       rule.notes       = body.notes

    await db.commit()
    await db.refresh(rule)
    return _rule_to_out(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: str,
    current_user: Annotated[User, Depends(_get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(NotificationRule).where(
            NotificationRule.id == uuid.UUID(rule_id),
            NotificationRule.tenant_id == current_user.tenant_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
