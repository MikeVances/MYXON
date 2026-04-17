from __future__ import annotations

import socket
from dataclasses import dataclass, field

from .protocol import AddressId, CommandId, SubCommand, build_frame, parse_frame
from .reassembly import FrameStreamReassembler
from .session_engine import CompletedMessage, SessionEngine


@dataclass
class RemotePlusRuntimeClient:
    host: str
    port: int
    src: int = int(AddressId.PC)
    timeout_sec: float = 20.0
    sock: socket.socket | None = field(default=None, init=False)
    reassembler: FrameStreamReassembler = field(default_factory=FrameStreamReassembler, init=False)
    sessions: SessionEngine = field(default_factory=SessionEngine, init=False)

    def connect(self) -> None:
        if self.sock is not None:
            return
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout_sec)
        self.sock.settimeout(self.timeout_sec)

    def close_socket(self) -> None:
        if self.sock is None:
            return
        try:
            self.sock.close()
        finally:
            self.sock = None

    def send_frame(
        self,
        dest: int,
        cmd: int,
        payload_hex: str = "",
        sub: int = int(SubCommand.BEGIN),
        block: int = 0,
    ) -> str:
        if self.sock is None:
            raise RuntimeError("socket is not connected")
        frame = build_frame(dest=dest, src=self.src, cmd=cmd, payload_hex=payload_hex, sub=sub, block=block)
        self.sock.sendall(frame.encode("ascii"))
        return frame

    def _receive_ready_messages(self) -> list[CompletedMessage]:
        if self.sock is None:
            raise RuntimeError("socket is not connected")
        chunk = self.sock.recv(8192)
        if not chunk:
            return []
        text = chunk.decode("ascii", errors="ignore")
        out: list[CompletedMessage] = []
        for raw in self.reassembler.feed(text):
            try:
                frame = parse_frame(raw)
            except ValueError:
                continue
            out.extend(self.sessions.feed(frame))
        return out

    def recv_until_cmd(self, cmd: int) -> CompletedMessage:
        while True:
            messages = self._receive_ready_messages()
            for msg in messages:
                if msg.cmd == cmd:
                    return msg

    def request(self, dest: int, cmd: int, payload_hex: str = "") -> CompletedMessage:
        self.send_frame(dest=dest, cmd=cmd, payload_hex=payload_hex)
        return self.recv_until_cmd(cmd)

    def configuration_read(self, dest: int) -> CompletedMessage:
        return self.request(dest=dest, cmd=int(CommandId.CONFIGURATION_READ))

    def capture_screen_fast(self, dest: int, mode: int = 0) -> CompletedMessage:
        payload_hex = format(mode, "X").zfill(2)
        return self.request(dest=dest, cmd=int(CommandId.CAPTURE_SCREEN_FAST), payload_hex=payload_hex)

    def main_group_read(self, dest: int) -> CompletedMessage:
        return self.request(dest=dest, cmd=int(CommandId.MAIN_GROUP_READ))

    def send_key(self, dest: int, key_code: int) -> CompletedMessage:
        payload_hex = format(key_code, "X").zfill(2)
        return self.request(dest=dest, cmd=int(CommandId.SEND_KEY), payload_hex=payload_hex)

    def close_remote(self, dest: int) -> None:
        self.send_frame(dest=dest, cmd=int(CommandId.CLOSE), payload_hex="")
