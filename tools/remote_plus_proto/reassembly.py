from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FrameStreamReassembler:
    """Splits incoming text chunks into complete '@...*\\r' frames."""

    buffer: str = field(default_factory=str)

    def feed(self, chunk: str) -> list[str]:
        self.buffer += chunk
        out: list[str] = []
        while True:
            end = self.buffer.find("\r")
            if end < 0:
                break
            candidate = self.buffer[: end + 1]
            self.buffer = self.buffer[end + 1 :]
            start = candidate.find("@")
            star = candidate.rfind("*")
            if start >= 0 and star >= 0 and star < len(candidate):
                out.append(candidate[start : star + 2])  # include '*\r'
        return out

