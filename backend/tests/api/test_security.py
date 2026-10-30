"""Security behaviour of the whole running application: headers, hosts, CORS, rate limit, ETag."""
import dataclasses

from fastapi.testclient import TestClient

from app.config import get_settings
from app.container import get_service
from app.main import create_app

V1 = "/api/v1"
SECURITY = {"x-content-type-options": "nosniff", "x-frame-options": "DENY", "referrer-policy": "no-referrer"}


def make_client(**overrides):
    """A separate app with different settings (call it after the `client` fixture has set the database)."""
    settings = dataclasses.replace(get_settings(), **overrides)
    return TestClient(create_app(settings), raise_server_exceptions=False)


def test_every_response_carries_a_request_id(client):
    for url in (f"{V1}/meta", f"{V1}/nope", f"{V1}/forecast?delivery_date=2026-01-01"):
        r = client.get(url)
        assert len(r.headers["x-request-id"]) >= 8, url


def test_error_bodies_repeat_the_request_id(client):
    r = client.get(f"{V1}/forecast?delivery_date=2026-01-01")
    assert r.status_code == 422
    assert r.json()["error"]["request_id"] == r.headers["x-request-id"]


def test_a_safe_client_request_id_is_echoed_and_an_unsafe_one_replaced(client):
    assert client.get(f"{V1}/meta", headers={"X-Request-ID": "my-trace-12345"}).headers["x-request-id"] == "my-trace-12345"
    replaced = client.get(f"{V1}/meta", headers={"X-Request-ID": "bad id!"}).headers["x-request-id"]
    assert replaced != "bad id!" and len(replaced) == 32


def test_security_headers_on_success_and_on_errors(client):
    for url in (f"{V1}/meta", f"{V1}/nope", f"{V1}/forecast?delivery_date=2026-01-01"):
        r = client.get(url)
        for name, value in SECURITY.items():
            assert r.headers[name] == value, (url, name)
        assert r.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"


def test_hsts_only_when_the_request_was_https(client):
    assert "strict-transport-security" not in client.get(f"{V1}/meta").headers
    assert "max-age" in client.get(f"{V1}/meta", headers={"X-Forwarded-Proto": "https"}).headers["strict-transport-security"]


def test_docs_page_has_the_looser_policy(client):
    r = client.get("/api/docs")
    assert r.status_code == 200 and "cdn.jsdelivr.net" in r.headers["content-security-policy"]


def test_internal_errors_still_carry_headers(client):
    def boom():
        raise RuntimeError("secret detail")

    client.app.dependency_overrides[get_service] = boom
    try:
        r = client.get(f"{V1}/meta")
    finally:
        client.app.dependency_overrides.clear()
    assert r.status_code == 500 and "secret" not in r.text
    assert r.headers["x-request-id"] and r.headers["x-content-type-options"] == "nosniff"
    assert r.json()["error"]["request_id"] == r.headers["x-request-id"]


def test_unexpected_hosts_are_rejected_with_json(client):
    r = client.get(f"{V1}/meta", headers={"Host": "evil.example"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_host"
    assert r.headers["x-request-id"]


def test_expected_hosts_are_accepted(client):
    for host in ("localhost:8000", "127.0.0.1", "my-project-abc.vercel.app"):
        assert client.get(f"{V1}/meta", headers={"Host": host}).status_code == 200, host


def test_no_cross_origin_access_by_default(client):
    r = client.get(f"{V1}/meta", headers={"Origin": "https://evil.example"})
    assert r.status_code == 200 and "access-control-allow-origin" not in r.headers


def test_cors_allows_only_the_configured_origin(client):
    app_client = make_client(allowed_origins=("http://localhost:5173",), rate_limit_per_min=0)
    ok = app_client.get(f"{V1}/meta", headers={"Origin": "http://localhost:5173"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    evil = app_client.get(f"{V1}/meta", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in evil.headers
    pre = app_client.options(
        f"{V1}/meta",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert pre.status_code == 200 and pre.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "GET" in pre.headers["access-control-allow-methods"] and "POST" not in pre.headers["access-control-allow-methods"]


def test_rate_limit_returns_429_with_retry_after(client):
    limited = make_client(rate_limit_per_min=5)
    for _ in range(5):
        assert limited.get(f"{V1}/meta").status_code == 200
    r = limited.get(f"{V1}/meta")
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
    assert r.json()["error"]["code"] == "rate_limited"
    assert r.headers["x-request-id"] and r.headers["x-content-type-options"] == "nosniff"
    assert limited.get(f"{V1}/health").status_code == 200            # health is exempt


def test_unchanged_responses_get_304(client):
    first = client.get(f"{V1}/accuracy/summary")
    etag = first.headers["etag"]
    assert etag.startswith('W/"')
    again = client.get(f"{V1}/accuracy/summary", headers={"If-None-Match": etag})
    assert again.status_code == 304 and again.content == b""
    assert "public" in again.headers["cache-control"]
    other = client.get(f"{V1}/accuracy/summary", headers={"If-None-Match": 'W/"something-else"'})
    assert other.status_code == 200 and other.headers["etag"] == etag


def test_large_responses_are_compressed(client):
    r = client.get(f"{V1}/accuracy/by-day", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200 and r.headers.get("content-encoding") == "gzip"