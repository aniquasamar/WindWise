"""Per-client rate limit: a sliding window of request times, kept in memory.

HONEST LIMITATION: counters live in this process. On a serverless platform requests are spread
over instances that do not share memory, so the limit there is best-effort. It is reliable on a
single process (local run and Docker). The health endpoint is exempt so monitoring never gets blocked.
"""
from __future__ import annotations

import math
import time
from collections import deque
from typing import Callable, Optional

from .common import get_header, send_error, set_headers


def client_ip(scope: dict, trust_proxy: bool) -> str:
    """Client address. The forwarded header is used only when a trusted proxy sets it."""
    if trust_proxy:
        forwarded = get_header(scope, "x-forwarded-for")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    client = scope.get("client")
    return client[0] if client else "unknown"


class RateLimitMiddleware:
    def __init__(
        self,
        app,
        limit: int,
        window_seconds: float = 60.0,
        trust_proxy: bool = False,
        exempt_paths: tuple[str, ...] = ("/api/v1/health",),
        clock: Callable[[], float] = time.monotonic,
        max_clients: int = 10_000,
    ) -> None:
        self.app = app
        self.limit = limit
        self.window = window_seconds
        self.trust_proxy = trust_proxy
        self.exempt = set(exempt_paths)
        self.clock = clock
        self.max_clients = max_clients
        self.hits: dict[str, deque] = {}

    def _prune(self, now: float) -> None:
        cutoff = now - self.window
        for ip in [ip for ip, dq in self.hits.items() if not dq or dq[-1] <= cutoff]:
            del self.hits[ip]
        if len(self.hits) > self.max_clients:      # still too many distinct clients: start afresh (fail open)
            self.hits.clear()

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope.get("path") in self.exempt:
            await self.app(scope, receive, send)
            return

        now = self.clock()
        if len(self.hits) > self.max_clients:
            self._prune(now)
        ip = client_ip(scope, self.trust_proxy)
        dq = self.hits.setdefault(ip, deque())
        while dq and dq[0] <= now - self.window:
            dq.popleft()

        if len(dq) >= self.limit:
            retry = max(1, math.ceil(dq[0] + self.window - now))
            await send_error(
                send, scope, 429, "rate_limited", "Too many requests. Please try again shortly.",
                [("Retry-After", str(retry)), ("RateLimit-Limit", str(self.limit)), ("RateLimit-Remaining", "0"),
                 ("RateLimit-Reset", str(retry))],
            )
            return

        dq.append(now)
        remaining = self.limit - len(dq)
        reset = max(1, math.ceil(dq[0] + self.window - now))
        info = [("RateLimit-Limit", str(self.limit)), ("RateLimit-Remaining", str(remaining)), ("RateLimit-Reset", str(reset))]

        async def send_with_info(message) -> None:
            if message["type"] == "http.response.start":
                set_headers(message, info)
            await send(message)

        await self.app(scope, receive, send_with_info)