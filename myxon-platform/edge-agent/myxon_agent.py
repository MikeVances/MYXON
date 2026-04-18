#!/usr/bin/env python3
"""MYXON Edge Agent — connects device to MYXON cloud platform.

Responsibilities:
  1. Auto-discover controllers on LAN interfaces (port scan)
  2. Register with control plane → receive FRPS tunnel config
  3. Start frpc tunnel so the server can reach the controller
  4. Maintain heartbeat
  5. Re-scan LAN periodically to detect newly connected controllers

No manual IP configuration needed — the agent finds controllers itself.
The only required config is the server URL and the device serial number.

Configuration: agent.env in the same directory (or systemd EnvironmentFile).
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import platform
import random
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("myxon-agent")


# ── Env file loader ────────────────────────────────────────────────────────────

def _load_env_file():
    """Load agent.env from script directory (dev convenience).
    systemd EnvironmentFile handles this automatically in production.
    """
    env_path = Path(__file__).parent / "agent.env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env_file()


# ── Configuration ──────────────────────────────────────────────────────────────

CLOUD_URL          = os.environ.get("MYXON_CLOUD_URL", "http://localhost:8000")
AGENT_PUBLIC_ID    = os.environ.get("MYXON_AGENT_ID", "agent-001")
AGENT_SECRET       = os.environ.get("MYXON_AGENT_SECRET", "dev-secret")
HEARTBEAT_INTERVAL = int(os.environ.get("MYXON_HEARTBEAT_INTERVAL", "15"))
DISCOVERY_INTERVAL = int(os.environ.get("MYXON_DISCOVERY_INTERVAL", "60"))

FRPC_BIN = os.environ.get("MYXON_FRPC_BIN", "frpc")

# ── Activation code (Scenario 2: OEM SDK / new device flow) ───────────────────
#
# Set MYXON_ACTIVATION_CODE instead of MYXON_SERIAL to provision a new device.
# The agent calls POST /api/v0/agent/activate, receives a generated serial number
# and frpc token, then persists them to DEVICE_STATE_FILE.
#
# On subsequent reboots the agent reads DEVICE_STATE_FILE and skips activation,
# using the already-assigned serial + token for the normal /register flow.
# This ensures the one-time code is only consumed once — even after power cycles.
ACTIVATION_CODE = os.environ.get("MYXON_ACTIVATION_CODE", "").strip()

# DEVICE_STATE_FILE: where the agent stores its identity after first activation.
# Contains: {"device_id": "...", "serial_number": "MX-2026-00001", "frpc_token": "..."}
DEVICE_STATE_FILE = Path(os.environ.get("MYXON_DEVICE_STATE", "/etc/myxon/device.json"))

# Legacy flow: pre-registered serial (MYXON_SERIAL env var)
# Used when there is no activation code — device was pre-registered by a dealer.
SERIAL_NUMBER = os.environ.get("MYXON_SERIAL", "MYXON-DEV-001")

# Per-device frpc token — issued by server on first registration.
# Stored locally so it survives restarts. Do NOT put this in agent.env;
# the agent manages it automatically in TOKEN_FILE.
TOKEN_FILE = Path(os.environ.get("MYXON_TOKEN_FILE", "/etc/myxon/agent_token"))

# Discovery mode:
#   auto      — scan non-WAN interfaces first; fall back to WAN subnet if none found (default)
#   lan-only  — only non-WAN interfaces (router/dual-NIC mode, never scans WAN subnet)
#   all       — scan ALL interfaces incl. WAN (for single-NIC farm LAN, explicit)
SCAN_MODE = os.environ.get("MYXON_SCAN_MODE", "auto").lower()

# Explicit LAN interface override — set by install.sh when Orange Pi is configured
# as a DHCP router/gateway (--lan-iface flag). When set, the agent scans ONLY
# this interface, bypassing auto-detection and SCAN_MODE entirely.
# Example: MYXON_LAN_IFACE=eth1  (USB Ethernet adapter connected to industrial switch)
LAN_IFACE = os.environ.get("MYXON_LAN_IFACE", "").strip()

# GSM modem for local SMS delivery.
# When set, the agent sends SMS from heartbeat response via mmcli (ModemManager CLI).
# If mmcli is unavailable, falls back to raw AT commands on this serial port.
# Example: MYXON_MODEM_PORT=/dev/ttyUSB0
MODEM_PORT = os.environ.get("MYXON_MODEM_PORT", "").strip()

FRPC_PID_FILE = Path("/tmp/myxon_frpc.pid")


# ── Retry / backoff helpers ────────────────────────────────────────────────────

async def _backoff_delay(attempt: int, base: float = 5.0, cap: float = 300.0) -> float:
    """
    Exponential backoff with ±20% jitter. Returns the actual delay used.

    Sequence: 5s → 10s → 20s → 40s → 80s → 160s → 300s (cap) → 300s …
    Jitter prevents thundering-herd when many devices restart simultaneously
    (e.g. after a power outage at the farm).
    """
    delay = min(base * (2 ** attempt), cap)
    jitter = delay * random.uniform(-0.2, 0.2)
    actual = max(1.0, delay + jitter)
    await asyncio.sleep(actual)
    return actual


async def send_sms(number: str, message: str) -> bool:
    """
    Send an SMS via the local GSM modem.

    Strategy:
      1. Try mmcli (ModemManager CLI) — works when MM owns the modem for 4G WAN.
         MM multiplexes SMS and data on the same modem without conflicts.
      2. Fall back to raw AT commands via the serial port (MYXON_MODEM_PORT).
         Only safe when ModemManager is NOT running (e.g. SMS-only modem).

    Returns True if sent successfully, False on error.
    """
    if not MODEM_PORT and not _mmcli_available():
        log.debug("SMS skipped: no modem configured (set MYXON_MODEM_PORT)")
        return False

    log.info("SMS → %s: %s", number, message[:40] + ("…" if len(message) > 40 else ""))

    # ── Strategy 1: mmcli ──────────────────────────────────────────────────────
    if _mmcli_available():
        return await _send_sms_mmcli(number, message)

    # ── Strategy 2: AT commands via serial port ────────────────────────────────
    return await _send_sms_at(number, message)


def _mmcli_available() -> bool:
    """Check if mmcli is installed and ModemManager has at least one modem."""
    try:
        result = subprocess.run(
            ["mmcli", "-L"],
            capture_output=True, text=True, timeout=5
        )
        # mmcli -L returns "No modems were found" or a list
        return result.returncode == 0 and "No modems" not in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


async def _send_sms_mmcli(number: str, message: str) -> bool:
    """
    Send SMS via ModemManager CLI.

    mmcli -m 0 --messaging-create-sms="number=+316...,text=Hello"
    → returns dbus path, then:
    mmcli -s /org/freedesktop/ModemManager1/SMS/0 --send
    """
    loop = asyncio.get_event_loop()

    def _run_mmcli(args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["mmcli"] + args,
            capture_output=True, text=True, timeout=30
        )

    try:
        # Step 1: create SMS object
        create_result = await loop.run_in_executor(
            None,
            lambda: _run_mmcli(["-m", "0", f'--messaging-create-sms=number={number},text={message}'])
        )
        if create_result.returncode != 0:
            log.error("mmcli create-sms failed: %s", create_result.stderr.strip())
            return False

        # Parse dbus path from output:  "/org/freedesktop/ModemManager1/SMS/N"
        sms_path = None
        for line in create_result.stdout.splitlines():
            line = line.strip()
            if line.startswith("/org/freedesktop/ModemManager1/SMS/"):
                sms_path = line
                break

        if not sms_path:
            log.error("mmcli: could not parse SMS dbus path from: %s", create_result.stdout)
            return False

        # Step 2: send it
        send_result = await loop.run_in_executor(
            None,
            lambda: _run_mmcli(["-s", sms_path, "--send"])
        )
        if send_result.returncode != 0:
            log.error("mmcli send failed: %s", send_result.stderr.strip())
            return False

        log.info("SMS sent via mmcli → %s", number)
        return True

    except subprocess.TimeoutExpired:
        log.error("mmcli timeout sending SMS to %s", number)
        return False
    except Exception as exc:
        log.error("mmcli SMS error: %s", exc)
        return False


async def _send_sms_at(number: str, message: str) -> bool:
    """
    Send SMS via raw AT commands on the serial port.

    Only use when ModemManager is NOT running — MM must not own the port.
    Requires: MYXON_MODEM_PORT set (e.g. /dev/ttyUSB0).

    AT command sequence:
      AT+CMGF=1        → set text mode
      AT+CMGS="+N"     → start message to number
      <text>\x1A       → message body + Ctrl-Z to send
    """
    if not MODEM_PORT:
        log.warning("SMS AT fallback: MYXON_MODEM_PORT not set")
        return False

    loop = asyncio.get_event_loop()

    def _do_at_sms() -> bool:
        import serial  # type: ignore  # optional dependency
        try:
            with serial.Serial(MODEM_PORT, baudrate=115200, timeout=5) as port:
                def at(cmd: bytes, delay: float = 0.5) -> bytes:
                    port.write(cmd + b"\r\n")
                    import time; time.sleep(delay)
                    return port.read(port.in_waiting)

                at(b"AT")                          # ping modem
                at(b"AT+CMGF=1")                   # text mode
                at(f'AT+CMGS="{number}"'.encode())  # destination number
                # Send message body + Ctrl-Z
                port.write(message.encode("utf-8", errors="replace") + b"\x1a")
                import time; time.sleep(4)         # modem needs time to transmit
                resp = port.read(port.in_waiting)
                if b"+CMGS:" in resp:
                    log.info("SMS sent via AT → %s", number)
                    return True
                log.error("AT SMS: unexpected response: %s", resp)
                return False
        except Exception as exc:
            log.error("AT SMS error on %s: %s", MODEM_PORT, exc)
            return False

    return await loop.run_in_executor(None, _do_at_sms)


async def _retry_until_success(coro_factory, *, label: str, base: float = 5.0, cap: float = 300.0):
    """
    Call coro_factory() repeatedly until it returns a truthy result.
    Uses exponential backoff between attempts. Never gives up.

    coro_factory must be a zero-argument async callable returning the result.
    """
    attempt = 0
    while True:
        result = await coro_factory()
        if result:
            return result
        delay = await _backoff_delay(attempt, base=base, cap=cap)
        log.warning("%s: attempt %d failed — retrying in %.0fs", label, attempt + 1, delay)
        attempt += 1


def _load_token() -> str | None:
    """Load persisted device token from TOKEN_FILE."""
    try:
        token = TOKEN_FILE.read_text().strip()
        return token if token else None
    except FileNotFoundError:
        return None


def _save_token(token: str) -> None:
    """Persist device token to TOKEN_FILE (mode 0600)."""
    try:
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(token)
        TOKEN_FILE.chmod(0o600)
        log.info("Agent token saved to %s", TOKEN_FILE)
    except OSError as e:
        log.warning("Could not save token to %s: %s — storing in memory only", TOKEN_FILE, e)


# Runtime token (loaded from file or received from server)
_agent_token: str | None = _load_token()


# ── Device state (activation code flow) ───────────────────────────────────────

def _load_device_state() -> dict | None:
    """
    Load persisted device identity from DEVICE_STATE_FILE.
    Returns dict with device_id, serial_number, frpc_token — or None if not activated yet.
    """
    try:
        data = json.loads(DEVICE_STATE_FILE.read_text())
        if "serial_number" in data and "frpc_token" in data:
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return None


def _save_device_state(device_id: str, serial_number: str, frpc_token: str) -> None:
    """
    Persist device identity after first activation.
    Written to DEVICE_STATE_FILE (mode 0600) so it survives reboots.
    The activation code is NOT stored — it's one-time use, already consumed.
    """
    state = {
        "device_id": device_id,
        "serial_number": serial_number,
        "frpc_token": frpc_token,
    }
    try:
        DEVICE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        DEVICE_STATE_FILE.write_text(json.dumps(state, indent=2))
        DEVICE_STATE_FILE.chmod(0o600)
        log.info("Device state saved to %s (serial=%s)", DEVICE_STATE_FILE, serial_number)
    except OSError as e:
        log.warning("Could not save device state: %s — state in memory only", e)

# Known controller ports to probe during LAN scan
# Format: {port: (resource_id, protocol, display_name)}
KNOWN_PORTS: dict[int, tuple[str, str, str]] = {
    5843: ("remote-plus", "tcp",  "HOTRACO Remote+"),
    5900: ("vnc",         "vnc",  "VNC"),
    80:   ("http",        "http", "HTTP"),
}

# Optional manual override — skip discovery if set explicitly
_MANUAL_RESOURCES = os.environ.get("MYXON_RESOURCES", "")

# State
running = True


# ── LAN auto-discovery ─────────────────────────────────────────────────────────

def _get_default_route_iface() -> str | None:
    """Return the interface name used for the default route (WAN side)."""
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if "dev" in line:
                parts = line.split()
                idx = parts.index("dev")
                return parts[idx + 1]
    except Exception:
        pass
    return None


def _get_iface_subnets(include_wan: bool = False, wan_iface: str | None = None) -> list[tuple[str, str]]:
    """
    Enumerate all IPv4 interfaces via `ip addr`.
    Returns list of (iface, subnet_cidr) for private networks.
    Skips loopback always; skips wan_iface unless include_wan=True.
    """
    subnets: list[tuple[str, str]] = []
    try:
        result = subprocess.run(
            ["ip", "-o", "-4", "addr", "show"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            iface = parts[1]
            if iface == "lo":
                continue
            if not include_wan and iface == wan_iface:
                continue
            cidr = parts[3]
            try:
                net = ipaddress.IPv4Network(cidr, strict=False)
                if net.is_private and net.num_addresses > 1:
                    subnets.append((iface, str(net)))
            except ValueError:
                continue
    except Exception as e:
        log.warning("Could not enumerate interfaces: %s", e)
    return subnets


def _get_lan_subnets() -> list[tuple[str, str]]:
    """
    Find subnets to scan for controllers. Behaviour depends on MYXON_SCAN_MODE:

      auto (default)
        1. Scan non-WAN interfaces first (classic dual-NIC router mode).
        2. If none found → fall back to WAN-interface subnet.
           This handles the common "Orange Pi plugged into existing farm LAN"
           scenario where eth0 is both the default-route interface AND the
           network that contains all controllers.

      lan-only
        Only non-WAN interfaces. Use when Orange Pi is a proper router/gateway
        with a dedicated LAN port and you never want to scan the WAN subnet.

      all
        All interfaces including WAN. Same result as auto-fallback but explicit.

    Returns list of (interface_name, subnet_cidr).
    """
    # Explicit interface override — highest priority, set by install.sh router mode.
    # When LAN_IFACE is set we scan ONLY that interface regardless of SCAN_MODE.
    if LAN_IFACE:
        all_subnets = _get_iface_subnets(include_wan=True, wan_iface=None)
        filtered = [(iface, net) for iface, net in all_subnets if iface == LAN_IFACE]
        if filtered:
            log.info("Discovery: explicit LAN interface %s → %s",
                     LAN_IFACE, [s[1] for s in filtered])
            return filtered
        log.warning(
            "Discovery: MYXON_LAN_IFACE=%s not found among interfaces %s — "
            "is the USB adapter connected?",
            LAN_IFACE, [s[0] for s in all_subnets],
        )
        return []

    wan_iface = _get_default_route_iface()

    if SCAN_MODE == "all":
        subnets = _get_iface_subnets(include_wan=True, wan_iface=wan_iface)
        log.info("Discovery mode: all interfaces (wan=%s)", wan_iface)
        return subnets

    # lan-only or auto: start with non-WAN interfaces
    subnets = _get_iface_subnets(include_wan=False, wan_iface=wan_iface)

    if subnets:
        log.info("Discovery mode: dedicated LAN interfaces %s",
                 [s[0] for s in subnets])
        # macOS fallback — for dev only
        if platform.system() == "Darwin" and not subnets:
            subnets = _get_lan_subnets_macos(wan_iface)
        return subnets

    if SCAN_MODE == "lan-only":
        log.warning("Discovery mode: lan-only, but no dedicated LAN interfaces found. "
                    "Nothing to scan. Set MYXON_SCAN_MODE=auto to enable fallback.")
        return []

    # auto fallback: single-interface mode (Orange Pi on existing farm LAN)
    # The WAN interface IS the LAN — scan its subnet for controllers.
    if wan_iface:
        fallback = _get_iface_subnets(include_wan=True, wan_iface=wan_iface)
        # Filter to only the WAN iface (include_wan=True returns everything, re-filter)
        fallback = [(iface, net) for iface, net in fallback if iface == wan_iface]
        if fallback:
            log.info("Discovery mode: single-interface fallback — scanning WAN iface %s "
                     "(farm LAN mode, no dedicated LAN port)", wan_iface)
            return fallback

    # macOS dev environment
    if platform.system() == "Darwin":
        return _get_lan_subnets_macos(wan_iface)

    log.warning("Discovery: no scannable subnets found (wan_iface=%s, mode=%s)",
                wan_iface, SCAN_MODE)
    return []


def _get_lan_subnets_macos(wan_iface: str | None) -> list[tuple[str, str]]:
    """macOS-specific subnet detection via ifconfig."""
    subnets = []
    try:
        result = subprocess.run(
            ["ifconfig", "-a"], capture_output=True, text=True, timeout=5
        )
        iface = None
        for line in result.stdout.splitlines():
            if not line.startswith("\t") and not line.startswith(" "):
                iface = line.split(":")[0]
            elif "inet " in line and iface and iface != wan_iface and iface != "lo0":
                parts = line.split()
                ip_idx = parts.index("inet") + 1
                mask_idx = parts.index("netmask") + 1 if "netmask" in parts else None
                if ip_idx < len(parts) and mask_idx:
                    ip = parts[ip_idx]
                    mask_hex = parts[mask_idx]
                    try:
                        mask = socket_mask_from_hex(mask_hex)
                        net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                        if net.is_private and net.num_addresses > 1:
                            subnets.append((iface, str(net)))
                    except Exception:
                        pass
    except Exception:
        pass
    return subnets


def socket_mask_from_hex(hex_mask: str) -> str:
    """Convert hex netmask (0xffffff00) to dotted notation."""
    val = int(hex_mask, 16)
    return ".".join(str((val >> (8 * i)) & 0xFF) for i in reversed(range(4)))


async def _probe_tcp(host: str, port: int, timeout: float = 0.4) -> bool:
    """Try to open a TCP connection. Returns True if port is open."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def discover_controllers() -> list[dict]:
    """
    Scan LAN interfaces for known controller ports.
    Returns list of resource dicts ready to include in published_resources.
    """
    subnets = _get_lan_subnets()
    if not subnets:
        log.warning("Discovery: no LAN subnets found")
        return []

    discovered: list[dict] = []

    for iface, subnet_cidr in subnets:
        network = ipaddress.IPv4Network(subnet_cidr)

        # Skip subnets larger than /24 — too slow to scan
        if network.num_addresses > 256:
            log.warning("Discovery: subnet %s too large (>256 hosts), skipping", subnet_cidr)
            continue

        hosts = list(network.hosts())
        log.info("Discovery: scanning %s (%d hosts) on iface %s", subnet_cidr, len(hosts), iface)

        for port, (res_id, protocol, name) in KNOWN_PORTS.items():
            tasks = [_probe_tcp(str(h), port) for h in hosts]
            results = await asyncio.gather(*tasks)

            for host, is_open in zip(hosts, results):
                if is_open:
                    host_str = str(host)
                    log.info("Discovery: found %s at %s:%d", name, host_str, port)
                    discovered.append({
                        "id": res_id,
                        "protocol": protocol,
                        "host": host_str,
                        "port": port,
                        "name": name,
                    })

    return discovered


