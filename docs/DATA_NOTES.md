# DATA_NOTES: Elexon wind actuals and forecasts

**Scope:** national-level GB wind generation, actuals (FUELHH) and forecasts (WINDFOR), for day-ahead purchase decisions made in **January 2026**.
**Purpose of this file:** a single record of what we know about the data, how we know it, and which methodology decisions follow from it. It feeds the README, the assumptions panel in the app, and the technical half of the video.
**Data retrieved:** the production database was built from a fetch at `2026-10-28T10:04:50Z` (`data_version` `284629bb721f`). The exploration scripts ran earlier against the same source.

## 0. How to read this file

Every statement carries one of four labels.

| Label | Meaning |
|---|---|
| **[Observed]** | Seen directly in the data we downloaded and analysed. |
| **[Documented]** | Stated in a source we read (listed in section 10). Mostly secondary sources, so treat with care. |
| **[Unverified]** | A hypothesis or belief we could not confirm with the permitted data. |
| **[Decision]** | A choice we made, with the reason. |

All exploration numbers in sections 4 to 7 were computed on **delivery days 1 to 31 January 2026**. Our final scope (section 8) is delivery days **2 January to 1 February 2026**, so every figure will be recomputed once the production pipeline exists. We expect small shifts, not a change in the story. Section 6.8 gives the headline figures recomputed on the final window with the production code; the other tables in section 6 are still on the exploration window.

## 1. Sources and access

| Item | Value |
|---|---|
| API | Elexon Insights (BMRS) API, base URL `https://data.elexon.co.uk/bmrs/api/v1` **[Documented]** |
| Authentication | None needed for the endpoints we used **[Observed]** |
| Actuals endpoint | `/datasets/FUELHH/stream`, with `settlementDateFrom`, `settlementDateTo`, `fuelType=WIND` **[Observed: worked]** |
| Forecasts endpoint | `/datasets/WINDFOR/stream`, with `publishDateTimeFrom`, `publishDateTimeTo` **[Observed: worked]** |
| Request windows used | 7 days per request. No truncation seen. **[Observed]** |
| Larger windows | Not tested. The real range limit is **[Unverified]** and not needed. |

**Row-count check for truncation:** each 7-day WINDFOR request returned 4,088 rows, which equals 7 days × 8 runs × 73 targets. The final single-day request returned 584 rows (8 × 73). Both match the structure exactly, so nothing was cut off. **[Observed]**

## 2. Schemas (observed)

**FUELHH (filtered to WIND):** `dataset`, `publishTime`, `startTime`, `settlementDate`, `settlementPeriod`, `fuelType`, `generation`.
**WINDFOR:** `dataset`, `publishTime`, `startTime`, `generation`.

- All timestamps are ISO 8601 strings ending in `Z` (UTC). **[Observed]**
- January is outside British Summer Time, so UTC equals UK local time for the whole scope. **[Decision]:** we still store UTC and convert to `Europe/London` in code, so the logic stays correct for other months.
- `generation` is an integer number of MW in both datasets. **[Observed]**
- `fuelType` contained only `WIND` after filtering. **[Observed]**

## 3. Actuals (FUELHH, WIND)

Checked over 1 to 31 January 2026 **[Observed]**:

| Check | Result |
|---|---|
| Rows | 1,488, exactly 31 × 48 |
| Missing half-hours | 0 |
| Duplicate `startTime` | 0 |
| Spacing | 30 minutes everywhere |
| Nulls / negatives | 0 / 0 |
| Minimum / maximum | 1,695 MW / 17,805 MW |
| Mean / median / std | 11,580.7 / 12,141 / 4,156.2 MW |
| 25th / 75th percentile | 8,197.5 / 15,265.5 MW |
| `publishTime` minus `startTime` | 30 minutes typically, maximum 2.42 hours |

**Consequences:**
- Actuals for a settlement period appear about 30 minutes after it ends, so at any cutoff the latest complete day is the previous calendar day.
- FUELHH values might be revised after first publication. We did not test this. **[Unverified]** We record the retrieval date in the database so the snapshot is reproducible.

## 4. Forecasts (WINDFOR)

Checked over runs published between 28 December 2025 and 1 February 2026 **[Observed]**:

