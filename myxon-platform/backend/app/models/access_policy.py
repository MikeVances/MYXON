"""
AccessPolicy — аналог IXON AccessCategory.

Определяет ЧТО пользователь может делать на конкретном устройстве/площадке.
Одна политика может быть назначена нескольким пользователям.
Один пользователь на разных площадках может иметь разные политики.

Примеры политик:
  "Оператор"       — только HMI через браузер, видит все аларми
  "Инженер"        — HMI + VNC + аларми + аудит
  "Наблюдатель"    — только критичные аларми, без HMI
  "Дилер-поддержка"— только аларми (временный доступ)
"""
import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class AccessPolicy(Base, UUIDPrimaryKey, TimestampMixin):
    """Named, reusable access policy — assigned to users per site."""

    __tablename__ = "access_policies"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Политика принадлежит тенанту (customer создаёт свои политики)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )

    # --- HMI / Remote access ---
    allow_hmi: Mapped[bool] = mapped_column(
        Boolean, default=True
    )  # Открыть HMI через TCP-бридж (Remote+ port 5843)
    allow_vnc: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # VNC-доступ к экрану (port 5900)
    allow_http: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # HTTP web-интерфейс устройства (port 80)

    # --- Аларми ---
    allow_alarms_view: Mapped[bool] = mapped_column(
        Boolean, default=True
    )  # Видеть панель алармов
    allow_alarms_acknowledge: Mapped[bool] = mapped_column(
        Boolean, default=True
    )  # Подтверждать аларми
    alarm_severity_filter: Mapped[str] = mapped_column(
        String(20), default="all"
    )  # "all" | "warning_and_above" | "critical_only"

    # --- Аудит ---
    allow_audit_view: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Видеть журнал действий (по умолчанию — нет)

    # --- Флаги ---
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Системная политика по умолчанию для тенанта


# ---------------------------------------------------------------------------
# Встроенные политики (создаются при инициализации тенанта)
# ---------------------------------------------------------------------------

DEFAULT_POLICIES = [
    {
        "name": "Полный доступ",
        "description": "Администратор — все возможности разрешены",
        "allow_hmi": True,
        "allow_vnc": True,
        "allow_http": True,
        "allow_alarms_view": True,
        "allow_alarms_acknowledge": True,
        "alarm_severity_filter": "all",
        "allow_audit_view": True,
        "is_default": False,
    },
    {
        "name": "Инженер",
        "description": "Техническое обслуживание — HMI, аларми, аудит",
        "allow_hmi": True,
        "allow_vnc": False,
        "allow_http": False,
        "allow_alarms_view": True,
        "allow_alarms_acknowledge": True,
        "alarm_severity_filter": "all",
        "allow_audit_view": True,
        "is_default": True,
    },
    {
        "name": "Оператор",
        "description": "Производственный персонал — только HMI и аларми",
        "allow_hmi": True,
        "allow_vnc": False,
        "allow_http": False,
        "allow_alarms_view": True,
        "allow_alarms_acknowledge": True,
        "alarm_severity_filter": "all",
        "allow_audit_view": False,
        "is_default": False,
    },
    {
        "name": "Наблюдатель",
        "description": "Только просмотр — аларми без HMI",
        "allow_hmi": False,
        "allow_vnc": False,
        "allow_http": False,
        "allow_alarms_view": True,
        "allow_alarms_acknowledge": False,
        "alarm_severity_filter": "critical_only",
        "allow_audit_view": False,
        "is_default": False,
    },
]
