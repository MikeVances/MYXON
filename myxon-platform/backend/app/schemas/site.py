from pydantic import BaseModel


class SiteOut(BaseModel):
    id: str
    name: str
    address: str | None = None
    devices_count: int = 0

