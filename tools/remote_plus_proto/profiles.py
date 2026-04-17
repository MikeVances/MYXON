from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScreenProfile:
    width: int
    height: int
    decoder: str


@dataclass(frozen=True)
class CaptureProfile:
    default_command: int
    supports_fast: bool


@dataclass(frozen=True)
class DeviceProfile:
    family: str
    brandings: tuple[str, ...]
    screen: ScreenProfile
    capture: CaptureProfile
    keys: dict[str, int]


def _profiles_path() -> Path:
    return Path(__file__).with_name("device_profiles.json")


def load_profiles() -> list[DeviceProfile]:
    raw = json.loads(_profiles_path().read_text(encoding="utf-8"))
    out: list[DeviceProfile] = []
    for item in raw.get("profiles", []):
        out.append(
            DeviceProfile(
                family=item["family"],
                brandings=tuple(item["brandings"]),
                screen=ScreenProfile(
                    width=int(item["screen"]["width"]),
                    height=int(item["screen"]["height"]),
                    decoder=item["screen"]["decoder"],
                ),
                capture=CaptureProfile(
                    default_command=int(item["capture"]["default_command"]),
                    supports_fast=bool(item["capture"]["supports_fast"]),
                ),
                keys={str(k): int(v) for k, v in item["keys"].items()},
            )
        )
    return out


def get_profile(family: str, branding: str | None = None) -> DeviceProfile:
    family_l = family.lower()
    branding_l = branding.lower() if branding else None
    candidates = [p for p in load_profiles() if p.family.lower() == family_l]
    if not candidates:
        raise KeyError(f"unknown family: {family}")
    if branding_l is None:
        return candidates[0]
    for p in candidates:
        if branding_l in (b.lower() for b in p.brandings):
            return p
    return candidates[0]

