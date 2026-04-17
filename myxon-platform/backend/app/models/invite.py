"""
Invite model: dealer creates an invite link for a new customer.
Customer registers via the invite token — no need for manual account creation.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class Invite(Base, UUIDPrimaryKey, TimestampMixin):
    """One-time invite for customer signup, created by a dealer."""

    __tablename__ = "invites"

    token: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )  # Secure random token sent in invite link

    # Who created the invite
    created_by_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )  # Dealer tenant
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Pre-filled customer info (dealer sets these when creating invite)
    customer_email: Mapped[str] = mapped_column(String(320), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Resulting customer tenant (filled after signup completes)
    customer_tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True
    )

    # State
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
