# PROJECT_PLAN: day-ahead wind forecast portal

A complete plan for the assignment, from data to deployment to video, with the reasoning behind every decision. Read it top to bottom once. After that, use the decision register (section 3) and the phase checklists (sections 5 to 15) as working references.

## 0. How to use this document

**Status labels** used in the decision register:

| Label | Meaning |
|---|---|
| **Decided (you)** | You chose it explicitly. |
| **Decided (evidence)** | The data or a source forced it. |
| **Proposed** | My recommendation. It stands unless you object. |

**Priority labels** on work items:

| Label | Meaning |
|---|---|
| **Must** | Required by the brief, or needed for the product to be credible. |
| **Should** | Strongly improves the result. |
| **Stretch** | Nice to have. Cut first. |

**On the 16-hour guideline.** You asked me to ignore it while planning. The brief still says reviewers expect the work to fit in about 16 hours, so each phase marks what is Must, Should and Stretch. If you later need to cut scope, you can cut cleanly without breaking the story.

**Companion file:** `DATA_NOTES.md` holds the verified facts, the exploration numbers, and the methodology decisions this plan depends on.

## 1. The assignment in plain terms

**The client** is a UK energy utility whose team buys power on the **day-ahead market**. They must decide the day before delivery, so they rely on **wind forecasts**. The more wind they expect, the less thermal power they buy.

**The product** is a web app that must let them:
1. See the **latest wind forecast available at the time they must decide**.
2. **Quantify the accuracy** of those forecasts so they can price in the error.

**Data (Elexon only, national level, January 2026 decisions):**
- Actuals: `FUELHH`, filtered to `fuelType = WIND`.
- Forecasts: `WINDFOR`, with `startTime`, `publishTime`, `generation`.

**Technical constraints:** React front end, Python back end, Docker, deployed on Vercel or Heroku, AI use disclosed in the README.

**Deliverables:**

| # | Deliverable | Notes |
|---|---|---|
| 1 | Unlisted YouTube video, max 10 minutes | Part 1: customer pitch (max 5 min). Part 2: technical review (max 5 min). Evaluated first. |
| 2 | Public GitHub repo with an anonymous name | README: files and directories, how to start, link to live app, AI disclosure. |
| 3 | Submission form | Open every link in incognito mode first. |

## 2. How the plan evolved (and why)

Several early ideas were wrong or incomplete. The corrections are part of the story you can tell in the technical video.

| Step | What we thought | What changed it | New position |
|---|---|---|---|
| First blueprint | Baseline = "yesterday's actual" | Self-review: at the cutoff, yesterday is incomplete, so it leaks the future | Baseline uses the latest complete day, 48 hours earlier |
| First blueprint | Buffer = P90 of **absolute** error | The costly risk is one-sided (wind under-delivers) | Buffer = P90 of the **signed** error |
| First blueprint | Error band computed from all of January | That uses future information | Expanding window: day D uses only earlier days |
| First blueprint | Pre-aggregate everything for Vercel | Hides the real backend work | Raw data in SQLite, metrics computed by the API, results cached |
| Docs research | WINDFOR runs 4 times a day, 49 values | Data showed **8 runs** a day, **73** values | Trust the data. Select by real `publishTime`, never by schedule |
| Docs research | Cutoff sensitivity would be meaningless | With 8 runs it is meaningful | Reframed as "which run you act on" |
| Exploration | Forecast and actuals differ by noise | Bias is **+1.85 GW**, persistent, level-dependent | Headline finding; adds the bias-corrected benchmark |
| Exploration | Bias might be an alignment artefact | Four alignments differ by under 4 MW | Ruled out |
| Exploration | Bias might fade near delivery | It does not, even for elapsed targets | Reported as a persistent gap, causes labelled unverified |
| Brief re-read | Delivery days = 1 to 31 January | "Decisions made in January" means delivery 2 January to 1 February | Date window changed (you agreed) |
| Deployment | Heroku runs Docker, Vercel does not | You chose Vercel Hobby | Docker for local/CI, Vercel serverless for production, same app code |

## 3. Decision register

### 3.1 Product and scope

| ID | Decision | Status | Alternatives | Why |
|---|---|---|---|---|
| P1 | Two pages: **Forecast** and **Accuracy** | Decided (you) | One tabbed page | Maps one page to each of the client's two needs |
| P2 | Public, read-only API, no login | Decided (you) | Shared password, Vercel protection | Reviewers must open it instantly. Data is public. |
| P3 | Date window: decisions **1 to 31 Jan 2026**, delivery **2 Jan to 1 Feb 2026** | Decided (you) | Delivery 1 to 31 Jan | Literal reading of the brief |
| P4 | Default cutoff **09:00 UK time** on the decision date, selectable | Decided (you) with evidence | 08:00 or 10:00 | Before the earliest hourly auction closure (09:20 per secondary sources) |
| P5 | Include horizon analysis and baseline comparison | Decided (you) | Lean scope | Adds depth the brief hints at |
| P6 | Bias-corrected benchmark as a **clearly labelled extra** | Decided (you) | Skip it | Bias dominates the error. Shows what is fixable. |
| P7 | Light, clean design with dark-mode toggle | Decided (you) | Dark-only | Suits a utility audience |
| P8 | Frame the output around **"firm wind"** (forecast minus buffer) and state that demand is out of scope | Proposed | Claim "MW to procure" | We have no demand data. Claiming it would be wrong. |

### 3.2 Data and analytics

