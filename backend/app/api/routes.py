"""All API routes (read-only GET endpoints under /api/v1)."""
from datetime import date, time

from fastapi import APIRouter, Depends

from app.api import schemas as s
from app.api.params import (
    allow_only,
    cache_public,
    confidence_param,
    cutoff_param,
    delivery_param,
    no_store,
    range_params,
    view_param,
)
from app.container import get_service
from app.services import AnalyticsService

router = APIRouter(prefix="/api/v1")

RANGE_CUTOFF = ("from", "to", "cutoff")
RANGE_CUTOFF_CONF = ("from", "to", "cutoff", "confidence")


def _public(*params: str) -> list:
    return [Depends(allow_only(*params)), Depends(cache_public)]


@router.get("/health", response_model=s.HealthOut, dependencies=[Depends(allow_only()), Depends(no_store)])
def health():
    return {"status": "ok"}


@router.get("/meta", response_model=s.MetaOut, dependencies=_public())
def meta(svc: AnalyticsService = Depends(get_service)):
    return svc.meta()


@router.get("/forecast", response_model=s.ForecastOut, dependencies=_public("delivery_date", "cutoff", "confidence"))
def forecast(
    delivery_date: date = Depends(delivery_param),
    cutoff: time = Depends(cutoff_param),
    confidence: float = Depends(confidence_param),
    svc: AnalyticsService = Depends(get_service),
):
    return svc.forecast(delivery_date, cutoff, confidence)


@router.get("/accuracy/summary", response_model=s.SummaryOut, dependencies=_public(*RANGE_CUTOFF_CONF))
def accuracy_summary(
    rng: tuple[date, date] = Depends(range_params),
    cutoff: time = Depends(cutoff_param),
    confidence: float = Depends(confidence_param),
    svc: AnalyticsService = Depends(get_service),
):
    return svc.summary(rng[0], rng[1], cutoff, confidence)


@router.get("/accuracy/intervals", response_model=s.IntervalsOut, dependencies=_public(*RANGE_CUTOFF_CONF))
def accuracy_intervals(
    rng: tuple[date, date] = Depends(range_params),
    cutoff: time = Depends(cutoff_param),
    confidence: float = Depends(confidence_param),
    svc: AnalyticsService = Depends(get_service),
):
    return svc.intervals(rng[0], rng[1], cutoff, confidence)


@router.get("/accuracy/by-hour", response_model=s.ByHourOut, dependencies=_public(*RANGE_CUTOFF))
def accuracy_by_hour(
    rng: tuple[date, date] = Depends(range_params),
    cutoff: time = Depends(cutoff_param),
    svc: AnalyticsService = Depends(get_service),
):
    return svc.by_hour(rng[0], rng[1], cutoff)


@router.get("/accuracy/by-day", response_model=s.ByDayOut, dependencies=_public(*RANGE_CUTOFF))
def accuracy_by_day(
    rng: tuple[date, date] = Depends(range_params),
    cutoff: time = Depends(cutoff_param),
    svc: AnalyticsService = Depends(get_service),
):
    return svc.by_day(rng[0], rng[1], cutoff)


@router.get("/accuracy/by-forecast-level", response_model=s.ByLevelOut, dependencies=_public(*RANGE_CUTOFF))
def accuracy_by_forecast_level(
    rng: tuple[date, date] = Depends(range_params),
    cutoff: time = Depends(cutoff_param),
    svc: AnalyticsService = Depends(get_service),
):
    return svc.by_forecast_level(rng[0], rng[1], cutoff)


@router.get("/accuracy/distribution", response_model=s.DistributionOut, dependencies=_public(*RANGE_CUTOFF))
def accuracy_distribution(
    rng: tuple[date, date] = Depends(range_params),
    cutoff: time = Depends(cutoff_param),
    svc: AnalyticsService = Depends(get_service),
):
    return svc.distribution(rng[0], rng[1], cutoff)


@router.get("/accuracy/horizon", response_model=s.HorizonOut, dependencies=_public("from", "to", "cutoff", "view"))
def accuracy_horizon(
    rng: tuple[date, date] = Depends(range_params),
    cutoff: time = Depends(cutoff_param),
    view: str = Depends(view_param),
    svc: AnalyticsService = Depends(get_service),
):
    return svc.horizon(rng[0], rng[1], cutoff, view)


@router.get("/accuracy/runs", response_model=s.RunsOut, dependencies=_public("from", "to"))
def accuracy_runs(
    rng: tuple[date, date] = Depends(range_params),
    svc: AnalyticsService = Depends(get_service),
):
    return svc.runs(rng[0], rng[1])


@router.get("/accuracy/benchmarks", response_model=s.BenchmarksOut, dependencies=_public(*RANGE_CUTOFF))
def accuracy_benchmarks(
    rng: tuple[date, date] = Depends(range_params),
    cutoff: time = Depends(cutoff_param),
    svc: AnalyticsService = Depends(get_service),
):
    return svc.benchmarks(rng[0], rng[1], cutoff)


@router.get("/buffer/backtest", response_model=s.BufferBacktestOut, dependencies=_public(*RANGE_CUTOFF_CONF))
def buffer_backtest(
    rng: tuple[date, date] = Depends(range_params),
    cutoff: time = Depends(cutoff_param),
    confidence: float = Depends(confidence_param),
    svc: AnalyticsService = Depends(get_service),
):
    return svc.buffer_backtest(rng[0], rng[1], cutoff, confidence)