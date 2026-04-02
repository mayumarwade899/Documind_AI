from fastapi import APIRouter, Depends
from monitoring.metrics_tracker import MetricsTracker
from api.dependencies import get_metrics_tracker
from config.logging_config import get_logger

router = APIRouter(prefix="/metrics", tags=["Metrics"])
logger = get_logger(__name__)

@router.get("")
async def get_metrics(
    days: int = 7,
    tracker: MetricsTracker = Depends(get_metrics_tracker)
):
    """
    Full metrics dashboard for the last N days.
    """
    return tracker.get_summary(days=days)

@router.get("/latency")
async def get_latency(
    days: int = 7,
    tracker: MetricsTracker = Depends(get_metrics_tracker)
):
    """
    Get latency percentiles only: p50, p95, p99.
    """
    stats = tracker.get_latency_stats(days = days)
    return {
        "period_days": days,
        "p50_ms": stats.p50_ms,
        "p95_ms": stats.p95_ms,
        "p99_ms": stats.p99_ms,
        "avg_ms": stats.avg_ms,
        "min_ms": stats.min_ms,
        "max_ms": stats.max_ms,
        "samples": stats.samples
    }

@router.get("/daily")
async def get_daily(
    days: int = 7,
    tracker: MetricsTracker = Depends(get_metrics_tracker)
):
    """
    Per-day aggregated metrics.
    """
    from dataclasses import asdict
    daily = tracker.get_daily_summary(days = days)
    return {
        "period_days": days,
        "days": [asdict(d) for d in daily]
    }