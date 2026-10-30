"""ETag and conditional requests (304 Not Modified) for successful JSON GET responses.

The data never changes within a deployment, so a client that already holds a response can be told
"unchanged" without resending the body. ETags are weak (W/"...") because the body may be compressed
by a layer further out.
"""
from __future__ import annotations

import hashlib
from typing import Optional

from .common import get_header


def _opaque(tag: str) -> str:
    tag = tag.strip()
    return tag[2:] if tag.startswith("W/") else tag


def matches(if_none_match: Optional[str], etag: str) -> bool:
    if not if_none_match:
        return False
    if if_none_match.strip() == "*":
        return True
    return any(_opaque(t) == _opaque(etag) for t in if_none_match.split(","))


class ETagMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope.get("method") != "GET":
            await self.app(scope, receive, send)
            return
        if_none_match = get_header(scope, "if-none-match")
        held: dict = {"start": None, "passthrough": False}
        chunks: list[bytes] = []

        async def wrapper(message) -> None:
            if message["type"] == "http.response.start":
                headers = dict((k.lower(), v) for k, v in message.get("headers", []))
                is_json = headers.get(b"content-type", b"").startswith(b"application/json")
                if message["status"] == 200 and is_json:
                    held["start"] = message          # hold until the whole body is known
                else:
                    held["passthrough"] = True
                    await send(message)
                return
            if held["passthrough"] or held["start"] is None:
                await send(message)
                return
            chunks.append(message.get("body", b""))
            if message.get("more_body", False):
                return
            body = b"".join(chunks)
            etag = 'W/"' + hashlib.sha256(body).hexdigest()[:20] + '"'
            start = held["start"]
            if matches(if_none_match, etag):
                keep = [(k, v) for k, v in start.get("headers", []) if k.lower() == b"cache-control"]
                keep.append((b"etag", etag.encode()))
                await send({"type": "http.response.start", "status": 304, "headers": keep})
                await send({"type": "http.response.body", "body": b""})
                return
            headers_out = [(k, v) for k, v in start.get("headers", []) if k.lower() != b"etag"]
            headers_out.append((b"etag", etag.encode()))
            await send({**start, "headers": headers_out})
            await send({"type": "http.response.body", "body": body})

        await self.app(scope, receive, wrapper)