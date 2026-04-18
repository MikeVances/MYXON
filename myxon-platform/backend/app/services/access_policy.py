"""
Access policy gate — 5-layer verification with AccessPolicy support.

Layer 1: User Identity — valid session
Layer 2: Tenant Context — user belongs to device's tenant
Layer 3: AccessPolicy — DB-based granular permissions (HMI, VNC, alarms…)
          Falls back to role-based check if no policy is assigned.
Layer 4: Device Scope — device is online + has the capability
Layer 5: Company Flags — tenant-level feature flags

AccessPolicy is loaded by the caller from user_site_access.access_policy → AccessPolicy.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access_policy import AccessPolicy
from app.models.device import Device
from app.models.tenant import Tenant
from app.models.user import User
from app.models.user_site_access import UserSiteAccess

logger = logging.getLogger(__name__)


@dataclass
class PolicyResult:
    allowed: bool
    denied_reason: str | None = None
    layer: str | None = None  # Which layer denied
    policy: AccessPolicy | None = None  # The resolved policy (for downstream use)


# ── Fallback role → capability matrix (used when no DB policy is assigned) ──
# Maps MYXON roles to the set of access types they get by default.
_ROLE_DEFAULT_CAPS: dict[str, set[str]] = {
    # Platform / partner / dealer — no direct device access
    "platform_admin": {"hmi", "vnc", "http", "alarms", "acknowledge", "audit"},
    "partner_admin": set(),
    "dealer_admin": set(),
    "dealer_engineer": set(),
    # Customer roles
    "customer_admin": {"hmi", "vnc", "alarms", "acknowledge", "audit"},
    "customer_engineer": {"hmi", "alarms", "acknowledge", "audit"},
    "customer_viewer": {"alarms"},
    # Legacy simple roles (User.role = admin|engineer|viewer|superadmin)
    # Used in seed data and early deployments before multi-tier naming was adopted.
    "superadmin": {"hmi", "vnc", "http", "alarms", "acknowledge", "audit"},
    "admin":      {"hmi", "vnc", "http", "alarms", "acknowledge", "audit"},
    "engineer":   {"hmi", "vnc", "http", "alarms", "acknowledge"},
    "viewer":     {"alarms"},
}


async def get_site_policy(
    db: AsyncSession,
    user_id: uuid.UUID,
    site_id: uuid.UUID,
) -> AccessPolicy | None:
    """
    Load the AccessPolicy assigned to this user on this site.
    Returns None if no explicit policy is assigned — caller falls back to role defaults.
    """
    result = await db.execute(
        select(UserSiteAccess).where(
            UserSiteAccess.user_id == user_id,
            UserSiteAccess.site_id == site_id,
        )
    )
    usa = result.scalar_one_or_none()
    if usa is None:
        return None
    # access_policy is lazy="joined" so it's already loaded
    return usa.access_policy


async def get_tenant_default_policy(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> AccessPolicy | None:
    """Return the tenant's default AccessPolicy (is_default=True), if any."""
    result = await db.execute(
        select(AccessPolicy).where(
            AccessPolicy.tenant_id == tenant_id,
            AccessPolicy.is_default == True,  # noqa: E712
        ).limit(1)
    )
    return result.scalar_one_or_none()


