"""
Cursor-based pagination utilities for MYXON API.

Design:
  - Cursor encodes the last item's sort key(s) as base64-JSON
  - Endpoints accept ?cursor=... and ?limit=N (default 50, max 200)
  - Response: { items: [...], next_cursor: str | None }
    next_cursor is None when there are no more pages

Usage (keyset pagination example):
    cursor_data = decode_cursor(cursor)
    if cursor_data:
        query = query.where(
            or_(
                Model.created_at < cursor_data["ts"],
                and_(Model.created_at == cursor_data["ts"], Model.id < cursor_data["id"])
            )
        )
    rows = await db.execute(query.limit(limit + 1))
    items = rows.scalars().all()
    next_cursor = None
    if len(items) > limit:
        last = items[limit - 1]
        next_cursor = encode_cursor({"ts": last.created_at.isoformat(), "id": str(last.id)})
        items = items[:limit]
"""
from __future__ import annotations

import base64
import json
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PagedOut(BaseModel, Generic[T]):
    """Paginated response wrapper."""
    items: list[T]
    next_cursor: str | None = None

    model_config = {"arbitrary_types_allowed": True}


def encode_cursor(data: dict) -> str:
    """Encode cursor data dict → URL-safe base64 string."""
    return base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode()


def decode_cursor(cursor: str | None) -> dict | None:
    """Decode cursor string → dict. Returns None on any error."""
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode() + b"==")  # pad
        data = json.loads(raw.decode())
        return data if isinstance(data, dict) else None
    except Exception:
        return None
