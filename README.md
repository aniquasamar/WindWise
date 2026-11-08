# WindWise

**Live app: https://b3v0we4d-efeg.vercel.app**  ·  **Demo Video: https://youtu.be/xjqYtS__xjY**

WindWise helps an energy buyer who must buy UK day-ahead power decide **how far to trust the wind forecast**. It uses national wind data from Elexon only, for purchase decisions made in January 2026 (delivery days 2 January to 1 February 2026).

- **Forecast page.** For any delivery day, the newest wind forecast that existed when the buying decision had to be made (default 09:00 UK time on the day before), shown against what actually happened, with a "firm wind" line (forecast minus a safety buffer).
- **Accuracy page.** How wrong the forecast was in January, how large a buffer is needed, and an honest test of whether that buffer held when applied day by day using only earlier data.

## What the analysis found

| Finding (decision-time forecast, 744 hourly pairs) | Value |
|---|---|
| Average error (forecast minus actual) | **+1,748 MW** (about +15% of average wind), 90% range 1,313 to 2,195 MW |
| Days on which the forecast was too high on average | 27 of 31 |
| Typical miss (MAE) / big-miss measure (RMSE) | 2,039 MW / 2,505 MW |
| Buffer to be covered 9 hours in 10 (in hindsight) | **4,098 MW**, 90% range 3,225 to 5,267 MW |
| Same buffer applied day by day with only earlier data | held in **85.5%** of hours, below the 90% promised |
| Error grows with the size of the forecast | +752 MW (low), +1,568 MW (medium), +2,929 MW (high) |
| Which forecast run you act on (before the auctions close) | changes the typical miss by at most about 1% |
| Experiment: correct the forecast with the previous 7 days | typical miss about 33% lower (experimental, not the official forecast) |

The cause of the persistent over-forecast cannot be established from these two datasets. Possible explanations are listed, labelled as unverified, in [`docs/DATA_NOTES.md`](docs/DATA_NOTES.md).

## The central rule: no peeking

Anything shown as "what the buyer knew" uses only information available at the decision time:

- the forecast is the latest WINDFOR run published **at or before** the cutoff, chosen per hour, and never filled from a later run;
- the 48-hour baseline uses only actuals that were already published;
- the buffer and the bias-corrected experiment for a day use only **earlier, completed** days.

These guarantees are enforced by dedicated "leakage tests" (`backend/tests/unit/test_leakage.py`). They change data that must not matter and assert the result is identical.

## Quick start

### With Docker (recommended)

```bash
docker compose up --build
```

Then open <http://localhost:8080>. The API documentation is at <http://localhost:8080/api/docs>.

### Without Docker

You need Python 3.12 and a current Node LTS.

```bash
# terminal 1: API on http://localhost:8000
python -m venv .venv
.venv/Scripts/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1   (macOS/Linux: source .venv/bin/activate)
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
cd backend
python -m uvicorn main:app --reload --port 8000
```

```bash
# terminal 2: web app on http://localhost:5173 (proxies /api to the API)
cd frontend
npm ci
npm run dev
```

### Tests

```bash
python -m pytest backend/tests -q        # from the repository root
cd frontend && npm test                  # unit tests for the front-end logic
cd frontend && npm run build             # strict TypeScript check and production build
```

## Repository map

```
.
├── README.md
├── docker-compose.yml          two containers: web (nginx) and api
├── vercel.json                 Vercel Services: static front end + Python API on one domain
├── .github/                    CI workflow and dependency updates
├── backend/
│   ├── main.py                 entry point (Vercel runs "main:app")
│   ├── Dockerfile
│   ├── requirements.txt        runtime packages
│   ├── requirements-dev.txt    test packages
│   ├── data/wind.sqlite        the read-only database that ships with the API
│   ├── app/
│   │   ├── core/               pure analytics, no I/O: selection, metrics, buffer, baseline,
│   │   │                       breakdowns, horizon, run sensitivity, benchmark, bootstrap, insights
│   │   ├── repository/         read-only SQLite access
│   │   ├── services.py         turns analytics into the JSON the API serves
│   │   ├── api/                routes, request parameters, response schemas, error handling
│   │   ├── middleware/         request ID, access log, trusted host, CORS, security headers,
│   │   │                       rate limit, ETag, error boundary
│   │   ├── validation.py       all request rules (framework-free)
│   │   └── config.py           settings from environment variables
│   └── tests/
│       ├── unit/               analytics, leakage, services, validation, middleware
│       ├── api/                the running app: routes, validation, headers, rate limit, caching
│       ├── data/               ingestion and database contract tests
│       └── support/            builds a realistic synthetic database for tests
├── frontend/
│   ├── Dockerfile, nginx.conf, security-headers.conf
│   ├── public/theme-init.js    sets dark/light before first paint
│   ├── src/
│   │   ├── api/                typed API client (types are generated, see below) and data hook
│   │   ├── lib/                pure logic: formatting, routing, scales, chart geometry, captions
│   │   ├── components/         line and bar charts (custom SVG), cards, legends, assumptions panel
│   │   └── pages/              Forecast and Accuracy pages
│   └── tests/                  unit tests for src/lib
├── scripts/
│   ├── ingest_elexon.py        fetch from Elexon, validate, build the database
│   ├── verify_db.py            checks the committed database matches the committed raw data
│   ├── gen_ts_types.py         generates front-end types from the backend schemas
│   ├── headline_check.py       prints the headline analysis from the real database
│   └── exploration/            the throw-away scripts used to explore the data first
├── data/raw/                   raw Elexon responses, with a manifest of SHA-256 hashes
├── postman/                    41-request collection and environments (local, production)
└── docs/
    ├── DATA_NOTES.md           what the data is, what was checked, results
```

