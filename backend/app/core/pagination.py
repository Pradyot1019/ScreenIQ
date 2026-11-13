"""Cursor pagination (spec Section 8: `?cursor=&limit=`).

Why cursors instead of `?page=3`: OFFSET pagination makes the database skip rows one by
one (slow on big tables), and if a new job is created while you're paging, every later
page shifts and you see a duplicate. A cursor says "continue after (created_at, id) of
the last item you saw", which the index finds directly and which new rows can't shift.

The cursor is opaque to clients (base64 JSON): they pass back `next_cursor` unchanged
and never build one themselves, so we're free to change its contents later.
"""

import base64
import binascii
import json
import uuid
from datetime import datetime

from app.core.errors import AppError


class InvalidCursorError(AppError):
    status, type_, title = 422, "invalid-cursor", "Invalid pagination cursor"


def encode_cursor(created_at: datetime, id_: uuid.UUID) -> str:
    raw = json.dumps({"t": created_at.isoformat(), "id": str(id_)}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        return datetime.fromisoformat(data["t"]), uuid.UUID(data["id"])
    except (binascii.Error, ValueError, KeyError, TypeError) as e:
        raise InvalidCursorError("The cursor is malformed. Use next_cursor as returned.") from e