| ID | Decision | Status | Alternatives | Why |
|---|---|---|---|---|
| D1 | Fetch Elexon **once** with a script. Never call it from the running app. | Proposed | Live API calls | Avoids rate limits, outages and cold-start delays. Data is historical and fixed. |
| D2 | Store in **SQLite**, committed to the repo, opened read-only | Proposed | Parquet, JSON, Postgres | Vercel has no writable disk, so a bundled read-only file is simplest. SQL gives typed schema and constraints. About 21k forecast rows, so tiny. |
| D3 | **Pure Python** analytics (standard library only) in production | Proposed | pandas and NumPy | The data is tiny, so pandas adds nothing. Keeps installs light and cold starts fast. Size alone would not have forced this: Vercel's Python bundle limit is 500 MB uncompressed. pandas stays in exploration only. |
| D4 | Hourly evaluation grain, actuals averaged over the hour | Decided (you) | Half-hourly with repeated forecasts | Forecasts are hourly |
| D5 | Sign convention: error = forecast − actual | Proposed | Actual − forecast | Positive means "too much wind forecast", which is the risky direction |
| D6 | Select the decision-time run by the real `publishTime` (≤ cutoff), per target, with no fallback to later runs | Decided (evidence) | Fixed schedule | Handles the 12:25 anomaly and prevents look-ahead |
| D7 | Buffer from the **signed** error percentile | Decided (evidence) | Absolute-error percentile | One-sided risk |
| D8 | Expanding-window statistics for anything shown as "known on day D" | Decided (evidence) | Whole-month statistics | Avoids using the future |
| D9 | Baseline: same hour **48 hours earlier** | Decided (evidence) | Yesterday's actual | Leakage-free |
| D10 | Bin errors by **forecast level**, not actual level | Proposed | Actual level | The forecast is known when deciding. Binning by actual creates misleading patterns. |
| D11 | Report **nMAE and WMAPE**, never plain MAPE | Proposed | MAPE | MAPE explodes near zero wind |
| D12 | Normalise by mean actual output and label it | Proposed | Installed capacity | Capacity is not in the permitted data |
| D13 | Exclude elapsed targets (horizon ≤ 0) from decision-time analysis | Decided (evidence) | Include | They are not forecasts |
| D14 | Show both an in-sample buffer ("what January would have needed") and an out-of-sample coverage backtest | Proposed | In-sample only | The honest test is whether the promise held |

### 3.3 Backend, security and testing

| ID | Decision | Status | Alternatives | Why |
|---|---|---|---|---|
| B1 | **FastAPI**, with analytics in a separate pure module | Proposed | Flask | Typed validation, OpenAPI docs, async-ready. Separation allows unit tests with no web code. |
| B2 | Versioned routes under `/api/v1` | Proposed | Unversioned | Cheap, and standard practice |
| B3 | Middleware stack in the order of section 9 | Proposed | Minimal | You asked for secure APIs and routes |
| B4 | In-app rate limiter is best-effort. Vercel firewall rules are used if the Hobby tier allows them. | Proposed | Redis counters | Serverless instances do not share memory. Redis adds moving parts. |
| B5 | Pydantic validation on every parameter, parameterised SQL only, read-only DB | Proposed | None | Core of "secure" for a public read-only API |
| B6 | Generate TypeScript types from the backend response schemas with a small script (`scripts/gen_ts_types.py`) | Proposed, revised | OpenAPI tooling, hand-written types | One source of truth. Runs anywhere (it reads the schema file as text). A test fails if the committed types drift. |
| B7 | "Leakage tests" as a first-class test category | Proposed | Ordinary unit tests only | Directly proves the product's central promise |
| B8 | Postman collection committed to the repo | Decided (you use Postman) | Manual checks | Reviewable evidence of security checks |

### 3.4 Frontend and deployment

| ID | Decision | Status | Alternatives | Why |
|---|---|---|---|---|
| F1 | Vite, React, **TypeScript**, plain CSS with design tokens | Decided (you: TypeScript), CSS revised | Tailwind, Next.js | One stylesheet that can be reviewed and checked in a real browser. Tailwind's setup changed recently. Dark mode is a variable swap. |
| F2 | Small **custom SVG charts** | Proposed, revised | Recharts, Plotly | React is the only runtime dependency (no peer-dependency clashes, smaller bundle). Full control of keyboard access and text alternatives. Verified in a headless browser. |
| F3 | A small data hook with an in-memory cache | Proposed, revised | TanStack Query | Responses never change within a deployment. About 60 lines cover loading, errors and retry, with no extra dependency. |
| F4 | Hash routes (`#/forecast?date=2026-01-28`) | Proposed, revised | React Router with path routes | Deep links work on any static host with no rewrite rules, which removes the Vercel single-page-app fallback uncertainty. |
| F5 | System font stack, no external requests | Proposed | Google Fonts | Faster, private, and no third-party dependency |
| H1 | Host on **Vercel Hobby**, frontend and API under one domain | Decided (you) | Heroku | Free. Same origin means CORS can be locked down. |
| H2 | Docker for local run and CI. Vercel runs the zero-configuration Python build. Same app code in both. Deploying a container image on Vercel (`Dockerfile.vercel`) is an optional spike. | Decided (evidence), revised | Container image on Vercel | Current Vercel docs say container images can run as functions, with no Compose support, but availability on the Hobby tier is unconfirmed. The zero-configuration path is documented and lower risk. An earlier version of this plan wrongly said Vercel cannot run containers. |
| H3 | Python 3.12 | Proposed | 3.13 | Matches your local version. Confirm Vercel supports it. |

## 4. System overview

```
                     (one-off, offline)
  Elexon Insights API ──► scripts/ingest_elexon.py ──► data/raw/*.json
                                    │                     (audit trail)
                                    ▼
                          backend/data/wind.sqlite  (read-only, committed)
                                    │
        ┌───────────────────────────┴────────────────────────────┐
        │  backend/app                                           │
        │   repository/  typed, read-only SQL access             │
        │   core/        PURE analytics (no I/O, fully tested)   │
        │   api/         routers, schemas, errors                │
        │   middleware/  request id, headers, limits, caching    │
        └───────────────────────────┬────────────────────────────┘
                                    │  JSON over HTTPS  (/api/v1/...)
                                    ▼
                  frontend (React + TS + Tailwind + Recharts)
                    Forecast page    Accuracy page    Assumptions panel
```

**Principles that every decision traces back to:**
1. **No peeking.** Nothing shown as "known at decision time" may use later information.
2. **Say what you assumed.** The cutoff, the data source, the sign convention and the sample size are always visible.
3. **Honest uncertainty.** If history is too short, show "insufficient history" instead of a shaky number.
4. **One truth.** The analytics module is the only place where metrics are computed. The API and UI only present them.
5. **Same code everywhere.** Docker, tests, CI and Vercel all run the same application package.

**Vocabulary used throughout:**

| Term | Meaning |
|---|---|
| Decision date `d` | The day the buying decision is made (1 to 31 Jan 2026) |
| Delivery day `D` | `d + 1`, the day the power is delivered (2 Jan to 1 Feb 2026) |
| Cutoff | The time on `d` after which new forecasts are ignored (default 09:00 UK) |
| Run | One publication of WINDFOR (eight a day) |
| Target | The hour a forecast value is about (`startTime`) |
| Horizon | `startTime` minus `publishTime` |

## 5. Phase 0: setup and de-risking

**Goal:** remove deployment and anonymity surprises before writing real code.

