# Fleet Monitoring

As a dealer, you have permanent visibility into the connectivity status of every device you ever registered — regardless of which customer owns it now. This is your **fleet dashboard**.

## Why dealers see the fleet

When you sell a device, you want to know:
- Is the device actually powered on and online?
- Did the customer ever connect it?
- Has it gone dark (potential hardware failure)?

MYXON retains the `dealer_id` link even after a customer claims a device. You see connectivity metrics, but **never** customer data (alarm history, HMI content, configurations).

## Reading the device table

> **Screenshot:** *Dealer device list with 5 devices. Three are online (green dot), one is offline (grey), one is pre_registered (blue badge). Columns: Serial, Model, Connectivity, Activation, Last seen.*

### Status combinations

| Connectivity | Activation | Meaning |
|-------------|-----------|---------|
| `pre_registered` | Unclaimed | Device in DB but agent never connected. Not shipped yet, or powered off. |
| `offline` | Unclaimed | Agent connected at some point but device is now unreachable and not yet claimed. |
| `online` | Unclaimed | Agent running, customer hasn't scanned QR yet. |
| `offline` | Activated | Customer claimed it, but device is currently offline (powered down, network issue). |
| `online` | Activated | **Healthy** — device in use. |

### What "Dark" looks like

A device that went `online` once but hasn't sent a heartbeat in days likely means:
- Power failure at the farm
- Network cut
- Hardware problem

Use the **Last seen** timestamp to identify dark devices. If a device has never been online at all (`pre_registered`), it may still be in your warehouse or the customer hasn't powered it on yet.

::: tip Analytics use case
Track the ratio of "ever connected" vs "pre_registered" devices across your fleet to understand customer activation rates. A high "pre_registered" count weeks after shipment may indicate installation issues worth investigating.
:::
