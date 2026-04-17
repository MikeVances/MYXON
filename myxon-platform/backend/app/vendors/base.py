"""
Base vendor adapter interface.

All vendor adapters must implement this interface so the platform core
can interact with devices through a uniform API regardless of protocol.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class TransportType(str, Enum):
    CLOUD_API = "cloud_api"       # HTTPS-based cloud control
    WEB_VNC = "web_vnc"           # Browser-accessible VNC/HTTP
    TCP_DIRECT = "tcp_direct"     # Raw TCP binary protocol
    MQTT = "mqtt"                 # MQTT-based IoT protocol


class SessionType(str, Enum):
    SCREEN = "screen"             # Interactive HMI screen capture
    KEY_INPUT = "key_input"       # Send key/button events
    CONFIG_READ = "config_read"   # Read device configuration
    ALARM_READ = "alarm_read"     # Read alarm/status
    WEB_ACCESS = "web_access"     # HTTP/VNC web tunnel


@dataclass
class DeviceCapability:
    """A capability that a device exposes through its vendor adapter."""
    id: str                       # e.g. "web-hmi", "vnc-plc", "screen-orion"
    name: str                     # Human-readable name
    protocol: str                 # "http", "vnc", "tcp-direct"
    transport: TransportType
    session_types: list[SessionType]
    metadata: dict[str, Any] | None = None  # Vendor-specific extra data


@dataclass
class DeviceFamily:
    """Device family profile for UI/protocol dispatch."""
    family: str                   # e.g. "orion", "cygnus", "sirius"
    screen_width: int
    screen_height: int
    decoder: str                  # Decoder identifier
    key_map: dict[str, int]       # UI key name -> protocol key code
    brandings: list[str]          # Supported brand themes


@dataclass
class ConnectionResult:
    """Result of a vendor adapter connection attempt."""
    success: bool
    session_id: str | None = None
    access_url: str | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


class BaseVendorAdapter(ABC):
    """
    Abstract base class for vendor protocol adapters.

    Each vendor (HOTRACO, Siemens, etc.) implements this interface
    to integrate their devices into the MYXON platform.
    """

    @property
    @abstractmethod
    def vendor_id(self) -> str:
        """Unique vendor identifier (e.g. 'hotraco', 'siemens')."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable vendor name."""
        ...

    @property
    @abstractmethod
    def supported_transports(self) -> list[TransportType]:
        """List of transport types this adapter supports."""
        ...

    @abstractmethod
    def get_device_families(self) -> list[DeviceFamily]:
        """Return all device families this vendor supports."""
        ...

    @abstractmethod
    def get_capabilities(self, family: str, branding: str | None = None) -> list[DeviceCapability]:
        """Return capabilities for a specific device family."""
        ...

    @abstractmethod
    async def connect(
        self,
        host: str,
        port: int,
        credentials: dict[str, str],
        device_address: str | None = None,
    ) -> ConnectionResult:
        """
        Establish a connection to a device through this vendor's protocol.

        For cloud-mediated connections, host/port point to the mediation server.
        For direct connections, they point to the device/gateway.
        """
        ...

    @abstractmethod
    async def disconnect(self, session_id: str) -> None:
        """Disconnect an active session."""
        ...

    @abstractmethod
    async def health_check(self, host: str, port: int) -> bool:
        """Check if the vendor's transport endpoint is reachable."""
        ...
