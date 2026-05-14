from fastapi import APIRouter
from api.dependencies import get_metrics_tracker
from config.logging_config import get_logger

router = APIRouter(prefix="/metrics", tags=["Metrics"])
logger = get_logger(__name__)

@router.get("/{session_id}")
async def get_metrics(session_id: str, days: int = 7):
    """Get metrics summary for a session."""
    tracker = get_metrics_tracker(session_id)
    return {
        "session_id": session_id,
        **tracker.get_summary(days=days)
    }

@router.get("/{session_id}/latency")
async def get_latency(session_id: str, days: int = 7):
    """Get latency statistics for a session."""
    tracker = get_metrics_tracker(session_id)
    stats = tracker.get_latency_stats(days = days)
    return {
        "session_id": session_id,
        "period_days": days,
        "p50_ms": stats.p50_ms,
        "p95_ms": stats.p95_ms,
        "p99_ms": stats.p99_ms,
        "avg_ms": stats.avg_ms,
        "min_ms": stats.min_ms,
        "max_ms": stats.max_ms,
        "samples": stats.samples
    }

@router.get("/{session_id}/daily")
async def get_daily(session_id: str, days: int = 7):
    """Get daily summary for a session."""
    from dataclasses import asdict
    tracker = get_metrics_tracker(session_id)
    daily = tracker.get_daily_summary(days = days)
    return {
        "session_id": session_id,
        "period_days": days,
        "days": [asdict(d) for d in daily]
    }