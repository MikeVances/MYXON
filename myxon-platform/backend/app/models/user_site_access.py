"""
UserSiteAccess: определяет доступ пользователя к конкретной площадке.

Теперь содержит ссылку на AccessPolicy — по аналогии с IXON AccessCategory.
Один пользователь может иметь разные политики на разных площадках:
  - на ферме A: политика "Инженер" (HMI + аларми + аудит)
  - на ферме Б: политика "Наблюдатель" (только критичные аларми)
"""
import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class UserSiteAccess(Base, UUIDPrimaryKey, TimestampMixin):
    """Grants a user access to a specific site with a specific AccessPolicy."""

    __tablename__ = "user_site_access"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(50), default="customer_viewer"
        # site-level role: customer_admin | customer_engineer | customer_viewer
    )

    # AccessPolicy — ЧТО пользователь может делать на устройствах этой площадки
    # Если NULL — применяется дефолтная политика tenant'а
    access_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("access_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    access_policy: Mapped["AccessPolicy | None"] = relationship(  # type: ignore[name-defined]
        "AccessPolicy", lazy="joined"
    )

    __table_args__ = (UniqueConstraint("user_id", "site_id", name="uq_user_site"),)