| Check | Result |
|---|---|
| Rows | 21,024 (288 runs × 73 targets) |
| Distinct `publishTime` values | 288, which is 36 days × 8 runs |
| Run times (UTC) | 02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30 |
| Exception | On 2026-01-15 the 11:30 run was published at **12:25** |
| Target resolution | **Hourly**, on the hour (`:00`) |
| Targets per run | 73 |
| Window per run | From 21:00 on the day *before* the run date to 21:00 two days *after* it |
| Nulls / negatives | 0 / 0 |
| Duplicate (`startTime`, `publishTime`) | 0 |

**Horizon** (`startTime` minus `publishTime`) per run:

| Run | Minimum (h) | Maximum (h) |
|---|---|---|
| 02:30 | −5.5 | 66.5 |
| 04:30 | −7.5 | 64.5 |
| 07:30 | −10.5 | 61.5 |
| 09:30 | −12.5 | 59.5 |
| 11:30 | −14.5 | 57.5 |
| 15:30 | −18.5 | 53.5 |
| 18:30 | −21.5 | 50.5 |
| 22:30 | −25.5 | 46.5 |

**Negative horizons are rows whose target time is already in the past when the run is published.** They are not forecasts in the ordinary sense. **[Decision]:** they are excluded from decision-time analysis and shown only in the full-horizon curve, clearly labelled as "targets already elapsed".

**Documentation conflict.** Elexon's glossary page describes WINDFOR as four runs a day (04:30, 10:30, 16:30, 22:30) with 49 values. **[Documented]** The data show eight runs a day and 73 values. **[Observed]** The glossary is outdated, so we rely on the data. We never assume a fixed schedule in code: selection uses the actual `publishTime` values, which also handles the 12:25 anomaly.

## 5. The decision-time forecast

**[Decision]** Rule: for delivery day D and decision date d = D − 1, take every forecast row whose `publishTime` is at or before the cutoff on d (default **09:00 UK time**). For each target hour, keep the row with the latest `publishTime`. Never fall back to a later run.

**[Observed]** With the 09:00 cutoff the rule picks **the 07:30 run on d for every delivery day**, giving:
- 24 hourly targets per delivery day (00:00 to 23:00),
- a decision-time horizon of **16.5 to 39.5 hours**,
- no day left without a forecast.

### Why 09:00

| Fact | Source |
|---|---|
| EPEX GB hourly day-ahead auction closes at 09:20 UK time | **[Documented]**, EPEX and Nord Pool pages |
| N2EX day-ahead auction closes at 09:50 GMT | **[Documented]** |
| EPEX GB 30-minute day-ahead auction closes at 15:30 UK time | **[Documented]** |

The 09:00 default sits before the earliest hourly closure. The next run after 07:30 is 09:30, which lands **after** EPEX's closure and before N2EX's. These times come from vendor and market-commentary pages, not a single official 2026 notice, so we must re-check them against a primary source before the video. **[Unverified]**

## 6. Exploration results (delivery days 1 to 31 January 2026)

Convention: error = forecast − actual, in MW. Positive means over-forecast.

### 6.1 Headline (decision-time forecast, n = 744 hourly pairs)

| Metric | Value | Relative to mean actual |
|---|---|---|
| Bias | +1,851.5 MW | 16.0% |
| MAE | 2,127.5 MW | 18.4% |
| RMSE | 2,606.1 MW | 22.5% |
| Std of error (derived) | about 1,834 MW | |
| Σ forecast ÷ Σ actual | 1.1599 | |

Of 31 delivery days, 27 had a positive mean error. On about 19 days every hour was over-forecast (mean error equals mean absolute error at the rounding used).

### 6.2 Does alignment explain the bias? No.

| Actual compared against forecast at hour T | Bias | MAE | RMSE |
|---|---|---|---|
| A(T) | 1,851.5 | 2,127.5 | 2,606.1 |
| mean of A(T), A(T+30) | 1,851.9 | 2,142.1 | 2,611.7 |
| mean of A(T−30), A(T) | 1,848.6 | 2,111.1 | 2,597.6 |
| A(T+30) | 1,852.3 | 2,162.8 | 2,625.5 |

The bias varies by under 4 MW across variants. **[Decision]:** compare each hourly forecast with the **mean of the two half-hours in that hour** (A(T) and A(T+30)), because an hourly value naturally describes the whole hour.

### 6.3 Does it shrink as delivery approaches? No.

All targets in January across all runs (n per bucket in the first column). Negative horizons are elapsed targets.

