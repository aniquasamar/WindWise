from datetime import date, time

import pytest

from app.validation import (
    ApiError,
    parse_cutoff,
    validate_confidence,
    validate_delivery_date,
    validate_range,
    validate_view,
)


def test_cutoff_accepts_valid_values():
    assert parse_cutoff("09:00") == time(9, 0)
    assert parse_cutoff("03:00") == time(3, 0)
    assert parse_cutoff("16:00") == time(16, 0)
    assert parse_cutoff("12:45") == time(12, 45)


@pytest.mark.parametrize("bad", ["", "9:00", "09:5", "25:00", "09:60", "02:45", "16:15", "09:10", "abc", "09:00:00", "09-00"])
def test_cutoff_rejects_invalid_values(bad):
    with pytest.raises(ApiError) as e:
        parse_cutoff(bad)
    assert e.value.status_code == 422 and e.value.code == "validation_error"


def test_cutoff_error_never_echoes_the_input():
    with pytest.raises(ApiError) as e:
        parse_cutoff("<script>alert(1)</script>")
    assert "script" not in e.value.message


def test_confidence():
    assert validate_confidence(0.9) == 0.9
    assert validate_confidence(0.95) == 0.95
    assert validate_confidence(0.8000000001) == 0.8
    for bad in (0.5, 0.99, 1.0, 0.0, -1):
        with pytest.raises(ApiError):
            validate_confidence(bad)


def test_delivery_date_window():
    assert validate_delivery_date(date(2026, 1, 2)) == date(2026, 1, 2)
    assert validate_delivery_date(date(2026, 2, 1)) == date(2026, 2, 1)
    for bad in (date(2026, 1, 1), date(2026, 2, 2), date(2025, 12, 31), date(2027, 1, 15)):
        with pytest.raises(ApiError):
            validate_delivery_date(bad)


def test_range_rules():
    assert validate_range(date(2026, 1, 2), date(2026, 2, 1)) == (date(2026, 1, 2), date(2026, 2, 1))
    assert validate_range(date(2026, 1, 10), date(2026, 1, 10)) == (date(2026, 1, 10), date(2026, 1, 10))
    with pytest.raises(ApiError):
        validate_range(date(2026, 1, 20), date(2026, 1, 10))      # reversed
    with pytest.raises(ApiError):
        validate_range(date(2026, 1, 1), date(2026, 1, 10))       # starts outside the window
    with pytest.raises(ApiError):
        validate_range(date(2026, 1, 10), date(2026, 3, 1))       # ends outside the window


def test_view():
    assert validate_view("decision") == "decision" and validate_view("full") == "full"
    with pytest.raises(ApiError):
        validate_view("other")