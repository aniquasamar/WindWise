"""Middleware tests. Pure ASGI: the apps are tiny fakes, so these need no web framework."""
import json
import logging

import pytest

from app.middleware.access_log import AccessLogMiddleware
from app.middleware.error_boundary import ErrorBoundaryMiddleware
from app.middleware.etag import ETagMiddleware, matches
from app.middleware.rate_limit import RateLimitMiddleware, client_ip
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.security_headers import API_CSP, DOCS_CSP, SecurityHeadersMiddleware
from app.middleware.trusted_host import TrustedHostMiddleware
from asgi_harness import call, failing_after_start_app, failing_app, json_app


# ----------------------------------------------------------------------------- request id
def test_request_id_is_generated_and_returned():
    r = call(RequestIdMiddleware(json_app()))
    rid = r.headers["x-request-id"]
    assert len(rid) == 32 and rid.isalnum()
    assert r.scope["state"]["request_id"] == rid


def test_a_safe_incoming_request_id_is_kept():
    r = call(RequestIdMiddleware(json_app()), headers={"X-Request-ID": "abc-123_XYZ.789"})
    assert r.headers["x-request-id"] == "abc-123_XYZ.789"


@pytest.mark.parametrize("bad", ["short", "has space in it!", "x" * 65, "semi;colon-in-it", "<script>alert(1)</script>"])
def test_an_unsafe_incoming_request_id_is_replaced(bad):
    r = call(RequestIdMiddleware(json_app()), headers={"X-Request-ID": bad})
    assert r.headers["x-request-id"] != bad and len(r.headers["x-request-id"]) == 32


def test_each_request_gets_a_different_id():
    app = RequestIdMiddleware(json_app())
    assert call(app).headers["x-request-id"] != call(app).headers["x-request-id"]


# ----------------------------------------------------------------------------- security headers
def test_security_headers_on_a_normal_response():
    r = call(SecurityHeadersMiddleware(json_app()))
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["content-security-policy"] == API_CSP
    assert "strict-transport-security" not in r.headers        # plain http: HSTS is meaningless


def test_security_headers_also_cover_error_responses():
    r = call(SecurityHeadersMiddleware(json_app(b'{"error":{}}', status=404)))
    assert r.status == 404 and r.headers["x-content-type-options"] == "nosniff"


def test_hsts_only_over_https():
    app = SecurityHeadersMiddleware(json_app())
    assert "max-age=31536000" in call(app, scheme="https").headers["strict-transport-security"]
    assert "strict-transport-security" in call(app, headers={"X-Forwarded-Proto": "https"}).headers
    assert "strict-transport-security" not in call(app, headers={"X-Forwarded-Proto": "http"}).headers


def test_docs_page_gets_the_looser_policy_only():
    app = SecurityHeadersMiddleware(json_app())
    assert call(app, path="/api/docs").headers["content-security-policy"] == DOCS_CSP
    assert call(app, path="/api/v1/meta").headers["content-security-policy"] == API_CSP
    assert "frame-ancestors 'none'" in DOCS_CSP


def test_security_headers_replace_conflicting_values():
    r = call(SecurityHeadersMiddleware(json_app(extra=[(b"x-frame-options", b"ALLOWALL")])))
    assert r.headers["x-frame-options"] == "DENY"


# ----------------------------------------------------------------------------- trusted host
HOSTS = ["localhost", "127.0.0.1", "*.vercel.app", "wind.example.com"]


def host_call(host):
    app = TrustedHostMiddleware(json_app(), HOSTS)
    return call(app, headers={"Host": host} if host is not None else {})


@pytest.mark.parametrize("host", ["localhost", "localhost:8000", "127.0.0.1:8000", "wind.example.com",
                                  "my-app-abc.vercel.app", "A.VERCEL.APP", "wind.example.com:443"])
def test_expected_hosts_pass(host):
    assert host_call(host).status == 200


@pytest.mark.parametrize("host", ["evil.example", "vercel.app", "evilvercel.app", "localhost.evil.com",
                                  "wind.example.com.evil.com", "", None])
def test_other_hosts_are_rejected_with_json(host):
    r = host_call(host)
    assert r.status == 400 and r.headers["content-type"] == "application/json"
    assert r.json()["error"]["code"] == "invalid_host"


# ----------------------------------------------------------------------------- rate limit
class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def limited(limit=3, **kw):
    clock = kw.pop("clock", None) or Clock()
    return RateLimitMiddleware(json_app(), limit=limit, window_seconds=60.0, clock=clock, **kw), clock


