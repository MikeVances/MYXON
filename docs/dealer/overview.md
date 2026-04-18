# Dealer Portal — Overview

The Dealer Portal is the workspace for **integrators, resellers, and OEM manufacturers**. It gives you everything you need to provision devices and hand them off to customers.

## Access

The Dealer Portal is available at `/dealer` after logging in with a dealer account. If you don't see it in the navigation, contact your MYXON administrator to check your account role.

> **Screenshot:** *Header with "Dealer Portal" badge and three tabs: Devices · Activation Codes · Customers*

## Portal tabs

### Devices tab

Register new device serial numbers and monitor the connectivity status of your entire fleet — including devices that have already been claimed by customers.

→ [Register devices (Scenario 1)](/dealer/register-devices)

### Activation Codes tab

Generate one-time activation codes for OEM devices. Each code provisions one device when it first connects to the internet.

→ [Activation codes (Scenario 2)](/dealer/activation-codes)

### Customers tab

Create invite links for new customer accounts. Customers use these links to register their own login without you needing to create credentials for them.

→ [Invite customers](/dealer/invite-customers)

## What dealers can see

Dealers have **limited visibility** by design:

| What dealers CAN see | What dealers CANNOT see |
|---------------------|------------------------|
| Device serial number | Customer name or email |
| Connectivity status (online/offline) | Alarm history |
| Last seen timestamp | HMI screen content |
| Claim state (claimed/unclaimed) | Any customer data |

This separation protects customer privacy while giving dealers the operational insight they need — for example, to know if a device was ever powered on, or if it dropped offline.
