"""
Notification routing service.

Handles alarm notifications via two channels:
  1. Email — sent directly from backend via SMTP (aiosmtplib)
  2. SMS   — queued in heartbeat response; delivered by edge agent via GSM modem

Routing uses NotificationRule → NotificationContact hierarchy:
  - Rules can be scoped to: tenant / site / device
  - Contacts have channel preferences: ["sms", "email"]
  - Rules filter by min_severity and optional category list

Call `route_alarm_notifications()` after a new active alarm is created.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.alarm import Alarm, AlarmSeverity, AlarmState
from app.models.device import Device
from app.models.notification import NotificationContact, NotificationRule

logger = logging.getLogger(__name__)

# ── Severity ordering ─────────────────────────────────────────────────────────

_SEVERITY_RANK = {
    AlarmSeverity.WARNING: 1,
    AlarmSeverity.ALARM:   2,
}

_SEVERITY_COLOR = {
    AlarmSeverity.ALARM:   "#dc2626",
    AlarmSeverity.WARNING: "#d97706",
}

_SEVERITY_LABEL = {
    AlarmSeverity.ALARM:   "ALARM",
    AlarmSeverity.WARNING: "WARNING",
}


def _severity_qualifies(alarm_severity: str, min_severity: str) -> bool:
    """Return True if alarm_severity >= min_severity threshold."""
    alarm_rank = _SEVERITY_RANK.get(alarm_severity, 0)
    min_rank   = _SEVERITY_RANK.get(min_severity, 99)
    return alarm_rank >= min_rank


# ── Rule matching ─────────────────────────────────────────────────────────────

async def _collect_contacts(
    db: AsyncSession,
    device: Device,
    alarm: Alarm,
) -> tuple[list[NotificationContact], list[NotificationContact]]:
    """
    Return (email_contacts, sms_contacts) for the given alarm.

    Collects all active rules covering the alarm's device (via device / site /
    tenant scope), filters by severity and category, de-duplicates contacts.
    """
    if not device.tenant_id:
        return [], []

    # Candidate scope IDs at each level
    scope_ids: list[tuple[str, str]] = [
        ("tenant", str(device.tenant_id)),
        ("device", str(device.id)),
    ]
    if device.site_id:
        scope_ids.append(("site", str(device.site_id)))

    # Fetch all matching active rules in one query
    rules_result = await db.execute(
        select(NotificationRule).where(
            NotificationRule.tenant_id == device.tenant_id,
            NotificationRule.active.is_(True),
        )
    )
    all_rules = rules_result.scalars().all()

    email_contacts: dict[str, NotificationContact] = {}
    sms_contacts:   dict[str, NotificationContact] = {}

    for rule in all_rules:
        # Match scope
        match = any(
            rule.scope_type == stype and str(rule.scope_id) == sid
            for stype, sid in scope_ids
        )
        if not match:
            continue

        # Filter by severity
        if not _severity_qualifies(alarm.severity, rule.min_severity):
            continue

        # Filter by category (empty list = all)
        if rule.categories and alarm.category not in rule.categories:
            continue

        contact = rule.contact
        if not contact or not contact.active:
            continue

        cid = str(contact.id)
        if "email" in contact.channels and contact.email:
            email_contacts[cid] = contact
        if "sms" in contact.channels and contact.phone:
            sms_contacts[cid] = contact

    return list(email_contacts.values()), list(sms_contacts.values())


# ── Email sending ─────────────────────────────────────────────────────────────

def _build_email(device: Device, alarm: Alarm, recipient_email: str) -> MIMEMultipart:
    severity_label = _SEVERITY_LABEL.get(alarm.severity, alarm.severity.upper())
    severity_color = _SEVERITY_COLOR.get(alarm.severity, "#6b7280")

    subject = (
        f"[MYXON] {severity_label}: {alarm.message or f'Alarm #{alarm.code}'}"
        f" — {device.name or device.serial_number}"
    )

    detail_rows = ""
    if alarm.details:
        for k, v in alarm.details.items():
            detail_rows += (
                f"<tr><td style='padding:4px 8px;color:#6b7280'>{k}</td>"
                f"<td style='padding:4px 8px'>{v}</td></tr>"
            )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="font-family:sans-serif;background:#f8fafc;margin:0;padding:24px">
  <div style="max-width:560px;margin:0 auto;background:#fff;border-radius:8px;
              overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.12)">
    <div style="background:{severity_color};padding:16px 24px">
      <span style="color:#fff;font-size:18px;font-weight:700">{severity_label}</span>
      <span style="color:#ffffffcc;font-size:14px;margin-left:8px">{alarm.category or 'general'}</span>
    </div>
    <div style="padding:24px">
      <h2 style="margin:0 0 8px;font-size:16px;color:#0f172a">
        {alarm.message or f'Alarm code {alarm.code}'}
      </h2>
      <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px">
        <tr style="background:#f1f5f9">
          <td style="padding:6px 8px;color:#6b7280;width:120px">Device</td>
          <td style="padding:6px 8px;font-weight:500">{device.name or 'N/A'}</td>
        </tr>
        <tr>
          <td style="padding:6px 8px;color:#6b7280">Serial</td>
          <td style="padding:6px 8px">{device.serial_number}</td>
        </tr>
        <tr style="background:#f1f5f9">
          <td style="padding:6px 8px;color:#6b7280">Alarm code</td>
          <td style="padding:6px 8px">{alarm.code}</td>
        </tr>
        <tr>
          <td style="padding:6px 8px;color:#6b7280">Category</td>
          <td style="padding:6px 8px">{alarm.category or 'general'}</td>
        </tr>
        <tr style="background:#f1f5f9">
          <td style="padding:6px 8px;color:#6b7280">Triggered at</td>
          <td style="padding:6px 8px">
            {alarm.triggered_at.strftime('%Y-%m-%d %H:%M UTC') if alarm.triggered_at else 'N/A'}
          </td>
        </tr>
        {detail_rows}
      </table>
      <p style="margin:16px 0 0;font-size:13px;color:#6b7280">
        Log in to <a href="{settings.app_base_url}" style="color:#2563eb">MYXON Dashboard</a>
        to acknowledge this alarm.
      </p>
    </div>
    <div style="background:#f8fafc;padding:12px 24px;font-size:11px;color:#94a3b8">
      MYXON Platform — automated notification, do not reply.
    </div>
  </div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.smtp_from
    msg["To"]      = recipient_email
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


async def _send_email(device: Device, alarm: Alarm, contact: NotificationContact) -> None:
    """Send email to one contact. Logs errors, never raises."""
    if not settings.smtp_host:
        return
    try:
        msg = _build_email(device, alarm, contact.email)
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=not settings.smtp_use_tls,
            start_tls=settings.smtp_use_tls,
        )
        logger.info(
            "Email sent: to=%s device=%s alarm_code=%d severity=%s",
            contact.email, device.serial_number, alarm.code, alarm.severity,
        )
    except Exception as exc:
        logger.error("Email failed to %s: %s", contact.email, exc)


# ── SMS text builder ──────────────────────────────────────────────────────────

def build_sms_text(device: Device, alarm: Alarm) -> str:
    """
    Build a concise SMS message (≤ 160 chars for single GSM segment).

    Example:
      ALARM [Farm Noord / Ventilator 2] Temperature too high (code 42)
    """
    severity = _SEVERITY_LABEL.get(alarm.severity, alarm.severity.upper())
    device_label = device.name or device.serial_number
    msg = alarm.message or f"Alarm code {alarm.code}"
    text = f"{severity} [{device_label}] {msg}"

    # Truncate to 155 chars + "…" to stay within single SMS segment
    if len(text) > 155:
        text = text[:154] + "…"
    return text


# ── Public API ────────────────────────────────────────────────────────────────

async def route_alarm_notifications(
    db: AsyncSession,
    device: Device,
    alarm: Alarm,
) -> list[dict]:
    """
    Route notifications for a new active alarm.

    - Sends email to all matched email-channel contacts immediately.
    - Returns list of {to, message} dicts for SMS (delivered via heartbeat).

    Never raises — all errors are logged internally.
    """
    if not settings.notify_on_alarm:
        return []

    if alarm.state != AlarmState.ACTIVE:
        return []

    if alarm.severity not in (AlarmSeverity.ALARM, AlarmSeverity.WARNING):
        return []

    email_contacts, sms_contacts = await _collect_contacts(db, device, alarm)

    # Send emails immediately
    for contact in email_contacts:
        await _send_email(device, alarm, contact)

    # Build SMS payloads (to be included in next heartbeat response)
    sms_text = build_sms_text(device, alarm)
    sms_payloads = [
        {"to": c.phone, "message": sms_text}
        for c in sms_contacts
        if c.phone
    ]

    if sms_payloads:
        logger.info(
            "Queued %d SMS for device=%s alarm_code=%d",
            len(sms_payloads), device.serial_number, alarm.code,
        )

    return sms_payloads


async def get_pending_sms_for_device(
    db: AsyncSession,
    device: Device,
) -> list[dict]:
    """
    Collect all pending SMS for a device (alarms with sms_sent_at=None).
    Marks them as sent atomically.

    Called from the heartbeat endpoint — inserts the list into the response
    so the agent can deliver them via the local GSM modem.
    """
    from app.models.alarm import Alarm  # avoid circular at module level

    result = await db.execute(
        select(Alarm).where(
            Alarm.device_id == device.id,
            Alarm.state == AlarmState.ACTIVE,
            Alarm.sms_sent_at.is_(None),
            Alarm.severity.in_([AlarmSeverity.ALARM, AlarmSeverity.WARNING]),
        )
    )
    pending = result.scalars().all()

    if not pending:
        return []

    # Collect SMS payloads for all pending alarms
    all_sms: list[dict] = []
    now = datetime.now(timezone.utc)

    for alarm in pending:
        _, sms_contacts = await _collect_contacts(db, device, alarm)
        sms_text = build_sms_text(device, alarm)
        for c in sms_contacts:
            if c.phone:
                all_sms.append({"to": c.phone, "message": sms_text})
        # Mark as sent regardless — even if no contacts, avoid re-processing
        alarm.sms_sent_at = now

    return all_sms
