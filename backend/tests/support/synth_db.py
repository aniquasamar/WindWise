"""Builds a realistic synthetic database (wind-like data with a systematic over-forecast).

Used by the service and API tests so they never depend on the real database or the network.
The shape matches the real data exactly: 8 runs a day, 73 hourly targets per run, half-hourly actuals.
"""
import importlib.util
import math
import random
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load_ingest():
    if "ingest_elexon" in sys.modules:
        return sys.modules["ingest_elexon"]
    spec = importlib.util.spec_from_file_location("ingest_elexon", ROOT / "scripts" / "ingest_elexon.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ingest_elexon"] = mod
    spec.loader.exec_module(mod)
    return mod


def build_synthetic_db(db_path: Path, seed: int = 7) -> Path:
    ing = _load_ingest()
    rng = random.Random(seed)
    t0 = ing.utc_midnight(ing.ACTUALS_FIRST)

    def wind(ts):
        day = (ts - t0).total_seconds() / 86400
        return 11000 + 4500 * math.sin(day * 0.9) + 1500 * math.sin(day * 5.3) + 600 * math.sin(ts.hour / 24 * 6.28)

    n_days = (ing.ACTUALS_LAST - ing.ACTUALS_FIRST).days + 1
    actuals = []
    for i in range(n_days * 48):
        st = t0 + timedelta(minutes=30 * i)
        actuals.append({
            "dataset": "FUELHH",
            "publishTime": ing.fmt_ts(st + timedelta(minutes=30)),
            "startTime": ing.fmt_ts(st),
            "settlementDate": st.date().isoformat(),
            "settlementPeriod": st.hour * 2 + st.minute // 30 + 1,
            "fuelType": "WIND",
            "generation": max(500, int(wind(st) + rng.gauss(0, 150))),
        })

    forecasts = []
    n_run_days = (ing.FORECAST_PUBLISH_TO - ing.FORECAST_PUBLISH_FROM).days
    for d in range(n_run_days):
        day = ing.utc_midnight(ing.FORECAST_PUBLISH_FROM) + timedelta(days=d)
        for hhmm in sorted(ing.EXPECTED_RUN_TIMES):
            h, m = map(int, hhmm.split(":"))
            pub = day + timedelta(hours=h, minutes=m)
            first = (day - timedelta(days=1)).replace(hour=21)
            for k in range(ing.TARGETS_PER_RUN):
                target = first + timedelta(hours=k)
                horizon = (target - pub).total_seconds() / 3600
                err = rng.gauss(0, 400 + 25 * max(horizon, 0))
                forecasts.append({
                    "dataset": "WINDFOR",
                    "publishTime": ing.fmt_ts(pub),
                    "startTime": ing.fmt_ts(target),
                    "generation": max(300, int(wind(target) * 1.15 + err)),
                })

    raw_dir = Path(db_path).parent / "raw_synthetic"
    files = [
        ing.save_raw(raw_dir, "FUELHH", "all", {"synthetic": True}, actuals),
        ing.save_raw(raw_dir, "WINDFOR", "all", {"synthetic": True}, forecasts),
    ]
    ing.write_manifest(raw_dir, files, retrieved_at="2026-10-01T00:00:00Z")
    ing.build(raw_dir, Path(db_path), out=lambda *_a, **_k: None)
    return Path(db_path)