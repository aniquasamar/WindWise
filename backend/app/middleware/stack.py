"""Installs the middleware in the right order.

Request path, outermost first:

  RequestId -> AccessLog -> TrustedHost -> CORS (only if origins are configured)
  -> SecurityHeaders -> RateLimit -> GZip -> ETag -> ErrorBoundary -> application

Starlette puts the LAST added middleware outermost, so they are added innermost-first below.
"""
from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.config import Settings

from .access_log import AccessLogMiddleware, configure_logging
from .error_boundary import ErrorBoundaryMiddleware
from .etag import ETagMiddleware
from .rate_limit import RateLimitMiddleware
from .request_id import RequestIdMiddleware
from .security_headers import SecurityHeadersMiddleware
from .trusted_host import TrustedHostMiddleware


def install_middleware(app: FastAPI, settings: Settings) -> None:
    configure_logging()
    app.add_middleware(ErrorBoundaryMiddleware)
    app.add_middleware(ETagMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    if settings.rate_limit_per_min > 0:
        app.add_middleware(RateLimitMiddleware, limit=settings.rate_limit_per_min, window_seconds=60.0,
                           trust_proxy=settings.trust_proxy)
    app.add_middleware(SecurityHeadersMiddleware)
    if settings.allowed_origins:
        # Off by default. With the front end and API on one origin, browsers need no CORS at all.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.allowed_origins),
            allow_methods=["GET"],
            allow_headers=["Accept", "Content-Type", "If-None-Match", "X-Request-ID"],
            expose_headers=["X-Request-ID", "ETag", "Retry-After"],
            allow_credentials=False,
            max_age=600,
        )
    if settings.allowed_hosts and "*" not in settings.allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)