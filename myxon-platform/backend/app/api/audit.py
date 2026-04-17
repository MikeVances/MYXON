import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.pagination import PagedOut, decode_cursor, encode_cursor
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.audit import AuditEventOut

router = APIRouter(prefix="/api/v0/audit", tags=["audit"])


@router.get("/events", response_model=PagedOut[AuditEventOut])
async def list_audit_events(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None),
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List audit events for the current tenant, with optional filters. Cursor-paginated."""
    query = (
        select(AuditEvent)
        .where(AuditEvent.tenant_id == user.tenant_id)
    )

    if device_id:
        query = query.where(AuditEvent.device_id == device_id)
    if action:
        query = query.where(AuditEvent.action == action)
    if from_date:
        query = query.where(AuditEvent.created_at >= from_date)
    if to_date:
        query = query.where(AuditEvent.created_at <= to_date)

    # Keyset cursor: order DESC by (created_at, id)
    c = decode_cursor(cursor)
    if c:
        after_ts = datetime.fromisoformat(c["before_ts"])
        after_id = uuid.UUID(c["before_id"])
        query = query.where(
            or_(
                AuditEvent.created_at < after_ts,
                and_(AuditEvent.created_at == after_ts, AuditEvent.id < after_id),
            )
        )

    query = query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit + 1)
    result = await db.execute(query)
    events = result.scalars().all()

    next_cursor = None
    if len(events) > limit:
        last = events[limit - 1]
        next_cursor = encode_cursor({
            "before_ts": last.created_at.isoformat(),
            "before_id": str(last.id),
        })
        events = events[:limit]

    return PagedOut(
        items=[
            AuditEventOut(
                id=str(e.id),
                tenant_id=str(e.tenant_id),
                actor_id=str(e.actor_id) if e.actor_id else None,
                device_id=str(e.device_id) if e.device_id else None,
                action=e.action,
                details=e.details,
                ip_address=e.ip_address,
                resource=e.resource,
                created_at=e.created_at,
            )
            for e in events
        ],
        next_cursor=next_cursor,
    )
