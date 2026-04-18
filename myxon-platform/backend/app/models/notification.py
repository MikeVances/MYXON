"""
Notification contacts and routing rules.

Architecture:
  NotificationContact — a person (engineer, manager) with phone/email
  NotificationRule    — when to notify that person (scope + severity filter)

Scope hierarchy (broadest → most specific):
  tenant  → all devices in the tenant
  site    → all devices at one farm/location
  device  → exactly one device

When an alarm fires, the backend collects all matching rules across all
three scopes and sends notifications to the resulting unique contact set.

SMS is delivered via the edge agent (heartbeat response field `pending_sms`),
which uses mmcli/AT commands to the local GSM modem. Email is sent directly
from the backend via SMTP.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.notification import NotificationRule


class NotificationContact(Base, UUIDPrimaryKey, TimestampMixin):
    """
    A person who can receive alarm notifications.

    One contact can be referenced by multiple rules (different scope or severity).
    Channels example: ["sms", "email"] — both; ["sms"] — SMS only.
    """
    __tablename__ = "notification_contacts"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Contact details — at least one must be set
    phone: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # E.164 format: +31612345678
    email: Mapped[str | None] = mapped_column(
        String(320), nullable=True
    )

    # Which channels to use when notifying this contact.
    # Valid values: "sms", "email"
    channels: Mapped[list] = mapped_column(
        JSON, nullable=False, default=lambda: ["sms", "email"]
    )

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Back-reference: which rules reference this contact
    rules: Mapped[list["NotificationRule"]] = relationship(
        back_populates="contact", lazy="selectin", cascade="all, delete-orphan"
    )


class NotificationRule(Base, UUIDPrimaryKey, TimestampMixin):
    """
    Routing rule: contact X receives alarms from scope Y with severity >= Z.

    scope_type / scope_id encoding:
      "tenant"  → scope_id = tenant UUID
      "site"    → scope_id = site UUID
      "device"  → scope_id = device UUID

    categories: [] means "all categories"; ["temperature","power"] means only those.
    min_severity: "warning" triggers on WARNING+ALARM; "alarm" triggers on ALARM only.
    """
    __tablename__ = "notification_rules"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notification_contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Scope
    scope_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "tenant" | "site" | "device"
    scope_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Filters
    min_severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="alarm"
    )  # "warning" | "alarm"
    categories: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )  # [] = all; ["temperature","power"] = filtered

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    contact: Mapped["NotificationContact"] = relationship(
        back_populates="rules", lazy="joined"
    )
