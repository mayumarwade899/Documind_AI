from typing import List, Dict, Tuple, Optional
from collections import defaultdict

from retrieval.vector_store import VectorStore, RetrievedChunk
from retrieval.bm25_retriever import BM25Retriever
from ingestion.embedder import GeminiEmbedder
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

def _reciprocal_rank_fusion(
        bm25_results = List[RetrievedChunk],
        vector_results = List[RetrievedChunk],
        k: int = 60,
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5
) -> List[RetrievedChunk]:
    """
    Merge two ranked lists using Reciprocal Rank Fusion (RRF)
    """
    rrf_scores: Dict[str, float] = defaultdict(float)

    chunk_map: Dict[str, RetrievedChunk] = {}

    for rank, chunk in enumerate(bm25_results, start = 1):
        rrf_score = bm25_weight / (k + rank)
        rrf_scores[chunk.chunk_id] += rrf_score
        chunk_map[chunk.chunk_id] = chunk

    for rank, chunk in enumerate(vector_results, start = 1):
        rrf_score = vector_weight / (k + rank)
        rrf_scores[chunk.chunk_id] += rrf_score

        if chunk.chunk_id not in chunk_map:
            chunk_map[chunk.chunk_id] = chunk

    sorted_ids = sorted(
        rrf_scores.keys(),
        key = lambda cid: rrf_scores[cid],
        reverse = True
    )

    merged = []
    for chunk_id in sorted_ids:
        chunk = chunk_map[chunk_id]

        in_bm25 = any(c.chunk_id == chunk_id for c in bm25_results)
        in_vector = any(c.chunk_id == chunk_id for c in vector_results)

        if in_bm25 and in_vector:
            method = "hybrid"
        elif in_bm25:
            method = "bm25"
        else:
            method = "vector"

        merged.append(RetrievedChunk(
            chunk_id = chunk.chunk_id,
            content = chunk.content,
            source_file = chunk.source_file,
            page_number = chunk.page_number,
            document_id = chunk.document_id,
            score = round(rrf_scores[chunk_id], 6),
            retrieval_method = method,
            metadata={
                **chunk.metadata,
                "rrf_score":  round(rrf_scores[chunk_id], 6),
                "in_bm25":    in_bm25,
                "in_vector":  in_vector,
            }
        ))

    return merged

class HybridRetriever:
    """
    Combines BM25 + vector search into one ranked result list.
    This is the main retrieval interface used by the RAG pipeline.
    """
    def __init__(
            self,
            vector_store: Optional[VectorStore] = None,
            bm25_retriever: Optional[BM25Retriever] = None,
            embedder: Optional[GeminiEmbedder] = None
    ):
        """
        Dependencies are injectable for easy testing.
        If not provided, creates default instances.
        """
        self.vector_store = vector_store or VectorStore()
        self.bm25_retriever = bm25_retriever or BM25Retriever()
        self.embedder = embedder or GeminiEmbedder()

        logger.info("hybrid_retriever_initialized")

    def retrieve(
            self,
            query: str,
            top_k: int = None,
            bm25_weight: float = 0.5,
            vector_weight: float = 0.5
    ) -> List[RetrievedChunk]:
        """
        Run hybrid retrieval for a single query.
        """
        if not query.strip():
            logger.warning("hybrid_retriev_called_with_empty_query")
            return []
        
        k = top_k or settings.retrieval.final_top_k
        candidate_k = settings.retrieval.vector_search_top_k

        logger.info(
            "hybrid_retrieval_started",
            query_preview = query[:80],
            candidate_k = candidate_k,
            final_top_k = k
        )

        try:
            query_vector = self.embedder.embed_query(query)
        except Exception as e:
            logger.error("query_embedding_failed", error=str(e))
            raise

        bm25_results = []
        try:
            bm25_results = self.bm25_retriever.search(
                query = query,
                top_k = candidate_k
            )
            logger.debug(
                "bm25_results_fetched",
                count = len(bm25_results)
            )
        except Exception as e:
            logger.warning("bm25_search_failed", error=str(e))

        vector_results = []
        try:
            vector_results = self.vector_store.search(
                query_vector = query_vector,
                top_k = candidate_k
            )
            logger.debug(
                "vector_results_fetched",
                count = len(vector_results)
            )
        except Exception as e:
            logger.warning("vector_search_failed", error=str(e))

        if not bm25_results and not vector_results:
            logger.warning(
                "hybrid_retrieval_no_results",
                query=query
            )
            return []
        
        if not bm25_results:
            logger.info("using_vector_only_fallback")
            return vector_results[:k]

        if not vector_results:
            logger.info("using_bm25_only_fallback")
            return bm25_results[:k]
        
        merged = _reciprocal_rank_fusion(
            bm25_results = bm25_results,
            vector_results = vector_results,
            bm25_weight = bm25_weight,
            vector_weight = vector_weight
        )

        final_results = merged[:k]

        hybrid_count = sum(
            1 for c in final_results
            if c.retrieval_method == "hybrid"
        )

        logger.info(
            "hybrid_retrieval_complete",
            query_preview = query[:80],
            bm25_candidates = len(bm25_results),
            vector_candidates = len(vector_results),
            merged_total = len(merged),
            final_returned = len(final_results),
            hybrid_overlap = hybrid_count,
            top_score =final_results[0].score if final_results else 0
        )

        return final_results
    
    def retrieve_multi_query(
        self,
        queries: List[str],
        top_k: int = None
    ) -> List[RetrievedChunk]:
        """
        Run hybrid retrieval across multiple query variants.
        Used by the multi-query retrieval module.
        """
        if not queries:
            return []
        
        k = top_k or settings.retrieval.final_top_k

        logger.info(
            "multi_query_retrieval_started",
            num_queries = len(queries)
        )

        all_results: Dict[str, RetrievedChunk] = {}

        for i, query in enumerate(queries):
            try:
                results = self.retrieve(query = query, top_k = k)

                for chunk in results:
                    if chunk.chunk_id not in all_results:
                        all_results[chunk.chunk_id] = chunk
                    else:
                        existing = all_results[chunk.chunk_id]
                        if chunk.score > existing.score:
                            all_results[chunk.chunk_id] = chunk
            
            except Exception as e:
                logger.warning(
                    "multi_query_single_query_failed",
                    query_index = i,
                    error = str(e)
                )

        deduplicated = sorted(
            all_results.values(),
            key = lambda c: c.score,
            reverse = True
        )[:k]

        logger.info(
            "multi_query_retrieval_complete",
            queries_run = len(queries),
            unique_chunks = len(deduplicated)
        )

        return deduplicated
