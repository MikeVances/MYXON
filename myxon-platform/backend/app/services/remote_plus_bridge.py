"""
Remote+ TCP ↔ WebSocket bridge.

Bridges the HOTRACO Remote+ binary TCP protocol to WebSocket so the
browser can render device HMI screens and send key events in real time.

Data flow:
  Browser (WS JSON) ↔ this bridge ↔ async TCP socket ↔ FRPS tunnel ↔ device

WebSocket message format (client → server):
  {"type": "screen_request", "mode": 0}          # 0=full, 1=update
  {"type": "send_key", "key_code": 19}
  {"type": "config_read"}
  {"type": "main_group_read"}
  {"type": "close"}

WebSocket message format (server → client):
  {"type": "screen_data", "hex": "...", "command": 96}
  {"type": "config", "password": 0, "devices": [...]}
  {"type": "main_group", "code": 0, "alarm_raw": 0}
  {"type": "error", "message": "..."}
  {"type": "connected"}
  {"type": "closed"}

Protocol re-implementation in async Python (based on tools/remote_plus_proto).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Protocol constants ──

START_MARKER = "@"
END_MARKER = "*"
TERMINATOR = "\r"


class CommandId:
    NONE = 0
    CLOSE = 1
    CONFIGURATION_READ = 2
    MAIN_GROUP_READ = 6
    CAPTURE_SCREEN = 92
    SEND_KEY = 93
    CAPTURE_SCREEN_FAST = 96
    MAIN_GROUP_CHANGED = 100
    COMPUTERS_REQUEST = 4091
    MEDIATE_REQUEST = 4092


class SubCmd:
    BEGIN = 0
    REPEAT = 1
    NEXT = 2
    END = 5


ADDR_PC = 1023


# ── Frame encoding/decoding (async-compatible) ──

def _hex_int(value: int, width: int = 2) -> str:
    return format(value, "X").zfill(width)


def _xor_checksum(text: str) -> int:
    v = 0
    for ch in text:
        v ^= ord(ch)
    return v


def build_frame(
    dest: int, src: int, cmd: int,
    payload_hex: str = "", sub: int = 0, block: int = 0,
) -> bytes:
    base = (
        START_MARKER
        + _hex_int(dest, 3)
        + _hex_int(src, 3)
        + _hex_int(cmd, 3)
        + _hex_int(sub, 1)
        + _hex_int(block, 2)
        + _hex_int(len(payload_hex) // 2, 2)
        + payload_hex
    )
    crc = _hex_int(_xor_checksum(base), 2)
    frame_str = base + crc + END_MARKER + TERMINATOR
    return frame_str.encode("ascii")


def parse_frame(raw: str) -> dict | None:
    if not raw.startswith(START_MARKER) or not raw.endswith(END_MARKER + TERMINATOR):
        return None
    if len(raw) < 20:
        return None
    try:
        payload_len = int(raw[13:15], 16)
        payload_chars = payload_len * 2
        payload_end = 15 + payload_chars
        payload_hex = raw[15:payload_end]
        crc = int(raw[payload_end:payload_end + 2], 16)
        body = raw[:payload_end]
        if _xor_checksum(body) != crc:
            return None
        return {
            "dest": int(raw[1:4], 16),
            "src": int(raw[4:7], 16),
            "cmd": int(raw[7:10], 16),
            "sub": int(raw[10:11], 16),
            "block": int(raw[11:13], 16),
            "payload_hex": payload_hex,
        }
    except (ValueError, IndexError):
        return None


# ── Stream reassembler ──

class StreamReassembler:
    """Collects TCP chunks and yields complete frames delimited by \\r."""

    def __init__(self):
        self._buf = ""

    def feed(self, chunk: str) -> list[str]:
        self._buf += chunk
        frames = []
        while TERMINATOR in self._buf:
            idx = self._buf.index(TERMINATOR)
            candidate = self._buf[:idx + 1]
            self._buf = self._buf[idx + 1:]
            if candidate.startswith(START_MARKER):
                frames.append(candidate)
        return frames


# ── Message accumulator ──

@dataclass
class MessageAccumulator:
    cmd: int
    parts: list[str] = field(default_factory=list)

    def add(self, payload_hex: str) -> None:
        self.parts.append(payload_hex)

    def complete(self) -> str:
        return "".join(self.parts)


# ── Async bridge session ──

@dataclass
class RemotePlusBridgeSession:
    """
    One active bridge session between a WebSocket client and a device.
    Manages the TCP socket, frame encoding, reassembly, and message dispatch.
    """
    host: str
    port: int
    device_dest: int  # device.config.number — destination address for commands
    src: int = ADDR_PC
    timeout: float = 20.0

    reader: asyncio.StreamReader | None = field(default=None, init=False)
    writer: asyncio.StreamWriter | None = field(default=None, init=False)
    reassembler: StreamReassembler = field(default_factory=StreamReassembler, init=False)
    accumulator: MessageAccumulator | None = field(default=None, init=False)
    _closed: bool = field(default=False, init=False)

    async def connect(self) -> bool:
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout,
            )
            logger.info("Bridge TCP connected to %s:%d", self.host, self.port)
            return True
        except Exception as exc:
            logger.error("Bridge TCP connect failed: %s", exc)
            return False

    async def close(self) -> None:
        self._closed = True
        if self.writer:
            try:
                # Send close command
                frame = build_frame(
                    dest=self.device_dest, src=self.src,
                    cmd=CommandId.CLOSE,
                )
                self.writer.write(frame)
                await self.writer.drain()
            except Exception:
                pass
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
            self.writer = None
            self.reader = None

    async def send_command(self, cmd: int, payload_hex: str = "") -> None:
        if not self.writer or self._closed:
            return
        frame = build_frame(
            dest=self.device_dest, src=self.src,
            cmd=cmd, payload_hex=payload_hex,
        )
        self.writer.write(frame)
        await self.writer.drain()

    async def recv_message(self) -> dict | None:
        """
        Read from TCP, reassemble frames, accumulate multi-block messages.
        Returns a complete message dict or None on connection loss.
        """
        if not self.reader or self._closed:
            return None
        try:
            chunk = await asyncio.wait_for(
                self.reader.read(8192),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

        if not chunk:
            return None  # Connection closed

        text = chunk.decode("ascii", errors="ignore")
        raw_frames = self.reassembler.feed(text)

        for raw in raw_frames:
            parsed = parse_frame(raw)
            if parsed is None:
                continue

            sub = parsed["sub"]
            cmd = parsed["cmd"]
            payload = parsed["payload_hex"]

            # Begin new message
            if sub == SubCmd.BEGIN:
                self.accumulator = MessageAccumulator(cmd=cmd)
                self.accumulator.add(payload)
                # Single-frame message (no END needed for BEGIN-only)
                # We'll wait for more or return on next read
                continue

            if self.accumulator is None:
                # Orphan fragment
                self.accumulator = MessageAccumulator(cmd=cmd)
                self.accumulator.add(payload)
                if sub == SubCmd.END:
                    result = {
                        "cmd": self.accumulator.cmd,
                        "payload_hex": self.accumulator.complete(),
                    }
                    self.accumulator = None
                    return result
                continue

            self.accumulator.add(payload)

            if sub == SubCmd.END:
                result = {
                    "cmd": self.accumulator.cmd,
                    "payload_hex": self.accumulator.complete(),
                }
                self.accumulator = None
                return result

        # If we have a single-frame accumulator, return it
        # (many commands are single-frame BEGIN without explicit END)
        if self.accumulator and len(self.accumulator.parts) > 0:
            result = {
                "cmd": self.accumulator.cmd,
                "payload_hex": self.accumulator.complete(),
            }
            self.accumulator = None
            return result

        return None

    # ── High-level request/response helpers ──

    async def request_screen(self, mode: int = 0) -> dict | None:
        await self.send_command(
            CommandId.CAPTURE_SCREEN_FAST,
            _hex_int(mode, 2),
        )
        return await self.recv_message()

    async def request_config(self) -> dict | None:
        await self.send_command(CommandId.CONFIGURATION_READ)
        return await self.recv_message()

    async def request_main_group(self) -> dict | None:
        await self.send_command(CommandId.MAIN_GROUP_READ)
        return await self.recv_message()

    async def send_key(self, key_code: int) -> dict | None:
        await self.send_command(
            CommandId.SEND_KEY,
            _hex_int(key_code, 2),
        )
        return await self.recv_message()
