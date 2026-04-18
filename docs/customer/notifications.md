# Alarm Notifications

MYXON automatically notifies the right people when an alarm fires — by **email** and/or **SMS via GSM modem** — without requiring a manual check of the dashboard.

## How it works

```
Controller sends alarm
    │
    ▼
MYXON collects & stores alarm
    │
    ├─► Email to matched contacts   (sent immediately via SMTP)
    └─► SMS via device GSM modem    (delivered within one heartbeat, ~15 s)
```

Notifications are routed by **rules**. Each rule links a contact person to a scope (the whole tenant, one site, or a specific device) and filters by alarm severity and category.

## Contacts

A **contact** is a person who can receive notifications. One contact can appear in many rules.

| Field | Description |
|-------|-------------|
| **Name** | Display name — "Ivan Petrov (Engineer)" |
| **Phone** | E.164 format: `+31612345678` — used for SMS |
| **Email** | Used for email notifications |
| **Channels** | Which methods to use: SMS, Email, or both |
| **Active** | Inactive contacts never receive notifications |

::: tip E.164 phone format
Always include the country code: `+31` (Netherlands), `+49` (Germany), `+7` (Russia).
No spaces or dashes — just `+` and digits.
:::

### Add a contact

Go to **Settings → Notifications → Contacts** and click **Add contact**.

> **Screenshot:** *Contacts tab with two entries: "Ivan Petrov (Engineer)" with phone and both channels, and "Maria Smith (Manager)" with phone, SMS channel only.*

## Rules

A **rule** defines: *when* should *this contact* be notified?

| Field | Options | Description |
|-------|---------|-------------|
| **Contact** | from your contacts list | Who receives the notification |
| **Scope** | Tenant / Site / Device | Which devices trigger this rule |
| **Min severity** | Warning+ / Alarm only | Alarm always fires; Warning+ also fires on warnings |
| **Categories** | empty = all, or select specific | e.g. only `temperature` and `power` |
| **Active** | on/off | Disable temporarily without deleting |

### Scope explained

```
Tenant-wide rule   → fires for ALL devices in your organisation
Site rule          → fires for ALL devices at one farm/location
Device rule        → fires for ONE specific device
```

Multiple rules can match the same alarm — all matched contacts receive the notification, with duplicates removed.

### Example setup: two-person farm team

| Rule | Contact | Scope | Severity | Categories |
|------|---------|-------|----------|------------|
| 1 | Ivan (Engineer) | Site: Farm Noord | Warning+ | all |
| 2 | Maria (Manager) | Tenant-wide | Alarm only | power, communication |
| 3 | Support team | Tenant-wide | Alarm only | all |

With this setup:
- Ivan gets **all alarms and warnings** from Farm Noord by SMS and email
- Maria gets **critical-only** (power and comms failures) from all farms
- Support gets **all critical alarms** across the entire tenant

### Add a rule

Go to **Settings → Notifications → Rules** and click **Add rule**.

> **Screenshot:** *Rules tab showing three rules with scope badges (Tenant-wide, Site, Device), severity chips (Warning+ in amber, Alarm only in red), and edit/delete buttons.*

## SMS delivery — how the GSM modem is used

SMS messages are delivered via the **local GSM modem on the Orange Pi**, not through an internet gateway. This means:

- SMS works even when the internet connection is degraded
- No third-party SMS account or subscription needed
- Delivery latency ≈ heartbeat interval (default 15 seconds)

```
Backend queues SMS in heartbeat response
    │
    └─► Agent receives it on next heartbeat (~15s)
            │
            └─► Agent sends via mmcli → GSM modem → SMS network
```

::: info No modem, no SMS
If the device was installed without `--backup-modem`, the GSM modem is not configured.
In that case, only email notifications will be delivered.
Check with your OEM or installer if SMS is required.
:::

## Email notifications

Email is sent directly from the MYXON server when the alarm fires. Configuration is done by the platform administrator in the server `.env` file:

```ini
SMTP_HOST=smtp.yourcompany.com
SMTP_PORT=587
SMTP_USER=noreply@yourcompany.com
SMTP_PASSWORD=...
SMTP_FROM=noreply@yourcompany.com
```

Leave `SMTP_HOST` empty to disable email globally (SMS-only mode).

## Alarm severity reference

| Severity | Colour | Typical cause |
|----------|--------|---------------|
| **Alarm** | Red | Critical failure — requires immediate action |
| **Warning** | Amber | Abnormal condition — monitor closely |

Off / Suppressed / None severities do not trigger notifications.

## Alarm categories

Categories classify the alarm source. Use them in rules to filter notifications:

| Category | Examples |
|----------|---------|
| `temperature` | Temp too high/low, frost warning |
| `humidity` | RH out of range |
| `co2` | CO₂ concentration alarm |
| `ventilation` | Fan failure, airflow blocked |
| `pressure` | Pressure alarm |
| `weather` | Wind, rain, storm sensors |
| `communication` | Connection loss, network timeout |
| `power` | Voltage failure, UPS, battery |
| `sensor` | Probe failure, bad reading |
| `general` | Everything else |

::: tip Rule of thumb
Engineers who respond on-site → subscribe to all categories at "Warning+".
Managers who escalate → subscribe to `power` and `communication` at "Alarm only".
:::