def test_requests_within_the_limit_pass_and_report_remaining():
    app, _ = limited(3)
    first = call(app, path="/api/v1/meta")
    assert first.status == 200 and first.headers["ratelimit-limit"] == "3" and first.headers["ratelimit-remaining"] == "2"
    assert call(app, path="/api/v1/meta").headers["ratelimit-remaining"] == "1"


def test_the_request_over_the_limit_gets_429_with_retry_after():
    app, clock = limited(3)
    for _ in range(3):
        assert call(app, path="/api/v1/meta").status == 200
    clock.t += 10
    r = call(app, path="/api/v1/meta")
    assert r.status == 429 and r.headers["retry-after"] == "50"      # the oldest hit leaves the window in 50 s
    assert r.json()["error"]["code"] == "rate_limited" and r.headers["ratelimit-remaining"] == "0"


def test_the_window_slides_so_requests_are_allowed_again():
    app, clock = limited(2)
    call(app, path="/x")
    call(app, path="/x")
    assert call(app, path="/x").status == 429
    clock.t += 61
    assert call(app, path="/x").status == 200


def test_each_client_has_its_own_counter():
    app, _ = limited(1)
    assert call(app, path="/x", client=("198.51.100.1", 1)).status == 200
    assert call(app, path="/x", client=("198.51.100.2", 1)).status == 200
    assert call(app, path="/x", client=("198.51.100.1", 2)).status == 429


def test_the_health_endpoint_is_exempt():
    app, _ = limited(1)
    for _ in range(5):
        assert call(app, path="/api/v1/health").status == 200


def test_forwarded_header_is_ignored_unless_the_proxy_is_trusted():
    untrusted, _ = limited(1, trust_proxy=False)
    assert call(untrusted, path="/x", headers={"X-Forwarded-For": "1.1.1.1"}).status == 200
    assert call(untrusted, path="/x", headers={"X-Forwarded-For": "2.2.2.2"}).status == 429   # same socket address

    trusted, _ = limited(1, trust_proxy=True)
    assert call(trusted, path="/x", headers={"X-Forwarded-For": "1.1.1.1, 10.0.0.1"}).status == 200
    assert call(trusted, path="/x", headers={"X-Forwarded-For": "2.2.2.2"}).status == 200
    assert call(trusted, path="/x", headers={"X-Forwarded-For": "1.1.1.1"}).status == 429


def test_client_ip_falls_back_to_the_socket_address():
    scope = {"headers": [], "client": ("192.0.2.7", 1)}
    assert client_ip(scope, trust_proxy=True) == "192.0.2.7"
    assert client_ip({"headers": []}, trust_proxy=False) == "unknown"


def test_memory_is_bounded():
    app, clock = limited(5, max_clients=3)
    for i in range(10):
        call(app, path="/x", client=(f"198.51.100.{i}", 1))
        clock.t += 100                                   # every earlier client has expired
    assert len(app.hits) <= 4


# ----------------------------------------------------------------------------- etag
BODY = b'{"value":42}'


def test_etag_is_added_to_a_json_200_and_is_stable():
    app = ETagMiddleware(json_app(BODY))
    a, b = call(app), call(app)
    assert a.status == 200 and a.body == BODY and a.headers["etag"].startswith('W/"')
    assert a.headers["etag"] == b.headers["etag"]
    assert ETagMiddleware(json_app(b'{"value":43}')) is not None
    assert call(ETagMiddleware(json_app(b'{"value":43}'))).headers["etag"] != a.headers["etag"]


def test_a_matching_if_none_match_gets_304_with_no_body():
    app = ETagMiddleware(json_app(BODY, extra=[(b"cache-control", b"public, max-age=300")]))
    etag = call(app).headers["etag"]
    r = call(app, headers={"If-None-Match": etag})
    assert r.status == 304 and r.body == b"" and r.headers["etag"] == etag
    assert r.headers["cache-control"] == "public, max-age=300" and "content-length" not in r.headers


def test_if_none_match_variants():
    app = ETagMiddleware(json_app(BODY))
    etag = call(app).headers["etag"]
    assert call(app, headers={"If-None-Match": "*"}).status == 304
    assert call(app, headers={"If-None-Match": f'"nope", {etag}'}).status == 304
    assert call(app, headers={"If-None-Match": etag.replace("W/", "")}).status == 304     # weak comparison
    other = call(app, headers={"If-None-Match": 'W/"different"'})
    assert other.status == 200 and other.body == BODY


