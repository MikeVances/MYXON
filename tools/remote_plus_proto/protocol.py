from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class CommandId(IntEnum):
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


class AddressId(IntEnum):
    GENERAL = 1018
    PC = 1023
    SMARTLINK_SERVER = 1184


class SubCommand(IntEnum):
    BEGIN = 0
    REPEAT = 1
    NEXT = 2
    END = 5


class ParseStatus(IntEnum):
    IGNORE = -1
    INCOMPLETE = 0
    COMPLETE = 1


@dataclass(frozen=True)
class Frame:
    dest: int
    src: int
    cmd: int
    sub: int
    block: int
    payload_hex: str
    crc: int


def encode_hex_int(value: int, width: int = 2) -> str:
    return format(value, "X").zfill(width)


def encode_ascii_hex(text: str, pad: int = 0) -> str:
    out = []
    for ch in text:
        out.append(format(ord(ch), "X").zfill(pad))
    return "".join(out)


def decode_ascii_hex(hex_text: str) -> str:
    out = []
    for i in range(0, len(hex_text), 2):
        out.append(chr(int(hex_text[i : i + 2], 16)))
    return "".join(out)


def checksum_xor(text: str) -> int:
    value = ord(text[0]) if text else 0
    for ch in text[1:]:
        value ^= ord(ch)
    return value


def pack_auth_data(username: str, hashed_password: str, address: str = "") -> str:
    user_hex = encode_ascii_hex(username, 2).ljust(40, "0")
    pass_hex = hashed_password.upper().rjust(40, "0")
    addr_hex = encode_ascii_hex(address, 2)
    return user_hex + pass_hex + addr_hex


def build_frame(
    dest: int,
    src: int,
    cmd: int,
    payload_hex: str = "",
    sub: int = SubCommand.BEGIN,
    block: int = 0,
) -> str:
    base = (
        "@"
        + encode_hex_int(dest, 3)
        + encode_hex_int(src, 3)
        + encode_hex_int(cmd, 3)
        + encode_hex_int(sub, 1)
        + encode_hex_int(block, 2)
        + encode_hex_int(len(payload_hex) // 2, 2)
        + payload_hex
    )
    crc = encode_hex_int(checksum_xor(base), 2)
    return base + crc + "*\r"


def parse_frame(frame_text: str) -> Frame:
    if not frame_text.startswith("@") or not frame_text.endswith("*\r"):
        raise ValueError("invalid frame markers")
    if len(frame_text) < 20:
        raise ValueError("frame too short")
    payload_len = int(frame_text[13:15], 16)
    payload_chars = payload_len * 2
    payload_end = 15 + payload_chars
    payload_hex = frame_text[15:payload_end]
    crc = int(frame_text[payload_end : payload_end + 2], 16)
    body = frame_text[:payload_end]
    expected_crc = checksum_xor(body)
    if expected_crc != crc:
        raise ValueError(f"crc mismatch expected={expected_crc:02X} got={crc:02X}")
    return Frame(
        dest=int(frame_text[1:4], 16),
        src=int(frame_text[4:7], 16),
        cmd=int(frame_text[7:10], 16),
        sub=int(frame_text[10:11], 16),
        block=int(frame_text[11:13], 16),
        payload_hex=payload_hex,
        crc=crc,
    )

