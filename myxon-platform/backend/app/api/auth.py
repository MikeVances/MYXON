import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.invite import Invite
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import (
    InviteCreateRequest,
    InviteOut,
    LoginRequest,
    RefreshRequest,
    RegisterByInviteRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/api/v0/auth", tags=["auth"])

DEALER_ROLES = ("dealer_admin", "dealer_engineer")
INVITE_TTL_DAYS = 7


# ---------------------------------------------------------------------------
# Login / Refresh / Me
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    token_data = {"sub": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    payload = decode_token(body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    token_data = {"sub": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return UserOut(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        tenant_id=str(user.tenant_id),
        tenant_name=user.tenant.name if user.tenant else None,
        tenant_tier=user.tenant.tier if user.tenant else None,
    )


# ---------------------------------------------------------------------------
# Invite flow: dealer creates invite → customer registers
# ---------------------------------------------------------------------------

@router.post("/invite", response_model=InviteOut)
async def create_invite(
    body: InviteCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Dealer creates a one-time invite link for a new customer."""
    if user.role not in DEALER_ROLES + ("superadmin", "admin", "platform_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only dealer accounts can create customer invites",
        )

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)

    invite = Invite(
        token=token,
        created_by_tenant_id=user.tenant_id,
        created_by_user_id=user.id,
        customer_email=body.customer_email,
        customer_name=body.customer_name,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.flush()

    # Build invite URL (frontend route)
    from app.core.config import settings
    base_url = getattr(settings, "app_base_url", "http://localhost:3000")
    invite_url = f"{base_url}/register?token={token}"

    return InviteOut(
        invite_id=str(invite.id),
        token=token,
        customer_email=body.customer_email,
        customer_name=body.customer_name,
        expires_at=expires_at.isoformat(),
        invite_url=invite_url,
    )


@router.post("/register-by-invite", response_model=TokenResponse)
async def register_by_invite(
    body: RegisterByInviteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Customer completes signup using the invite link token.
    Creates a new Tenant (customer) and User in one transaction.
    """
    # Validate invite token
    result = await db.execute(select(Invite).where(Invite.token == body.invite_token))
    invite = result.scalar_one_or_none()

    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found or invalid")
    if invite.is_used:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invite already used")
    if invite.expires_at and invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite expired")

    # Check email not already registered
    existing = await db.execute(select(User).where(User.email == invite.customer_email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Create customer Tenant
    # Slug: lowercase email local-part + random suffix for uniqueness
    slug_base = invite.customer_email.split("@")[0].lower().replace(".", "-")
    slug = f"{slug_base}-{secrets.token_hex(3)}"

    customer_tenant = Tenant(
        name=invite.customer_name,
        slug=slug,
        tier="customer",
        parent_id=invite.created_by_tenant_id,  # dealer is the parent in hierarchy
    )
    db.add(customer_tenant)
    await db.flush()  # get tenant.id

    # Create customer_admin user
    full_name = body.full_name or invite.customer_name
    user = User(
        email=invite.customer_email,
        hashed_password=hash_password(body.password),
        full_name=full_name,
        role="customer_admin",
        tenant_id=customer_tenant.id,
    )
    db.add(user)

    # Mark invite as used
    invite.is_used = True
    invite.used_at = datetime.now(timezone.utc)
    invite.customer_tenant_id = customer_tenant.id

    await db.flush()

    # Return tokens so customer is immediately logged in
    token_data = {"sub": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.get("/invite/{token}")
async def get_invite_info(token: str, db: Annotated[AsyncSession, Depends(get_db)]):
    """Public endpoint: frontend fetches invite details to pre-fill the registration form."""
    result = await db.execute(select(Invite).where(Invite.token == token))
    invite = result.scalar_one_or_none()

    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    if invite.is_used:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invite already used")
    if invite.expires_at and invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite expired")

    return {
        "customer_email": invite.customer_email,
        "customer_name": invite.customer_name,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
    }
