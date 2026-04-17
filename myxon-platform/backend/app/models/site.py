import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.tenant import Tenant


class Site(Base, UUIDPrimaryKey, TimestampMixin):
    """Physical location / facility where devices are deployed."""

    __tablename__ = "sites"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="sites", lazy="joined")
    devices: Mapped[list["Device"]] = relationship(back_populates="site", lazy="selectin")
