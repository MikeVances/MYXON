"""
Vendor adapter layer.

MYXON is a multi-vendor platform. Each device manufacturer/protocol
is encapsulated in a separate adapter module under this package.

Current adapters:
  - hotraco: HOTRACO/SyslinQ Remote+ protocol (TCP, port 5843)

Architecture:
  - Each adapter exposes a standard interface (BaseVendorAdapter)
  - The platform core dispatches to adapters based on device.vendor_id
  - Adapters handle transport, framing, auth, and device-specific logic
"""