async def resolve_resources() -> list[dict]:
    """
    Determine the list of published resources:
    1. If MYXON_RESOURCES is set manually — use it (explicit override).
    2. Otherwise — run LAN auto-discovery.
    """
    if _MANUAL_RESOURCES.strip():
        try:
            resources = json.loads(_MANUAL_RESOURCES)
            log.info("Using manual MYXON_RESOURCES (%d entries)", len(resources))
            return resources
        except json.JSONDecodeError as e:
            log.error("MYXON_RESOURCES is not valid JSON: %s", e)

    log.info("Auto-discovering controllers on LAN...")
    resources = await discover_controllers()

    if not resources:
        log.warning("Discovery: no controllers found. Will retry later.")

    return resources


# ── Device metadata ────────────────────────────────────────────────────────────

def get_hw_info() -> tuple[str, str]:
    """Return (firmware_version, hardware_info) from the host OS."""
    firmware = "myxon-agent/0.2.0"
    hardware = platform.platform()

    debian_version = Path("/etc/debian_version")
    if debian_version.exists():
        hardware = f"Debian {debian_version.read_text().strip()} / {platform.machine()}"

    return firmware, hardware


# ── Registration ───────────────────────────────────────────────────────────────

async def activate(
    client: httpx.AsyncClient,
    resources: list[dict],
    code: str,
) -> tuple[str | None, str | None, dict | None]:
    """
    Activation-code flow: first-time device registration using one-time code.
    Calls POST /api/v0/agent/activate — no prior device pre-registration needed.

    Returns: (device_id, serial_number, tunnel_config) or (None, None, None) on failure.
    After success, caller must persist serial_number and frpc_token via _save_device_state().
    """
    global _agent_token, SERIAL_NUMBER

    firmware, hardware = get_hw_info()

    payload = {
        "code": code,
        "metadata": {
            "firmware_version": firmware,
            "hardware_info": hardware,
            "model": hardware,
            "published_resources": resources,
        },
    }

    try:
        resp = await client.post(f"{CLOUD_URL}/api/v0/agent/activate", json=payload)

        if resp.status_code == 201:
            data = resp.json()
            tc = data.get("tunnel")

            # Persist token and update runtime state
            frpc_token = data["frpc_token"]
            serial = data["serial_number"]
            dev_id = data["device_id"]

            _agent_token = frpc_token
            _save_token(frpc_token)

            # Update module-level SERIAL_NUMBER so _build_frpc_config uses the correct name
            SERIAL_NUMBER = serial

            log.info("Activated! device_id=%s serial=%s tunnel_port=%s",
                     dev_id, serial, tc.get("assigned_port") if tc else "none")
            return dev_id, serial, tc

        elif resp.status_code == 409:
            log.error("Activation code already used — cannot activate again. "
                      "Check DEVICE_STATE_FILE or contact your dealer for a new code.")
        elif resp.status_code == 410:
            log.error("Activation code expired — contact dealer for a new code.")
        elif resp.status_code == 404:
            log.error("Activation code not found — verify MYXON_ACTIVATION_CODE value.")
        else:
            log.error("Activation failed: %d %s", resp.status_code, resp.text[:200])

    except httpx.RequestError as e:
        log.error("Activation error: %s", e)

    return None, None, None


