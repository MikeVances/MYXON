import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.site import Site
    from app.models.tenant import Tenant


class Device(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "devices"

    serial_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hardware_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Vendor adapter identity (multi-vendor support)
    vendor_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )  # e.g. "hotraco", "siemens" — maps to vendor adapter
    device_family: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # e.g. "orion", "cygnus", "sirius"
    device_capabilities: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Capabilities advertised by vendor adapter
    # Example: [{"id": "screen-orion", "protocol": "tcp-direct", "transport": "tcp_direct"}]

    # Agent credentials
    agent_token_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    activation_code_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # State
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pre_registered"
    )  # pre_registered | online | offline | blocked
    claim_state: Mapped[str] = mapped_column(
        String(50), nullable=False, default="ready_for_transfer"
    )  # ready_for_transfer | claimed | consumed | expired | blocked
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Tunnel
    tunnel_port: Mapped[int | None] = mapped_column(nullable=True)
    tunnel_subdomain: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Published resources (VNC/HTTP endpoints behind the device)
    published_resources: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Example: [{"id": "vnc-hmi", "protocol": "vnc", "host": "192.168.27.11", "port": 5900, "name": "HMI Panel"}]

    # Selling chain (financial attribution, NOT data access)
    dealer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )  # Dealer who registered/sold this device
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )  # Partner (white-label) above dealer

    # Relationships
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )  # Customer tenant who owns/claimed this device
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id"), nullable=True, index=True
    )
    tenant: Mapped["Tenant | None"] = relationship(
        back_populates="devices", lazy="joined", foreign_keys="[Device.tenant_id]"
    )
    site: Mapped["Site | None"] = relationship(back_populates="devices", lazy="joined")

    access_sessions: Mapped[list["AccessSession"]] = relationship(
        back_populates="device", lazy="selectin"
    )


class AccessSession(Base, UUIDPrimaryKey, TimestampMixin):
    """A time-bounded remote access session to a device resource."""

    __tablename__ = "access_sessions"

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False)
    protocol: Mapped[str] = mapped_column(String(20), nullable=False)  # vnc | http | rdp | ssh
    access_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active | closed | expired
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    device: Mapped["Device"] = relationship(back_populates="access_sessions", lazy="joined")
