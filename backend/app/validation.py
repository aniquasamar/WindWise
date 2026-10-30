"""Request validation rules (framework-free, so they are unit-tested without a web server).

Every rule raises ApiError with HTTP 422 and a short message that never echoes raw input.
"""
from __future__ import annotations

import re
from datetime import date, time

from app.scope import FIRST_DELIVERY, LAST_DELIVERY

DEFAULT_CUTOFF = time(9, 0)
CUTOFF_MIN = time(3, 0)
CUTOFF_MAX = time(16, 0)
CUTOFF_STEP_MINUTES = 15
ALLOWED_CONFIDENCE = (0.80, 0.90, 0.95)
DEFAULT_CONFIDENCE = 0.90
VIEWS = ("decision", "full")
MAX_RANGE_DAYS = 31

_CUTOFF_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class ApiError(Exception):
    """An error that is safe to show to the client."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _bad(message: str) -> ApiError:
    return ApiError(422, "validation_error", message)


def parse_cutoff(value: str) -> time:
    m = _CUTOFF_RE.match(value or "")
    problem = (
        f"cutoff must be HH:MM UK time in {CUTOFF_STEP_MINUTES}-minute steps, "
        f"between {CUTOFF_MIN.strftime('%H:%M')} and {CUTOFF_MAX.strftime('%H:%M')}"
    )
    if not m:
        raise _bad(problem)
    t = time(int(m.group(1)), int(m.group(2)))
    if not (CUTOFF_MIN <= t <= CUTOFF_MAX) or t.minute % CUTOFF_STEP_MINUTES != 0:
        raise _bad(problem)
    return t


def validate_confidence(value: float) -> float:
    for allowed in ALLOWED_CONFIDENCE:
        if abs(value - allowed) < 1e-9:
            return allowed
    raise _bad("confidence must be one of " + ", ".join(f"{c:g}" for c in ALLOWED_CONFIDENCE))


def validate_delivery_date(d: date) -> date:
    if not (FIRST_DELIVERY <= d <= LAST_DELIVERY):
        raise _bad(f"delivery_date must be between {FIRST_DELIVERY.isoformat()} and {LAST_DELIVERY.isoformat()}")
    return d


def validate_range(first: date, last: date) -> tuple[date, date]:
    for name, d in (("from", first), ("to", last)):
        if not (FIRST_DELIVERY <= d <= LAST_DELIVERY):
            raise _bad(f"{name} must be between {FIRST_DELIVERY.isoformat()} and {LAST_DELIVERY.isoformat()}")
    if first > last:
        raise _bad("from must not be after to")
    if (last - first).days + 1 > MAX_RANGE_DAYS:
        raise _bad(f"the range may cover at most {MAX_RANGE_DAYS} days")
    return first, last


def validate_view(value: str) -> str:
    if value not in VIEWS:
        raise _bad("view must be one of " + ", ".join(VIEWS))
    return value