def test_etag_leaves_other_responses_alone():
    assert "etag" not in call(ETagMiddleware(json_app(BODY, status=422))).headers
    assert "etag" not in call(ETagMiddleware(json_app(b"<html>", content_type=b"text/html"))).headers
    assert "etag" not in call(ETagMiddleware(json_app(BODY)), method="POST").headers


def test_matches_helper():
    assert matches('W/"a"', 'W/"a"') and matches('"a"', 'W/"a"') and matches("*", 'W/"a"')
    assert not matches(None, 'W/"a"') and not matches('W/"b"', 'W/"a"')


# ----------------------------------------------------------------------------- error boundary
def test_unexpected_errors_become_a_clean_500():
    r = call(ErrorBoundaryMiddleware(failing_app()))
    assert r.status == 500 and r.json()["error"]["code"] == "internal_error"
    for leaked in ("secret", "RuntimeError", "private", ".py", "Traceback"):
        assert leaked not in r.body.decode()


def test_error_responses_still_get_the_request_id_and_security_headers():
    stack = RequestIdMiddleware(SecurityHeadersMiddleware(ErrorBoundaryMiddleware(failing_app())))
    r = call(stack)
    assert r.status == 500
    assert r.headers["x-request-id"] and r.headers["x-content-type-options"] == "nosniff"
    assert r.json()["error"]["request_id"] == r.headers["x-request-id"]


def test_the_error_is_logged_server_side_with_its_detail():
    records = []

    class Grab(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger("app.errors")
    handler = Grab()
    logger.addHandler(handler)
    try:
        call(ErrorBoundaryMiddleware(failing_app("boom-detail")))
    finally:
        logger.removeHandler(handler)
    assert records and records[0].exc_info is not None and "boom-detail" in str(records[0].exc_info[1])


def test_a_failure_after_the_response_started_is_not_swallowed():
    with pytest.raises(RuntimeError):
        call(ErrorBoundaryMiddleware(failing_after_start_app()))


# ----------------------------------------------------------------------------- access log
def capture_access_log():
    lines = []

    class Grab(logging.Handler):
        def emit(self, record):
            lines.append(record.getMessage())

    logger = logging.getLogger("app.access")
    handler = Grab()
    old_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return lines, lambda: (logger.removeHandler(handler), logger.setLevel(old_level))


def test_one_json_line_per_request_without_sensitive_data():
    lines, restore = capture_access_log()
    try:
        app = RequestIdMiddleware(AccessLogMiddleware(json_app()))
        r = call(app, path="/api/v1/meta", headers={"Authorization": "Bearer top-secret", "Cookie": "sid=1"})
    finally:
        restore()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["event"] == "request" and entry["method"] == "GET" and entry["path"] == "/api/v1/meta"
    assert entry["status"] == 200 and entry["request_id"] == r.headers["x-request-id"] and entry["duration_ms"] >= 0
    assert "top-secret" not in lines[0] and "203.0.113.9" not in lines[0] and "sid=1" not in lines[0]


def test_failures_are_logged_as_500_and_still_raise():
    lines, restore = capture_access_log()
    try:
        with pytest.raises(RuntimeError):
            call(AccessLogMiddleware(failing_app()))
    finally:
        restore()
    assert json.loads(lines[0])["status"] == 500


# ----------------------------------------------------------------------------- the whole stack, in order
def test_stack_order_gives_every_response_the_full_set_of_headers():
    inner = ErrorBoundaryMiddleware(ETagMiddleware(json_app(BODY, extra=[(b"cache-control", b"public")])))
    stack = RequestIdMiddleware(AccessLogMiddleware(TrustedHostMiddleware(
        SecurityHeadersMiddleware(RateLimitMiddleware(inner, limit=1, window_seconds=60.0, clock=Clock())),
        ["localhost"],
    )))
    ok = call(stack, path="/api/v1/meta", headers={"Host": "localhost"})
    limited_ = call(stack, path="/api/v1/meta", headers={"Host": "localhost"})
    bad_host = call(stack, path="/api/v1/meta", headers={"Host": "evil.example"})
    assert (ok.status, limited_.status, bad_host.status) == (200, 429, 400)
    for r in (ok, limited_, bad_host):
        assert r.headers["x-request-id"]                      # RequestId is outermost: always present
    for r in (ok, limited_):
        assert r.headers["x-content-type-options"] == "nosniff"   # SecurityHeaders wraps the limiter: 429 is covered
    assert ok.headers["etag"]