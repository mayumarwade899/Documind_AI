from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

from generation.answer_generator import AnswerGenerator
from verification.answer_verifier import AnswerVerifier
from monitoring.metrics_tracker import MetricsTracker
from api.dependencies import (
    get_answer_generator,
    get_answer_verifier,
    get_metrics_tracker,
    get_session_manager
)
from monitoring.session_manager import SessionManager
from config.logging_config import get_logger

router = APIRouter(prefix = "/query", tags = ["Query"])
logger = get_logger(__name__)

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3)
    use_query_rewriting: bool = True
    use_multi_query: bool = True
    verify_answer: bool = True
    document_id: Optional[str] = None
    session_id: Optional[str] = None
    history: List[Dict] = []

class SourceItem(BaseModel):
    source_file: str
    page_number: int
    chunk_id: str
    relevance_score: float
    content_preview: str

class VerificationInfo(BaseModel):
    is_fully_supported: bool
    support_ratio: float
    confidence: float
    citation_count: int
    unsupported_claims: List[str]
    has_citations: bool

class PipelineMetrics(BaseModel):
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

class QueryResponse(BaseModel):
    success: bool
    query: str
    rewritten_query: str
    answer: str
    sources: List[SourceItem]
    verification: Optional[VerificationInfo]
    metrics: PipelineMetrics

@router.post("", response_model = QueryResponse)
async def query(
    request: QueryRequest,
    generator: AnswerGenerator = Depends(get_answer_generator),
    verifier: AnswerVerifier = Depends(get_answer_verifier),
    tracker: MetricsTracker = Depends(get_metrics_tracker),
    session_manager: SessionManager = Depends(get_session_manager)
):
    logger.debug(
        "query_request_received",
        query_preview = request.query[:80]
    )
    try:
        rag_response = generator.generate(
            query = request.query,
            use_query_rewriting = request.use_query_rewriting,
            use_multi_query = request.use_multi_query,
            filter_document_id = request.document_id,
            history = request.history
        )
    except Exception as e:
        logger.error("query_generation_failed", error = str(e))
        raise HTTPException(
            status_code = 500,
            detail = f"Generation failed: {str(e)}"
        )
    
    verification_result = None
    verification_info = None

    if request.verify_answer and rag_response.chunks_used:
        try:
            verification_result = verifier.verify(
                answer = rag_response.answer,
                chunks = rag_response.chunks_used,
                query = request.query
            )
            verification_info = VerificationInfo(
                is_fully_supported = verification_result.is_fully_supported,
                support_ratio = verification_result.support_ratio,
                confidence = verification_result.confidence,
                citation_count = verification_result.citation_count,
                unsupported_claims = verification_result.unsupported_claims,
                has_citations = verification_result.has_citations
            )
        except Exception as e:
            logger.warning("verification_failed", error = str(e))

    try:
        tracker.record(
            rag_response = rag_response,
            verification_result = verification_result
        )
    except Exception as e:
        logger.warning("metrics_recording_failed", error = str(e))

    if request.session_id:
        try:
            interaction = {
                "query": request.query,
                "rewritten_query": rag_response.rewritten_query,
                "answer": rag_response.answer,
                "sources": rag_response.sources,
                "verification": verification_info.dict() if verification_info else None,
                "metrics": {
                    "total_latency_ms": rag_response.total_latency_ms,
                    "total_tokens": rag_response.total_tokens,
                    "cost_usd": rag_response.cost_usd,
                    "num_chunks_used": len(rag_response.chunks_used)
                }
            }
            session_manager.save_interaction(request.session_id, interaction)
        except Exception as e:
            logger.warning("session_recording_failed", error = str(e))

    return QueryResponse(
        success = rag_response.success,
        query = rag_response.query,
        rewritten_query = rag_response.rewritten_query,
        answer = rag_response.answer,
        sources = [SourceItem(**s) for s in rag_response.sources],
        verification = verification_info,
        metrics = PipelineMetrics(
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
            retrieval_methods = rag_response.retrieval_methods
        )
    )

@router.get("/history/{session_id}", response_model = List[Dict])
async def get_history(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Retrieve full history for a session."""
    return session_manager.get_history(session_id)

@router.delete("/history/{session_id}")
async def clear_history(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Clear history for a session."""
    success = session_manager.clear_session(session_id)
    return {"success": success}

# Streaming endpoint
@router.post("/stream")
async def query_stream(
    request: QueryRequest,
    generator: AnswerGenerator = Depends(get_answer_generator),
):
    """
    SSE streaming variant of /query.
    Each SSE event is a JSON object with type: meta / chunk / done / error.
    """
    def event_stream():
        yield from generator.generate_stream(
            query               = request.query,
            use_query_rewriting = request.use_query_rewriting,
            use_multi_query     = request.use_multi_query,
            filter_document_id  = request.document_id,
            history             = request.history,
        )

    return StreamingResponse(
        event_stream(),
        media_type = "text/event-stream",
        headers    = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