## API

Read-only `GET` endpoints under `/api/v1`. Interactive documentation: `/api/docs`.

| Endpoint | Returns |
|---|---|
| `health`, `meta` | liveness; date window, defaults, assumptions, data provenance |
| `forecast?delivery_date=` | the decision-time forecast for one day, with actuals, firm wind, buffer status |
| `accuracy/summary`, `accuracy/intervals` | headline metrics, buffer, backtest, baseline, insights; 90% intervals |
| `accuracy/by-hour`, `by-day`, `by-forecast-level`, `distribution` | breakdowns |
| `accuracy/horizon?view=decision\|full`, `accuracy/runs` | error against forecast horizon; effect of the decision time |
| `accuracy/benchmarks`, `buffer/backtest` | baseline and experimental correction; day-by-day buffer test |

Common parameters: `cutoff` (UK time, 15-minute steps, 03:00 to 16:00, default 09:00), `confidence` (0.8, 0.9 or 0.95), `from` and `to` (delivery dates). Sign convention everywhere: **error = forecast minus actual**, so positive means the forecast was too high.

Configuration is read from environment variables, with safe defaults:

| Variable | Meaning | Default |
|---|---|---|
| `WIND_DB_PATH` | path to the SQLite file | `backend/data/wind.sqlite` |
| `ALLOWED_HOSTS` | comma-separated host names (wildcards like `*.vercel.app`; `*` turns the check off) | localhost, 127.0.0.1, `*.vercel.app` |
| `ALLOWED_ORIGINS` | origins allowed cross-origin access | none (same-origin only) |
| `RATE_LIMIT_PER_MIN` | requests per minute per client (`0` turns it off) | 120 |
| `TRUST_PROXY` | read the client address from `X-Forwarded-For` | on for Vercel, off elsewhere |

## Security

The API is public and read-only, serving public data, so there is deliberately no login. Protection comes from:

- strict validation of every parameter, with unknown parameters rejected; no user input in SQL; the database is opened read-only and immutable;
- one error shape with no internals, a request ID on every response, and a JSON access log with no query strings or addresses;
- trusted-host check, no cross-origin access by default, security headers on every response including errors, per-client rate limiting, and ETag/304 caching;
- a strict Content-Security-Policy on the web pages, non-root containers, read-only container file systems.

Limitation: the rate limiter keeps its counters in memory. On a serverless platform requests are spread over instances that do not share memory, so the limit there is best-effort. It is reliable with Docker or a single process.

## Data and reproducibility

- Source: Elexon Insights Solution (BMRS) `FUELHH` (wind actuals, half-hourly) and `WINDFOR` (wind forecasts, eight runs a day, hourly targets). Nothing else is used.
- `python scripts/ingest_elexon.py` fetches the data once, validates it (gaps, duplicates, nulls, run structure) and fails loudly on any problem. It saves the raw responses in `data/raw/` with hashes and builds the database. `--build-only` rebuilds offline from the saved files, and CI checks that the committed database matches them (`scripts/verify_db.py`).
- The running app never calls Elexon. It serves a fixed snapshot, so it is fast and cannot be affected by Elexon outages or rate limits.

## Assumptions and limitations

- Decisions are made on 1 to 31 January 2026 at 09:00 UK time, before the earliest hourly day-ahead auction closes (about 09:20 per the exchanges; confirm the current timetable).
- Hourly forecasts are compared with the mean of the two half-hourly actuals in that hour.
- The buffer assumes the costly risk is wind falling short of the forecast. There is no price or demand data, so the app reports a haircut on wind, **not a quantity to buy**.
- Thirty-one days of one winter month is a small sample. Errors cluster by day, so the real sample is closer to 31 independent days than to 744 hours. The app shows intervals and says so.
- The bias-corrected forecast is an experiment and is always labelled as such.

## Built with AI assistance

I used an AI assistant (Anthropic's Claude) throughout this project. It drafted most of
the code, tests and documentation, and helped me think through the design. I directed the
work and made the key decisions: the 09:00 decision time, the January decision window,
comparing hourly forecasts with hourly averages of actuals, the extra analyses (horizon,
baseline, the experimental correction), TypeScript, Vercel with a public read-only API,
two pages with light and dark themes, and the product name. I set up the repository,
deployment, Docker and CI, ran and checked everything against the real Elexon data, and
tested the API with Postman.

## Data attribution

Wind data comes from the Elexon Insights Solution (BMRS). Check Elexon's terms of use before reusing the data.