| # | Task | Priority |
|---|---|---|
| 0.1 | Create the repo with a random name. **Before the first commit** set a neutral git identity (`git config user.name` and `user.email` with a no-reply or placeholder address). | Must |
| 0.2 | Check metadata that leaks identity: `package.json` author, `pyproject.toml` authors, LICENSE holder, README, editor config, Vercel project and team name (it appears in the URL), YouTube channel name. | Must |
| 0.3 | Create the folder skeleton (section 6.6) and tooling: ruff, mypy, pytest, ESLint, Prettier, `.editorconfig`, `.gitignore`, pre-commit hooks. | Should |
| 0.4 | Deploy a **hello-world** to Vercel: one React page and one FastAPI route at `/api/v1/health`, with a tiny SQLite file bundled and read. | Must |
| 0.5 | In that deploy, verify the **unknowns** listed in section 17: Python version, function entry-point layout, bundle size, how to include the DB file, response-size limit, what the Hobby firewall offers. | Must |
| 0.6 | Set up GitHub Actions with a trivial passing job so CI exists from day one. | Should |

**Done when:** a public URL returns the health JSON and a static page, and you know which Vercel assumptions held.

## 6. Phase 1: data (exploration, ingestion, database)

### 6.1 Exploration (done)

We ran two scripts and recorded everything in `DATA_NOTES.md`. In short:
- Actuals: complete, half-hourly, no gaps, 1,695 to 17,805 MW.
- Forecasts: hourly targets, eight runs a day, 73 targets per run, one late run on 15 January.
- Decision-time rule at 09:00 selects the 07:30 run, horizon 16.5 to 39.5 hours.
- Forecast bias is about **+1.85 GW** (16%), persistent and level-dependent.

### 6.2 Ingestion script (`scripts/ingest_elexon.py`)

**Behaviour:**

| Aspect | Design |
|---|---|
| Windows | Actuals: settlement dates **2025-12-29 to 2026-02-01**. Forecasts: `publishTime` from **2025-12-29** to **2026-02-02** (exclusive). Fetched in 7-day chunks, which worked in exploration. |
| Why this range | Delivery days run 2 Jan to 1 Feb. The baseline needs actuals from 31 Dec. The full-horizon curve needs all runs that target those days. |
| Reliability | Timeouts, retries with exponential backoff, a polite delay between calls, a clear user agent. |
| Idempotent | Re-running replaces rows. It never duplicates. |
| Audit trail | Each raw chunk saved as JSON under `data/raw/`, with a SHA-256 hash recorded. |
| Fail loudly | Aborts if an invariant breaks (below) unless `--allow-gaps` is given. |
| Provenance | Writes a `meta` table: retrieval timestamp, endpoint URLs, parameters, row counts, script version. |

**Invariants checked on ingest:**
- Actuals: 48 rows per settlement date, 30-minute spacing, no duplicates, no nulls, fuel type is WIND.
- Forecasts: 73 rows per run, hourly spacing, no duplicate (`startTime`, `publishTime`), no nulls.
- Value ranges: no negatives (flag, do not clamp), and a plausible upper bound.
- The run list matches the eight expected clock times, with exceptions logged (the 12:25 run).

### 6.3 Database schema (SQLite)

```sql
CREATE TABLE actuals_half_hourly (
  start_time        TEXT PRIMARY KEY,        -- ISO 8601 UTC, e.g. 2026-01-15T10:30:00Z
  settlement_date   TEXT NOT NULL,
  settlement_period INTEGER NOT NULL CHECK (settlement_period BETWEEN 1 AND 50),
  wind_mw           INTEGER NOT NULL CHECK (wind_mw >= 0),
  published_at      TEXT NOT NULL
);

CREATE TABLE forecasts (
  publish_time TEXT NOT NULL,                -- ISO 8601 UTC
  start_time   TEXT NOT NULL,
  wind_mw      INTEGER NOT NULL,
  PRIMARY KEY (publish_time, start_time)
) WITHOUT ROWID;

CREATE INDEX idx_forecasts_target ON forecasts (start_time, publish_time);

CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
```

**Design notes:**
- Timestamps are UTC ISO strings. They sort correctly as text, and the code converts to UK time where needed.
- The composite primary key makes duplicate runs impossible by construction.
- No derived data is stored. Hourly actuals and every metric are computed in code, so there is one source of truth.
- The DB file is opened with `file:...?mode=ro&immutable=1` because the Vercel filesystem is read-only. We verify this in Phase 0.

### 6.4 Data contract tests

Run against the committed `wind.sqlite`, in CI:
- Row counts match the expected structure.
- No gaps, duplicates or nulls remain.
- Every delivery day from 2 Jan to 1 Feb has a decision-time forecast for all 24 hours.
- The `meta` table is present and complete.

### 6.5 Licence and attribution

Check the Elexon Insights terms and add attribution to the app footer and README. **Must** (small).

### 6.6 Repository layout

```
<anonymous-repo-name>/
├── README.md
├── docs/
│   ├── DATA_NOTES.md
│   ├── PROJECT_PLAN.md        (or trimmed into DECISIONS.md)
│   ├── DECISIONS.md           (short ADR log)
│   └── METHODOLOGY.md         (the maths, for reviewers)
├── data/
│   └── raw/                   (as fetched, with hashes; not deployed)
├── scripts/
│   ├── ingest_elexon.py
│   └── exploration/           (the two throwaway scripts, archived)
├── backend/
│   ├── pyproject.toml / requirements.txt   (pinned)
│   ├── data/wind.sqlite       (read-only database, inside backend/ so it ships with the API)
│   ├── app/
│   │   ├── main.py            (app factory)
│   │   ├── config.py
│   │   ├── core/              (pure analytics, see section 7)
│   │   ├── repository/        (read-only SQLite access)
│   │   ├── api/               (routers, schemas, error handlers)
│   │   └── middleware/
│   ├── tests/ (unit/, api/, data/)
│   ├── Dockerfile
│   └── .dockerignore
├── frontend/
│   ├── src/ (api/, components/, pages/, theme/, hooks/, lib/)
│   ├── tests/
│   ├── Dockerfile
│   └── nginx.conf
├── postman/                   (collection and environments)
├── docker-compose.yml
├── docker-compose.dev.yml
├── vercel.json
└── .github/ (workflows/ci.yml, dependabot.yml)
```

The exact Vercel entry layout is confirmed in Phase 0.

## 7. Phase 2: the analytics core and the maths