async def register(client: httpx.AsyncClient, resources: list[dict]) -> tuple[str | None, dict | None]:
    """Register with control plane. Returns (device_id, tunnel_config)."""
    global _agent_token

    firmware, hardware = get_hw_info()

    payload = {
        "agent_public_id": AGENT_PUBLIC_ID,
        "serial_number": SERIAL_NUMBER,
        "signature": AGENT_SECRET,
        "metadata": {
            "serial_number": SERIAL_NUMBER,
            "firmware_version": firmware,
            "hardware_info": hardware,
            "model": platform.machine(),
            "published_resources": resources,
        },
    }

    try:
        resp = await client.post(f"{CLOUD_URL}/api/v0/agent/register", json=payload)
        if resp.status_code == 200:
            data = resp.json()
            tc = data.get("tunnel")

            # Server issues a frpc_token only on first registration (or after rotation).
            # If received — persist immediately; old token is now invalid.
            new_token = data.get("frpc_token")
            if new_token:
                _agent_token = new_token
                _save_token(new_token)
                log.info("New frpc token received and persisted.")

            log.info("Registered. device_id=%s tunnel_port=%s",
                     data["device_id"], tc.get("assigned_port") if tc else "none")
            return data["device_id"], tc
        else:
            log.error("Registration failed: %d %s", resp.status_code, resp.text[:200])
            return None, None
    except httpx.RequestError as e:
        log.error("Registration error: %s", e)
        return None, None


