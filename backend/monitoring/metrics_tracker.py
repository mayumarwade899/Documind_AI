import json
import time
import uuid
import statistics
from pathlib import Path
from datetime import datetime, date
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class RequestMetric:
    """
    Metrics captured for a single RAG request.
    One of these is written to disk per request.
    """
    request_id: str
    timestamp: str 
    date: str 

    query_preview: str

    total_latency_ms: float
    retrieval_latency_ms: float
    reranking_latency_ms: float
    generation_latency_ms: float

    input_tokens: int
    output_tokens: int
    total_tokens: int

    cost_usd: float

    num_chunks_retrieved: int
    num_chunks_used: int
    num_queries_used: int
    retrieval_methods: List[str]

    is_verified: bool
    support_ratio: float
    citation_count: int

    success: bool
    error: Optional[str] = None

@dataclass
class LatencyStats:
    """
    Computed latency percentiles.
    """
    p50_ms: float
    p95_ms: float 
    p99_ms: float 
    min_ms: float
    max_ms: float
    avg_ms: float
    samples: int

@dataclass
class DailySummary:
    """
    Aggregated stats for one day.
    """
    date: str
    total_requests: int
    successful: int
    failed: int
    total_cost_usd: float
    total_tokens: int
    avg_latency_ms: float
    p95_latency_ms: float
    avg_chunks_used: float
    avg_support_ratio: float

def _append_jsonl(
    file_path: Path,
    record: dict
) -> None:
    """
    Append one JSON record to a .jsonl file.
    """
    file_path.parent.mkdir(parents = True, exist_ok = True)
    with open(file_path, "a", encoding = "utf-8") as f:
        f.write(json.dumps(record, ensure_ascii = False) + "\n")

