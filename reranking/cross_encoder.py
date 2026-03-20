import time
from typing import List, Optional, Tuple

from sentence_transformers import CrossEncoder
from retrieval.vector_store import RetrievedChunk
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

_cross_encoder_model = Optional[CrossEncoder] = None

def _get_model(model_name: str) -> CrossEncoder:
    """
    Load the Cross Encoder model once and cache it in memory.
    """
    global _cross_encoder_model

    if _cross_encoder_model is None:
        logger.info(
            "cross_encoder_loading",
            model=model_name
        )

        start = time.time()
        _cross_encoder_model = CrossEncoder(
            model_name,
            max_length = 512
        )
        elapsed = round(time.time() - start, 2)

        logger.info(
            "cross_encoder_loaded",
            model = model_name,
            load_time_sec = elapsed
        )

    return _cross_encoder_model

def _normalize_scores(scores: List[float]) -> List[float]:
    """
    Normalize raw Cross Encoder scores to [0, 1] range.
    """
    if not scores:
        return []
    
    min_score = min(scores)
    max_score = max(scores)
    score_range = max_score - min_score

    if score_range == 0:
        return [1.0] * len(scores)
    
    return [
        round((s - min_score) / score_range, 4)
        for s in scores
    ]

class CrossEncoderReranker:
    """
    Reranks retrieved chunks using a Cross Encoder model.
    """
    def __init__(self, model_name: str = None):
        """
        Initialize and load the Cross Encoder model.
        Model is loaded once here and reused for all requests.
        """
        self.model_name = (
            model_name or settings.reranker.reranker_model
        )
        self.model = _get_model(self.model_name)

        logger.info(
            "cross_encoder_reranker_ready",
            model = self.model_name
        )

    def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_k: int = None
    ) -> List[RetrievedChunk]:
        
        """
        Rerank chunks by relevance to the query.
        """
        if not chunks:
            logger.warning("rerank_called_with_empty_chunks")
            return []
        
        if not query.strip():
            logger.warning("rerank_called_with_empty_query")
            return chunks
        
        k = top_k or settings.retrieval.final_top_k

        logger.info(
            "reranking_started",
            query_preview = query[:80],
            num_chunks = len(chunks),
            top_k = k
        )
        start_time = time.time()

        pairs = []
        for chunk in chunks:
            pairs.append((query, chunk.content))

        try:
            raw_score: List[float] = self.model.predict(
                pairs,
                batch_size = 32,
                show_progress_bar = False
            ).tolist()

        except Exception as e:
            logger.error(
                "cross_encoder_scoring_failed",
                error = str(e)
            )
            logger.warning("falling_back_to_original_order")
            return chunks[:k]
        
        normalized_scores = _normalize_scores(raw_score)

        scored_chunks: List[Tuple[float, RetrievedChunk]] = []

        for chunk, raw_score, norm_score in zip(
            chunks, raw_score, normalized_scores
        ):
            scored_chunks.append((norm_score, chunk))

        scored_chunks.sort(key = lambda x: x[0], reverse = True)

        reranked = List[RetrievedChunk] = []

        for rank, (norm_score, chunk) in enumerate(
            scored_chunks[:k], start = 1
        ):
            reranked.append(RetrievedChunk(
                chunk_id = chunk.chunk_id,
                content = chunk.content,
                source_file = chunk.source_file,
                page_number = chunk.page_number,
                document_id = chunk.document_id,
                score = norm_score,
                retrieval_method = chunk.retrieval_method,
                metadata = {
                    **chunk.metadata,
                    "rerank_score": norm_score,
                    "rerank_rank": rank,
                    "original_score": chunk.score,
                    "original_method": chunk.retrieval_method,
                }
            ))

        elapsed = round(time.time() - start_time, 3)

        logger.info(
            "reranking_complete",
            input_chunks = len(chunks),
            output_chunks = len(reranked),
            elapsed_sec = elapsed,
            top_score = reranked[0].score if reranked else 0,
            top_chunk_source = (
                reranked[0].source_file if reranked else "none"
            )
        )

        return reranked
    
    def rerank_with_threshold(
            self,
        query: str,
        chunks: List[RetrievedChunk],
        top_k: int = None,
        min_score: float = 0.1
    ) -> List[RetrievedChunk]:
        
        """
        Rerank and filter out chunks below a minimum score.
        """
        reranked = self.rerank(query, chunks, top_k)

        filtered = [c for c in reranked if c.score >= min_score]

        if len(filtered) < len(reranked):
            logger.info(
                "rerank_threshold_filter_applied",
                before = len(reranked),
                after = len(filtered),
                min_score = min_score
            )

        if not filtered and reranked:
            logger.warning(
                "rerank_threshold_filtered_all_returning_top_1",
                min_score = min_score
            )
            return reranked[:1]

        return filtered