**Principle:** `backend/app/core/` is pure. It takes typed data in and returns typed results. It does no I/O and has no web or database imports. This is what gets the most testing.

### 7.1 Definitions

For each delivery day `D` and target hour `T`:

| Symbol | Meaning |
|---|---|
| `F(T)` | Decision-time forecast for hour T (MW) |
| `A(T)` | Actual for hour T: mean of the half-hours at `T` and `T+30` min (MW) |
| `e(T)` | Error, `F(T) − A(T)` (positive means over-forecast) |

Day definition: the UK local calendar day (identical to UTC in January).

### 7.2 Decision-time selection

1. Convert the cutoff (decision date `d`, local time, `Europe/London`) to UTC with `zoneinfo`.
2. Keep forecast rows where `publish_time <= cutoff` (equality is included) and the target falls on delivery day `D`.
3. Per target, keep the row with the latest `publish_time`.
4. A target with no eligible row is reported as **"no forecast at cutoff"**. It is never filled from a later run.
5. Record the run's `publish_time` and its age at the cutoff.

### 7.3 Alignment

- `A(T)` is defined only if both half-hours exist. Otherwise the hour is dropped and counted.
- Pairs need both `F` and `A`. The count of dropped hours is always returned.

### 7.4 Summary metrics

| Metric | Formula | Question answered |
|---|---|---|
| Bias | mean of `e` | Is the forecast systematically high or low? |
| MAE | mean of `|e|` | How big is a typical miss? |
| RMSE | √mean of `e²` | How much do big misses hurt? |
| Std of error | √(RMSE² − bias²) | How scattered are errors after removing the offset? |
| nMAE, nRMSE | MAE or RMSE ÷ mean `A` | Size relative to wind level (label the denominator) |
| WMAPE | Σ`|e|` ÷ Σ`A` | Relative error without near-zero blow-up |
| P50, P90, P95 of `|e|` | percentiles of absolute error | How bad are bad hours, ignoring direction? |
| Over-forecast share | share of hours with `e > 0` | How often is the risky direction hit? |
| Signed P10 and P90 | percentiles of `e` | The two tails of the signed error |

**Percentile method:** linear interpolation between order statistics (the common default). Implemented once, tested against known values, and documented.

**Worked check (also a unit test):** forecasts 3000, 2000, 4000, 1500 against actuals 2900, 2050, 3800, 1650 give errors +100, −50, +200, −150. Bias +25, MAE 125, RMSE ≈ 136.93, std ≈ 134.63.

### 7.5 The buffer ("so what")

- `buffer = max(0, P_c of e)` where `c` is the confidence level (default 0.90, options 0.80 and 0.95).
- `firm wind = max(0, F − buffer)`.
- **Meaning:** if `e` is at most the buffer in a share `c` of hours, then actual wind was at least `F − buffer` in that share of hours.
- **Assumption (stated in the app):** the costly direction is a shortfall of wind against forecast, because the buyer must then cover late. We have no price data, so we do not size the cost. We show both signed tails (P10 and P90) so the client can weigh them.

**Two views, both labelled:**

| View | Method | Use |
|---|---|---|
| In-sample ("what January needed") | Percentile over the whole selected window | A descriptive headline |
| Out-of-sample backtest | For each decision date, percentile from complete earlier delivery days only, with at least 7 days of history | Tests whether the promise held |

**Coverage** = share of hours (on days with a valid buffer) where `e ≤ buffer`. If the app promised 90% and got 78%, it says 78%.

**History rule.** On decision date `d`, a delivery day counts as history only if its actuals are complete before the cutoff on `d`, meaning delivery days up to `d − 1`. Days with insufficient history show "insufficient history".

### 7.6 Breakdowns

| Breakdown | Notes |
|---|---|
| By hour of day | Bias and MAE per hour, plus buffer by hour (a refinement, since day-to-day variation is larger) |
| By delivery day | Daily bias, MAE, forecast mean and actual mean |
| By **forecast level** | Terciles of `F`. Decision-relevant because `F` is known at decision time (D10). |
| Error distribution | Histogram with P10 and P90 marked |

### 7.7 Horizon analysis (two separate views)

| View | Data | What it shows |
|---|---|---|
| **Decision-time** | The selected run only, horizon 16.5 to 39.5 h | Does error vary across the delivery day? |
| **Full curve** | All runs, horizon buckets (for example 6 hours wide) from 0 up to 70 hours | How forecasts improve (or do not) toward delivery |

Elapsed targets (horizon ≤ 0) are shown only in the full curve, in a separate, labelled bucket. Samples overlap heavily, so the page says the curve is descriptive.

### 7.8 Run and cutoff sensitivity

Evaluate the whole window once per run (02:30, 04:30, 07:30, 09:30, 11:30, and so on). Show metrics and the change against the default run. Annotate which runs are usable before which auction closes. Exploration says earlier-than-closure runs differ little, while 11:30 is better but arrives after the hourly auctions close.

### 7.9 Baseline and skill

- **Baseline:** `A` for the same hour two days earlier. At the cutoff on `d`, day `D − 2 = d − 1` is complete, so this is leakage-free.
- **Skill** = 1 − (forecast RMSE ÷ baseline RMSE), and the same with MAE. Positive means better than the baseline.
- Exploration: skill about 0.51, but the baseline is nearly unbiased while the forecast is not, so it is a weak yardstick (see 7.10).

### 7.10 Bias-corrected benchmark (clearly labelled extra)

**Purpose:** show how much of the error is a fixable offset, and give the client a stronger yardstick than persistence.

- For decision date `d`, use only delivery days whose actuals are complete before the cutoff.
- **Default: multiplicative correction.** Corrected `F = F × (Σ A ÷ Σ F)` over a rolling window of up to 7 complete delivery days, with at least 3 days of history. Reason: exploration showed bias scales with wind level.
- An **additive** variant (subtract the trailing mean error) is implemented too and compared once on the final data. Both results go in the technical review. The UI ships the default and says plainly that it is out-of-sample.
- The window length and minimum are fixed **before** looking at results, to avoid fitting January.
- The UI label: "Experimental benchmark: bias-corrected forecast (uses only past days)". It is never presented as the official forecast.

### 7.11 Uncertainty about the metrics (Should)

Errors cluster by day, so 744 hours behave like roughly 31 independent days. **Day-block bootstrap** (resample whole delivery days, fixed seed, about 1,000 draws) gives intervals on bias, MAE and the buffer. Pure Python is fast enough at this size. The UI shows an interval next to the headline numbers, or at minimum a note about effective sample size.