| Horizon bucket (h) | n | Bias | MAE | RMSE |
|---|---|---|---|---|
| −30 to −12 | 1,086 | 1,913 | 1,998 | 2,521 |
| −12 to 0 | 2,635 | 1,682 | 1,831 | 2,345 |
| 0 to 12 | 2,976 | 1,582 | 1,801 | 2,277 |
| 12 to 24 | 2,976 | 1,811 | 1,991 | 2,474 |
| 24 to 36 | 2,976 | 1,839 | 2,123 | 2,587 |
| 36 to 48 | 2,945 | 2,005 | 2,337 | 2,866 |
| 48 to 70 | 2,510 | 1,480 | 2,372 | 2,978 |

Bias stays near +1.5 to +2.0 GW at every horizon, including targets already in the past. MAE grows with horizon, but only from about 1.8 GW to about 2.4 GW. A floor of about 1.8 GW at zero horizon means the two series do not converge. Samples within and across buckets are strongly dependent (same targets in many runs, same weather days), so treat these as descriptive.

### 6.4 By delivery day (decision-time forecast, mean over the 24 hours)

| Day | Forecast mean | Actual mean | Bias | MAE |
|---|---|---|---|---|
| 01-01 | 19,580 | 15,356 | 4,223 | 4,223 |
| 01-02 | 18,279 | 15,209 | 3,070 | 3,070 |
| 01-03 | 17,353 | 15,255 | 2,098 | 2,098 |
| 01-04 | 14,490 | 13,387 | 1,103 | 1,103 |
| 01-05 | 9,384 | 9,499 | −115 | 1,294 |
| 01-06 | 11,284 | 9,346 | 1,938 | 2,158 |
| 01-07 | 13,611 | 12,239 | 1,372 | 1,407 |
| 01-08 | 5,373 | 4,497 | 876 | 1,853 |
| 01-09 | 11,562 | 10,745 | 816 | 877 |
| 01-10 | 8,693 | 8,798 | −105 | 1,070 |
| 01-11 | 18,359 | 13,506 | 4,853 | 4,853 |
| 01-12 | 19,320 | 14,445 | 4,875 | 4,875 |
| 01-13 | 10,225 | 10,115 | 110 | 1,356 |
| 01-14 | 9,586 | 9,597 | −10 | 1,005 |
| 01-15 | 11,610 | 10,584 | 1,025 | 1,025 |
| 01-16 | 7,930 | 7,582 | 349 | 810 |
| 01-17 | 7,374 | 5,714 | 1,659 | 1,659 |
| 01-18 | 6,532 | 4,937 | 1,594 | 1,594 |
| 01-19 | 5,796 | 6,480 | −684 | 684 |
| 01-20 | 15,482 | 15,067 | 415 | 993 |
| 01-21 | 19,390 | 15,713 | 3,677 | 3,677 |
| 01-22 | 18,855 | 16,208 | 2,647 | 2,647 |
| 01-23 | 17,661 | 16,120 | 1,542 | 1,542 |
| 01-24 | 17,793 | 15,846 | 1,947 | 1,947 |
| 01-25 | 15,494 | 13,699 | 1,794 | 1,794 |
| 01-26 | 12,421 | 10,350 | 2,071 | 2,071 |
| 01-27 | 19,888 | 16,469 | 3,419 | 3,419 |
| 01-28 | 11,135 | 5,806 | 5,329 | 5,329 |
| 01-29 | 11,932 | 10,132 | 1,800 | 1,800 |
| 01-30 | 17,209 | 15,815 | 1,393 | 1,405 |
| 01-31 | 12,813 | 10,498 | 2,315 | 2,315 |

Observations:
- **Level dependence.** On the 11 days with a forecast mean above 17 GW the average bias was about +3.1 GW. On the 14 days below 12 GW it was about +1.0 GW (this group includes 28 January, a +5.3 GW outlier). **[Observed]**
- **A ceiling in actuals.** The forecast's daily mean exceeded 19 GW on four days (1, 12, 21, 27 January), while no actual half-hour in the month exceeded 17.8 GW. **[Observed]**
- **A genuine large miss.** On 28 January the forecast was about 5.3 GW above outturn even though the level was moderate. **[Observed]**
- **Clustering.** Errors persist within a day, so the effective sample size is much closer to 31 days than to 744 hours.

### 6.5 By hour of day (UTC equals UK time in January)

