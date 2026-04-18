"""
Activation Code endpoints — dealer-side provisioning flow.

A dealer generates a code BEFORE shipping a device.
The device uses that code on first boot to self-register via POST /api/v0/agent/activate.

Flow:
  Dealer UI → POST /api/v0/activation-codes  → code: "A3F1-B2E4-C9D7-0F56"
  Device boot → POST /api/v0/agent/activate   → code="A3F1-B2E4-C9D7-0F56"
                                               ← device_id, serial, frpc_token, tunnel
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.activation_code import ActivationCode
from app.models.user import User

router = APIRouter(prefix="/api/v0/activation-codes", tags=["activation-codes"])

# ─── Schemas ────────────────────────────────────────────────────────────────

class GenerateCodeRequest(BaseModel):
    device_name: str | None = None  # Optional label ("Farm Noord unit #3")
    ttl_days: int = 7               # How long the code stays valid


class ActivationCodeOut(BaseModel):
    id: str
    code: str
    device_name: str | None
    expires_at: datetime
    used_at: datetime | None
    device_id: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Helpers ────────────────────────────────────────────────────────────────

def _generate_code() -> str:
    """
    Generate a cryptographically secure activation code.
    Format: XXXX-XXXX-XXXX-XXXX (16 uppercase hex chars grouped by 4).
    Example: A3F1-B2E4-C9D7-0F56
    """
    raw = secrets.token_hex(8).upper()  # 8 bytes = 16 hex chars
    return f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}"


# ─── Endpoints ──────────────────────────────────────────────────────────────

@router.post("", response_model=ActivationCodeOut, status_code=status.HTTP_201_CREATED)
async def generate_activation_code(
    body: GenerateCodeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Generate a one-time activation code.
    Called by dealer before shipping a device.
    The code is valid for ttl_days (default 7).
    """
    now = datetime.now(timezone.utc)

    activation_code = ActivationCode(
        id=uuid.uuid4(),
        code=_generate_code(),
        tenant_id=current_user.tenant_id,  # Dealer's tenant
        created_by=current_user.id,
        device_name=body.device_name,
        expires_at=now + timedelta(days=body.ttl_days),
    )
    db.add(activation_code)
    await db.flush()  # Ensure DB-generated fields are populated before returning

    return ActivationCodeOut(
        id=str(activation_code.id),
        code=activation_code.code,
        device_name=activation_code.device_name,
        expires_at=activation_code.expires_at,
        used_at=activation_code.used_at,
        device_id=str(activation_code.device_id) if activation_code.device_id else None,
        created_at=activation_code.created_at,
    )


@router.get("", response_model=list[ActivationCodeOut])
async def list_activation_codes(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    List all activation codes for the dealer's tenant.
    Includes both unused (pending) and used (consumed) codes.
    """
    result = await db.execute(
        select(ActivationCode)
        .where(ActivationCode.tenant_id == current_user.tenant_id)
        .order_by(ActivationCode.created_at.desc())
    )
    codes = result.scalars().all()

    return [
        ActivationCodeOut(
            id=str(c.id),
            code=c.code,
            device_name=c.device_name,
            expires_at=c.expires_at,
            used_at=c.used_at,
            device_id=str(c.device_id) if c.device_id else None,
            created_at=c.created_at,
        )
        for c in codes
    ]


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_activation_code(
    code: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Revoke (delete) an unused activation code.
    Cannot revoke codes that have already been consumed by a device.
    """
    result = await db.execute(
        select(ActivationCode).where(
            ActivationCode.code == code,
            ActivationCode.tenant_id == current_user.tenant_id,
        )
    )
    activation_code = result.scalar_one_or_none()

    if activation_code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code not found")

    if activation_code.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot revoke a code that has already been used by a device",
        )

    await db.delete(activation_code)
