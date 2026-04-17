from datetime import datetime

from pydantic import BaseModel


class DeviceOut(BaseModel):
    id: str
    serial_number: str
    name: str
    model: str | None = None
    firmware_version: str | None = None
    status: str
    claim_state: str
    last_seen_at: datetime | None = None
    tenant_id: str | None = None
    site_id: str | None = None
    dealer_id: str | None = None
    partner_id: str | None = None
    vendor_id: str | None = None
    device_family: str | None = None
    device_capabilities: list[dict] | None = None
    published_resources: list[dict] | None = None

    model_config = {"from_attributes": True}


class DeviceRegisterRequest(BaseModel):
    """Dealer registers a new device serial number before shipping to customer."""
    serial_number: str
    model: str | None = None
    vendor_id: str | None = None
    device_family: str | None = None


class DeviceRegisterResponse(BaseModel):
    device_id: str
    serial_number: str
    status: str
    message: str


class DeviceClaimRequest(BaseModel):
    """Customer claims a device using only the serial number (printed on label)."""
    serial_number: str
    site_id: str | None = None
    # activation_code removed — serial number is sufficient for customer self-claim


class DeviceClaimPreview(BaseModel):
    serial_number: str
    model: str | None = None
    claim_state: str
    current_tenant: str | None = None


class DeviceClaimResponse(BaseModel):
    device_id: str
    claim_status: str
    message: str


class AgentRegisterRequest(BaseModel):
    agent_public_id: str
    serial_number: str
    signature: str
    metadata: dict | None = None


class AgentHeartbeatRequest(BaseModel):
    device_id: str
    metrics: dict | None = None
    tunnel_state: str | None = None


class AgentHeartbeatResponse(BaseModel):
    online: bool = True
    server_time: datetime
    config_version: int | None = None


class AccessSessionCreate(BaseModel):
    resource_id: str
    protocol: str  # vnc | http
    ttl_minutes: int = 30


class AccessSessionOut(BaseModel):
    id: str
    device_id: str
    resource_id: str
    protocol: str
    access_url: str | None = None
    status: str
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}