| Hour | Bias | MAE | Mean actual |
|---|---|---|---|
| 00 | 2,045 | 2,121 | 11,824 |
| 01 | 2,207 | 2,261 | 11,595 |
| 02 | 2,324 | 2,361 | 11,407 |
| 03 | 2,411 | 2,501 | 11,259 |
| 04 | 2,414 | 2,494 | 11,182 |
| 05 | 2,446 | 2,521 | 11,043 |
| 06 | 2,427 | 2,494 | 10,960 |
| 07 | 2,268 | 2,345 | 11,056 |
| 08 | 2,023 | 2,145 | 11,243 |
| 09 | 1,944 | 2,079 | 11,295 |
| 10 | 1,883 | 2,049 | 11,325 |
| 11 | 1,661 | 2,052 | 11,457 |
| 12 | 1,467 | 1,978 | 11,527 |
| 13 | 1,400 | 2,014 | 11,512 |
| 14 | 1,440 | 2,004 | 11,459 |
| 15 | 1,394 | 1,961 | 11,587 |
| 16 | 1,468 | 1,941 | 11,683 |
| 17 | 1,482 | 2,030 | 11,874 |
| 18 | 1,517 | 2,042 | 12,068 |
| 19 | 1,506 | 2,043 | 12,218 |
| 20 | 1,505 | 1,931 | 12,263 |
| 21 | 1,616 | 1,833 | 12,165 |
| 22 | 1,711 | 1,864 | 12,071 |
| 23 | 1,877 | 1,997 | 11,874 |

Bias peaks around 03:00 to 06:00 (about +2.4 GW) and is lowest from 12:00 to 16:00 (about +1.4 GW). The pattern is real but smaller than the variation between days.

### 6.6 Which run you act on (cutoff sensitivity, n = 744 each)

| Cutoff (UK) | Run used | Bias | MAE | RMSE |
|---|---|---|---|---|
| 03:00 | 02:30 | 1,862 | 2,189 | 2,689 |
| 05:00 | 04:30 | 1,798 | 2,129 | 2,632 |
| 08:00 and 09:00 | 07:30 | 1,852 | 2,128 | 2,606 |
| 09:45 | 09:30 | 1,840 | 2,107 | 2,611 |
| 12:00 | 09:30 / 11:30 | 1,806 | 2,003 | 2,470 |

- Differences between runs before the auctions close are small (MAE within about 3%).
- Only the 11:30 run helps visibly: MAE about 6% lower and RMSE about 5% lower than the 07:30 run. It arrives after the hourly day-ahead auctions have closed.
- The 12:00 row mixes two runs. For delivery on 16 January the late 12:25 publication falls after a 12:00 cutoff, so the 09:30 run is used that day.

### 6.7 Baseline: actual wind 48 hours earlier

| | Bias | MAE | RMSE |
|---|---|---|---|
| Forecast | 1,851.5 | 2,127.5 | 2,606.1 |
| Baseline (same hour, 48 h earlier) | −255.3 | 4,301.3 | 5,313.7 |

Skill: 0.505 (MAE), 0.51 (RMSE). The baseline is nearly unbiased while the forecast is not, and wind persistence at two days is a weak benchmark. A skill of 0.5 against it is therefore not strong evidence of quality. This is why the plan adds a second, bias-corrected benchmark (section 8).

### 6.8 Headline recomputed on the final window (production code)

Source: `scripts/headline_check.py`. Delivery days 2 January to 1 February 2026 (31 days), cutoff 09:00 UK time, database `data_version` `284629bb721f`. Every day used the 07:30 run. 744 hourly pairs, with no missing forecast and no missing actual hours. **[Observed]**

| Metric | Exploration (delivery 1 to 31 Jan) | Final window (2 Jan to 1 Feb) |
|---|---|---|
| Bias (MW) | +1,851.5 | +1,748 |
| MAE (MW) | 2,127.5 | 2,039 |
| RMSE (MW) | 2,606.1 | 2,505 |
| Std of error (MW) | about 1,834 | 1,794 |
| Mean actual (MW) | about 11,580 | 11,284 |
| nMAE / nRMSE | 18.4% / 22.5% | 18.1% / 22.2% |
| Days with positive mean error | 27 of 31 | 27 of 31 |
| Over-forecast share of hours | not computed | 84.9% |
| Skill vs 48-hour baseline (MAE / RMSE) | 0.505 / 0.51 | 0.530 / 0.535 |

