"""Gives every request an ID, available to handlers and returned in X-Request-ID.

A client-supplied ID is kept only if it looks safe (8 to 64 letters, digits, dot, dash or
underscore). Anything else is replaced, so odd input can never reach logs or response headers.
"""
from __future__ import annotations

import re
import uuid

from .common import get_header, set_headers

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class RequestIdMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = get_header(scope, "x-request-id")
        request_id = incoming if incoming and _SAFE_ID.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message) -> None:
            if message["type"] == "http.response.start":
                set_headers(message, [("X-Request-ID", request_id)])
            await send(message)

        await self.app(scope, receive, send_with_id)