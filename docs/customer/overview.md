# Customer Portal — Overview

The Customer Portal is where farm operators and their staff **monitor and remotely access** controllers. You see alarms, open HMI sessions, and manage who has access to which site.

## Navigation

After logging in, you land on the **Locations** page. The main sections are:

| Page | Path | Purpose |
|------|------|---------|
| Locations | `/locations` | Overview of all your sites and their devices |
| Devices | `/devices` | Full device list with filtering by site |
| Device Dashboard | `/devices/{id}` | Individual device detail, HMI, alarms, event log |
| Activate Device | `/claim` | Claim a new device by serial or QR code |

> **Screenshot:** *Locations page showing two farm sites: "Stable A" (3 devices) and "Greenhouse 1" (1 device). Search bar at top. Each site card shows address and device count.*

## First-time setup

### 1. Register your account

Your dealer sends you an invite link by email or message. Open the link, choose a password, and your account is ready. No app download needed.

### 2. Activate your device

Scan the QR code attached to your MYXON device with your phone camera. This opens the claim wizard automatically.

→ [Claim a device (QR code)](/customer/claim-device)

### 3. Assign to a location

During activation, you can assign the device to a site (e.g. "Stable A"). You can also skip this and assign it later from the device dashboard.

→ [Locations](/customer/locations)

## User roles

Customer accounts have four roles:

| Role | Can do |
|------|--------|
| **Admin** | Everything + manage users and access policies |
| **Engineer** | Open HMI/VNC sessions, view and acknowledge alarms |
| **Viewer** | View alarms only (read-only) |

Your dealer creates your first admin account. You can then invite colleagues yourself.
