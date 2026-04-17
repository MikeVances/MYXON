import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.site import Site
    from app.models.user import User


class Tenant(Base, UUIDPrimaryKey, TimestampMixin):
    """Company / organization. Top-level isolation boundary."""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    tier: Mapped[str] = mapped_column(
        String(50), nullable=False, default="customer"
    )  # vendor | master_dealer | dealer | integrator | customer
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )  # channel hierarchy
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    # relationships
    users: Mapped[list["User"]] = relationship(back_populates="tenant", lazy="selectin")
    devices: Mapped[list["Device"]] = relationship(back_populates="tenant", lazy="selectin")
    sites: Mapped[list["Site"]] = relationship(back_populates="tenant", lazy="selectin")