**Reconciliation.** Moving the window drops 1 January (a +4,223 MW day) and adds 1 February. Solving the two means for the added day implies a bias of roughly +1,015 MW on 1 February. This is arithmetic from the two averages and has not been checked against the day directly. The direction and size of every change are consistent with that swap, so the production code reproduces the exploration.

**Percentiles and buffers (final window).**

| Measure | Value (MW) |
|---|---|
| P50 / P90 / P95 of absolute error | 1,671 / 4,098 / 5,283 |
| Signed error P10 / P90 | −549 / 4,098 |
| In-sample buffer at 80% / 90% / 95% | 3,104 / 4,098 / 5,283 |

P90 of absolute error equals the signed P90 because the largest absolute errors are all over-forecasts. The under-forecast side is shallow (P10 is only −549 MW).

Largest daily over-forecasts: 28 Jan (+5,375 MW), 12 Jan (+4,868 MW), 11 Jan (+4,802 MW).

**Out-of-sample backtest** (expanding window, at least 7 days of history, 23 days and 552 hours scored, 8 days skipped):

| Promised confidence | Hours where actual wind was at least forecast minus buffer |
|---|---|
| 90% | **85.5%** |
| 95% | **88.8%** |

The buffer fell short of its promise at both levels. The per-day output (section 6.9) shows the shortfall is concentrated, not diffuse: 18 of the 23 scored days were fully covered, and all 80 uncovered hours (of 552) fall on five days (11, 12, 21, 27 and 28 January). The first two came with only 8 to 9 days of history, which supports the short-history explanation for them. 28 January came with 25 days of history and still exceeded the buffer (day mean error 5,375 MW against a buffer of 3,845 MW). So a trailing 90th percentile also cannot anticipate rare, large misses, even with a longer history. **[Observed]** With about 23 usable days the buffer estimate is itself uncertain (6.9). We report the shortfall as measured and do not tune it away.

### 6.9 Remaining analyses on the final window (production code)

Same script and database as 6.8: delivery days 2 January to 1 February 2026, 09:00 cutoff, error = forecast − actual. **[Observed]**

**Uncertainty.** 90% intervals from a day-block bootstrap (1,000 resamples of whole delivery days, fixed seed):

| Statistic | Point (MW) | 90% interval (MW) |
|---|---|---|
| Bias | 1,748 | 1,313 to 2,195 |
| MAE | 2,039 | 1,678 to 2,408 |
| RMSE | 2,505 | 2,037 to 2,903 |
| Buffer at 90% | 4,098 | 3,225 to 5,267 |

The bias interval sits well above zero, so the over-forecast is robust across days. The buffer is uncertain by roughly one gigawatt either way.

**Per-day backtest at 90%** (23 scored days). Days that were not fully covered:

| Day | History days | Buffer (MW) | Hours covered | Day mean error (MW) | Day max error (MW) |
|---|---|---|---|---|---|
| 11 Jan | 8 | 3,459 | 0 of 24 | 4,802 | 5,953 |
| 12 Jan | 9 | 3,339 | 6 of 24 | 4,868 | 6,870 |
| 21 Jan | 18 | 4,012 | 13 of 24 | 3,658 | 4,844 |
| 27 Jan | 24 | 3,926 | 21 of 24 | 3,479 | 6,184 |
| 28 Jan | 25 | 3,845 | 0 of 24 | 5,375 | 6,271 |

The buffer itself moved between about 3.3 and 4.8 GW across scored days: it rose after the 11 and 12 January misses and drifted down as calmer days accumulated.

**By forecast level** (terciles of the forecast):

| Level | Forecast range (MW) | n | Bias | MAE | RMSE | nMAE |
|---|---|---|---|---|---|---|
| Low | 3,161 to 10,099 | 248 | 746 | 1,504 | 1,830 | 22.5% |
| Medium | 10,118 to 16,655 | 248 | 1,568 | 1,684 | 2,192 | 14.6% |
| High | 16,658 to 21,064 | 248 | 2,929 | 2,929 | 3,266 | 18.7% |

Bias roughly doubles from one level to the next. In the high tercile the MAE equals the bias, which means every hour was over-forecast. A single constant buffer is therefore too large on low-wind days and too small on high-wind days. This is consistent with the ceiling in actuals noted in 6.4.

**By hour of day (UK time).** Bias peaks from 03:00 to 06:00 (2.3 to 2.4 GW) and is lowest at 15:00 (1.25 GW). MAE ranges from 1.8 to 2.4 GW.

**Horizon, decision-time view** (6-hour buckets):

