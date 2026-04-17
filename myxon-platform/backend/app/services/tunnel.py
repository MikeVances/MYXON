"""
Tunnel port allocator.

Assigns unique FRPS tunnel ports to devices from a configurable range
(default 10000-10100). Ports are tracked via Device.tunnel_port in the DB.

The allocator is called during agent registration and returns the port
that the edge agent should use in its FRPC configuration.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.device import Device

logger = logging.getLogger(__name__)


async def allocate_tunnel_port(db: AsyncSession, device: Device) -> int | None:
    """
    Allocate a tunnel port for a device.

    If the device already has a port assigned, return it.
    Otherwise, find the next available port in the range.
    Returns None if no ports are available.
    """
    # Already allocated
    if device.tunnel_port is not None:
        return device.tunnel_port

    port_min = settings.tunnel_port_range_start
    port_max = settings.tunnel_port_range_end

    # Get all currently allocated ports
    result = await db.execute(
        select(Device.tunnel_port).where(Device.tunnel_port.is_not(None))
    )
    used_ports = {row[0] for row in result.all()}

    # Find first available port
    for port in range(port_min, port_max + 1):
        if port not in used_ports:
            device.tunnel_port = port
            device.tunnel_subdomain = f"dev-{device.serial_number.lower()}"
            logger.info(
                "Allocated tunnel port %d for device %s",
                port, device.serial_number,
            )
            return port

    logger.error(
        "No tunnel ports available in range %d-%d (%d used)",
        port_min, port_max, len(used_ports),
    )
    return None


async def release_tunnel_port(db: AsyncSession, device: Device) -> None:
    """Release a device's tunnel port back to the pool."""
    if device.tunnel_port is None:
        return
    old_port = device.tunnel_port
    device.tunnel_port = None
    device.tunnel_subdomain = None
    logger.info(
        "Released tunnel port %d from device %s",
        old_port, device.serial_number,
    )
