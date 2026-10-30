"""One structured (JSON) log line per request: id, method, path, status, duration.

Deliberately NOT logged: query strings, client addresses and headers.
"""
from __future__ import annotations

import json
import logging
import time

from .common import request_id_of

log = logging.getLogger("app.access")


def configure_logging() -> None:
    """Make the 'app' loggers print plain JSON lines (idempotent, safe under auto-reload)."""
    logger = logging.getLogger("app")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False


class AccessLogMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = {"code": 0}

        async def send_wrapper(message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            status["code"] = status["code"] or 500
            raise
        finally:
            log.info(
                json.dumps(
                    {
                        "event": "request",
                        "request_id": request_id_of(scope),
                        "method": scope.get("method"),
                        "path": str(scope.get("path", ""))[:200],
                        "status": status["code"],
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                )
            )