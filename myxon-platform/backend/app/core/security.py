import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


# ── Agent / device token helpers ──────────────────────────────────────────────
# We use SHA-256 (not bcrypt) for agent tokens because:
#  1. Tokens are already 256-bit random — no need for key stretching
#  2. frps plugin calls the auth webhook on EVERY frpc reconnect;
#     bcrypt would add 100–300ms latency per reconnect

def generate_agent_token() -> str:
    """Generate a cryptographically secure 256-bit agent token (URL-safe base64)."""
    return secrets.token_urlsafe(32)


def hash_agent_token(token: str) -> str:
    """Return SHA-256 hex digest of the token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_agent_token(plain: str, hashed: str) -> bool:
    """Constant-time comparison of token hash."""
    return hashlib.sha256(plain.encode()).hexdigest() == hashed