### 7.12 Insights (templated, deterministic)

A small function turns results into 3 or 4 sentences, for example "Largest miss: 28 Jan, forecast 5.3 GW above outturn" and "The forecast was too high on 27 of 31 days". Fixed templates, no generated text, so the same numbers always yield the same sentences and tests can check them.

### 7.13 Edge cases to test

- Missing target, missing half-hour, missing run.
- A run published exactly at the cutoff (included).
- The 12:25 anomaly (selection still correct).
- Negative or zero actuals (percentage metrics must not blow up).
- Empty history, history shorter than the minimum.
- Timezone logic: January (no offset) and a July date (one-hour offset) to prove the conversion is real, even though the data is January only.

## 8. Phase 3: backend API

**Common parameters:**

| Parameter | Rules | Default |
|---|---|---|
| `cutoff` | `HH:MM` UK time, 15-minute steps, from 03:00 to 16:00 | `09:00` |
| `confidence` | One of 0.80, 0.90, 0.95 | 0.90 |
| `from`, `to` | Delivery dates within 2026-01-02 to 2026-02-01, `from ≤ to`, at most 31 days | whole window |
| `delivery_date` | Within the same window | none |

**Endpoints:**

| Method and path | Returns |
|---|---|
| `GET /api/v1/health` | Liveness |
| `GET /api/v1/meta` | Valid date range, available runs, defaults, assumptions text, data provenance (retrieval date, sources), sign convention |
| `GET /api/v1/forecast?delivery_date=` | Decision date and cutoff in UTC, the run used and its age, 24 points with forecast, actual (null if unavailable), error, horizon, firm wind, baseline, and the buffer with its status and history length. Counts of missing items. |
| `GET /api/v1/accuracy/summary` | All headline metrics, counts, buffer (in-sample and backtest), skill vs baseline, insights |
| `GET /api/v1/accuracy/by-hour` | Per-hour metrics |
| `GET /api/v1/accuracy/by-day` | Per-delivery-day metrics |
| `GET /api/v1/accuracy/by-forecast-level` | Metrics per forecast tercile |
| `GET /api/v1/accuracy/distribution` | Histogram bins and signed percentiles |
| `GET /api/v1/accuracy/horizon?view=decision\|full` | The two horizon views |
| `GET /api/v1/accuracy/runs` | Run and cutoff sensitivity |
| `GET /api/v1/accuracy/benchmarks` | Baseline and bias-corrected benchmark metrics and skill |
| `GET /api/v1/buffer/backtest` | Per-day buffer, coverage, and "insufficient history" markers |

All endpoints are `GET`. Other methods return 405.

**Response conventions:**
- Timestamps are ISO 8601 UTC with `Z`. MW values are numbers in MW, rounded only at presentation.
- Every response that depends on the cutoff echoes the cutoff and the run it used.
- Every metric response includes `n_pairs` and `n_dropped`.
- Pydantic response models define the OpenAPI schema, which generates the front-end types.

**Error format** (one shape everywhere):

```json
{ "error": { "code": "validation_error", "message": "delivery_date must be between 2026-01-02 and 2026-02-01", "request_id": "..." } }
```

| Status | When |
|---|---|
| 200 | Success |
| 404 | Unknown route (JSON, never an HTML page) |
| 405 | Wrong method |
| 422 | Failed validation |
| 429 | Rate limit exceeded |
| 500 | Unexpected error: generic message and request id only |

**Caching:**
- Responses depend only on the query and the bundled data, so they are immutable per deployment.
- `Cache-Control: public, max-age=300, s-maxage=86400` plus an `ETag` derived from the query and a data-version hash. (Exact edge behaviour on Vercel is verified in Phase 0.)
- An in-process `lru_cache` on the heavy computations helps within a warm instance. It is best-effort, because serverless instances do not share memory.

**Performance expectation:** about 744 pairs and about 21k forecast rows, so computations take milliseconds. The backtest touches 31 days. No premature optimisation.

## 9. Phase 4: middleware and security

### 9.1 Posture

The API is **public, read-only, and serves public data**. "Secure" therefore means:
- it cannot be abused or overloaded,
- it rejects bad input cleanly,
- it leaks nothing internal,
- browsers are told to behave safely.

It does **not** mean a login. A login would block reviewers and protect nothing. We explain this reasoning in the technical review.

### 9.2 Middleware stack (outermost first)

| # | Middleware | Behaviour | Why |
|---|---|---|---|
| 1 | Request ID | Generate or accept a safe ID. Add it to the response and to log lines. | Trace any failure in logs and Postman |
| 2 | Structured logging | Log method, path, status, duration, request ID. Never log full query strings with user input beyond validated fields. | Debugging, and "development practices" |
| 3 | Trusted host | Allow only the production host, localhost and Vercel preview hosts. | Blocks host-header attacks |
| 4 | CORS | Allow only the known front-end origin. Same-origin on Vercel means almost nothing is needed. | Stops other sites calling the API from browsers |
| 5 | Security headers | `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Strict-Transport-Security`, frame protection, a restrictive `Content-Security-Policy` for the API. | Standard browser hardening |
| 6 | Rate limiting | Per-client sliding window, 120 requests per minute by default (`RATE_LIMIT_PER_MIN`, 0 turns it off). The client IP comes from the forwarded header only when a trusted proxy is configured (`TRUST_PROXY`, on by default on Vercel). Returns 429 with `Retry-After`. Health is exempt. | Limits scraping and overload |
| 7 | GZip | Compress larger JSON. | Speed on the Docker path (Vercel also compresses at the edge) |
| 8 | Cache headers | As in section 8. | The data is static |
| 9 | Global exception handler | Convert any crash into the standard error body. No traceback, no file paths. | No leakage |

**Implementation notes:**
- Prefer pure-ASGI middleware classes for request ID and security headers, which avoids known pitfalls of Starlette's `BaseHTTPMiddleware`.
- Keep middleware configuration in one `config.py`, read from environment variables (`ALLOWED_HOSTS`, `ALLOWED_ORIGINS`, `RATE_LIMIT_PER_MIN`, `ENV`). No secrets are needed.

### 9.3 Beyond middleware

