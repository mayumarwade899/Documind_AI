"""
backend/api/routes/evaluation.py

Exposes the golden dataset and latest evaluation report
to the frontend via HTTP.  Mount this in api/main.py with:

    from api.routes import evaluation
    app.include_router(evaluation.router)
"""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from evaluation.golden_dataset import GoldenDataset
from config.settings import get_settings
from config.logging_config import get_logger

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])
logger = get_logger(__name__)
settings = get_settings()


# ─── Response schemas ────────────────────────────────────────────────────────

class GoldenPair(BaseModel):
    question: str
    ground_truth: str
    contexts: List[str] = []
    source_files: List[str] = []
    metadata: dict = {}


class DatasetResponse(BaseModel):
    total: int
    pairs: List[GoldenPair]


class MetricScore(BaseModel):
    score: float
    passed: bool
    threshold: float


class EvalReportResponse(BaseModel):
    run_id: str
    timestamp: str
    dataset_size: int
    overall_passed: bool
    avg_score: float
    metrics: dict
    evaluation_latency_ms: float


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("/dataset", response_model=DatasetResponse)
async def get_golden_dataset():
    """
    Return all pairs from the golden QA dataset.
    Called by the frontend Evaluation page.
    """
    try:
        dataset = GoldenDataset()
        pairs = dataset.load()

        return DatasetResponse(
            total=len(pairs),
            pairs=[
                GoldenPair(
                    question=p.question,
                    ground_truth=p.ground_truth,
                    contexts=p.contexts or [],
                    source_files=getattr(p, "source_files", []),
                    metadata=p.metadata or {},
                )
                for p in pairs
            ],
        )
    except Exception as e:
        logger.error("get_golden_dataset_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_dataset_stats():
    """Return quick stats: total pairs, path, context coverage."""
    try:
        dataset = GoldenDataset()
        return dataset.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latest", response_model=Optional[EvalReportResponse])
async def get_latest_report():
    """
    Return the most recent evaluation report JSON from disk.
    Reports are written by RAGASEvaluator._save_report() to
    data/evaluation_reports/eval_YYYY-MM-DD_<run_id>.json
    """
    reports_dir = Path("data/evaluation_reports")
    if not reports_dir.exists():
        return None

    report_files = sorted(reports_dir.glob("eval_*.json"), reverse=True)
    if not report_files:
        return None

    try:
        with open(report_files[0], "r", encoding="utf-8") as f:
            data = json.load(f)
        return EvalReportResponse(**data)
    except Exception as e:
        logger.error("get_latest_report_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