| Horizon | n | Bias | MAE | RMSE |
|---|---|---|---|---|
| 12 to 18 h | 62 | 2,043 | 2,098 | 2,600 |
| 18 to 24 h | 186 | 2,287 | 2,359 | 2,858 |
| 24 to 30 h | 186 | 1,630 | 1,966 | 2,373 |
| 30 to 36 h | 186 | 1,323 | 1,901 | 2,285 |
| 36 to 42 h | 124 | 1,608 | 1,846 | 2,393 |

Because one run is used for the whole delivery day, horizon and time of day move together in this view, so it cannot separate the two. The full curve below is the proper horizon view.

**Horizon, full curve** (all runs, all window targets, 12-hour buckets; descriptive):

| Horizon | n | Bias | MAE | RMSE |
|---|---|---|---|---|
| Already elapsed (0 h or less) | 3,697 | 1,666 | 1,800 | 2,295 |
| 0 to 12 h | 2,976 | 1,465 | 1,697 | 2,156 |
| 12 to 24 h | 2,976 | 1,703 | 1,893 | 2,368 |
| 24 to 36 h | 2,976 | 1,718 | 2,019 | 2,481 |
| 36 to 48 h | 2,945 | 1,905 | 2,250 | 2,789 |
| 48 to 60 h | 2,076 | 1,522 | 2,306 | 2,901 |
| 60 to 72 h | 434 | 829 | 2,370 | 3,041 |

MAE grows from about 1.70 GW (0 to 12 h) to about 2.37 GW (60 to 72 h), roughly 40%. Bias stays between +1.5 and +1.9 GW (the last bucket is sparse). Targets that had already elapsed still show an MAE of 1.8 GW, which points to a persistent gap between the two series and not to a lack of forecast skill.

**Cutoff sensitivity:**

| Cutoff (UK) | Run(s) used | Bias | MAE | RMSE | MAE vs 09:00 |
|---|---|---|---|---|---|
| 03:00 | 02:30 | 1,735 | 2,073 | 2,578 | +1.7% |
| 05:00 | 04:30 | 1,671 | 2,016 | 2,521 | −1.1% |
| 08:00 and 09:00 | 07:30 | 1,748 | 2,039 | 2,505 | 0 |
| 10:00 | 09:30 | 1,730 | 2,013 | 2,506 | −1.3% |
| 12:00 | 09:30 and 11:30 | 1,687 | 1,901 | 2,359 | −6.8% |
| 16:00 | 15:30 | 1,709 | 1,873 | 2,327 | −8.1% |

The 12:00 row mixes two runs because the 11:30 run on 15 January was published at 12:25. Runs available before the hourly day-ahead auctions close change MAE by at most about 1.3% in either direction. Later runs help by about 7 to 8%, but they arrive after those closures. The 15:30 run appears at the time the 30-minute auction is documented to close (15:30 UK), so it is unlikely to help that auction either. **[Documented closure times, unverified for 2026]**

**Experimental benchmark** (forecast corrected using only past days; 7-day window, at least 3 days of history; 27 days and 648 hours scored, the first 4 days skipped):

| Method | Official bias / MAE / RMSE (MW) | Corrected bias / MAE / RMSE (MW) | RMSE change | MAE change |
|---|---|---|---|---|
| Ratio (default) | 1,773 / 2,056 / 2,541 | 274 / 1,383 / 1,810 | −28.8% | −32.8% |
| Offset | 1,773 / 2,056 / 2,541 | 129 / 1,572 / 2,019 | −20.5% | −23.5% |

The ratio method was chosen as the default in advance, before any results were seen, because the bias grows with wind level. The results confirm it was the better choice. The remaining RMSE of about 1.8 GW is random scatter that a simple correction cannot remove.

## 7. Interpretation

**[Observed]** The forecast over-predicts GB wind outturn by a large, persistent margin in January 2026. The gap is not an artefact of hourly alignment (6.2), does not shrink toward delivery (6.3), grows with wind level (6.4), and the actuals show a ceiling that the forecast does not respect.

**[Unverified] Candidate explanations**, in rough order of plausibility. We cannot settle them with the permitted data:

