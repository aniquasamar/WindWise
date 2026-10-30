#!/usr/bin/env python3
"""Fetch Elexon wind actuals (FUELHH) and forecasts (WINDFOR); build backend/data/wind.sqlite.

Two stages, so the database can always be rebuilt offline from the saved raw files:

  fetch -> data/raw/*.json + data/raw/manifest.json   (needs network and `requests`)
  build -> backend/data/wind.sqlite                   (standard library only)

Usage (from the repository root):
  python scripts/ingest_elexon.py                  fetch, then build
  python scripts/ingest_elexon.py --build-only     rebuild the database from saved raw files
  python scripts/ingest_elexon.py --allow-issues   turn validation errors into warnings

The build fails loudly if any structural invariant is broken (gaps, duplicates,
nulls, wrong run counts). Nothing is silently repaired, filled or clamped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from datetime import time as dtime
from pathlib import Path

SCRIPT_VERSION = "1.0.0"
BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "backend" / "data" / "wind.sqlite"   # inside backend/ so it ships with the API

# ---------------------------------------------------------------------------
# Scope. Decisions are made 1-31 Jan 2026, so delivery days are 2 Jan - 1 Feb.
# The extra days at the start feed baselines and the full-horizon curve.
# The whole window is GMT (no clock change), so a UTC date equals the
# settlement date; the validation below relies on that.
# ---------------------------------------------------------------------------
ACTUALS_FIRST = date(2025, 12, 29)           # settlement dates, inclusive
ACTUALS_LAST = date(2026, 2, 1)
FORECAST_PUBLISH_FROM = date(2025, 12, 29)   # publishTime, inclusive (00:00Z)
FORECAST_PUBLISH_TO = date(2026, 2, 2)       # publishTime, exclusive (00:00Z)
CHUNK_DAYS = 7                               # window size that worked in exploration

# Structure observed in the data (see DATA_NOTES.md section 4).
EXPECTED_RUN_TIMES = {"02:30", "04:30", "07:30", "09:30", "11:30", "15:30", "18:30", "22:30"}
RUNS_PER_DAY = 8
TARGETS_PER_RUN = 73

SCHEMA = """
CREATE TABLE actuals_half_hourly (
  start_time        TEXT PRIMARY KEY,
  settlement_date   TEXT NOT NULL,
  settlement_period INTEGER NOT NULL CHECK (settlement_period BETWEEN 1 AND 50),
  wind_mw           INTEGER NOT NULL CHECK (wind_mw >= 0),
  published_at      TEXT NOT NULL
);
CREATE TABLE forecasts (
  publish_time TEXT NOT NULL,
  start_time   TEXT NOT NULL,
  wind_mw      INTEGER NOT NULL,
  PRIMARY KEY (publish_time, start_time)
) WITHOUT ROWID;
CREATE INDEX idx_forecasts_target ON forecasts (start_time, publish_time);
CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


class ValidationFailed(Exception):
    """Raised when the raw data breaks a structural invariant."""


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


