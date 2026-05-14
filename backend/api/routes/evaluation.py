import json
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional

from config.settings import get_settings, get_session_storage_manager
from config.logging_config import get_logger

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])
logger = get_logger(__name__)
settings = get_settings()

class EvaluationManager:
    def __init__(self):
        self.is_running = False
        self.last_run_id = None
        self.last_result = None
        self.error = None

    def start_run(self):
        self.is_running = True
        self.error = None
        self.last_result = None

    def complete_run(self, result, run_id):
        self.is_running = False
        self.last_result = result
        self.last_run_id = run_id
        self.error = None

    def fail_run(self, error):
        self.is_running = False
        self.error = error

    def get_status(self):
        return {
            "is_running": self.is_running,
            "last_run_id": self.last_run_id,
            "last_result": self.last_result,
            "error": self.error
        }

eval_manager = EvaluationManager()

class MetricScore(BaseModel):
    score: float
    passed: bool
    threshold: float

class MetricGroup(BaseModel):
    faithfulness: MetricScore
    context_relevance: MetricScore
    answer_correctness: MetricScore

class EvalReportResponse(BaseModel):
    run_id: str
    timestamp: str
    dataset_size: int
    overall_passed: bool
    avg_score: float
    metrics: MetricGroup
    evaluation_latency_ms: float
    total_cost_usd: Optional[float] = 0.0
    total_tokens: Optional[int] = 0

@router.get("/status/{session_id}")
async def get_evaluation_status(session_id: str):
    """Return the current background evaluation status for a session."""
    # Note: In this lightweight implementation, we just track if evaluation is running.
    # For production, consider using Redis or a database for multi-instance deployments.
    eval_manager = EvaluationManager()
    return {
        "session_id": session_id,
        **eval_manager.get_status()
    }

@router.get("/latest/{session_id}", response_model=Optional[EvalReportResponse])
async def get_latest_report(session_id: str):
    """Get latest evaluation report for a session."""
    storage_manager = get_session_storage_manager()
    reports_dir = storage_manager.get_evaluations_dir(session_id)
    
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
        logger.error(
            "get_latest_report_failed",
            session_id=session_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

def _bg_run_evaluation(session_id: str, max_questions: int):
    """
    Background task logic for TruLens evaluation (session-scoped).
    Converted to sync 'def' so FastAPI runs it in a thread pool,
    preventing the event loop from being blocked.
    """
    from evaluation.trulens_evaluator import TruLensEvaluator
    
    try:
        evaluator = TruLensEvaluator(session_id)
        report = evaluator.evaluate(max_questions=max_questions)
        
        eval_manager = EvaluationManager()
        eval_manager.complete_run(
            result=report.to_dict(),
            run_id=report.run_id
        )
        logger.info(
            "background_evaluation_completed",
            session_id=session_id,
            run_id=report.run_id
        )
        
    except Exception as e:
        eval_manager = EvaluationManager()
        eval_manager.fail_run(error=str(e))
        logger.error(
            "background_evaluation_failed",
            session_id=session_id,
            error=str(e)
        )

@router.post("/run/{session_id}")
async def run_evaluation(
    session_id: str,
    background_tasks: BackgroundTasks,
    max_questions: Optional[int] = 6
):
    """Start background evaluation for a session."""
    eval_manager = EvaluationManager()
    
    if eval_manager.is_running:
        return {
            "session_id": session_id,
            "status": "already_running",
            "run_id": eval_manager.last_run_id
        }

    eval_manager.start_run()
    background_tasks.add_task(_bg_run_evaluation, session_id, max_questions)
    
    return {
        "session_id": session_id,
        "status": "started",
        "message": "Evaluation running in background"
    }

@router.get("/history/{session_id}", response_model=List[EvalReportResponse])
async def get_history_reports(session_id: str):
    """Get all evaluation reports for a session."""
    storage_manager = get_session_storage_manager()
    reports_dir = storage_manager.get_evaluations_dir(session_id)
    
    if not reports_dir.exists():
        return []

    report_files = sorted(reports_dir.glob("eval_*.json"), reverse=True)
    reports = []
    
    for rf in report_files:
        try:
            with open(rf, "r", encoding="utf-8") as f:
                data = json.load(f)
            reports.append(EvalReportResponse(**data))
        except Exception as e:
            logger.warning(
                "failed_to_load_report",
                session_id=session_id,
                file=str(rf),
                error=str(e)
            )
            
    return reports
