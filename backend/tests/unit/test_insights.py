from datetime import date

from app.core.breakdowns import DaySummary
from app.core.buffer import BacktestDay, BacktestResult
from app.core.insights import generate_insights
from app.core.stats import Metrics, summarize


def day(n, bias):
    return DaySummary(date(2026, 1, n), 1000.0, 900.0, Metrics(n=24, bias=bias, mae=abs(bias)))


def overall():
    f = [1100.0, 1100.0, 1100.0, 900.0]
    a = [1000.0, 1000.0, 1000.0, 1000.0]
    return summarize(f, a)


def test_all_sentences_are_generated_with_the_right_numbers():
    bt = BacktestResult(0.9, 7, (BacktestDay(date(2026, 1, 10), 150.0, 7, 10, 8),), 0)
    lines = generate_insights(overall(), [day(1, 100.0), day(28, 5375.0), day(3, -200.0)], 4098.0, 0.9, bt)
    text = "\n".join(lines)
    assert "above actual wind in 75% of hours and on 2 of 3 days" in text
    assert "+50 MW" in text
    assert "Largest daily miss: 28 Jan" in text and "5,375 MW above actual wind" in text
    assert "forecast minus 4,098 MW" in text and "90% of hours" in text
    assert "held in 80.0% of hours" in text
    assert len(lines) == 5


def test_largest_miss_can_be_below_actual():
    lines = generate_insights(overall(), [day(1, 100.0), day(2, -900.0)], None, 0.9)
    assert any("Largest daily miss: 2 Jan" in l and "below actual wind" in l for l in lines)


def test_sentences_are_skipped_when_inputs_are_missing():
    assert generate_insights(Metrics(n=0), [], None, 0.9) == []
    lines = generate_insights(overall(), [], None, 0.9)
    assert not any("Largest daily miss" in l for l in lines)
    assert not any("buffer" in l or "minus" in l for l in lines)