"""
Guacamole connection manager.

Manages dynamic connection configuration for Apache Guacamole (guacd).
When a user requests web access to a device resource, this service:
  1. Resolves the target host/port via the device's tunnel port
  2. Generates a guacamole-compatible connection token
  3. Returns the access URL for the frontend iframe/embed

Architecture:
  - guacd runs as a Docker container (port 4822)
  - Nginx proxies /guacamole/websocket-tunnel → guacd
  - This service generates connection parameters that the
    guacamole-lite or guacamole-client uses to connect
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from base64 import b64encode
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)

# Connection token signing key (in production, use a proper secret)
_SIGNING_KEY = settings.secret_key.encode()


@dataclass
class GuacamoleConnection:
    """A resolved guacamole connection ready for the client."""
    connection_id: str
    access_url: str
    protocol: str
    hostname: str
    port: int
    expires_at: int  # Unix timestamp


def _sign_token(payload: dict) -> str:
    """
    Sign a connection token for guacamole-lite / custom auth extension.

    The token encodes connection parameters (protocol, hostname, port, etc.)
    so that the Guacamole client can establish the connection without
    needing a full Guacamole server with DB-backed auth.
    """
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    sig = hmac.new(_SIGNING_KEY, raw.encode(), hashlib.sha256).hexdigest()
    token_data = {"d": payload, "s": sig}
    return b64encode(json.dumps(token_data).encode()).decode()


def create_guacamole_connection(
    device_serial: str,
    resource_id: str,
    protocol: str,
    tunnel_port: int | None,
    resource_host: str = "127.0.0.1",
    resource_port: int | None = None,
    ttl_minutes: int = 30,
) -> GuacamoleConnection:
    """
    Create a guacamole connection for a device resource.

    For VNC: connects to the device's tunnel_port where FRPC
    forwards VNC traffic from the device LAN.

    For HTTP: generates a URL that Nginx proxies through the tunnel.
    """
    # Determine target
    if tunnel_port is None:
        raise ValueError("Device has no tunnel port allocated")

    # The tunnel_port on FRPS corresponds to the device's forwarded service
    hostname = settings.guacd_host  # guacd connects to frps-exposed port
    target_port = resource_port or tunnel_port

    # For guacd, the connection is:
    #   guacd -> localhost:{tunnel_port} -> (FRPS tunnel) -> device LAN resource
    # Since guacd and frps are on the same Docker network, use frps hostname
    guacd_target_host = "frps"
    guacd_target_port = target_port

    now = int(time.time())
    expires = now + (ttl_minutes * 60)

    connection_id = f"{device_serial}-{resource_id}-{now}"

    # Build guacamole connection parameters
    guac_params: dict = {
        "protocol": protocol,
        "hostname": guacd_target_host,
        "port": str(guacd_target_port),
    }

    if protocol == "vnc":
        guac_params.update({
            "color-depth": "16",
            "cursor": "remote",
            "swap-red-blue": "false",
        })
    elif protocol == "http":
        # For HTTP web access, we generate a direct proxy URL
        # rather than going through guacd
        access_url = f"/tunnel/{device_serial}/{resource_id}/"
        return GuacamoleConnection(
            connection_id=connection_id,
            access_url=access_url,
            protocol=protocol,
            hostname=guacd_target_host,
            port=guacd_target_port,
            expires_at=expires,
        )

    # Sign the token
    token_payload = {
        "connection": guac_params,
        "exp": expires,
        "sub": connection_id,
    }
    token = _sign_token(token_payload)

    access_url = f"/guacamole/websocket-tunnel?token={token}"

    logger.info(
        "Created guacamole connection: id=%s protocol=%s target=%s:%d ttl=%dm",
        connection_id, protocol, guacd_target_host, guacd_target_port, ttl_minutes,
    )

    return GuacamoleConnection(
        connection_id=connection_id,
        access_url=access_url,
        protocol=protocol,
        hostname=guacd_target_host,
        port=guacd_target_port,
        expires_at=expires,
    )
