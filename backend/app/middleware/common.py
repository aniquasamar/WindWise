"""Small helpers shared by the middleware."""
from __future__ import annotations

import json
from typing import Iterable, Optional


def get_header(scope: dict, name: str) -> Optional[str]:
    """First request header called `name` (case-insensitive), or None."""
    target = name.lower().encode("latin-1")
    for key, value in scope.get("headers", []):
        if key == target:
            return value.decode("latin-1")
    return None


def set_headers(message: dict, pairs: Iterable[tuple[str, str]]) -> None:
    """Add or replace response headers on an `http.response.start` message."""
    items = list(pairs)
    names = {n.lower().encode("latin-1") for n, _ in items}
    headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in names]
    headers.extend((n.lower().encode("latin-1"), v.encode("latin-1")) for n, v in items)
    message["headers"] = headers


def request_id_of(scope: dict) -> Optional[str]:
    return scope.get("state", {}).get("request_id")


async def send_error(send, scope: dict, status: int, code: str, message: str, extra_headers: Iterable[tuple[str, str]] = ()) -> None:
    """Send the standard JSON error body. Used when a middleware answers a request itself."""
    body = json.dumps({"error": {"code": code, "message": message, "request_id": request_id_of(scope)}}).encode("utf-8")
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    headers.extend((n.lower().encode("latin-1"), v.encode("latin-1")) for n, v in extra_headers)
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})