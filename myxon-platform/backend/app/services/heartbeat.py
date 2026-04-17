"""
Background heartbeat checker.

Periodically scans devices with status='online' and marks them
as 'offline' if last_seen_at exceeds the heartbeat timeout.
Emits audit events for status transitions.

Runs as an asyncio background task within the FastAPI lifespan.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session
from app.models.audit import AuditEvent
from app.models.device import Device

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SEC = 15  # How often to run the sweep


async def _sweep_once() -> int:
    """
    Single sweep: find online devices past heartbeat timeout, mark offline.
    Returns number of devices transitioned to offline.
    """
    threshold = datetime.now(timezone.utc) - timedelta(
        seconds=settings.heartbeat_timeout_seconds
    )

    async with async_session() as db:
        # Find devices that are online but haven't sent a heartbeat in time
        result = await db.execute(
            select(Device).where(
                Device.status == "online",
                Device.last_seen_at < threshold,
            )
        )
        stale_devices = result.scalars().all()

        if not stale_devices:
            return 0

        count = 0
        for device in stale_devices:
            device.status = "offline"
            count += 1

            # Emit audit event for tenant-owned devices
            if device.tenant_id:
                audit = AuditEvent(
                    tenant_id=device.tenant_id,
                    device_id=device.id,
                    action="device.offline",
                    details={
                        "reason": "heartbeat_timeout",
                        "last_seen_at": device.last_seen_at.isoformat()
                        if device.last_seen_at
                        else None,
                        "threshold_seconds": settings.heartbeat_timeout_seconds,
                    },
                )
                db.add(audit)

        await db.commit()
        return count


async def heartbeat_checker_loop() -> None:
    """
    Long-running loop that periodically sweeps for stale devices.
    Designed to run as a background task in the FastAPI lifespan.
    """
    logger.info(
        "Heartbeat checker started: interval=%ds, timeout=%ds",
        CHECK_INTERVAL_SEC,
        settings.heartbeat_timeout_seconds,
    )
    while True:
        try:
            count = await _sweep_once()
            if count > 0:
                logger.info("Heartbeat sweep: %d device(s) marked offline", count)
        except Exception:
            logger.exception("Heartbeat sweep error")
        await asyncio.sleep(CHECK_INTERVAL_SEC)
