"""Request parameter dependencies. All real rules live in app.validation (framework-free)."""
from datetime import date, time

from fastapi import Query, Request, Response

from app.scope import FIRST_DELIVERY, LAST_DELIVERY
from app.validation import (
    ApiError,
    parse_cutoff,
    validate_confidence,
    validate_delivery_date,
    validate_range,
    validate_view,
)


def cutoff_param(cutoff: str = Query("09:00", description="UK-time cutoff on the decision date, HH:MM, 15-minute steps, 03:00 to 16:00")) -> time:
    return parse_cutoff(cutoff)


def confidence_param(confidence: float = Query(0.9, description="Buffer confidence level: 0.8, 0.9 or 0.95")) -> float:
    return validate_confidence(confidence)


def range_params(
    first: date = Query(FIRST_DELIVERY, alias="from", description="First delivery date (YYYY-MM-DD)"),
    last: date = Query(LAST_DELIVERY, alias="to", description="Last delivery date (YYYY-MM-DD)"),
) -> tuple[date, date]:
    return validate_range(first, last)


def delivery_param(delivery_date: date = Query(..., description="Delivery date (YYYY-MM-DD)")) -> date:
    return validate_delivery_date(delivery_date)


def view_param(view: str = Query("decision", description="'decision' or 'full'")) -> str:
    return validate_view(view)


def allow_only(*names: str):
    """Reject query parameters the endpoint does not define."""
    allowed = set(names)

    def check(request: Request) -> None:
        extra = set(request.query_params.keys()) - allowed
        if extra:
            raise ApiError(422, "unknown_parameter", "Unknown query parameter: " + ", ".join(sorted(extra)))

    return check


def cache_public(response: Response) -> None:
    """Data is immutable per deployment, so responses can be cached by browsers and the CDN."""
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=86400"


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"