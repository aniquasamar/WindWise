"""API tests: routing, validation, error format, caching headers and response shape."""
import pytest

from app.container import get_service

V1 = "/api/v1"
DATA_ENDPOINTS = [
    f"{V1}/meta",
    f"{V1}/forecast?delivery_date=2026-01-20",
    f"{V1}/accuracy/summary",
    f"{V1}/accuracy/intervals",
    f"{V1}/accuracy/by-hour",
    f"{V1}/accuracy/by-day",
    f"{V1}/accuracy/by-forecast-level",
    f"{V1}/accuracy/distribution",
    f"{V1}/accuracy/horizon",
    f"{V1}/accuracy/horizon?view=full",
    f"{V1}/accuracy/runs",
    f"{V1}/accuracy/benchmarks",
    f"{V1}/buffer/backtest",
]


def test_health(client):
    r = client.get(f"{V1}/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert r.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("url", DATA_ENDPOINTS)
def test_data_endpoints_return_json_with_cache_headers(client, url):
    r = client.get(url)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/json")
    assert "public" in r.headers["cache-control"] and "s-maxage" in r.headers["cache-control"]


def test_meta_contents(client):
    body = client.get(f"{V1}/meta").json()
    assert body["window"]["first_delivery"] == "2026-01-02" and body["window"]["last_delivery"] == "2026-02-01"
    assert body["defaults"]["cutoff"] == "09:00" and body["allowed"]["confidence"] == [0.8, 0.9, 0.95]
    assert "forecast - actual" in body["sign_convention"]


def test_forecast_shape_and_values(client):
    body = client.get(f"{V1}/forecast?delivery_date=2026-01-20&cutoff=09:00&confidence=0.9").json()
    assert body["delivery_date"] == "2026-01-20" and body["decision_date"] == "2026-01-19"
    assert len(body["points"]) == 24 and body["counts"]["missing_forecast"] == 0
    assert body["runs_used"][0]["publish_time"] == "2026-01-19T07:30:00Z"
    first = body["points"][0]
    assert set(first) == {"time", "forecast_mw", "actual_mw", "error_mw", "horizon_h", "baseline_mw", "firm_mw", "corrected_mw"}


def test_forecast_cutoff_selects_a_different_run(client):
    body = client.get(f"{V1}/forecast?delivery_date=2026-01-20&cutoff=05:00").json()
    assert body["runs_used"][0]["publish_time"] == "2026-01-19T04:30:00Z"


def test_summary_values(client):
    body = client.get(f"{V1}/accuracy/summary").json()
    assert body["metrics"]["n"] == 744 and body["range"]["n_days"] == 31
    assert body["backtest"]["days_scored"] == 23 and body["backtest"]["days_skipped"] == 8
    assert len(body["insights"]) >= 4


@pytest.mark.parametrize(
    "url",
    [
        f"{V1}/forecast",                                              # missing delivery_date
        f"{V1}/forecast?delivery_date=2026-01-01",                     # before the window
        f"{V1}/forecast?delivery_date=2026-02-02",                     # after the window
        f"{V1}/forecast?delivery_date=not-a-date",
        f"{V1}/forecast?delivery_date=2026-01-20&cutoff=25:00",
        f"{V1}/forecast?delivery_date=2026-01-20&cutoff=09:10",        # not a 15-minute step
        f"{V1}/forecast?delivery_date=2026-01-20&cutoff=02:00",        # outside the allowed hours
        f"{V1}/forecast?delivery_date=2026-01-20&confidence=0.7",
        f"{V1}/forecast?delivery_date=2026-01-20&confidence=abc",
        f"{V1}/accuracy/summary?from=2026-01-20&to=2026-01-10",        # reversed
        f"{V1}/accuracy/summary?from=2025-12-01",                      # outside the window
        f"{V1}/accuracy/summary?bogus=1",                              # unknown parameter
        f"{V1}/accuracy/horizon?view=nope",
        f"{V1}/meta?anything=1",
        f"{V1}/health?x=1",
    ],
)
def test_bad_input_gets_a_clean_422(client, url):
    r = client.get(url)
    assert r.status_code == 422, r.text
    err = r.json()["error"]
    assert set(err) == {"code", "message", "request_id"}
    assert err["code"] in {"validation_error", "unknown_parameter"} and isinstance(err["message"], str)
    assert "Traceback" not in r.text


def test_unknown_route_is_json_404(client):
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
    assert r.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("url", ["/api/v1/health"] + DATA_ENDPOINTS)
def test_the_api_is_read_only(client, url):
    path = url.split("?")[0]
    for method in ("post", "put", "patch", "delete"):
        r = getattr(client, method)(path)
        assert r.status_code == 405, (method, path)
        assert r.json()["error"]["code"] == "method_not_allowed"


def test_internal_errors_leak_nothing(client):
    def boom():
        raise RuntimeError("secret detail at C:\\private\\path.py")

    client.app.dependency_overrides[get_service] = boom
    try:
        r = client.get(f"{V1}/meta")
    finally:
        client.app.dependency_overrides.clear()
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    for leaked in ("secret", "RuntimeError", "Traceback", "private", ".py"):
        assert leaked not in r.text


def test_openapi_and_docs_are_available(client):
    spec = client.get("/api/openapi.json")
    assert spec.status_code == 200
    body = spec.json()
    assert "/api/v1/forecast" in body["paths"] and "ForecastOut" in body["components"]["schemas"]
    docs = client.get("/api/docs")
    assert docs.status_code == 200 and docs.headers["content-type"].startswith("text/html")