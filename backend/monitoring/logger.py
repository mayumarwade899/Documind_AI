import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional

from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

class RequestLogger:

    def __init__(self, log_dir: str = "data/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents = True, exist_ok = True)

        logger.info(
            "request_logger_initialized",
            log_dir = str(self.log_dir)
        )

    def _today_file(self) -> Path:
        today = datetime.utcnow().strftime("%Y_%m_%d")
        return self.log_dir / f"requests_{today}.jsonl"
    
    def log_request(
        self,
        rag_response,
        verification_result = None,
        session_id: Optional[str] = None
    ) -> str:
        request_id = str(uuid.uuid4())
        now = datetime.utcnow()

        verification_summary = None
        if verification_result:
            verification_summary = {
                "is_fully_supported": verification_result.is_fully_supported,
                "support_ratio": verification_result.support_ratio,
                "confidence": verification_result.confidence,
                "citation_count": verification_result.citation_count,
                "unsupported_claims": verification_result.unsupported_claims,
                "has_citations": verification_result.has_citations
            }

        record = {
            "request_id": request_id,
            "session_id": session_id,
            "timestamp": now.isoformat() + "Z",
            "date": now.strftime("%Y-%m-%d"),

            "query": rag_response.query,
            "rewritten_query": rag_response.rewritten_query,

            "answer": rag_response.answer,
            "success": rag_response.success,
            "error": rag_response.error,

            "sources": [
                {
                    "source_file": s.get("source_file"),
                    "page_number": s.get("page_number"),
                    "relevance_score": s.get("relevance_score")
                }
                for s in rag_response.sources
            ],

            "metrics": {
                "total_latency_ms": rag_response.total_latency_ms,
                "retrieval_latency_ms": rag_response.retrieval_latency_ms,
                "reranking_latency_ms": rag_response.reranking_latency_ms,
                "generation_latency_ms": rag_response.generation_latency_ms,
                "input_tokens": rag_response.input_tokens,
                "output_tokens": rag_response.output_tokens,
                "total_tokens": rag_response.total_tokens,
                "cost_usd": rag_response.cost_usd,
                "num_chunks_retrieved": rag_response.num_chunks_retrieved,
                "num_chunks_used": rag_response.num_chunks_used,
                "num_queries_used": rag_response.num_queries_used,
                "retrieval_methods": rag_response.retrieval_methods
            },

            "verification": verification_summary
        }

        log_file = self._today_file()
        with open(log_file, "a", encoding = "utf-8") as f:
            f.write(json.dumps(record, ensure_ascii = False) + "\n")

        logger.debug(
            "request_logged",
            request_id = request_id,
            success = rag_response.success,
            total_latency_ms = rag_response.total_latency_ms
        )

        return request_id