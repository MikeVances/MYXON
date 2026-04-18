# Alarms

MYXON collects alarm events from connected controllers and displays them in a unified alarm panel. The panel is visible on every device dashboard and can be filtered by severity.

## Alarm states

```
  ACTIVE ──► ACKNOWLEDGED ──► CLEARED
    │                            │
    └── auto-clears if controller ──┘
        sends clear signal
```

| State | Meaning | Color |
|-------|---------|-------|
| **Active** | Alarm is firing right now | Red |
| **Acknowledged** | A user has seen and confirmed it | Amber |
| **Cleared** | Alarm condition resolved | Green |

## Alarm panel

> **Screenshot:** *Alarm panel on device dashboard: table with columns Severity (color-coded badge), Code, Message, Triggered, Acknowledged, and Acknowledge button. Three rows: one CRITICAL (red), one WARNING (amber, acknowledged), one INFO (grey, cleared).*

### Columns

| Column | Description |
|--------|------------|
| **Severity** | `critical` / `warning` / `info` |
| **Code** | Numeric alarm code from the controller |
| **Message** | Human-readable description (if provided by vendor) |
| **Triggered** | When the alarm first fired |
| **Acknowledged** | Timestamp + who acknowledged it (empty if not yet) |

## Acknowledge an alarm

Click **Acknowledge** next to an active or unacknowledged alarm. This marks it as seen and sets the `acknowledged_at` timestamp with your user ID.

::: warning Access policy required
Acknowledging alarms requires the `allow_alarms_acknowledge` permission in your access policy. If the Acknowledge button is not visible, your role or site policy restricts this action. Contact your admin.
:::

## Severity filter

The alarm panel shows all severities by default. If your access policy has a **severity filter** set (e.g. "warning and above"), info-level alarms are automatically hidden for your user.

| Filter setting | What you see |
|----------------|-------------|
| All | Critical + Warning + Info |
| Warning and above | Critical + Warning |
| Critical only | Critical only |

## Alarm history

The alarm panel on the device dashboard shows the **current and recent** alarms. For historical alarm data and cross-device reporting, the audit log provides a full event trail.

## Notifications

MYXON can automatically notify your team when an alarm fires — by **email** or **SMS via GSM modem** — without anyone having to watch the dashboard.

Notifications are configured in **Settings → Notifications**:
- Add **contacts** (engineers, managers) with their phone and/or email
- Add **rules** to define who gets notified for which devices and at which severity

→ [Notification contacts & rules](/customer/notifications)
