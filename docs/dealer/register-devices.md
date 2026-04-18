# Register Devices (Scenario 1)

This workflow is for the **MYXON Box** model: you sell your own hardware with the agent pre-installed, and the customer activates it by scanning a QR code.

## Step 1 — Register the serial number

1. Open **Dealer Portal → Devices** tab
2. Enter the serial number in the **Serial Number** field (e.g. `MX-2026-00001`)
3. Optionally enter a **Model** name
4. Click **+ Register**

> **Screenshot:** *"Register New Device" form with serial number field, model field, and Register button. Below: helper text "After registering, print the QR code and attach it to the device."*

::: tip Serial number format
Use a consistent format across your product line. Recommended: `MX-{YEAR}-{5-digit-seq}`, e.g. `MX-2026-00001`. The format is flexible — any alphanumeric string up to 100 characters works.
:::

## Step 2 — Print the QR label

After registration, a QR code panel appears immediately below the form:

> **Screenshot:** *QR code panel: large QR code on the left, device serial number below it. On the right: "Device registered!" message, the encoded URL, "Print QR Label" button, and "Dismiss" button.*

The QR code encodes the URL:
```
https://your-domain.com/claim?sn=MX-2026-00001
```

Click **Print QR Label** to open the browser print dialog. The QR and serial number are formatted for label printing. Attach the label to the device or its packaging.

::: warning Before shipping
Make sure the Orange Pi is running the MYXON agent and has connected to the server at least once before the device leaves your facility. Verify its status shows **online** in the device list.
:::

## Step 3 — Ship the device

Ship the device with the QR label attached. The customer activates it by scanning the QR code — no configuration needed on their end.

→ Customer activation flow: [Claim a device](/customer/claim-device)

## Device list

After registration, all your devices appear in the table:

> **Screenshot:** *Device table with columns: Serial, Model, Connectivity (badge: online/offline/pre_registered), Activation (badge: Unclaimed/Activated), Last seen timestamp.*

| Column | What it shows |
|--------|--------------|
| **Connectivity** | Current tunnel status: `online` / `offline` / `pre_registered` |
| **Activation** | Whether a customer has claimed it: `Unclaimed` / `Activated` |
| **Last seen** | Timestamp of the last heartbeat from the agent |

::: info Unclaimed devices stay in your list
When a customer claims a device, it becomes "Activated" in your view. The device remains in your dealer list forever — you always retain fleet visibility.
:::
