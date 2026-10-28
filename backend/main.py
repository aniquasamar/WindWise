import sqlite3
import sys
import time
from pathlib import Path

from fastapi import FastAPI, Request, Response

app = FastAPI(title="hello")
DB = Path(__file__).parent / "data" / "hello.sqlite"


@app.get("/v1/health")
def health(request: Request):
    # Read-only, immutable open: the same mode the real app will use.
    con = sqlite3.connect(f"{DB.as_uri()}?mode=ro&immutable=1", uri=True)
    try:
        rows = con.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    finally:
        con.close()
    return {
        "status": "ok",
        "python": sys.version.split()[0],
        "sqlite_rows": rows,
        "x_forwarded_for": request.headers.get("x-forwarded-for"),
    }


@app.get("/v1/cache-test")
def cache_test(response: Response):
    response.headers["Cache-Control"] = "public, s-maxage=60"
    return {"server_time": time.time()}