# ── FRPC tunnel ────────────────────────────────────────────────────────────────

def _build_frpc_config(tc: dict, resources: list[dict]) -> str:
    """
    Generate frpc TOML config from tunnel parameters and resource list.

    Auth strategy (Этап 2):
      - No global auth.token (frps.toml has auth.token = "")
      - `user` field carries the device serial_number (visible in frps dashboard)
      - `metadatas.device_token` carries the per-device token for the HTTP plugin
    """
    frps_host     = tc.get("frps_host", "localhost")
    frps_port     = tc.get("frps_port", 7000)
    assigned_port = tc.get("assigned_port")
    token         = _agent_token or ""

    lines = [
        f'serverAddr = "{frps_host}"',
        f"serverPort = {frps_port}",
        # Serial number in user field → visible in frps dashboard & plugin content.user
        f'user = "{SERIAL_NUMBER}"',
        # Per-device token in metadatas → read by our auth webhook
        f'[metadatas]',
        f'device_token = "{token}"',
        "",
    ]

    if not token:
        log.warning(
            "No frpc token available yet. frps will reject this connection. "
            "Re-register to obtain a token."
        )

    if not assigned_port:
        return "\n".join(lines)

    port_offset = 0
    for res in resources:
        proxy_name  = f"{SERIAL_NUMBER}-{res['id']}"
        local_host  = res.get("host", "127.0.0.1")
        local_port  = res["port"]
        remote_port = assigned_port + port_offset

        lines += [
            "[[proxies]]",
            f'name       = "{proxy_name}"',
            f'type       = "tcp"',
            f'localIP    = "{local_host}"',
            f"localPort  = {local_port}",
            f"remotePort = {remote_port}",
            "",
        ]
        port_offset += 1

    return "\n".join(lines)


