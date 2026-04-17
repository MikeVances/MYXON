from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    tenant_id: str
    tenant_name: str | None = None
    tenant_tier: str | None = None  # platform | partner | dealer | customer

    model_config = {"from_attributes": True}


# --- Invite flow ---

class InviteCreateRequest(BaseModel):
    """Dealer creates an invite for a new customer."""
    customer_email: EmailStr
    customer_name: str


class InviteOut(BaseModel):
    invite_id: str
    token: str
    customer_email: str
    customer_name: str
    expires_at: str
    invite_url: str  # full URL to send to customer


class RegisterByInviteRequest(BaseModel):
    """Customer fills in password after clicking invite link."""
    invite_token: str
    password: str
    full_name: str | None = None  # can override the name set by dealer