def _read_jsonl(file_path: Path) -> List[dict]:
    """
    Read all records from a .jsonl file.
    Returns empty list if file doesn't exist.
    """
    if not file_path.exists():
        return []
    
    records = []
    with open(file_path, "r", encoding = "utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    return records

def _compute_percentile(values: List[float], p: float) -> float:
    """
    Compute the p-th percentile of a list of values.
    """
    if not values:
        return 0.0
    
    sorted_vals = sorted(values)
    idx = (p / 100) * (len(sorted_vals) - 1)
    lower = int(idx)
    upper = min(lower + 1, len(sorted_vals) - 1)
    fraction = idx - lower

    return round(
        sorted_vals[lower] * (1 -fraction) + sorted_vals[upper] * fraction, 2
    )

class MetricsTracker:
    """
    Captures, stores, and aggregates request metrics.
    One JSONL line per request. Efficient for both
    writing and reading.
    """
    def __init__(self):
        self.metrics_dir = settings.metrics_log_path
        self.metrics_dir.mkdir(parents = True, exist_ok = True)

        logger.info(
            "metrics_tracker_initialized",
            metrics_dir = str(self.metrics_dir)
        )

    def _today_file(self) -> Path:
        """
        Return path to today's metrics JSONL file.
        """
        today = date.today().strftime("%Y_%m_%d")
        return self.metrics_dir / f"requests_{today}.jsonl"
    
    def _load_recent_records(self, days: int = 7) -> List[dict]:
        """
        Load metric records from the last N days.
        """
        all_records = []

        for day_offset in range(days):
            from datetime import timedelta
            target_date = (
                date.today() -
                timedelta(days = day_offset)
            ).strftime("%Y_%m_%d")

            file_path = self.metrics_dir / f"requests_{target_date}.jsonl"
            records   = _read_jsonl(file_path)
            all_records.extend(records)

        return all_records
    
    def record(
        self,
        rag_response, 
        verification_result=None
    ) -> RequestMetric:
        """
        Record metrics from a completed RAG request.
        Called automatically after every generate() call.
        """
        now = datetime.utcnow()

        is_verified = False
        support_ratio = 0.0
        citation_count = 0

        if verification_result:
            is_verified = verification_result.is_fully_supported
            support_ratio = verification_result.support_ratio
            citation_count = verification_result.citation_count

        metric = RequestMetric(
            request_id = str(uuid.uuid4()),
            timestamp = now.isoformat() + "Z",
            date = now.strftime("%Y-%m-%d"),
            query_preview = rag_response.query[:100],
            total_latency_ms = rag_response.total_latency_ms,
            retrieval_latency_ms = rag_response.retrieval_latency_ms,
            reranking_latency_ms = rag_response.reranking_latency_ms,
            generation_latency_ms = rag_response.generation_latency_ms,
            input_tokens = rag_response.input_tokens,
            output_tokens = rag_response.output_tokens,
            total_tokens = rag_response.total_tokens,
            cost_usd = rag_response.cost_usd,
            num_chunks_retrieved = rag_response.num_chunks_retrieved,
            num_chunks_used = rag_response.num_chunks_used,
            num_queries_used = rag_response.num_queries_used,
            retrieval_methods = rag_response.retrieval_methods,
            is_verified = is_verified,
            support_ratio = support_ratio,
            citation_count = citation_count,
            success = rag_response.success,
            error = rag_response.error
        )

        _append_jsonl(self._today_file(), asdict(metric))

        logger.debug(
            "metric_recorded",
            request_id = metric.request_id,
            total_latency_ms = metric.total_latency_ms,
            total_tokens = metric.total_tokens,
            cost_usd = metric.cost_usd
        )

        return metric
    
    def get_latency_stats(self, days: int = 7) -> LatencyStats:
        """
        Compute p50/p95/p99 latency over the last N days.
        """
        records = self._load_recent_records(days)

        if not records:
            return LatencyStats(
                p50_ms=0, p95_ms=0, p99_ms=0,
                min_ms=0, max_ms=0, avg_ms=0, samples=0
            )

        latencies = [
            r["total_latency_ms"]
            for r in records
            if r.get("success") and r.get("total_latency_ms")
        ]

        if not latencies:
            return LatencyStats(
                p50_ms=0, p95_ms=0, p99_ms=0,
                min_ms=0, max_ms=0, avg_ms=0, samples=0
            )
        
        return LatencyStats(
            p50_ms = _compute_percentile(latencies, 50),
            p95_ms = _compute_percentile(latencies, 95),
            p99_ms = _compute_percentile(latencies, 99),
            min_ms = round(min(latencies), 2),
            max_ms = round(max(latencies), 2),
            avg_ms = round(statistics.mean(latencies), 2),
            samples = len(latencies)
        )
    
    def get_daily_summary(self, days: int = 7) -> List[DailySummary]:
        """
        Get per-day aggregated metrics for the last N days.
        """
        records = self._load_recent_records(days)

        by_date: Dict[str, List[dict]] = {}
        for r in records:
            d = r.get("date", "unknown")
            if d not in by_date:
                by_date[d] = []
            by_date[d].append(r)

        summaries = []
        for day, day_records in sorted(
            by_date.items(), reverse = True
        ):
            successful = [r for r in day_records if r.get("success")]
            failed = [r for r in day_records if not r.get("success")]

            latencies = [
                r["total_latency_ms"]
                for r in successful
                if r.get("total_latency_ms")
            ]

            summaries.append(DailySummary(
                date = day,
                total_requests = len(day_records),
                successful = len(successful),
                failed = len(failed),
                total_cost_usd = round(
                    sum(r.get("cost_usd", 0) for r in day_records), 6
                ),
                total_tokens = sum(
                    r.get("total_tokens", 0) for r in day_records
                ),
                avg_latency_ms = round(
                    statistics.mean(latencies), 2
                ) if latencies else 0,
                p95_latency_ms = _compute_percentile(latencies, 95),
                avg_chunks_used = round(
                    statistics.mean([
                        r.get("num_chunks_used", 0)
                        for r in successful
                    ]), 2
                ) if successful else 0,
                avg_support_ratio = round(
                    statistics.mean([
                        r.get("support_ratio", 0)
                        for r in successful
                    ]), 3
                ) if successful else 0
            ))

        return summaries
    
    def get_summary(self, days: int = 7) -> dict:
        """
        Full metrics dashboard summary for the API endpoint.
        """
        records = self._load_recent_records(days)
        latency = self.get_latency_stats(days)
        daily = self.get_daily_summary(days)

        total_requests = len(records)
        total_cost = sum(r.get("cost_usd", 0) for r in records)
        total_tokens = sum(r.get("total_tokens", 0) for r in records)
        successful = [r for r in records if r.get("success")]
        failed = [r for r in records if not r.get("success")]

        avg_support = 0.0
        if successful:
            avg_support = round(
                statistics.mean([
                    r.get("support_ratio", 0) for r in successful
                ]), 3
            )

        return {
            "period_days": days,
            "total_requests": total_requests,
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": round(
                len(successful) / total_requests, 3
            ) if total_requests else 0,

            "total_cost_usd": round(total_cost, 6),
            "avg_cost_usd": round(
                total_cost / total_requests, 6
            ) if total_requests else 0,

            "total_tokens": total_tokens,
            "avg_tokens": round(
                total_tokens / total_requests
            ) if total_requests else 0,

            "latency": {
                "p50_ms": latency.p50_ms,
                "p95_ms": latency.p95_ms,
                "p99_ms": latency.p99_ms,
                "avg_ms": latency.avg_ms,
                "min_ms": latency.min_ms,
                "max_ms": latency.max_ms,
                "samples": latency.samples
            },

            "avg_support_ratio": avg_support,

            "daily": [asdict(d) for d in daily]
        }