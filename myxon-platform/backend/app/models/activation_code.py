"""
ActivationCode model: dealer generates a one-time code before shipping a device.
The device uses this code to self-register without a pre-known serial number.

Lifecycle:
  1. Dealer calls POST /api/v0/activation-codes → code generated, device_id=NULL
  2. Device boots, calls POST /api/v0/agent/activate with code
  3. Backend validates code, creates Device record, sets device_id + used_at
  4. Code is now "consumed" — cannot be used again
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class ActivationCode(Base, UUIDPrimaryKey, TimestampMixin):
    """One-time activation code issued by a dealer to provision a new device."""

    __tablename__ = "activation_codes"

    # The code itself: human-readable format XXXX-XXXX-XXXX-XXXX (32 hex chars + 3 dashes)
    code: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, index=True
    )

    # Dealer tenant that issued this code
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )

    # User (dealer employee) who generated the code
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Optional human label to identify what device this code is meant for
    # (e.g. "Farm Noord unit #3") — set by dealer at generation time
    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # When the code expires — default 7 days, set by caller
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Filled after the device self-registers using this code
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True
    )

    # Timestamp when the code was consumed (NULL = still valid)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