def start_frpc(tc: dict, resources: list[dict]) -> subprocess.Popen | None:
    """Write frpc config and start the process. Writes PID to FRPC_PID_FILE."""
    cfg_path = Path("/tmp/myxon_frpc.toml")
    cfg_path.write_text(_build_frpc_config(tc, resources))
    log.info("frpc config → %s", cfg_path)

    try:
        proc = subprocess.Popen(
            [FRPC_BIN, "-c", str(cfg_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        log.info("frpc started (PID %d)", proc.pid)
        # Write PID so local_api.py /status can check tunnel health
        try:
            FRPC_PID_FILE.write_text(str(proc.pid))
        except OSError as e:
            log.debug("Could not write frpc PID file: %s", e)
        return proc
    except FileNotFoundError:
        log.warning("frpc not found at '%s'. Tunnel disabled.", FRPC_BIN)
        log.warning("Install: brew install frp  |  apt install frpc  |  opkg install frpc")
        return None


def stop_frpc(proc: subprocess.Popen | None):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    # Clean up PID file so local_api.py reports tunnel as stopped
    try:
        FRPC_PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


# ── Heartbeat ──────────────────────────────────────────────────────────────────

async def heartbeat_loop(client: httpx.AsyncClient, dev_id: str):
    """
    Send periodic heartbeats to the cloud server.

    Tracks consecutive failures to escalate log level from WARNING → ERROR
    after 3 missed beats (~45s with 15s interval). The loop never exits —
    it waits for connectivity to come back. systemd handles service restart
    only on unhandled exceptions.
    """
    global running
    boot_time = datetime.now(timezone.utc)
    consecutive_failures = 0

    while running:
        uptime = int((datetime.now(timezone.utc) - boot_time).total_seconds())
        try:
            resp = await client.post(
                f"{CLOUD_URL}/api/v0/agent/heartbeat",
                json={
                    "device_id": dev_id,
                    "tunnel_state": "connected",
                    "metrics": {
                        "uptime_seconds": uptime,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                },
            )
            if resp.status_code == 200:
                if consecutive_failures > 0:
                    log.info("Heartbeat restored after %d failure(s)", consecutive_failures)
                consecutive_failures = 0
                log.debug("Heartbeat OK (uptime %ds)", uptime)
                # Write timestamp for Local API /status endpoint
                try:
                    Path("/tmp/myxon_last_heartbeat").write_text(
                        datetime.now(timezone.utc).isoformat()
                    )
                except OSError:
                    pass
                # Process SMS notifications queued by the server.
                # Server includes these when a new alarm needs GSM notification.
                data = resp.json()
                pending_sms = data.get("pending_sms", [])
                if pending_sms:
                    log.info("Received %d pending SMS from server", len(pending_sms))
                    for sms in pending_sms:
                        await send_sms(sms.get("to", ""), sms.get("message", ""))
            else:
                consecutive_failures += 1
                log.warning("Heartbeat HTTP %d (failure #%d)", resp.status_code, consecutive_failures)
        except httpx.RequestError as e:
            consecutive_failures += 1
            if consecutive_failures <= 3:
                log.warning("Heartbeat failed (failure #%d): %s", consecutive_failures, e)
            elif consecutive_failures % 10 == 0:
                # Only log every 10 failures after the first 3 to avoid log spam
                # during prolonged server unavailability (e.g. 4G dropout)
                log.error(
                    "Server unreachable for ~%ds (failure #%d). "
                    "Agent running in local-only mode.",
                    consecutive_failures * HEARTBEAT_INTERVAL,
                    consecutive_failures,
                )

        await asyncio.sleep(HEARTBEAT_INTERVAL)


# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    global running, SERIAL_NUMBER, _agent_token

    def handle_signal(sig, _frame):
        global running
        log.info("Signal %s — shutting down...", sig)
        running = False

    signal.signal(signal.SIGINT,  handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    log.info("MYXON Agent v0.2 starting")
    log.info("  server : %s", CLOUD_URL)

    frpc_proc: subprocess.Popen | None = None

    # ── Step 1: Discover controllers ──────────────────────────────────────────
    resources = await resolve_resources()

    # If nothing found yet — still register (resources = []) and retry discovery
    async with httpx.AsyncClient(timeout=10) as client:

        # ── Step 2: Choose registration flow ──────────────────────────────────
        #
        # Priority order:
        #  A. DEVICE_STATE_FILE exists → already activated; use stored serial + token
        #  B. MYXON_ACTIVATION_CODE set → first boot; call /activate endpoint
        #  C. MYXON_SERIAL set (legacy) → pre-registered flow; call /register
        #
        device_id = None
        tunnel_config = None

        existing_state = _load_device_state()

        if existing_state:
            # ── Flow A: Already activated — restore identity and re-register ──
            SERIAL_NUMBER = existing_state["serial_number"]
            _agent_token  = existing_state["frpc_token"]
            _save_token(_agent_token)  # Sync TOKEN_FILE with state file
            log.info("Restored device identity: serial=%s", SERIAL_NUMBER)
            log.info("Using /register flow (state file found)")

            async def _try_register():
                did, tc = await register(client, resources)
                return (did, tc) if did else None

            device_id, tunnel_config = await _retry_until_success(
                _try_register, label="register"
            )

        elif ACTIVATION_CODE:
            # ── Flow B: First boot with activation code ────────────────────────
            # Activation codes are one-time-use. We stop retrying on permanent
            # errors (409 Conflict = already used, 410 Gone = expired/revoked).
            log.info("Activation code present — using /activate flow")
            log.info("  code : %s", ACTIVATION_CODE[:4] + "-****-****-****")  # Mask for logs

            async def _try_activate():
                dev_id, serial, tc = await activate(client, resources, ACTIVATION_CODE)
                if dev_id:
                    # Persist identity so next reboot uses Flow A
                    _save_device_state(dev_id, serial, _agent_token or "")
                    return (dev_id, tc)
                return None

            device_id, tunnel_config = await _retry_until_success(
                _try_activate, label="activate"
            )

        else:
            # ── Flow C: Legacy pre-registered serial flow ──────────────────────
            log.info("  serial : %s", SERIAL_NUMBER)
            log.info("Using legacy /register flow (MYXON_SERIAL)")

            async def _try_register_legacy():
                did, tc = await register(client, resources)
                return (did, tc) if did else None

            device_id, tunnel_config = await _retry_until_success(
                _try_register_legacy, label="register (legacy)"
            )

        # At this point device_id is always set — _retry_until_success never returns None

        # ── Step 3: Start tunnel ──────────────────────────────────────────────
        if tunnel_config and tunnel_config.get("assigned_port") and resources:
            frpc_proc = start_frpc(tunnel_config, resources)
        elif not resources:
            log.warning("No controllers discovered yet — tunnel not started. "
                        "Will retry discovery in %ds.", DISCOVERY_INTERVAL)
        else:
            log.warning("No tunnel port assigned — running heartbeat-only mode.")

        # ── Step 4: Concurrent heartbeat + periodic re-discovery ──────────────
        async def rediscovery_loop():
            """Re-scan LAN periodically. Restart tunnel if new devices appear."""
            nonlocal frpc_proc, resources
            while running:
                await asyncio.sleep(DISCOVERY_INTERVAL)
                if not running:
                    break

                log.info("Re-scanning LAN for controllers...")
                new_resources = await resolve_resources()

                if new_resources and new_resources != resources:
                    log.info("Controllers changed — re-registering and restarting tunnel.")
                    resources = new_resources

                    new_did, new_tc = await register(client, resources)
                    if new_did and new_tc and new_tc.get("assigned_port"):
                        stop_frpc(frpc_proc)
                        frpc_proc = start_frpc(new_tc, resources)

        await asyncio.gather(
            heartbeat_loop(client, device_id),
            rediscovery_loop(),
        )

    # ── Cleanup ───────────────────────────────────────────────────────────────
    stop_frpc(frpc_proc)
    log.info("Agent stopped.")


if __name__ == "__main__":
    asyncio.run(main())
