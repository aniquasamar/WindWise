"""Decision-time forecast selection: the "no peeking" rule.

For delivery day D the buying decision is made on D-1 at the cutoff time (default 09:00 UK).
The forecast the buyer could have seen for a target hour is the one with the latest
`publish_time` that is at or before the cutoff.

Hard rules:
  * only `publish_time <= cutoff` is eligible (equality is included);
  * selection is per target hour;
  * if a target has no eligible forecast it is reported as MISSING. It is never filled
    from a later run, because that would use information the buyer did not have.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Iterable, Optional

from .timeutils import HOUR, cutoff_utc, day_bounds_utc, decision_date_for, hourly_grid

DEFAULT_CUTOFF = time(9, 0)


@dataclass(frozen=True)
class ForecastRow:
    publish_time: datetime
    target_time: datetime
    mw: float


@dataclass(frozen=True)
class SelectedPoint:
    target_time: datetime
    forecast_mw: float
    publish_time: datetime

    @property
    def horizon_h(self) -> float:
        """Hours between publication and the target hour."""
        return (self.target_time - self.publish_time).total_seconds() / 3600.0


class ForecastBook:
    """All forecast rows, indexed by target hour for fast "latest at or before" lookups."""

    def __init__(self, rows: Iterable[ForecastRow]) -> None:
        grouped: dict[datetime, list[tuple[datetime, float]]] = defaultdict(list)
        for r in rows:
            grouped[r.target_time].append((r.publish_time, r.mw))
        self._pubs: dict[datetime, list[datetime]] = {}
        self._mws: dict[datetime, list[float]] = {}
        for target, items in grouped.items():
            items.sort(key=lambda x: x[0])
            pubs = [p for p, _ in items]
            if len(set(pubs)) != len(pubs):
                raise ValueError(f"duplicate forecast for target {target} at the same publish time")
            self._pubs[target] = pubs
            self._mws[target] = [m for _, m in items]

    def latest_at_or_before(self, target: datetime, cutoff: datetime) -> Optional[tuple[datetime, float]]:
        pubs = self._pubs.get(target)
        if not pubs:
            return None
        i = bisect_right(pubs, cutoff)  # how many publications are <= cutoff
        if i == 0:
            return None
        return pubs[i - 1], self._mws[target][i - 1]

    def publications_for(self, target: datetime) -> list[tuple[datetime, float]]:
        """Every (publish_time, mw) recorded for a target hour, oldest publication first."""
        return list(zip(self._pubs.get(target, []), self._mws.get(target, [])))

    def publish_times(self) -> list[datetime]:
        return sorted({p for pubs in self._pubs.values() for p in pubs})

    def has_target(self, target: datetime) -> bool:
        return target in self._pubs


@dataclass(frozen=True)
class DecisionForecast:
    delivery_date: date
    decision_date: date
    cutoff_utc: datetime
    points: tuple[SelectedPoint, ...]
    missing_targets: tuple[datetime, ...]

    @property
    def runs_used(self) -> tuple[datetime, ...]:
        return tuple(sorted({p.publish_time for p in self.points}))


def select_decision_forecast(
    book: ForecastBook, delivery_date: date, cutoff_local: time = DEFAULT_CUTOFF
) -> DecisionForecast:
    decision = decision_date_for(delivery_date)
    cutoff = cutoff_utc(decision, cutoff_local)
    start, end = day_bounds_utc(delivery_date)

    points: list[SelectedPoint] = []
    missing: list[datetime] = []
    for target in hourly_grid(start, end):
        hit = book.latest_at_or_before(target, cutoff)
        if hit is None:
            missing.append(target)
        else:
            pub, mw = hit
            points.append(SelectedPoint(target_time=target, forecast_mw=mw, publish_time=pub))

    return DecisionForecast(
        delivery_date=delivery_date,
        decision_date=decision,
        cutoff_utc=cutoff,
        points=tuple(points),
        missing_targets=tuple(missing),
    )