1. **Curtailment and constraints.** Outturn from metered units reflects operational actions such as curtailment, which NESO training material describes. A forecast of potential output would exceed outturn most when wind is high. This fits the level dependence and the ceiling.
2. **Scope mismatch.** The two series may not cover exactly the same fleet (for example transmission-metered versus a wider set of units). The Elexon glossary calls WINDFOR a forecast for "all Power Park Modules" and the NESO material distinguishes metered from non-metered wind, but neither source settles what each dataset includes.
3. **Genuine forecast bias** in the model for this period. Day 28 January looks like a real miss rather than a scope effect.

**[Decision]** We present the gap as a measured, systematic property of the two series as published. We state the hypotheses plainly, label them unverified, and recommend that the client confirm the scope of each series with Elexon or NESO. We do not claim to know the cause.

## 8. Methodology decisions that follow

| # | Decision | Reason |
|---|---|---|
| 1 | Decisions are made **1 to 31 January 2026** at the cutoff; delivery days are **2 January to 1 February 2026** | Literal reading of "purchase decisions to be made in January 2026" |
| 2 | Default cutoff **09:00 UK time on the decision date**, selectable in 15-minute steps | Before the earliest hourly auction closure (section 5) |
| 3 | Decision-time forecast is the latest run with `publishTime` ≤ cutoff, selected per target, never backfilled from a later run | Prevents look-ahead |
| 4 | Evaluation grain is **hourly**; actuals are the mean of the two half-hours starting at each hour | Forecasts are hourly (6.2) |
| 5 | Error = forecast − actual; positive means over-forecast | One convention everywhere |
| 6 | Hours missing either value are excluded and counted, never filled | Honest sample size |
| 7 | Elapsed-target rows (horizon ≤ 0) are excluded from decision-time analysis and shown only in the full-horizon curve | They are not forecasts |
| 8 | Baseline = actual for the same hour 48 hours earlier | Day D−1 is incomplete at the cutoff, so D−2 is the latest complete day |
| 9 | A second, **clearly labelled extra benchmark**: the decision-time forecast corrected using only past complete days | Bias dominates the error; the buffer alone does not show how much is fixable |
| 10 | Buffer uses the **signed** error distribution (P90 of forecast − actual, floored at 0) | The costly risk is over-forecasting wind |
| 11 | Anything shown as "what you would have known on day D" uses only earlier days (expanding window) | Same no-peeking principle applied to statistics |
| 12 | Errors are binned by **forecast level**, not by actual level | The forecast is known at decision time; the actual is not |

**Lookback data.** Baselines for the earliest delivery days need actuals from 31 December. They belong to the information available at the 1 January decision, so we include them and say so. No pre-January forecast run is used for scored decision-time results.

## 9. Open items to verify

| Item | How |
|---|---|
| Gate-closure times in January 2026 | Read the operators' own notices. Update section 5 and the app text. |
| Whether FUELHH values are revised after first publication | Re-fetch a past period at ingestion and compare. |
| Scope of WINDFOR versus FUELHH | Ask or read Elexon and NESO method notes. Cannot be settled from this data. |
| Why the 15 January run was published at 12:25 | Informational only. Record it in the app's data-quality note. |
| Elexon data licence and attribution wording | Check the Insights terms. Add attribution to the footer and README. |
| Larger request windows | Not needed. Skip unless ingestion changes. |

## 10. Reproducibility

- Exploration scripts: `explore_elexon.py` (fetch and checks) and `explore2.py` (offline analysis of the saved CSVs). To be archived under `scripts/exploration/`.
- Raw outputs: `raw_actuals.csv`, `raw_forecasts.csv`, `report.txt`, `report2.txt`.
- Production ingestion will replace these. It will store raw responses, the SQLite database, and the retrieval date and row counts in a `meta` table.

**References consulted** (secondary sources, to be replaced by primary ones where possible):
- Elexon Insights developer portal: `https://developer.data.elexon.co.uk/`
- Elexon glossary, Wind Generation Forecast: `https://elexon.co.uk/glossary/wind-generation-forecast`
- Elexon change proposal CP1381 (WINDFOR fields and hourly structure): `https://assets.elexon.co.uk/wp-content/uploads/sites/11/2012/10/28165754/CP1381.pdf`
- Nord Pool, about the day-ahead GB auction: `https://support.nordpoolgroup.com/support/solutions/articles/8000088463-about-the-day-ahead-gb-auction`
- EPEX SPOT: `https://www.epexspot.com`
- NESO forecasting training slides: `https://cer.iitk.ac.in/assets/advs/Energy%20Forecasting%20standard%20slides%20-%20India%20delegation%20Nov24.pdf`