| Control | Detail |
|---|---|
| Input validation | Every parameter through Pydantic with explicit bounds. Reject malformed dates, out-of-range cutoffs, unknown confidence levels, reversed ranges. Consider forbidding unknown query parameters. |
| SQL safety | Parameterised queries only. The database is opened read-only and immutable. |
| Output limits | Maximum range of 31 days. Fixed-size outputs otherwise. |
| Secrets | None required. Anything added later goes in Vercel environment variables. |
| Docs endpoints | Leave `/docs` and `/openapi.json` on (public, read-only) and say so. |
| Dependencies | Pinned. `pip-audit` and `npm audit` in CI. Dependabot for updates. |
| Front-end headers | Set in `vercel.json` (and `nginx.conf` for Docker): CSP, nosniff, referrer policy, frame protection. Test that Recharts' inline styles still work. |

### 9.4 The Vercel rate-limit caveat

An in-memory limiter counts per instance, so serverless fan-out weakens it. Plan:
1. Keep the in-app limiter. It is reliable in Docker and best-effort on Vercel.
2. Check in Phase 0 what the Hobby firewall offers. Use platform rate-limit rules if available.
3. Document the limitation honestly in the technical review.

### 9.5 Postman collection (`postman/`)

| Folder | Checks |
|---|---|
| Happy path | Each endpoint returns 200 and the expected fields. |
| Validation | Bad date, out-of-window date, reversed range, bad cutoff, bad confidence: 422 with a clear message. |
| Routing | Unknown route returns 404 JSON. POST to a GET route returns 405. |
| CORS | `Origin: https://evil.example` receives no allow-origin header. |
| Headers | Security headers and `X-Request-ID` present. |
| Rate limit | Collection Runner burst produces 429 with `Retry-After`. |
| Leakage | Force an error: no traceback or file path in the body. |
| Caching | `Cache-Control` and `ETag` present, and a conditional request returns 304. |

Two environments: local (Docker) and production. Run the same collection against both and keep the results as evidence for the video. **Stretch:** run it in CI with Newman.

### 9.6 Threat summary

| Threat | Mitigation |
|---|---|
| Scraping and overload | Rate limit, edge caching, small payloads |
| Injection | Validation plus parameterised read-only SQL |
| Information leak | Generic errors, no stack traces, no secrets |
| Host and CORS abuse | Trusted host, strict CORS |
| Clickjacking, content sniffing, XSS | Headers, CSP, React escaping, no `dangerouslySetInnerHTML` |
| Supply chain | Pinned dependencies, audits, Dependabot |

## 10. Phase 5: testing and quality

### 10.1 The test pyramid

| Layer | Tooling | What it covers |
|---|---|---|
| Unit (core) | pytest | Selection, alignment, every metric, percentile method, buffer, baseline, benchmark, backtest, insights, timezone handling |
| Leakage tests | pytest | See 10.2 |
| Data contract | pytest | The committed database (section 6.4) |
| Repository | pytest, small fixture DB | Queries return typed rows and never write |
| API | FastAPI TestClient | Shapes, validation errors, 404 and 405, headers, CORS, request ID, rate limit, error body, caching |
| Contract | CI check | Regenerated OpenAPI types match the committed front-end types |
| Frontend unit | Vitest, Testing Library, MSW | KPI cards, assumptions panel, date picker bounds, theme toggle, error and empty states |
| Accessibility | axe checks in tests | No critical violations on both pages |
| End to end (Stretch) | Playwright | Open page, pick a date, see chart and numbers |

### 10.2 Leakage tests (the signature test category)

These prove the central promise directly:
1. **Future-run test.** Add a forecast run published after the cutoff. The selected forecast must not change.
2. **Future-actual test.** Change actuals after the decision time. The baseline and bias-corrected benchmark for that day must not change.
3. **Expanding-window test.** Change errors on day `D` and later. The buffer for day `D` must not change.
4. **Boundary test.** A run published at exactly the cutoff is included, and one a second later is not.
5. **No fallback test.** A target with only a later run available is reported as missing.

### 10.3 Quality tooling

- Python: ruff for lint and format, mypy for types, coverage target on `core/` close to complete.
- TypeScript: strict mode, ESLint, Prettier.
- Pre-commit hooks run lint and format.
- **CI (GitHub Actions)** runs: backend lint, types and tests with coverage; front-end lint, type-check, tests and build; Docker image builds; dependency audits. Dependabot weekly.

## 11. Phase 6: frontend

### 11.1 Design principles

1. **Answer first, detail second.** The key number is visible within five seconds.
2. **One sign convention** and one colour meaning everywhere.
3. **Assumptions always visible** (cutoff, source, window, sign).
4. **Honest uncertainty** in wording and visuals.
5. **Accessible by default.**

### 11.2 Design system

| Aspect | Decision |
|---|---|
| Theme | Light by default. A toggle persists the choice. The first visit follows the operating-system setting. |
| Tokens | Colours, spacing and radii as CSS variables. Dark mode swaps the variables, with no component rewrite. |
| Colours | Colour-blind-safe palette. Forecast, actual, over-forecast and under-forecast get distinct hues **and** distinct line styles or labels, never colour alone. |
| Type | System font stack. Tabular numerals for all numbers. |
| Layout | One column on mobile. Two-column grid on wide screens. Wide tables and charts scroll inside their own container. |
| Motion | Subtle, and disabled under `prefers-reduced-motion`. |

### 11.3 Shell

- Top bar: product name, page switch (Forecast and Accuracy), theme toggle.
- **Assumptions chip** ("Cutoff 09:00 UK · Source: Elexon · Decisions 1 to 31 Jan 2026") that opens a panel listing every assumption, the sign convention, the data retrieval date and the attribution.
- Footer: attribution and the AI-use note.
- URLs carry state (`?date=2026-01-28&cutoff=09:00`) so a view can be shared.

### 11.4 Page 1: Forecast ("What did I know when I had to decide?")

| Element | Detail |
|---|---|
| Controls | Delivery-date picker limited to 2 Jan to 1 Feb, previous and next arrows, cutoff selector |
| Headline strip | Peak forecast, average forecast, and "Latest run before cutoff: published 07:30 on 14 Jan (1h 30m before cutoff)" |
| Main chart | Forecast line, firm-wind line or band (when history allows), actual line. A "Show what actually happened" toggle lets the presenter hide actuals first and reveal them. |
| Buffer note | "Buffer for this day: X MW at 90%, based on N earlier days" or "insufficient history" |
| Data table | Collapsible hourly table, with CSV download |
| States | Skeleton on load, error with retry, empty state where actuals are unavailable |

### 11.5 Page 2: Accuracy ("How much should I trust it?")

