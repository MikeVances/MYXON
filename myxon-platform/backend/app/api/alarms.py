"""
Alarm API — list, filter, and acknowledge device alarms.

AccessPolicy enforcement:
  - allow_alarms_view=False   → 403 on list endpoint
  - allow_alarms_acknowledge=False → 403 on acknowledge endpoint
  - alarm_severity_filter     → applied server-side to filter list results
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.pagination import PagedOut, decode_cursor, encode_cursor
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.user import User
from app.services.access_policy import (
    get_site_policy,
    get_tenant_default_policy,
    get_alarm_severity_filter,
)
from app.services.alarm_ingestion import acknowledge_alarm

router = APIRouter(prefix="/api/v0/alarms", tags=["alarms"])


class AlarmOut(BaseModel):
    id: str
    device_id: str
    code: int
    category: str
    severity: str
    state: str
    message: str | None = None
    triggered_at: str
    acknowledged_at: str | None = None
    cleared_at: str | None = None

    model_config = {"from_attributes": True}


async def _resolve_policy(db: AsyncSession, user: User, device_id: str | None):
    """
    Resolve the effective AccessPolicy for the current user.

    If a specific device_id is given, looks up its site to get the site-level policy.
    Falls back to tenant-default policy, then None.
    """
    if device_id:
        # Load device to find its site
        dev_result = await db.execute(
            select(Device).where(Device.id == uuid.UUID(device_id))
        )
        device = dev_result.scalar_one_or_none()
        if device and device.site_id:
            policy = await get_site_policy(db, user.id, device.site_id)
            if policy:
                return policy

    # Tenant-level default
    return await get_tenant_default_policy(db, user.tenant_id)


@router.get("", response_model=PagedOut[AlarmOut])
async def list_alarms(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: str | None = Query(None),
    state: str | None = Query(None),
    severity: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """
    List alarms for the current tenant, optionally filtered. Cursor-paginated.
    Respects AccessPolicy: allow_alarms_view and alarm_severity_filter.
    """
    policy = await _resolve_policy(db, user, device_id)

    if policy is not None and not policy.allow_alarms_view:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your access policy does not permit viewing alarms",
        )

    q = select(Alarm).where(Alarm.tenant_id == user.tenant_id)

    if device_id:
        q = q.where(Alarm.device_id == uuid.UUID(device_id))
    if state:
        q = q.where(Alarm.state == state)
    if severity:
        q = q.where(Alarm.severity == severity)

    # Keyset cursor: order DESC by (triggered_at, id)
    c = decode_cursor(cursor)
    if c:
        after_ts = datetime.fromisoformat(c["before_ts"])
        after_id = uuid.UUID(c["before_id"])
        q = q.where(
            or_(
                Alarm.triggered_at < after_ts,
                and_(Alarm.triggered_at == after_ts, Alarm.id < after_id),
            )
        )

    # ── Push severity filter to SQL so keyset pagination is correct ──────────
    # Python-side filtering after LIMIT would cause pages with < limit items
    # while next_cursor still points to an unfiltered boundary.
    severity_filter = get_alarm_severity_filter(policy)
    if severity_filter == "warning_and_above":
        q = q.where(Alarm.severity.in_(["warning", "alarm"]))
    elif severity_filter == "critical_only":
        q = q.where(Alarm.severity == "alarm")
    # "all" → no additional SQL clause

    q = q.order_by(Alarm.triggered_at.desc(), Alarm.id.desc()).limit(limit + 1)
    result = await db.execute(q)
    rows = list(result.scalars().all())

    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor({
            "before_ts": last.triggered_at.isoformat() if last.triggered_at else "",
            "before_id": str(last.id),
        })
        rows = rows[:limit]

    return PagedOut(
        items=[
            AlarmOut(
                id=str(a.id),
                device_id=str(a.device_id),
                code=a.code,
                category=a.category,
                severity=a.severity,
                state=a.state,
                message=a.message,
                triggered_at=a.triggered_at.isoformat() if a.triggered_at else "",
                acknowledged_at=a.acknowledged_at.isoformat() if a.acknowledged_at else None,
                cleared_at=a.cleared_at.isoformat() if a.cleared_at else None,
            )
            for a in rows
        ],
        next_cursor=next_cursor,
    )


@router.post("/{alarm_id}/acknowledge")
async def ack_alarm(
    alarm_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Acknowledge an active alarm.
    Requires allow_alarms_acknowledge=True in the user's AccessPolicy.
    """
    # Load alarm to find device → site → policy
    alarm_result = await db.execute(
        select(Alarm).where(Alarm.id == uuid.UUID(alarm_id))
    )
    alarm = alarm_result.scalar_one_or_none()
    if alarm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alarm not found or already acknowledged",
        )

    policy = await _resolve_policy(db, user, str(alarm.device_id))

    if policy is not None and not policy.allow_alarms_acknowledge:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your access policy does not permit acknowledging alarms",
        )

    acked = await acknowledge_alarm(db, alarm_id, str(user.id))
    if acked is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alarm not found or already acknowledged",
        )
    return {"acknowledged": True, "alarm_id": alarm_id}
