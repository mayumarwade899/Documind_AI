import time
import re
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
from retrieval.vector_store import RetrievedChunk
from retrieval.hybrid_retriever import HybridRetriever
from retrieval.query_rewriter import QueryRewriter, RewrittenQuery
from reranking.cross_encoder import CrossEncoderReranker
from generation.prompt_builder import PromptBuilder, BuiltPrompt
from generation.llm_client import GeminiClient, LLMResponse
from monitoring.query_cache import get_query_cache
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class RAGResponse:
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
    def __init__(
        self,
        hybrid_retriever: Optional[HybridRetriever] = None,
        query_rewriter: Optional[QueryRewriter] = None,
        reranker: Optional[CrossEncoderReranker] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        llm_client: Optional[GeminiClient] = None,
    ):

        self.retriever = hybrid_retriever or HybridRetriever()
        self.query_rewriter = query_rewriter or QueryRewriter()
        self.reranker  = reranker or CrossEncoderReranker()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.llm_client = llm_client or GeminiClient()

        logger.debug("answer_generator_initialized")

    def _ensure_complete_sentences(self, text: str) -> str:
        """
        Trims text to the last complete sentence if it ends abruptly.
        Follows VALID_ENDINGS = ('.', '!', '?', ':', ')', ']')
        """
        if not text:
            return ""

        valid_endings = (".", "!", "?", ":", ")", "]")
        min_length = 30

        text = text.strip()
        
        if text.endswith(valid_endings):
            return text

        pattern = r'[.!?:\]\)](?!.*[.!:?\]\)])'
        last_match = list(re.finditer(pattern, text))
        
        if last_match:
            last_idx = last_match[-1].end()
            trimmed = text[:last_idx].strip()
            
            trimmed = re.sub(r'[,;\"\'\-\s]+$', '', trimmed)
            
            if trimmed.endswith(valid_endings):
                if len(trimmed) >= min_length:
                    return trimmed
                else:
                    logger.debug("trimmed_answer_too_short", length=len(trimmed))
                    return ""
        
        logger.debug("no_sentence_boundary_found_for_trimming")
        return ""


    def _is_summary_query(self, query: str) -> bool:
        """Detect if the query likely requires a summary output."""
        keywords = {
            "summary", "summarize", "summarise", "summarization",
            "overview", "tl;dr", "tldr",
            "key points", "key takeaways", "main points", "main ideas",
            "what is this about", "what is this document about",
            "executive summary", "high-level", "brief me", "give me a summary",
            "outline", "recap"
        }
        query_lower = query.lower()
        return any(kw in query_lower for kw in keywords)

    def _step_rewrite_query(
        self, query: str, history: List[Dict] = []
    ) -> RewrittenQuery:

        try:
            return self.query_rewriter.rewrite_with_variants(query, history = history)
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
        filter_document_id: Optional[str] = None,
        top_k: Optional[int] = None
    ) -> List[RetrievedChunk]:

        k = top_k or settings.retrieval.vector_search_top_k
        
        if len(rewritten.all_queries) > 1:
            return self.retriever.retrieve_multi_query(
                queries = rewritten.all_queries,
                top_k = k,
                filter_document_id = filter_document_id
            )
        else:
            return self.retriever.retrieve(
                query = rewritten.rewritten_query,
                top_k = k,
                filter_document_id = filter_document_id
            )
        
    def _step_rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_k: int = 6
    ) -> List[RetrievedChunk]:

        try:
            return self.reranker.rerank_with_threshold(
                query = query,
                chunks = chunks,
                top_k = top_k,
                min_score = settings.retrieval.rerank_threshold
            )
        except Exception as e:
            logger.warning(
                "reranking_step_failed_using_original_order",
                error = str(e)
            )
            return chunks[:top_k]
        
    def _verify_and_repair_grounding(
        self,
        draft_text: str,
        chunks: List[RetrievedChunk],
        query: str,
        is_retry: bool = False
    ) -> str:
        """
        Internal audit to catch 'Expert Hallucinations' (legal knowledge drift).
        Reviews the draft against snippets and repairs unsupported claims.
        """
        if is_retry or not draft_text:
            return draft_text

        v_prompt = self.prompt_builder.build_verification_prompt(draft_text, chunks)
        try:
            v_res = self.llm_client.generate(v_prompt, max_tokens=1000)
            text = v_res.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            import json
            audit = json.loads(text)
            
            if audit.get("is_supported", True):
                return draft_text

            # 2. Repair Call
            logger.info("grounding_audit_failed_triggering_repair", claims=audit.get("unsupported_claims"))
            repair_prompt = (
                f"You are a strict document auditor. Your previous answer contained claims NOT supported by the context.\n\n"
                f"CONTEXT:\n{self.prompt_builder._build_context_block(chunks)}\n\n"
                f"DRAFT ANSWER:\n{draft_text}\n\n"
                f"UNSUPPORTED CLAIMS:\n{', '.join(audit.get('unsupported_claims', []))}\n\n"
                f"TASK: Rewrite the answer to be EXACTLY supported by context. REMOVE any claim that is not verbatim or strongly implied in the snippets. MAINTAIN the [Snippet X] citations."
            )
            
            repair_res = self.llm_client.generate(repair_prompt, max_tokens=1200)
            return repair_res.text
            
        except Exception as e:
            logger.warning("grounding_audit_failed_to_execute_skipping", error=str(e))
            return draft_text

    def _step_generate(
        self,
        built_prompt: BuiltPrompt,
        max_output_tokens: int = 1200,
        is_retry: bool = False
    ) -> LLMResponse:
        
        # 1. Raw Generation
        response = self.llm_client.generate(
            prompt = built_prompt.prompt,
            max_tokens = max_output_tokens,
            metadata = {
                "num_chunks": len(built_prompt.chunks_used),
                "num_sources": built_prompt.num_sources,
                "is_retry": is_retry
            }
        )
        
        return response
    
    def generate(
        self,
        query: str,
        use_query_rewriting: bool = True,
        use_multi_query: bool = True,
        filter_document_id: Optional[str] = None,
        history: List[Dict] = [],
        top_k: Optional[int] = None
    ) -> RAGResponse:

        if not query.strip():
            raise ValueError("Query cannot be empty")
        
        
        cache = get_query_cache()
        cached_data = cache.get(query, filter_document_id)
        if cached_data:
            try:
                chunks = [RetrievedChunk(**c) for c in cached_data["chunks_used"]]
                cached_data["chunks_used"] = chunks
                
                resp = RAGResponse(**cached_data)
                resp.metadata["is_cached"] = True
                return resp
            except Exception as e:
                logger.warning("failed_to_reconstruct_response_from_cache", error=str(e))

        pipeline_start = time.time()

        logger.debug(
            "rag_pipeline_started",
            query_preview = query[:100],
            use_query_rewriting = use_query_rewriting,
            use_multi_query = use_multi_query
        )

        if use_query_rewriting:
            rewritten = self._step_rewrite_query(query, history = history)
        else:
            rewritten = RewrittenQuery(
                original_query = query,
                rewritten_query = query,
                variants = [],
                all_queries = [query]
            )

        if not use_multi_query:
            rewritten.all_queries = [rewritten.rewritten_query]

        logger.debug(
            "query_rewrite_done",
            original = query[:80],
            rewritten = rewritten.rewritten_query[:80],
            num_variants = len(rewritten.variants)
        )

        retrieval_start = time.time()
        
        try:
            chunks = self._step_retrieve(rewritten, filter_document_id, top_k = top_k)
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

        if filter_document_id and chunks:
            before = len(chunks)
            chunks = [c for c in chunks if c.document_id == filter_document_id]
            after = len(chunks)
            if before != after:
                logger.warning(
                    "cross_document_leakage_detected_and_removed",
                    filter_document_id=filter_document_id,
                    chunks_before=before,
                    chunks_removed=before - after,
                    chunks_kept=after
                )

        logger.debug(
            "retrieval_done",
            chunks_retrieved=num_retrieved,
            chunks_after_guard=len(chunks),
            latency_ms=retrieval_latency
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
        
        is_summary = self._is_summary_query(query)
        
        final_top_k = settings.retrieval.summary_final_top_k if is_summary else settings.retrieval.final_top_k
        context_budget = settings.retrieval.summary_context_tokens if is_summary else settings.retrieval.max_context_tokens
        max_output_tokens = 2000 if is_summary else 1200 

        logger.info(
            "rag_dynamic_limits_applied",
            is_summary=is_summary,
            final_top_k=final_top_k,
            context_budget=context_budget,
            max_output_tokens=max_output_tokens,
            filter_document_id=filter_document_id or "none"
        )

        reranking_start = time.time()
        reranked_chunks = self._step_rerank(
            query = rewritten.rewritten_query,
            chunks = chunks,
            top_k = final_top_k
        )
        reranking_latency = round(
            (time.time() - reranking_start) * 1000, 2
        )

        logger.debug(
            "reranking_done",
            is_summary = is_summary,
            final_top_k = final_top_k,
            chunks_after_reranking = len(reranked_chunks),
            latency_ms = reranking_latency
        )

        built_prompt = self.prompt_builder.build_rag_prompt(
            query = rewritten.rewritten_query,
            chunks = reranked_chunks,
            max_context_tokens = context_budget,
            is_summary = is_summary
        )

        generation_start = time.time()

        try:
            llm_response = self._step_generate(built_prompt, max_output_tokens = max_output_tokens)
            
            final_text = self._verify_and_repair_grounding(
                draft_text = llm_response.text,
                chunks = reranked_chunks,
                query = query
            )
            llm_response.text = final_text
            
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

        try:
            res_dict = asdict(response)
            cache.set(query, res_dict, filter_document_id)
        except Exception as e:
            logger.warning("failed_to_cache_response", error=str(e))
            import traceback
            logger.debug(traceback.format_exc())

        return response
    
    def _error_response(
        self,
        query: str,
        rewritten_query: str,
        error: str,
        pipeline_start: float
    ) -> RAGResponse:

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

    def generate_stream(
        self,
        query: str,
        use_query_rewriting: bool = True,
        use_multi_query: bool = True,
        filter_document_id = None,
        history = []
    ):
        """
        Run the full RAG pipeline then stream the LLM response token-by-token via SSE.
        """
        import json as _json

        pipeline_start = time.time()

        if not query.strip():
            yield f'data: {_json.dumps({"type": "error", "message": "Query cannot be empty"})}\n\n'
            return

        if use_query_rewriting:
            rewritten = self._step_rewrite_query(query, history=history)
        else:
            rewritten = RewrittenQuery(query, query, [], [query])

        if not use_multi_query:
            rewritten.all_queries = [rewritten.rewritten_query]

        yield f'data: {_json.dumps({"type": "meta", "rewritten_query": rewritten.rewritten_query, "step": "retrieval"})}\n\n'

        try:
            chunks = self._step_retrieve(rewritten, filter_document_id)
        except Exception as e:
            yield f'data: {_json.dumps({"type": "error", "message": f"Retrieval failed: {str(e)}"})}\n\n'
            return

        num_retrieved = len(chunks)

        if filter_document_id and chunks:
            chunks = [c for c in chunks if c.document_id == filter_document_id]

        if not chunks:
            yield f'data: {_json.dumps({"type": "error", "message": "I cannot find this information in the provided documents."})}\n\n'
            return

        is_summary     = self._is_summary_query(query)
        final_top_k    = settings.retrieval.summary_final_top_k if is_summary else settings.retrieval.final_top_k
        context_budget = settings.retrieval.summary_context_tokens if is_summary else settings.retrieval.max_context_tokens
        max_output_tokens = 2000 if is_summary else 1200

        yield f'data: {_json.dumps({"type": "meta", "step": "reranking"})}\n\n'

        reranked_chunks = self._step_rerank(
            query=rewritten.rewritten_query, chunks=chunks, top_k=final_top_k
        )

        built_prompt = self.prompt_builder.build_rag_prompt(
            query=rewritten.rewritten_query,
            chunks=reranked_chunks,
            max_context_tokens=context_budget,
            is_summary=is_summary
        )

        yield f'data: {_json.dumps({"type": "meta", "step": "generation"})}\n\n'

        generation_start = time.time()
        full_text = ""

        try:
            for text_chunk in self.llm_client.stream_generate(
                prompt=built_prompt.prompt,
                max_tokens=max_output_tokens
            ):
                if text_chunk:
                    full_text += text_chunk
                    yield f'data: {_json.dumps({"type": "chunk", "text": text_chunk})}\n\n'
        except Exception as e:
            yield f'data: {_json.dumps({"type": "error", "message": f"Generation failed: {str(e)}"})}\n\n'
            return

        generation_latency = round((time.time() - generation_start) * 1000, 2)
        total_latency      = round((time.time() - pipeline_start)    * 1000, 2)

        sources           = self.prompt_builder.format_chunk_as_sources(reranked_chunks)
        retrieval_methods = list({c.retrieval_method for c in reranked_chunks})

        metrics = {
            "total_latency_ms":      total_latency,
            "retrieval_latency_ms":  0,
            "reranking_latency_ms":  0,
            "generation_latency_ms": generation_latency,
            "input_tokens":          len(built_prompt.prompt) // 4,
            "output_tokens":         len(full_text) // 4,
            "total_tokens":          len(built_prompt.prompt) // 4 + len(full_text) // 4,
            "cost_usd":              0.0,
            "num_chunks_retrieved":  num_retrieved,
            "num_chunks_used":       len(reranked_chunks),
            "num_queries_used":      len(rewritten.all_queries),
            "retrieval_methods":     retrieval_methods,
        }

        yield f'data: {_json.dumps({"type": "done", "sources": sources, "metrics": metrics, "rewritten_query": rewritten.rewritten_query})}\n\n'

        logger.info(
            "streaming_generation_complete",
            query_preview    = query[:80],
            total_latency_ms = total_latency,
            chunks_used      = len(reranked_chunks),
        )
