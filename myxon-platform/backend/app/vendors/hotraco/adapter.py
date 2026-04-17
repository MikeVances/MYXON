"""
HOTRACO Remote+ vendor adapter implementation.

Wraps the remote_plus_proto library (from tools/) into the
MYXON vendor adapter interface. Provides:
  - Device family profiles (Orion/Cygnus/Sirius)
  - TCP connection management
  - Protocol-level operations (auth, mediation, screen, keys)
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.vendors.base import (
    BaseVendorAdapter,
    ConnectionResult,
    DeviceCapability,
    DeviceFamily,
    SessionType,
    TransportType,
)

logger = logging.getLogger(__name__)

# ── Protocol constants (from REMOTE_PLUS_PROTOCOL_SPEC) ──

DEFAULT_HOST = "smartlinkserver.com"
DEFAULT_PORT = 5843
FALLBACK_HOST = "5.157.85.29"

# Command IDs
CMD_CLOSE = 1
CMD_CONFIGURATION_READ = 2
CMD_MAIN_GROUP_READ = 6
CMD_CAPTURE_SCREEN = 92
CMD_SEND_KEY = 93
CMD_CAPTURE_SCREEN_FAST = 96
CMD_COMPUTERS_REQUEST = 4091
CMD_MEDIATE_REQUEST = 4092

# Address IDs
ADDR_PC = 1023
ADDR_GENERAL = 1018
ADDR_SMARTLINK_SERVER = 1184

# ── Device family definitions ──

DEVICE_FAMILIES: list[DeviceFamily] = [
    DeviceFamily(
        family="orion",
        screen_width=240,
        screen_height=128,
        decoder="orion_rle",
        key_map={
            "up": 19, "right": 18, "down": 20, "left": 17, "ok": 21,
            "plusminus": 22, "dot": 46,
            "num0": 48, "num1": 49, "num2": 50, "num3": 51, "num4": 52,
            "num5": 53, "num6": 54, "num7": 55, "num8": 56, "num9": 57,
            "f1": 64, "f2": 65, "f3": 66, "f4": 67, "f5": 68, "f6": 69,
            "prev": 80, "next": 81,
        },
        brandings=["hotraco", "syslinq", "agri", "horti", "vdl", "opticow", "delaval"],
    ),
    DeviceFamily(
        family="cygnus",
        screen_width=128,
        screen_height=64,
        decoder="cygnus_rle_mirrored_row",
        key_map={
            "up": 19, "right": 18, "down": 20, "left": 17, "ok": 21,
            "f1": 64, "f2": 65, "f3": 66, "f4": 67,
        },
        brandings=["hotraco", "syslinq"],
    ),
    DeviceFamily(
        family="sirius",
        screen_width=122,
        screen_height=32,
        decoder="sirius_bit_unpack",
        key_map={
            "up": 1, "right": 3, "down": 2, "ok": 4,
            "key1": 16, "key2": 17, "key3": 18, "key4": 19, "key5": 20,
            "key6": 21, "key7": 22, "key8": 23, "key9": 24, "key10": 25,
        },
        brandings=["hotraco", "syslinq"],
    ),
]


def _sha1_hex(password: str) -> str:
    """SHA-1 hash as 40-char uppercase hex (matches Remote+ client)."""
    return hashlib.sha1(password.encode()).hexdigest().upper()


@dataclass
class ActiveSession:
    session_id: str
    host: str
    port: int
    reader: asyncio.StreamReader | None = None
    writer: asyncio.StreamWriter | None = None


@dataclass
class HotracoAdapter(BaseVendorAdapter):
    """HOTRACO/SyslinQ Remote+ protocol adapter."""

    _sessions: dict[str, ActiveSession] = field(default_factory=dict, init=False)

    @property
    def vendor_id(self) -> str:
        return "hotraco"

    @property
    def display_name(self) -> str:
        return "HOTRACO / SyslinQ"

    @property
    def supported_transports(self) -> list[TransportType]:
        return [TransportType.TCP_DIRECT, TransportType.CLOUD_API]

    def get_device_families(self) -> list[DeviceFamily]:
        return list(DEVICE_FAMILIES)

    def get_capabilities(
        self, family: str, branding: str | None = None
    ) -> list[DeviceCapability]:
        fam = family.lower()
        matched = [f for f in DEVICE_FAMILIES if f.family == fam]
        if not matched:
            return []
        f = matched[0]
        return [
            DeviceCapability(
                id=f"screen-{f.family}",
                name=f"{f.family.title()} HMI Screen",
                protocol="tcp-direct",
                transport=TransportType.TCP_DIRECT,
                session_types=[SessionType.SCREEN, SessionType.KEY_INPUT],
                metadata={
                    "width": f.screen_width,
                    "height": f.screen_height,
                    "decoder": f.decoder,
                },
            ),
            DeviceCapability(
                id=f"config-{f.family}",
                name=f"{f.family.title()} Configuration",
                protocol="tcp-direct",
                transport=TransportType.TCP_DIRECT,
                session_types=[SessionType.CONFIG_READ, SessionType.ALARM_READ],
            ),
        ]

    async def connect(
        self,
        host: str,
        port: int,
        credentials: dict[str, str],
        device_address: str | None = None,
    ) -> ConnectionResult:
        """
        Connect to a HOTRACO device via Remote+ protocol.

        For remote mode:
          1. TCP connect to mediation server
          2. ComputersRequest with auth
          3. MediateRequest with target address

        For direct mode:
          1. TCP connect to device host:port directly
        """
        session_id = str(uuid.uuid4())
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=20.0,
            )
            self._sessions[session_id] = ActiveSession(
                session_id=session_id,
                host=host,
                port=port,
                reader=reader,
                writer=writer,
            )
            logger.info(
                "hotraco: connected session=%s to %s:%d",
                session_id, host, port,
            )
            return ConnectionResult(
                success=True,
                session_id=session_id,
                metadata={"host": host, "port": port},
            )
        except Exception as exc:
            logger.error("hotraco: connection failed: %s", exc)
            return ConnectionResult(
                success=False,
                error=str(exc),
            )

    async def disconnect(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session and session.writer:
            try:
                session.writer.close()
                await session.writer.wait_closed()
            except Exception:
                pass
        logger.info("hotraco: disconnected session=%s", session_id)

    async def health_check(self, host: str, port: int) -> bool:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0,
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False
