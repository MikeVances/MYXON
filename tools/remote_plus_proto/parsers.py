from __future__ import annotations

from dataclasses import dataclass

from .protocol import decode_ascii_hex


@dataclass(frozen=True)
class DeviceConfig:
    computer: int
    sort: int
    type: int
    company: int
    computer_version: int
    pc_version: int
    serial: int
    number: int
    options_change_count: int


def parse_computers_response(data_hex: str) -> dict:
    username_status = int(data_hex[0:2], 16)
    password_status = int(data_hex[2:4], 16)
    connections = []
    block = data_hex[4:]
    for i in range(0, len(block), 60):
        row = block[i : i + 60]
        if len(row) < 60:
            continue
        addr_hex = row[0:20]
        name_hex = row[20:60]
        address = decode_ascii_hex(addr_hex)
        name = decode_ascii_hex(name_hex).replace("\x00", "").strip()
        connections.append(
            {
                "id": int(address) if address.isdigit() else address,
                "address": address,
                "name": name,
                "port": None,
            }
        )
    return {
        "username_status": username_status,
        "password_status": password_status,
        "connections": connections,
    }


def parse_mediate_response(data_hex: str) -> dict:
    return {
        "username_status": int(data_hex[0:2], 16),
        "password_status": int(data_hex[2:4], 16),
        "mediation_status": int(data_hex[4:6], 16),
    }


def parse_configuration_read_response(data_hex: str) -> dict:
    password = int(data_hex[0:4], 16)
    rows = data_hex[4:]
    configs = []
    for i in range(0, len(rows), 40):
        row = rows[i : i + 40]
        if len(row) < 40:
            continue
        configs.append(
            DeviceConfig(
                computer=int(row[0:4], 16),
                sort=int(row[4:8], 16),
                type=int(row[8:12], 16),
                company=int(row[12:16], 16),
                computer_version=int(row[16:20], 16),
                pc_version=int(row[20:24], 16),
                serial=int(row[24:32], 16),
                number=int(row[32:36], 16),
                options_change_count=int(row[36:40], 16),
            )
        )
    return {"password": password, "device_configs": configs}


def parse_main_group_response(data_hex: str, alarm_offset: int, alarm_len: int) -> dict:
    return {
        "code": int(data_hex[0:4], 16),
        "alarm_raw": int(data_hex[alarm_offset : alarm_offset + alarm_len], 16),
    }

