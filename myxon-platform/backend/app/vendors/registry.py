"""
Vendor adapter registry.

Manages registration and lookup of vendor adapters.
The platform core uses this to dispatch device operations
to the correct protocol adapter based on device.vendor_id.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.vendors.base import BaseVendorAdapter

logger = logging.getLogger(__name__)

_registry: dict[str, BaseVendorAdapter] = {}


def register_adapter(adapter: BaseVendorAdapter) -> None:
    """Register a vendor adapter in the global registry."""
    _registry[adapter.vendor_id] = adapter
    logger.info(
        "Registered vendor adapter: %s (%s), transports=%s",
        adapter.vendor_id,
        adapter.display_name,
        [t.value for t in adapter.supported_transports],
    )


def get_adapter(vendor_id: str) -> BaseVendorAdapter | None:
    """Look up a vendor adapter by ID."""
    return _registry.get(vendor_id)


def list_adapters() -> list[BaseVendorAdapter]:
    """Return all registered vendor adapters."""
    return list(_registry.values())


def init_default_adapters() -> None:
    """Register all built-in vendor adapters."""
    from app.vendors.hotraco.adapter import HotracoAdapter

    register_adapter(HotracoAdapter())
    logger.info("Vendor adapter registry initialized with %d adapters", len(_registry))
