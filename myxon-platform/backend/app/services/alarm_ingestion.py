"""
Alarm ingestion and normalization service.

Receives raw alarm data from device heartbeats or Remote+ MainGroupRead
responses and normalizes them into the platform's alarm model.

Alarm categories (from SyslinQ alarm vocabulary):
  - temperature, humidity, co2, ventilation, pressure
  - weather, communication, power, sensor, general

Severity mapping follows the device profile's alarmColor scheme:
  EF enum -> Alarm / Warning / Off / Suppressed / None / Unknown
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alarm import Alarm, AlarmSeverity, AlarmState
from app.models.audit import AuditEvent
from app.models.device import Device
from app.services.notifications import route_alarm_notifications

logger = logging.getLogger(__name__)

# ── Alarm category classifier ──

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "temperature": ["temp", "temperature", "heat", "cold", "frost"],
    "humidity": ["rh", "humidity", "moisture"],
    "co2": ["co2", "carbon"],
    "ventilation": ["vent", "fan", "air"],
    "pressure": ["pressure", "bar"],
    "weather": ["weather", "wind", "rain", "storm"],
    "communication": ["comm", "connection", "link", "network", "timeout"],
    "power": ["power", "voltage", "battery", "ups"],
    "sensor": ["sensor", "probe", "input"],
}


def classify_alarm_category(code: int, message: str | None = None) -> str:
    """Classify alarm by code range or message keywords."""
    if message:
        msg_lower = message.lower()
        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in msg_lower for kw in keywords):
                return category
    # Fallback: code-based ranges (vendor-specific, can be extended per adapter)
    return "general"


def map_severity(raw_value: int) -> str:
    """Map raw alarm severity from device profile to normalized severity."""
    severity_map = {
        0: AlarmSeverity.OFF,
        1: AlarmSeverity.ALARM,
        2: AlarmSeverity.WARNING,
        3: AlarmSeverity.SUPPRESSED,
        4: AlarmSeverity.NONE,
    }
    return severity_map.get(raw_value, AlarmSeverity.UNKNOWN)


async def ingest_alarm(
    db: AsyncSession,
    device: Device,
    code: int,
    severity_raw: int,
    message: str | None = None,
    details: dict | None = None,
) -> Alarm:
    """
    Ingest a single alarm event from a device.

    If an active alarm with the same code already exists on this device,
    update its severity. Otherwise, create a new alarm.
    """
    severity = map_severity(severity_raw)
    category = classify_alarm_category(code, message)
    now = datetime.now(timezone.utc)

    # Check for existing active alarm with same code
    result = await db.execute(
        select(Alarm).where(
            Alarm.device_id == device.id,
            Alarm.code == code,
            Alarm.state == AlarmState.ACTIVE,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update severity if changed
        if existing.severity != severity:
            existing.severity = severity
            if details:
                existing.details = details
            logger.info(
                "Alarm updated: device=%s code=%d severity=%s",
                device.serial_number, code, severity,
            )
        # If severity is OFF or NONE, auto-clear
        if severity in (AlarmSeverity.OFF, AlarmSeverity.NONE):
            existing.state = AlarmState.CLEARED
            existing.cleared_at = now
            logger.info("Alarm auto-cleared: device=%s code=%d", device.serial_number, code)
        return existing

    # Create new alarm
    alarm = Alarm(
        device_id=device.id,
        tenant_id=device.tenant_id,
        code=code,
        category=category,
        severity=severity,
        state=AlarmState.ACTIVE if severity in (AlarmSeverity.ALARM, AlarmSeverity.WARNING) else AlarmState.CLEARED,
        message=message,
        details=details,
        triggered_at=now,
        cleared_at=now if severity in (AlarmSeverity.OFF, AlarmSeverity.NONE) else None,
    )
    db.add(alarm)

    # Audit event for new alarms
    if device.tenant_id and severity in (AlarmSeverity.ALARM, AlarmSeverity.WARNING):
        audit = AuditEvent(
            tenant_id=device.tenant_id,
            device_id=device.id,
            action="alarm.triggered",
            details={
                "code": code,
                "severity": severity,
                "category": category,
                "message": message,
            },
        )
        db.add(audit)

    logger.info(
        "Alarm created: device=%s code=%d severity=%s category=%s",
        device.serial_number, code, severity, category,
    )

    # Route notifications (email now, SMS queued for next heartbeat).
    # Fire-and-forget: all errors logged inside route_alarm_notifications, never raised.
    if alarm.state == AlarmState.ACTIVE:
        await route_alarm_notifications(db, device, alarm)

    return alarm


async def acknowledge_alarm(
    db: AsyncSession,
    alarm_id: str,
    user_id: str,
) -> Alarm | None:
    """Acknowledge an active alarm."""
    result = await db.execute(
        select(Alarm).where(Alarm.id == alarm_id)
    )
    alarm = result.scalar_one_or_none()
    if alarm is None or alarm.state != AlarmState.ACTIVE:
        return None

    alarm.state = AlarmState.ACKNOWLEDGED
    alarm.acknowledged_at = datetime.now(timezone.utc)
    alarm.acknowledged_by = user_id
    return alarm