def check_access(
    user: User,
    device: Device,
    protocol: str,
    resource_id: str,
    tenant: Tenant | None = None,
    policy: AccessPolicy | None = None,
) -> PolicyResult:
    """
    Run all 5 access policy layers.

    protocol values:
      "hmi"         → HMI via Remote+ TCP bridge (allow_hmi)
      "vnc"         → VNC access (allow_vnc)
      "http"        → HTTP web interface (allow_http)
      "tcp-direct"  → alias for "hmi" (legacy)
      "alarms"      → view alarms (allow_alarms_view)
      "acknowledge" → ack alarms (allow_alarms_acknowledge)
      "audit"       → view audit log (allow_audit_view)

    Returns PolicyResult with allowed=True or denied reason.
    """
    # Normalise legacy protocol name
    if protocol == "tcp-direct":
        protocol = "hmi"

    # Layer 1: User Identity (guaranteed by get_current_user dep)
    if user is None:
        return PolicyResult(
            allowed=False,
            denied_reason="Authentication required",
            layer="identity",
        )

    # Layer 2: Tenant Context
    if device.tenant_id is None:
        return PolicyResult(
            allowed=False,
            denied_reason="Device is not claimed by any tenant",
            layer="tenant",
        )
    if user.tenant_id != device.tenant_id:
        return PolicyResult(
            allowed=False,
            denied_reason="You do not have access to this device",
            layer="tenant",
        )

    # Layer 3: AccessPolicy (DB) or role fallback
    if policy is not None:
        result = _check_policy_object(user, protocol, policy)
        if result is not None:
            return result
    else:
        # No DB policy — fall back to role-based capabilities
        allowed_caps = _ROLE_DEFAULT_CAPS.get(user.role, set())
        if protocol not in allowed_caps:
            return PolicyResult(
                allowed=False,
                denied_reason=f"Your role ({user.role}) does not permit {protocol} access",
                layer="role",
            )

    # Layer 4: Device Scope + Capability
    if protocol in ("hmi", "vnc", "http") and device.status != "online":
        return PolicyResult(
            allowed=False,
            denied_reason="Device is offline",
            layer="device_scope",
        )

    # Check if device has the requested resource (for HMI/VNC)
    if protocol == "hmi" and device.published_resources and resource_id != "screen":
        resource_ids = [r.get("id") for r in device.published_resources]
        if resource_id not in resource_ids:
            return PolicyResult(
                allowed=False,
                denied_reason=f"Resource '{resource_id}' not found on this device",
                layer="device_scope",
            )

    # Layer 5: Tenant-level feature flags
    if tenant and hasattr(tenant, "metadata") and tenant.metadata:
        tenant_meta = tenant.metadata
        if protocol == "vnc" and not tenant_meta.get("vnc_access_enabled", True):
            return PolicyResult(
                allowed=False,
                denied_reason="VNC access is disabled for your organization",
                layer="company_flags",
            )

    logger.info(
        "Access granted: user=%s device=%s protocol=%s resource=%s",
        user.email, device.serial_number, protocol, resource_id,
    )
    return PolicyResult(allowed=True, policy=policy)


def _check_policy_object(
    user: User,
    protocol: str,
    policy: AccessPolicy,
) -> PolicyResult | None:
    """
    Check protocol permission against an AccessPolicy object.
    Returns PolicyResult(denied) if denied, None if allowed (caller continues to next layer).
    """
    denied = lambda reason: PolicyResult(  # noqa: E731
        allowed=False, denied_reason=reason, layer="access_policy", policy=policy
    )

    if protocol == "hmi" and not policy.allow_hmi:
        return denied("Your access policy does not permit HMI access")
    if protocol == "vnc" and not policy.allow_vnc:
        return denied("Your access policy does not permit VNC access")
    if protocol == "http" and not policy.allow_http:
        return denied("Your access policy does not permit HTTP access")
    if protocol == "alarms" and not policy.allow_alarms_view:
        return denied("Your access policy does not permit viewing alarms")
    if protocol == "acknowledge" and not policy.allow_alarms_acknowledge:
        return denied("Your access policy does not permit acknowledging alarms")
    if protocol == "audit" and not policy.allow_audit_view:
        return denied("Your access policy does not permit viewing the audit log")

    return None  # allowed by policy


def get_alarm_severity_filter(policy: AccessPolicy | None) -> str:
    """
    Return the alarm_severity_filter from the policy, or 'all' if no policy.
    Used by alarms.py to filter what the user sees.
    """
    if policy is None:
        return "all"
    return policy.alarm_severity_filter


SEVERITY_ORDER = {"alarm": 3, "warning": 2, "off": 1, "suppressed": 0, "none": 0, "unknown": 0}


def severity_passes_filter(severity: str, filter_value: str) -> bool:
    """
    Return True if the given alarm severity passes the filter.

    Filters:
      "all"               — all severities pass
      "warning_and_above" — warning + alarm pass
      "critical_only"     — only alarm passes
    """
    if filter_value == "all":
        return True
    if filter_value == "warning_and_above":
        return SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER["warning"]
    if filter_value == "critical_only":
        return severity == "alarm"
    return True
