from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List

from monitoring.feedback_store import FeedbackStore
from api.dependencies import get_feedback_store
from config.logging_config import get_logger

router = APIRouter(prefix="/feedback", tags=["Feedback"])
logger = get_logger(__name__)

class FeedbackRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    query: str = Field(..., min_length=3)
    answer: str = Field(..., min_length=1)
    rating: int = Field(..., ge=-1, le=1)
    sources: List[dict] = []
    comment: Optional[str] = None
    session_id: Optional[str] = None

    rewritten_query: str = ""
    num_chunks_used: int = 0
    total_latency_ms: float = 0.0
    model_used: str = ""

class FeedbackResponse(BaseModel):
    success: bool
    feedback_id: str
    rating_label: str

@router.post("", response_model = FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    store: FeedbackStore = Depends(get_feedback_store)
):
    try:
        feedback = store.save(
            query = request.query,
            answer = request.answer,
            rating = request.rating,
            sources = request.sources,
            comment = request.comment,
            session_id = request.session_id,
            rewritten_query = request.rewritten_query,
            num_chunks_used = request.num_chunks_used,
            total_latency_ms = request.total_latency_ms,
            model_used = request.model_used
        )
        return FeedbackResponse(
            success = True,
            feedback_id = feedback.feedback_id,
            rating_label = feedback.rating_label
        )
    except Exception as e:
        logger.error("feedback_save_failed", error = str(e))
        raise HTTPException(
            status_code = 500,
            detail = f"Failed to save feedback: {str(e)}"
        )
    
@router.get("/summary")
async def feedback_summary(
    days: int = 30,
    store: FeedbackStore = Depends(get_feedback_store)
):
    summary = store.get_summary(days=days)
    return {
        "period_days": summary.period_days,
        "total_feedback": summary.total_feedback,
        "positive": summary.positive,
        "negative": summary.negative,
        "neutral": summary.neutral,
        "positive_rate": summary.positive_rate,
        "negative_rate": summary.negative_rate,
        "avg_rating": summary.avg_rating,
        "recent_comments": summary.recent_comments,
        "low_rated_queries": summary.low_rated_queries,
        "daily_trend": summary.daily_trend
    }

@router.get("/negative")
async def get_negative_feedback(
    days: int = 30,
    store: FeedbackStore = Depends(get_feedback_store)
):
    records = store.get_negative_feedback(days = days)
    return {
        "count": len(records),
        "feedback": [
            {
                "feedback_id": r.feedback_id,
                "date": r.date,
                "query": r.query,
                "answer": r.answer[:300],
                "comment": r.comment,
                "sources": r.sources
            }
            for r in records
        ]
    }