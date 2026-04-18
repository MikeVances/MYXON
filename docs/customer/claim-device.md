# Claim a Device

Claiming a device transfers ownership to your account. After claiming, the device appears in your dashboard and you can open remote access sessions.

## Method 1 — Scan the QR code (recommended)

The simplest way is to scan the QR label printed by your dealer.

1. **Point your phone camera** at the QR code on the device or its packaging
2. Tap the notification that appears — it opens your browser
3. If you're not logged in, you'll be redirected to the login page first — the QR destination is saved automatically and you'll be sent there after login
4. The **Activate Device** wizard opens with the serial number already filled in

> **Screenshot:** *Mobile browser showing the Activate Device wizard, step 2 "Confirm device" with serial number MX-2026-00001, model shown, status "✓ Available". Two buttons: "Back" and "Continue →".*

## Method 2 — Enter serial number manually

1. Go to **Devices** → click **Activate Device** (or navigate to `/claim` directly)
2. Type the serial number from the device label
3. Press Enter or click **Find Device →**

> **Screenshot:** *Step 1 "Enter Serial Number" — white card with "Serial Number" label, monospace input field with placeholder "e.g. MX-2024-00001", and "Find Device →" button.*

## Claim wizard steps

### Step 1 — Enter serial

Type or auto-fill the serial number. The system looks up the device and verifies it's available for claiming.

**Possible errors:**

| Error | Cause | Solution |
|-------|-------|---------|
| Device not found | Wrong serial or device not registered | Check the label, contact your dealer |
| Device already claimed | Someone else claimed it | Contact your dealer |
| State is not `ready_for_transfer` | Device is blocked or already consumed | Contact your dealer |

### Step 2 — Confirm device

Review the device details:
- **Serial number** — verify it matches the label
- **Model** — the device type registered by your dealer
- **Status** — must be "✓ Available" to continue

> **Screenshot:** *Device details card showing Serial: MX-2026-00001, Model: Orange Pi 5, Status: "✓ Available" in green. Back and Continue buttons.*

### Step 3 — Assign location

Choose which of your sites to assign this device to. You can also skip and assign later.

> **Screenshot:** *Site selection list: "Skip for now" (selected, blue border), "Stable A — Farmroad 12", "Greenhouse 1". Scroll for more.*

### Step 4 — Done

> **Screenshot:** *Success screen: green checkmark icon, "Device Activated!" heading, message text, small note about tunnel connection. Two buttons: "All Devices" and "Open Dashboard →".*

::: info Tunnel connection delay
After claiming, the device needs a moment to establish its tunnel connection. If the device shows "offline" immediately after claiming, wait 30 seconds and refresh — it should come online.
:::
