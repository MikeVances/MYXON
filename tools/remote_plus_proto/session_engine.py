from __future__ import annotations

from dataclasses import dataclass, field

from .protocol import Frame, SubCommand


@dataclass(frozen=True)
class CompletedMessage:
    cmd: int
    src: int
    dest: int
    payload_hex: str
    blocks: list[int]


@dataclass
class MessageAccumulator:
    cmd: int
    src: int
    dest: int
    payload_parts: list[str] = field(default_factory=list)
    blocks: list[int] = field(default_factory=list)

    def add(self, frame: Frame) -> None:
        self.payload_parts.append(frame.payload_hex)
        self.blocks.append(frame.block)

    def complete(self) -> CompletedMessage:
        return CompletedMessage(
            cmd=self.cmd,
            src=self.src,
            dest=self.dest,
            payload_hex="".join(self.payload_parts),
            blocks=list(self.blocks),
        )


@dataclass
class SessionEngine:
    """Accumulates protocol fragments (`SUB`/`BLOCK`) into complete messages."""

    current: MessageAccumulator | None = None

    def feed(self, frame: Frame) -> list[CompletedMessage]:
        out: list[CompletedMessage] = []
        sub = int(frame.sub)

        if sub == int(SubCommand.BEGIN):
            self.current = MessageAccumulator(cmd=frame.cmd, src=frame.src, dest=frame.dest)
            self.current.add(frame)
            return out

        if self.current is None:
            # Orphan fragment: start implicit session to avoid data loss.
            self.current = MessageAccumulator(cmd=frame.cmd, src=frame.src, dest=frame.dest)
            self.current.add(frame)
            if sub == int(SubCommand.END):
                out.append(self.current.complete())
                self.current = None
            return out

        # If command/source tuple changed mid-stream, close previous accumulator.
        if (
            self.current.cmd != frame.cmd
            or self.current.src != frame.src
            or self.current.dest != frame.dest
        ):
            out.append(self.current.complete())
            self.current = MessageAccumulator(cmd=frame.cmd, src=frame.src, dest=frame.dest)

        self.current.add(frame)

        if sub == int(SubCommand.END):
            out.append(self.current.complete())
            self.current = None

        return out

