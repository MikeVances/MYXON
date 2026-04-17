"""
Vendor adapter API — exposes vendor/device-family metadata to the portal.

Used by the frontend to render family-specific UI (screen decoders,
key maps, branding) and by the session layer to dispatch connections.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.vendors.registry import get_adapter, list_adapters

router = APIRouter(prefix="/api/v0/vendors", tags=["vendors"])


@router.get("")
async def list_vendors():
    """List all registered vendor adapters."""
    return [
        {
            "vendor_id": a.vendor_id,
            "display_name": a.display_name,
            "transports": [t.value for t in a.supported_transports],
            "families": [
                {
                    "family": f.family,
                    "screen_width": f.screen_width,
                    "screen_height": f.screen_height,
                    "decoder": f.decoder,
                    "brandings": f.brandings,
                    "key_count": len(f.key_map),
                }
                for f in a.get_device_families()
            ],
        }
        for a in list_adapters()
    ]


@router.get("/{vendor_id}/families/{family}/keys")
async def get_key_map(vendor_id: str, family: str):
    """Get the key map for a specific device family."""
    adapter = get_adapter(vendor_id)
    if adapter is None:
        return {"error": f"Unknown vendor: {vendor_id}"}
    for f in adapter.get_device_families():
        if f.family == family.lower():
            return {
                "vendor_id": vendor_id,
                "family": f.family,
                "keys": f.key_map,
            }
    return {"error": f"Unknown family: {family}"}


@router.get("/{vendor_id}/families/{family}/capabilities")
async def get_capabilities(vendor_id: str, family: str):
    """Get capabilities for a device family."""
    adapter = get_adapter(vendor_id)
    if adapter is None:
        return {"error": f"Unknown vendor: {vendor_id}"}
    caps = adapter.get_capabilities(family)
    return [
        {
            "id": c.id,
            "name": c.name,
            "protocol": c.protocol,
            "transport": c.transport.value,
            "session_types": [s.value for s in c.session_types],
            "metadata": c.metadata,
        }
        for c in caps
    ]
