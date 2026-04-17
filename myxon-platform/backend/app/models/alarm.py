"""
Alarm model — normalized alarm/event storage.

Based on the alarm architecture discovered in Android RE:
  - Rich alarm vocabulary (temperature, RH, CO2, ventilation, weather, communication)
  - Severity levels from device profile (Alarm/Warning/Off/Suppressed/None/Unknown)
  - Per-device alarm state tracked via MainGroupRead responses
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class AlarmSeverity:
    ALARM = "alarm"
    WARNING = "warning"
    OFF = "off"
    SUPPRESSED = "suppressed"
    NONE = "none"
    UNKNOWN = "unknown"


class AlarmState:
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    CLEARED = "cleared"


class Alarm(Base, UUIDPrimaryKey, TimestampMixin):
    """Individual alarm instance on a device."""

    __tablename__ = "alarms"

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )

    # Alarm identification
    code: Mapped[int] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, default="general"
    )  # temperature, humidity, co2, ventilation, communication, general
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown"
    )  # alarm, warning, off, suppressed, none, unknown
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active, acknowledged, cleared

    # Description
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cleared_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
