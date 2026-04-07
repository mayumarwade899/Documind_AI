import time
from dataclasses import dataclass, field
from typing import List, Optional

from retrieval.vector_store import RetrievedChunk
from retrieval.hybrid_retriever import HybridRetriever
from retrieval.query_rewriter import QueryRewriter, RewrittenQuery
from reranking.cross_encoder import CrossEncoderReranker
from generation.prompt_builder import PromptBuilder, BuiltPrompt
from generation.llm_client import GeminiClient, LLMResponse
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class RAGResponse:
    """
    The complete response returned to the user and API layer.
    Contains the answer, all source citations, and full
    pipeline metrics for observability and evaluation.
    """
    answer: str
    query: str
    rewritten_query: str

    sources: List[dict]
    chunks_used: List[RetrievedChunk]

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

    success: bool = True
    error: Optional[str] = None
    metadata: dict = field(default_factory = dict)

class AnswerGenerator:
    """
    Full RAG pipeline orchestrator.
    Composes all retrieval and generation modules into
    one clean generate() call.
    """
    def __init__(
        self,
        hybrid_retriever: Optional[HybridRetriever] = None,
        query_rewriter: Optional[QueryRewriter] = None,
        reranker: Optional[CrossEncoderReranker] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        llm_client: Optional[GeminiClient] = None,
    ):
        """
        Initialize with all pipeline components.
        Creates defaults if not injected.
        """
        self.retriever = hybrid_retriever or HybridRetriever()
        self.query_rewriter = query_rewriter or QueryRewriter()
        self.reranker  = reranker or CrossEncoderReranker()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.llm_client = llm_client or GeminiClient()

        logger.info("answer_generator_initialized")

    def _step_rewrite_query(
        self, query: str
    ) -> RewrittenQuery:
        
        """
        Rewrite query and generate variants.
        Falls back to original query on failure.
        """
        try:
            return self.query_rewriter.rewrite_with_variants(query)
        except Exception as e:
            logger.warning(
                "query_rewrite_step_failed_using_original",
                error = str(e)
            )

            return RewrittenQuery(
                original_query = query,
                rewritten_query = query,
                variants = [],
                all_queries = [query]
            )
    
    def _step_retrieve(
        self,
        rewritten: RewrittenQuery,
        filter_document_id: Optional[str] = None
    ) -> List[RetrievedChunk]:
        
        """
        Run hybrid retrieval across all query variants.
        Uses multi-query retrieval if variants exist.
        Optionally scoped to a specific document.
        """
        if len(rewritten.all_queries) > 1:
            return self.retriever.retrieve_multi_query(
                queries = rewritten.all_queries,
                top_k = settings.retrieval.vector_search_top_k,
                filter_document_id = filter_document_id
            )
        else:
            return self.retriever.retrieve(
                query = rewritten.rewritten_query,
                top_k = settings.retrieval.vector_search_top_k,
                filter_document_id = filter_document_id
            )
        
    def _step_rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        
        """
        Rerank retrieved chunks using Cross Encoder.
        Falls back to original order on failure.
        """
        try:
            return self.reranker.rerank(
                query = query,
                chunks = chunks,
                top_k = settings.retrieval.final_top_k
            )
        except Exception as e:
            logger.warning(
                "reranking_step_failed_using_original_order",
                error = str(e)
            )
            return chunks[:settings.retrieval.final_top_k]
        
    def _step_generate(
        self,
        built_prompt: BuiltPrompt
    ) -> LLMResponse:
        """
        Call Gemini to generate the answer.
        """
        return self.llm_client.generate(
            prompt = built_prompt.prompt,
            metadata = {
                "num_chunks": len(built_prompt.chunks_used),
                "num_sources": built_prompt.num_sources
            }
        )
    
    def generate(
        self,
        query: str,
        use_query_rewriting: bool = True,
        use_multi_query: bool = True,
        filter_document_id: Optional[str] = None,
    ) -> RAGResponse:
        """
        Run the full RAG pipeline for a user question.
        Optionally scoped to a specific document.
        """
        if not query.strip():
            raise ValueError("Query cannot be empty")
        
        pipeline_start = time.time()

        logger.info(
            "rag_pipeline_started",
            query_preview = query[:100],
            use_query_rewriting = use_query_rewriting,
            use_multi_query = use_multi_query
        )

        if use_query_rewriting:
            rewritten = self._step_rewrite_query(query)
        else:
            rewritten = RewrittenQuery(
                original_query = query,
                rewritten_query = query,
                variants = [],
                all_queries = [query]
            )

        if not use_multi_query:
            rewritten.all_queries = [rewritten.rewritten_query]

        logger.info(
            "query_rewrite_done",
            original = query[:80],
            rewritten = rewritten.rewritten_query[:80],
            num_variants = len(rewritten.variants)
        )

        retrieval_start = time.time()
        
        try:
            chunks = self._step_retrieve(rewritten, filter_document_id)
        except Exception as e:
            logger.error("retrieval_step_failed", error=str(e))
            return self._error_response(
                query = query,
                rewritten_query = rewritten.rewritten_query,
                error = f"Retrieval failed: {str(e)}",
                pipeline_start = pipeline_start
            )
        
        retrieval_latency = round(
            (time.time() - retrieval_start) * 1000, 2
        )
        num_retrieved = len(chunks)

        logger.info(
            "retrieval_done",
            chunks_retrieved = num_retrieved,
            latency_ms = retrieval_latency
        )

        if not chunks:
            logger.warning(
                "no_chunks_retrieved",
                query=query[:80]
            )

            return RAGResponse(
                answer = "I cannot find this information in the provided documents.",
                query = query,
                rewritten_query = rewritten.rewritten_query,
                sources = [],
                chunks_used = [],
                total_latency_ms = round(
                    (time.time() - pipeline_start) * 1000, 2
                ),
                retrieval_latency_ms = retrieval_latency,
                reranking_latency_ms = 0,
                generation_latency_ms = 0,
                input_tokens = 0,
                output_tokens = 0,
                total_tokens = 0,
                cost_usd = 0.0,
                num_chunks_retrieved = 0,
                num_chunks_used = 0,
                num_queries_used = len(rewritten.all_queries),
                retrieval_methods = [],
                success = True
            )
        
        reranking_start = time.time()
        reranked_chunks = self._step_rerank(
            query = rewritten.rewritten_query,
            chunks = chunks
        )
        reranking_latency = round(
            (time.time() - reranking_start) * 1000, 2
        )

        logger.info(
            "reranking_done",
            chunks_after_reranking = len(reranked_chunks),
            latency_ms = reranking_latency,
            top_score = reranked_chunks[0].score if reranked_chunks else 0
        )

        built_prompt = self.prompt_builder.build_rag_prompt(
            query = rewritten.rewritten_query,
            chunks = reranked_chunks
        )

        generation_start = time.time()

        try:
            llm_response = self._step_generate(built_prompt)
        except Exception as e:
            logger.error("generation_step_failed", error=str(e))
            return self._error_response(
                query = query,
                rewritten_query = rewritten.rewritten_query,
                error = f"Generation failed: {str(e)}",
                pipeline_start = pipeline_start
            )
        
        generation_latency = round(
            (time.time() - generation_start) * 1000, 2
        )

        retrieval_methods = list({
            c.retrieval_method for c in reranked_chunks
        })

        sources = self.prompt_builder.format_chunk_as_sources(
            reranked_chunks
        )

        total_latency = round(
            (time.time() - pipeline_start) * 1000, 2
        )

        response = RAGResponse(
            answer = llm_response.text,
            query = query,
            rewritten_query = rewritten.rewritten_query,
            sources = sources,
            chunks_used = reranked_chunks,
            total_latency_ms = total_latency,
            retrieval_latency_ms = retrieval_latency,
            reranking_latency_ms = reranking_latency,
            generation_latency_ms = generation_latency,
            input_tokens = llm_response.input_tokens,
            output_tokens = llm_response.output_tokens,
            total_tokens = llm_response.total_tokens,
            cost_usd = llm_response.cost_usd,
            num_chunks_retrieved = num_retrieved,
            num_chunks_used = len(reranked_chunks),
            num_queries_used = len(rewritten.all_queries),
            retrieval_methods = retrieval_methods,
            success = True
        )

        logger.info(
            "rag_pipeline_complete",
            query_preview = query[:80],
            total_latency_ms = total_latency,
            retrieval_latency_ms = retrieval_latency,
            reranking_latency_ms = reranking_latency,
            generation_latency_ms = generation_latency,
            total_tokens = llm_response.total_tokens,
            cost_usd = llm_response.cost_usd,
            num_sources = len(sources)
        )

        return response
    
    def _error_response(
        self,
        query: str,
        rewritten_query: str,
        error: str,
        pipeline_start: float
    ) -> RAGResponse:
        """
        Build a clean error response when pipeline fails.
        Always returns a valid RAGResponse
        """
        total_latency = round(
            (time.time() - pipeline_start) * 1000, 2
        )

        logger.error(
            "rag_pipeline_error_response",
            query = query[:80],
            error = error,
            total_latency_ms = total_latency
        )

        return RAGResponse(
            answer = "An error occurred while processing your question. Please try again.",
            query = query,
            rewritten_query = rewritten_query,
            sources = [],
            chunks_used = [],
            total_latency_ms = total_latency,
            retrieval_latency_ms = 0,
            reranking_latency_ms = 0,
            generation_latency_ms = 0,
            input_tokens = 0,
            output_tokens = 0,
            total_tokens = 0,
            cost_usd = 0.0,
            num_chunks_retrieved = 0,
            num_chunks_used = 0,
            num_queries_used = 0,
            retrieval_methods = [],
            success = False,
            error = error
        )