# ---------------------------------------------------------------------------
# Time helpers (everything is stored as UTC text like 2026-01-15T10:30:00Z)
# ---------------------------------------------------------------------------
def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def fmt_ts(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_ts(s: str) -> str:
    return fmt_ts(parse_ts(s))


def utc_midnight(d: date) -> datetime:
    return datetime.combine(d, dtime(0, 0), tzinfo=timezone.utc)


def date_chunks(first: date, last: date, days: int):
    """Yield (start, end) date pairs, both inclusive, covering first..last."""
    a = first
    while a <= last:
        b = min(a + timedelta(days=days - 1), last)
        yield a, b
        a = b + timedelta(days=1)


# ---------------------------------------------------------------------------
# Stage 1: fetch
# ---------------------------------------------------------------------------
def http_get_json(session, path: str, params: dict, attempts: int = 4):
    """GET with retries and exponential backoff on network errors, 429 and 5xx."""
    url = f"{BASE_URL}{path}"
    err = ""
    for n in range(1, attempts + 1):
        try:
            r = session.get(url, params=params, timeout=90)
        except Exception as exc:  # network problem: retry
            err = repr(exc)
        else:
            if r.status_code == 200:
                body = r.json()
                return body["data"] if isinstance(body, dict) and "data" in body else body
            if r.status_code < 500 and r.status_code != 429:
                raise RuntimeError(f"HTTP {r.status_code} for {r.url}: {r.text[:300]}")
            err = f"HTTP {r.status_code}"
        if n == attempts:
            raise RuntimeError(f"giving up after {attempts} attempts: {err}")
        time.sleep(2**n)
    raise RuntimeError("unreachable")


def save_raw(raw_dir: Path, dataset: str, label: str, params: dict, rows: list) -> dict:
    """Write one raw chunk and return its manifest entry (with SHA-256)."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    name = f"{dataset}_{label}.json"
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    (raw_dir / name).write_bytes(payload)
    return {
        "dataset": dataset,
        "file": name,
        "params": params,
        "rows": len(rows),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def write_manifest(raw_dir: Path, files: list[dict], retrieved_at: str | None = None) -> dict:
    manifest = {
        "script_version": SCRIPT_VERSION,
        "base_url": BASE_URL,
        "retrieved_at": retrieved_at or fmt_ts(datetime.now(timezone.utc)),
        "actuals_window": f"{ACTUALS_FIRST}..{ACTUALS_LAST}",
        "forecast_publish_window": f"{FORECAST_PUBLISH_FROM}..{FORECAST_PUBLISH_TO} (end exclusive)",
        "files": files,
    }
    (raw_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def fetch_all(raw_dir: Path) -> None:
    import requests  # imported here so --build-only needs only the standard library

    session = requests.Session()
    session.headers.update(
        {"Accept": "application/json", "User-Agent": f"wind-portal-ingest/{SCRIPT_VERSION}"}
    )
    raw_dir.mkdir(parents=True, exist_ok=True)
    for old in raw_dir.glob("*.json"):
        old.unlink()

    files: list[dict] = []
    for a, b in date_chunks(ACTUALS_FIRST, ACTUALS_LAST, CHUNK_DAYS):
        params = {
            "settlementDateFrom": a.isoformat(),
            "settlementDateTo": b.isoformat(),
            "fuelType": "WIND",
        }
        rows = http_get_json(session, "/datasets/FUELHH/stream", params)
        files.append(save_raw(raw_dir, "FUELHH", f"{a}_{b}", params, rows))
        print(f"FUELHH  {a}..{b}: {len(rows)} rows")
        time.sleep(0.5)

    for a, b in date_chunks(FORECAST_PUBLISH_FROM, FORECAST_PUBLISH_TO - timedelta(days=1), CHUNK_DAYS):
        params = {
            "publishDateTimeFrom": f"{a.isoformat()}T00:00:00Z",
            "publishDateTimeTo": f"{(b + timedelta(days=1)).isoformat()}T00:00:00Z",
        }
        rows = http_get_json(session, "/datasets/WINDFOR/stream", params)
        files.append(save_raw(raw_dir, "WINDFOR", f"{a}_{b}", params, rows))
        print(f"WINDFOR {a}..{b}: {len(rows)} rows")
        time.sleep(0.5)

    write_manifest(raw_dir, files)
    print(f"Raw files and manifest written to {raw_dir}")


# ---------------------------------------------------------------------------
# Stage 2: validate and build
# ---------------------------------------------------------------------------
def load_raw(raw_dir: Path):
    manifest_path = raw_dir / "manifest.json"
    if not manifest_path.exists():
        raise ValidationFailed(f"{manifest_path} not found: run a fetch first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actuals: list[dict] = []
    forecasts: list[dict] = []
    for f in manifest["files"]:
        data = (raw_dir / f["file"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != f["sha256"]:
            raise ValidationFailed(f"hash mismatch for {f['file']}: raw file was modified")
        rows = json.loads(data)
        (actuals if f["dataset"] == "FUELHH" else forecasts).extend(rows)
    return manifest, actuals, forecasts


def clean_actuals(rows: list[dict], rep: Report):
    out: dict[str, tuple] = {}
    dups = 0
    nulls, negatives, date_mismatch = [], [], []
    other_fuel: Counter = Counter()

    for r in rows:
        if r.get("fuelType") != "WIND":
            other_fuel[r.get("fuelType")] += 1
            continue
        start = norm_ts(r["startTime"])
        g = r.get("generation")
        if g is None:
            nulls.append(start)
            continue
        if g < 0:
            negatives.append(start)
            continue
        if r["settlementDate"] != start[:10]:
            date_mismatch.append(start)
        rec = (start, r["settlementDate"], int(r["settlementPeriod"]), int(g), norm_ts(r["publishTime"]))
        if start in out:
            dups += 1
            if out[start][3] != rec[3]:
                rep.error(f"actuals: conflicting duplicate values at {start}")
            continue
        out[start] = rec

    if other_fuel:
        rep.error(f"actuals: unexpected fuel types {dict(other_fuel)}")
    if nulls:
        rep.error(f"actuals: {len(nulls)} null generation values, first {nulls[:3]}")
    if negatives:
        rep.error(f"actuals: {len(negatives)} negative generation values, first {negatives[:3]}")
    if date_mismatch:
        rep.error(f"actuals: {len(date_mismatch)} rows where settlementDate differs from the UTC date, "
                  f"first {date_mismatch[:3]} (window is assumed to be GMT)")

    n_days = (ACTUALS_LAST - ACTUALS_FIRST).days + 1
    first = utc_midnight(ACTUALS_FIRST)
    grid = {fmt_ts(first + timedelta(minutes=30 * i)) for i in range(n_days * 48)}
    missing = sorted(grid - set(out))
    extra = sorted(set(out) - grid)
    if missing:
        rep.error(f"actuals: {len(missing)} missing half-hours, first {missing[:5]}")
    if extra:
        rep.error(f"actuals: {len(extra)} rows outside the expected window, first {extra[:5]}")
    if dups:
        rep.warn(f"actuals: {dups} identical duplicate rows dropped")
    return list(out.values()), dups


def clean_forecasts(rows: list[dict], rep: Report):
    out: dict[tuple[str, str], int] = {}
    dups = 0
    nulls, negatives = [], []

    for r in rows:
        pub, start = norm_ts(r["publishTime"]), norm_ts(r["startTime"])
        g = r.get("generation")
        if g is None:
            nulls.append((pub, start))
            continue
        key = (pub, start)
        if key in out:
            dups += 1
            if out[key] != int(g):
                rep.error(f"forecasts: conflicting duplicate values at {key}")
            continue
        out[key] = int(g)
        if g < 0:
            negatives.append(key)

    if nulls:
        rep.error(f"forecasts: {len(nulls)} null generation values, first {nulls[:3]}")
    if negatives:
        rep.warn(f"forecasts: {len(negatives)} negative values kept as published, first {negatives[:3]}")
    if dups:
        rep.warn(f"forecasts: {dups} identical duplicate rows dropped")

    by_run: dict[str, list[str]] = defaultdict(list)
    for (pub, start) in out:
        by_run[pub].append(start)

    window_start = utc_midnight(FORECAST_PUBLISH_FROM)
    window_end = utc_midnight(FORECAST_PUBLISH_TO)
    unscheduled: list[str] = []
    runs_per_date: Counter = Counter()

    for pub in sorted(by_run):
        pub_dt = parse_ts(pub)
        starts = sorted(by_run[pub])
        runs_per_date[pub_dt.date()] += 1
        if not (window_start <= pub_dt < window_end):
            rep.error(f"forecasts: run {pub} is outside the publish window")
        if pub[11:16] not in EXPECTED_RUN_TIMES:
            unscheduled.append(pub)
        if len(starts) != TARGETS_PER_RUN:
            rep.error(f"forecasts: run {pub} has {len(starts)} targets, expected {TARGETS_PER_RUN}")
            continue
        times = [parse_ts(s) for s in starts]
        if any(b - a != timedelta(hours=1) for a, b in zip(times, times[1:])):
            rep.error(f"forecasts: run {pub} targets are not consecutive hours")
        exp_first = datetime.combine(pub_dt.date() - timedelta(days=1), dtime(21, 0), tzinfo=timezone.utc)
        if times[0] != exp_first:
            rep.warn(f"forecasts: run {pub} starts at {starts[0]}, expected {fmt_ts(exp_first)}")

    if unscheduled:
        rep.warn(f"forecasts: {len(unscheduled)} run(s) published at an unusual clock time: {unscheduled}")

    d = FORECAST_PUBLISH_FROM
    while d < FORECAST_PUBLISH_TO:
        if runs_per_date[d] != RUNS_PER_DAY:
            rep.error(f"forecasts: {d} has {runs_per_date[d]} runs, expected {RUNS_PER_DAY}")
        d += timedelta(days=1)

    forecasts = [(pub, start, g) for (pub, start), g in out.items()]
    return forecasts, sorted(by_run), dups, unscheduled


def write_db(db_path: Path, actuals: list, forecasts: list, meta: dict) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.executemany("INSERT INTO actuals_half_hourly VALUES (?,?,?,?,?)", sorted(actuals))
        con.executemany("INSERT INTO forecasts VALUES (?,?,?)", sorted(forecasts))
        con.executemany("INSERT INTO meta VALUES (?,?)", sorted(meta.items()))
        con.commit()
        con.execute("VACUUM")
    finally:
        con.close()


def build(raw_dir: Path, db_path: Path, allow_issues: bool = False, out=print) -> dict:
    manifest, act_raw, fc_raw = load_raw(raw_dir)
    rep = Report()
    actuals, a_dups = clean_actuals(act_raw, rep)
    forecasts, runs, f_dups, unscheduled = clean_forecasts(fc_raw, rep)

    for w in rep.warnings:
        out("WARNING: " + w)
    for e in rep.errors:
        out("ERROR:   " + e)
    if rep.errors and not allow_issues:
        raise ValidationFailed(f"{len(rep.errors)} validation error(s); database not written")

    data_version = hashlib.sha256(
        "".join(sorted(f["sha256"] for f in manifest["files"])).encode("utf-8")
    ).hexdigest()
    meta = {
        "schema_version": "1",
        "script_version": SCRIPT_VERSION,
        "source": "Elexon Insights Solution (BMRS) API: FUELHH (WIND) and WINDFOR",
        "source_base_url": manifest["base_url"],
        "retrieved_at": manifest["retrieved_at"],
        "actuals_window": manifest["actuals_window"],
        "forecast_publish_window": manifest["forecast_publish_window"],
        "scope": "decisions made 2026-01-01..2026-01-31; delivery days 2026-01-02..2026-02-01",
        "rows_actuals": str(len(actuals)),
        "rows_forecasts": str(len(forecasts)),
        "runs": str(len(runs)),
        "unscheduled_runs": ",".join(unscheduled),
        "duplicates_dropped": str(a_dups + f_dups),
        "validation_issues_allowed": "yes" if (rep.errors and allow_issues) else "no",
        "data_version": data_version,
    }
    write_db(db_path, actuals, forecasts, meta)

    out(f"Wrote {db_path}")
    out(f"  actuals   : {len(actuals)} half-hours")
    out(f"  forecasts : {len(forecasts)} rows in {len(runs)} runs")
    out(f"  retrieved : {meta['retrieved_at']}   data_version: {data_version[:12]}")
    return meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build-only", action="store_true", help="skip the fetch; rebuild from saved raw files")
    ap.add_argument("--allow-issues", action="store_true", help="write the database even if validation fails")
    ap.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    ap.add_argument("--db", type=Path, default=DB_PATH)
    args = ap.parse_args(argv)
    try:
        if not args.build_only:
            fetch_all(args.raw_dir)
        build(args.raw_dir, args.db, args.allow_issues)
    except ValidationFailed as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())