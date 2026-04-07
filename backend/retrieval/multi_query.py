from typing import List, Optional

from retrieval.vector_store import RetrievedChunk
from retrieval.hybrid_retriever import HybridRetriever
from retrieval.query_rewriter import QueryRewriter
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

class MultiQueryRetriever:
    def __init__(
        self,
        hybrid_retriever: Optional[HybridRetriever] = None,
        query_rewriter: Optional[QueryRewriter] = None
    ):
        self.retriever = hybrid_retriever or HybridRetriever()
        self.query_rewriter = query_rewriter  or QueryRewriter()

        logger.info("multi_query_retriever_initialized")

    def retrieve(
        self,
        query: str,
        top_k: int = None,
        num_variants: int = None
    ) -> List[RetrievedChunk]:
        k = top_k or settings.retrieval.final_top_k
        n = num_variants or settings.retrieval.multi_query_count

        logger.info(
            "multi_query_retrieve_started",
            query_preview = query[:80],
            num_variants = n,
            top_k = k
        )

        try:
            rewritten = self.query_rewriter.rewrite_with_variants(
                query = query,
                num_variants = n
            )
            all_queries = rewritten.all_queries
        
        except Exception as e:
            logger.warning(
                "multi_query_rewrite_failed_using_original",
                error = str(e)
            )
            all_queries = [query]

        logger.info(
            "multi_query_variants_ready",
            num_queries = len(all_queries),
            queries_preview = [q[:60] for q in all_queries]
        )

        return self.retriever.retrieve_multi_query(
            queries = all_queries,
            top_k = k
        )