from datetime import datetime

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: str
    tenant_id: str
    actor_id: str | None = None
    device_id: str | None = None
    action: str
    details: dict | None = None
    ip_address: str | None = None
    resource: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
