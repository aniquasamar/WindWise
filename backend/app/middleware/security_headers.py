"""Standard browser-hardening headers on every response, including errors.

The API serves JSON only, so its Content-Security-Policy forbids everything. The interactive
documentation page is the one exception: it loads its viewer from a CDN and needs a looser policy.
"""
from __future__ import annotations

from .common import get_header, set_headers

API_CSP = "default-src 'none'; frame-ancestors 'none'"
DOCS_CSP = (
    "default-src 'none'; img-src 'self' data: https://fastapi.tiangolo.com; "
    "script-src 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'unsafe-inline' https://cdn.jsdelivr.net; "
    "connect-src 'self'; frame-ancestors 'none'"
)
HSTS = "max-age=31536000; includeSubDomains"


class SecurityHeadersMiddleware:
    def __init__(self, app, docs_prefix: str = "/api/docs") -> None:
        self.app = app
        self.docs_prefix = docs_prefix

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_docs = str(scope.get("path", "")).startswith(self.docs_prefix)
        forwarded = (get_header(scope, "x-forwarded-proto") or "").split(",")[0].strip().lower()
        https = scope.get("scheme") == "https" or forwarded == "https"

        headers = [
            ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "no-referrer"),
            ("X-Frame-Options", "DENY"),
            ("Content-Security-Policy", DOCS_CSP if is_docs else API_CSP),
        ]
        if https:
            headers.append(("Strict-Transport-Security", HSTS))

        async def send_with_headers(message) -> None:
            if message["type"] == "http.response.start":
                set_headers(message, headers)
            await send(message)

        await self.app(scope, receive, send_with_headers)