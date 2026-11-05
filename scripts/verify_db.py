#!/usr/bin/env python3
"""Check that the committed database is exactly what the committed raw Elexon files produce.

Rebuilds the database from data/raw into a temporary file and compares it with
backend/data/wind.sqlite (provenance record, row counts, sums and date ranges).
Exit code 1 on any difference.   Usage: python scripts/verify_db.py
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest_elexon as ing  # noqa: E402


def snapshot(path: Path) -> dict:
    con = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        return {
            "meta": dict(con.execute("SELECT key, value FROM meta")),
            "actuals": con.execute("SELECT COUNT(*), SUM(wind_mw), MIN(start_time), MAX(start_time) FROM actuals_half_hourly").fetchone(),
            "forecasts": con.execute("SELECT COUNT(*), SUM(wind_mw), MIN(publish_time), MAX(publish_time) FROM forecasts").fetchone(),
        }
    finally:
        con.close()


def main() -> int:
    if not ing.DB_PATH.exists():
        print(f"missing {ing.DB_PATH}")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        rebuilt = Path(tmp) / "rebuilt.sqlite"
        ing.build(ing.RAW_DIR, rebuilt, out=lambda *_a, **_k: None)
        committed, fresh = snapshot(ing.DB_PATH), snapshot(rebuilt)
    problems = [k for k in committed if committed[k] != fresh[k]]
    if problems:
        for k in problems:
            print(f"DIFFERENT: {k}\n  committed: {committed[k]}\n  rebuilt:   {fresh[k]}")
        return 1
    print("OK: the committed database matches the committed raw data "
          f"({committed['actuals'][0]} actuals, {committed['forecasts'][0]} forecast rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())