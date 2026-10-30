"""Accept requests only for expected host names (blocks Host-header attacks).

Patterns: an exact name ("localhost") or a wildcard suffix ("*.vercel.app", which matches any
subdomain but not the bare domain). The port is ignored.
"""
from __future__ import annotations

from typing import Iterable

from .common import get_header, send_error


def _strip_port(host: str) -> str:
    host = host.strip().lower()
    if host.startswith("["):                      # IPv6 literal such as [::1]:8000
        end = host.find("]")
        return host[: end + 1] if end != -1 else host
    return host.split(":", 1)[0]


class TrustedHostMiddleware:
    def __init__(self, app, allowed_hosts: Iterable[str]) -> None:
        self.app = app
        patterns = [h.strip().lower() for h in allowed_hosts if h.strip()]
        self.exact = {h for h in patterns if not h.startswith("*.")}
        self.suffixes = tuple(h[1:] for h in patterns if h.startswith("*."))   # ".vercel.app"

    def _allowed(self, host: str) -> bool:
        if host in self.exact:
            return True
        return any(host.endswith(s) and len(host) > len(s) for s in self.suffixes)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        raw = get_header(scope, "host")
        if not raw or not self._allowed(_strip_port(raw)):
            await send_error(send, scope, 400, "invalid_host", "Invalid host header.")
            return
        await self.app(scope, receive, send)