| Element | Detail |
|---|---|
| Filters | Date range, confidence level (80, 90, 95) |
| **Buffer callout** | The largest element: "To be covered 9 times out of 10, plan on forecast minus X MW." Underneath: the in-sample sentence and the **backtested coverage** ("held in Y% of hours when applied day by day"). |
| KPI cards | Bias (with an "over-forecasts" label), MAE, RMSE, P90 of absolute error, nMAE, skill vs baseline. Each has a plain-English tooltip. Intervals or the effective-sample note sit beside them. |
| Charts | (1) Signed error over time with zero line. (2) Error by hour of day, with buffer by hour. (3) Daily bias. (4) Distribution histogram with P10 and P90. (5) Error by forecast level, with the P90 over-forecast (a level-specific haircut) for each level. (6) Horizon, with a switch between decision-time and full curve. (7) Run and cutoff sensitivity. (8) Forecast against baseline against bias-corrected benchmark (labelled experimental). |
| Insights | Three or four generated sentences from the deterministic templates |
| Honesty panel | A short "What this does not tell you" box: demand and prices are out of scope, causes of the bias are unverified, sample is 31 days |

### 11.6 Technology and structure

- **Vite, React and strict TypeScript, with plain CSS design tokens. React is the only runtime dependency.** Charts are small custom SVG components, data loading is a small hook, and routing uses the address-bar hash.
- API types are generated from the backend schemas (`scripts/gen_ts_types.py`) and checked by a test.
- Route-level code splitting, so the charts library loads only when needed.
- Each chart has an accessible text summary and a "view as table" option.
- Number formatting in one helper (MW with thousands separators, percentages to one decimal place).

### 11.7 Accessibility checklist

Keyboard-navigable controls, visible focus, ARIA labels on charts and controls, contrast of at least 4.5:1 in both themes, text alternatives for charts, and no information conveyed by colour alone.

## 12. Phase 7: Docker and deployment

### 12.1 Docker (local, CI, reviewer reproducibility)

| File | Design |
|---|---|
| `backend/Dockerfile` | Python 3.12 slim base with a pinned tag. Non-root user. Install pinned requirements without cache. Copy only the app and the data file. `HEALTHCHECK` on `/api/v1/health`. Starts `uvicorn` on `$PORT`. |
| `frontend/Dockerfile` | Multi-stage: Node build stage, then an Nginx stage serving the built files. |
| `frontend/nginx.conf` | SPA fallback to `index.html`, security headers, gzip, and a proxy from `/api/` to the backend, so the browser sees one origin (as on Vercel). |
| `docker-compose.yml` | Two services, `backend` and `frontend`. The frontend waits for the backend health check. Database mounted read-only. Single exposed port. |
| `docker-compose.dev.yml` | Override for development: bind mounts, auto-reload, Vite dev server. |
| `.dockerignore` | Excludes `node_modules`, caches, `.git`, and test artefacts. |

**Reviewer experience:** `docker compose up --build`, then open `http://localhost:8080`.

### 12.2 Vercel (production)

| Aspect | Plan |
|---|---|
| Project | One project containing both the Vite build and the FastAPI function, using Vercel **Services** (beta) |
| Front end | Static output served by the platform. SPA fallback rewrite for `/accuracy`. |
| API | FastAPI service declared under `services` in `vercel.json` and reached through a rewrite from `/api/(.*)`. The backend receives the full path, so app routes are defined as `/api/v1/...` everywhere. Nginx (Docker) and the Vite dev proxy forward `/api` unchanged. Same domain, so no cross-origin traffic. |
| Data | `wind.sqlite` included with the function bundle, opened read-only and immutable |
| Config | `vercel.json` with `services` (the older `experimentalServices` key is rejected for new projects), service rewrites, headers and any file inclusion, and the dashboard Framework Preset set to Services. **Details confirmed in Phase 0. Fallback: two projects joined by an external rewrite.** |
| Environment variables | `ALLOWED_HOSTS`, `ALLOWED_ORIGINS`, `RATE_LIMIT_PER_MIN`, `ENV` |
| Naming | Neutral project name so the URL does not reveal identity |
| Verification | Run the Postman collection against the live URL. Open it in an incognito window on a phone and a laptop. |

**How the two paths stay identical:** only the entry point differs (uvicorn in Docker, a thin `backend/main.py` that re-exports the app on Vercel). The application package, tests and data are shared. CI runs the tests once, and builds the Docker images to prove they work.

## 13. Phase 8: documentation

### 13.1 README outline

1. One-paragraph description and the live link.
2. **AI-use disclosure** (required): which tools were used and for what (planning, code, tests, documentation), and that outputs were reviewed and tested.
3. Quick start with Docker (one command).
4. Quick start without Docker (Python and Node steps).
5. Repository map (every top-level file and folder).
6. How the data was obtained and how to re-run ingestion.
7. Key assumptions (cutoff, window, sign, alignment) and where to read more.
8. Testing: how to run each suite.
9. Deployment notes (Vercel, and why Docker is not used there).
10. Limitations and future work.
11. Attribution and licence.

### 13.2 Other documents

| Document | Content |
|---|---|
| `DATA_NOTES.md` | Facts and exploration (already written) |
| `METHODOLOGY.md` | The maths of section 7, with the worked example |
| `DECISIONS.md` | Short ADR entries: context, decision, consequence. Seeded from section 3 here. |
| Inline docstrings | Every `core` function states its inputs, its outputs and its no-peeking guarantee |

## 14. Phase 9: the video (max 10 minutes)

The evaluation **starts with the video**, so it gets real preparation.

### 14.1 Part 1: customer pitch (max 5 minutes)

**Goal:** impress. Tell one story: "Here is what you will see tomorrow morning, how far to trust it, and what to do about it."

| Time | Beat | On screen |
|---|---|---|
| 0:00 to 0:30 | The problem: buy day-ahead, depend on wind forecasts, errors are costly both ways | A single slide or the assumptions panel |
| 0:30 to 1:30 | **Forecast page.** Pick a day with a dramatic miss (28 January is a strong candidate). Show what the buyer knew, then **reveal the actuals** | Forecast page, toggle on |
| 1:30 to 3:00 | **Accuracy page.** Headline: the forecast ran about 1.9 GW (16%) too high in January and was too high on most days. Explain MAE, bias and the over-forecast share in plain words | KPI cards, error-over-time chart |
| 3:00 to 4:00 | **The "so what".** The buffer: "plan on forecast minus X MW to be covered 9 times in 10". Show the coverage backtest honestly. Mention the benchmark that removes the offset | Buffer callout, backtest, benchmark chart |
| 4:00 to 4:30 | **Timing insight.** Waiting for later runs before the auctions changes little | Run sensitivity chart |
| 4:30 to 5:00 | **Honesty and next steps.** Demand and prices are out of scope. Suggest confirming what each series covers. Offer the extensions. | Honesty panel |

