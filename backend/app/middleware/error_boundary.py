"""Last line of defence: turn any unexpected exception into the standard 500 JSON response.

It sits closest to the application but INSIDE the other middleware, so even error responses
get the request ID and the security headers. Details go to the server log only.
"""
from __future__ import annotations

import logging

from .common import send_error

log = logging.getLogger("app.errors")


class ErrorBoundaryMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def wrapper(message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, wrapper)
        except Exception:
            log.exception("unhandled error")           # traceback goes to the log, never to the client
            if started:
                raise                                   # a response is already on the wire: cannot replace it
            await send_error(send, scope, 500, "internal_error", "An unexpected error occurred.")