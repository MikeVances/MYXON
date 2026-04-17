from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.device import Device
from app.models.site import Site
from app.models.user import User
from app.schemas.site import SiteOut

router = APIRouter(prefix="/api/v0/sites", tags=["sites"])


@router.get("", response_model=list[SiteOut])
async def list_sites(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = (
        select(
            Site.id,
            Site.name,
            Site.address,
            func.count(Device.id).label("devices_count"),
        )
        .outerjoin(Device, Device.site_id == Site.id)
        .where(Site.tenant_id == user.tenant_id)
        .group_by(Site.id, Site.name, Site.address)
        .order_by(Site.name)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        SiteOut(
            id=str(r.id),
            name=r.name,
            address=r.address,
            devices_count=int(r.devices_count or 0),
        )
        for r in rows
    ]

