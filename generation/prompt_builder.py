from dataclasses import dataclass, field
from typing import List, Optional

from retrieval.vector_store import RetrievedChunk
from config.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class BuildPrompt:
    """
    The complete prompt package sent to Gemini.
    Carries both the prompt text and metadata about
    what was included and used later for citation mapping
    and observability.
    """
    prompt: str
    query: str
    chunks_used: List[RetrievedChunk]
    total_context_tokens: int
    num_sources: int

RAG_SYSTEM_PROMPT = """
    You are a precise document analysis assistant.

    Your job is to answer questions based STRICTLY on the provided context chunks.

    RULES YOU MUST FOLLOW:
    1. Answer ONLY using information from the context chunks below.
    2. Every factual claim MUST be followed by a citation in this exact format: [Source: filename, Page: N]
    3. If the answer cannot be found in the provided context, respond exactly with: "I cannot find this information in the provided documents."
    4. Do NOT use any prior knowledge or make assumptions beyond what is stated in the context.
    5. If multiple chunks support a claim, cite all of them.
    6. Keep your answer clear, structured, and factual.
    7. Do NOT copy chunks verbatim — synthesize the information in your own words.
"""

RAG_CONTEXT_TEMPLATE = """
    CONTEXT_CHUNKS: {context_block}

    USER QUESTION: {query}

    ANSWER (with citation):    
"""

CONTEXT_CHUNK_TEMPLATE = """
    [Chunk {index}]
    Source: {source_file}
    Page: {page_number}
    Content: {content}
"""

NO_CONTEXT_PROMPT = """
    You are a document analysis assistant.
    The user asked: "{query}"
    No relevant context chunks were retrieved from the documents.
    Respond with exactly: "I cannot find this information in the provided documents."
 """

VERIFICATION_PROMPT = """
    Your task is to verify if the answer below is fully supported by the provided context chunks.
        
    CONTEXT CHUNKS: {context_block}
    ANSWER TO VERIFY: {answer}

    Check each claim in the answer against the context chunks.
        
    Respond in this exact JSON format:
    {{
        "is_supported": true or false,
        "unsupported_claims": ["claim 1", "claim 2"],
        "confidence": 0.0 to 1.0,
        "reasoning": "brief explanation"
    }}

    If all claims are supported, unsupported_claims should be an empty list [].
"""

def _build_context_block(chunks: List[RetrievedChunk]) -> str:
    """
    Format retrieved chunks into a numbered context block.
    Each chunk gets a clear header with source and page number
    so the LLM knows exactly where to pull citations from.
    """
    if not chunks:
        return "No context available"
    
    block_parts = []

    for idx, chunk in enumerate(chunks, start = 1):
        chunk_text = CONTEXT_CHUNK_TEMPLATE.format(
            index = idx,
            source_file = chunk.source_file,
            page_number = chunk.page_number,
            content = chunk.content.strip()
        )
        block_parts.append(chunk_text)

    return "\n".join(block_parts)

def _estimate_tokens(text: str) -> int:
    """Quick token estimate"""
    return len(text)

class PromptBuilder:
    """
    Builds structured prompts from query + retrieved chunks.
    """

    def __init__(self, max_context_tokens: int = 6000):
        """
        Max tokens to use for context.
        """
        self.max_context_tokens = max_context_tokens

        logger.info(
            "prompt_builder_initialized",
            max_context_tokens=max_context_tokens
        )

    def _trim_chunks_to_token_limit(
        self,
        chunks: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        
        """
        Trim chunk list so context fits within token limit.
        """
        selected = []
        total_tokens = 0

        for chunk in chunks:
            chunk_tokens = _estimate_tokens(chunk.content)

            if total_tokens + chunk_tokens > self.max_context_tokens:
                if not selected:
                    selected.append(chunk)
                    logger.warning(
                        "single_chunk_exceeds_token_limit",
                        chunk_id=chunk.chunk_id,
                        chunk_tokens=chunk_tokens,
                        limit=self.max_context_tokens
                    )
                break

            selected.append(chunk)
            total_tokens += chunk_tokens

        if len(selected) < len(chunks):
            logger.info(
                "chunks_trimmed_to_fit_token_limit",
                original=len(chunks),
                kept=len(selected),
                total_tokens=total_tokens
            )
        
        return selected
    
    def build_rag_prompt(
        self,
        query: str,
        chunks: List[RetrievedChunk]
    ) -> BuildPrompt:
        
        """
        Build the main RAG prompt for answer generation.
        """
        if not query.strip():
            raise ValueError("Query cannot be empty")
        
        if not chunks:
            logger.warning(
                "build_rag_prompt_no_chunks",
                query=query[:80]
            )

            prompt = NO_CONTEXT_PROMPT.format(query = query)
            return BuildPrompt(
                prompt=prompt,
                query=query,
                chunks_used=[],
                total_context_tokens=_estimate_tokens(prompt),
                num_sources=0
            )
        
        selected_chunks = self._trim_chunks_to_token_limit(chunks)
        context_block = _build_context_block(selected_chunks)

        context_section = RAG_CONTEXT_TEMPLATE.format(
            context_block = context_block,
            query = query
        )

        full_prompt = RAG_SYSTEM_PROMPT + context_section

        total_tokens = _estimate_tokens(full_prompt)
        unique_sources = len({c.source_file for c in selected_chunks})

        built = BuildPrompt(
            prompt=full_prompt,
            query=query,
            chunks_used=selected_chunks,
            total_context_tokens=total_tokens,
            num_sources=unique_sources
        )

        logger.info(
            "rag_prompt_built",
            query_preview=query[:80],
            chunks_in_context=len(selected_chunks),
            unique_sources=unique_sources,
            estimated_tokens=total_tokens
        )

        return built
    
    def build_verification_prompt(
        self,
        answer: str,
        chunks: List[RetrievedChunk]
    ) -> str:
        
        """
        Build a prompt for the answer verification module.
        Asks Gemini to check if every claim in the answer
        is supported by the retrieved chunks.
        """
        if not answer.strip():
            raise ValueError("Answer cannot be empty for verification")
        
        context_block = _build_context_block(chunks)

        prompt = VERIFICATION_PROMPT.format(
            context_block = context_block,
            answer = answer
        )

        logger.debug(
            "verification_prompt_built",
            answer_preview=answer[:80],
            num_chunks=len(chunks)
        )

        return prompt
    
    def format_chunk_as_sources(
        self,
        chunks: List[RetrievedChunk]
    ) -> List[dict]:
        
        """
        Format chunks into a clean sources list for the API response.
        This is what gets returned to the user alongside the answer
        so they can verify claims against original documents.
        """
        sources = []
        seen = set()

        for chunk in chunks:
            key = f"{chunk.source_file} :: {chunk.page_number}"
            if key in seen:
                continue

            seen.add(key)

            sources.append({
                "source_file": chunk.source_file,
                "page_number": chunk.page_number,
                "chunk_id": chunk.chunk_id,
                "relevance_score": round(chunk.score, 4),
                "content_preview": chunk.content[:200] + "..."
                    if len(chunk.content) > 200
                    else chunk.content
            })

        return sources