**Tone:** confident, plain English, no jargon without a gloss.

### 14.2 Part 2: technical review (max 5 minutes)

**Goal:** make review easy and transfer knowledge.

| Time | Beat | On screen |
|---|---|---|
| 0:00 to 0:45 | Architecture in one diagram: ingestion, SQLite, core, API, front end, two runtime paths | Diagram and repo tree |
| 0:45 to 1:45 | **Data.** What the exploration found (eight runs, hourly targets, 12:25 anomaly), the schema, why SQLite and why no live calls | `DATA_NOTES.md`, schema |
| 1:45 to 2:45 | **The core rule and the maths.** No-peeking selection. Run a leakage test live. Signed-error buffer and why. Expanding window. | `core/`, passing tests |
| 2:45 to 3:30 | **API and security.** Middleware order, validation, a Postman run showing 422, 429 and headers | Postman |
| 3:30 to 4:15 | **Front end, Docker, CI.** Generated types, accessibility, `docker compose up`, a green pipeline | Terminal, CI page |
| 4:15 to 5:00 | **Trade-offs and limits.** Rate limiting on serverless, small effective sample, unverified bias cause. What you would do with more time. | Closing slide |

### 14.3 Recording checklist

- Rehearse twice with a timer. Hard-stop each part at five minutes.
- Close notifications. Use a clean browser profile and a readable zoom level.
- Pre-open every tab. Warm the live app first so there is no cold start on camera.
- Record audio first and check it. Decide in advance what is on camera, if anything.
- Upload as **unlisted**. Open the link in incognito mode. Add timestamps for the two parts in the description.

## 15. Phase 10: submission

**Final checklist:**

- [ ] Repository is public, with an anonymous name.
- [ ] Commit history shows a neutral identity. No personal data in any file, including `package.json`, LICENSE, README, and the deployed URL.
- [ ] README contains: file and directory details, how to start, the live link, the AI disclosure.
- [ ] A fresh clone starts with `docker compose up --build`, tested on a clean machine or clean directory.
- [ ] Live Vercel link works in an **incognito window**, on desktop and mobile.
- [ ] Both themes look right. No console errors.
- [ ] CI is green on the final commit.
- [ ] Postman collection exported and committed.
- [ ] Video is unlisted, at most 10 minutes, link tested in incognito.
- [ ] Every URL in the form was opened in incognito and verified.
- [ ] Form submitted.

## 16. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Vercel Python setup (entry point, file inclusion, version) behaves differently than assumed | Medium | High | Phase 0 hello-world early |
| SQLite cannot be opened in the read-only runtime | Medium | High | Open with `mode=ro&immutable=1`. Fall back to loading the data into memory at start-up. |
| Rate limiting unreliable on serverless | High | Low | Document it. Use platform rules if the Hobby tier permits them. |
| The reviewer questions the large bias | High | Medium | Present the evidence, the three tests, and the labelled hypotheses. Do not overclaim. |
| Percentiles are unstable with 31 days | High | Medium | Day-block bootstrap intervals, minimum-history rule, effective-sample note |
| Secondary-source gate closures are out of date for 2026 | Medium | Medium | Verify against operators' notices before the video |
| Identity leakage through metadata or URLs | Medium | Medium | Phase 0 audit and final checklist |
| Scope creep beyond the brief | High | Medium | Must, Should and Stretch labels. Cut Stretch first. |
| Cold start on the live app during the demo | Medium | Low | Warm the app before recording |

## 17. Open items to verify (carried over)

| Item | When | How |
|---|---|---|
| Services (beta) layout works on Hobby, file inclusion for the database, response size limit, `/api/docs` behaviour under a prefix. Already confirmed from the docs: Python 3.12 default, 500 MB bundle limit, zero-configuration FastAPI. | Phase 0 | Hello-world deploy |
| What the Hobby firewall allows for rate limiting | Phase 0 | Dashboard |
| Edge caching behaviour of `s-maxage` on function responses | Phase 0 | Inspect headers on the deploy |
| Gate-closure times for January 2026 | Before the video | Operators' own notices |
| Whether FUELHH values are revised after publication | Phase 1 | Re-fetch and compare |
| What WINDFOR and FUELHH each cover | Cannot settle with permitted data | State as a limitation, recommend the client ask Elexon or NESO |
| Elexon licence and attribution wording | Phase 1 | Insights terms |

## 18. Out of scope and future work

Say these out loud in the video. They show judgement rather than gaps.

- **Demand data** and therefore the actual "MW to procure". The app reports "firm wind" instead.
- **Prices** and therefore the money cost of over- or under-buying.
- **Installed capacity**, so normalisation uses mean actual output.
- **Explaining the bias**: curtailment, scope differences, or model error.
- **Regional or solar data**, and any source beyond Elexon.
- **Automatic data refresh**. The app serves a fixed January 2026 snapshot. A production version would refresh on a schedule.
- **Probabilistic forecasting** beyond empirical quantiles.

## 19. Glossary

| Term | Meaning |
|---|---|
| Day-ahead market | Auction where power for tomorrow is bought and sold today |
| Gate closure | The deadline after which bids for an auction are no longer accepted |
| Settlement period | A 30-minute slot of the electricity trading day, numbered 1 to 48 |
| MW | Megawatt, a rate of power. Wind output here is a national total in MW. |
| WINDFOR | Elexon dataset of wind generation forecasts |
| FUELHH | Elexon dataset of half-hourly generation by fuel type (actuals) |
| Run | One publication of a WINDFOR forecast |
| Horizon | Time between when a forecast was published and the time it is about |
| Bias | Average signed error. Positive means the forecast is too high. |
| MAE, RMSE | Average size of error, and a version that punishes large errors more |
| Percentile (P90) | The value that 90% of observations do not exceed |
| Buffer | MW to subtract from the forecast to be covered at a chosen confidence |
| Firm wind | Forecast minus buffer |
| Coverage | Share of hours in which actual wind was at least the firm-wind level |
| Skill score | Improvement over a baseline, from 0 (none) towards 1 (perfect) |
| Curtailment | Reducing wind output for grid or system reasons |
| Look-ahead (leakage) | Using information that would not have been available at decision time |