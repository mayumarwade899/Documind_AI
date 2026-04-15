import tiktoken
from dataclasses import dataclass
from typing import List, Optional
from retrieval.vector_store import RetrievedChunk
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class BuiltPrompt:
    prompt: str
    query: str
    chunks_used: List[RetrievedChunk]
    total_context_tokens: int
    num_sources: int

RAG_SYSTEM_PROMPT = """
You are a precise document assistant. Answer ONLY using the provided context chunks below.

RULES:
1. Use ONLY information from the context. No external knowledge.
2. If the context does not contain the answer, say exactly: "I cannot find this information in the provided documents."
3. Be EXTREMELY thorough and detailed in your answer — provide multi-paragraph explanations. Do not truncate or summarize if more detail is available.
4. Use bullet points, bold text, and structure for clarity.
5. Do NOT reference chunk numbers or say "according to the context".
6. Break down complex concepts into step-by-step explanations or sections.
7. Ensure every response ends with a complete sentence and proper punctuation. Avoid starting sentences you cannot finish.
"""

SUMMARY_SYSTEM_PROMPT = """
You are a precise document assistant. Produce a comprehensive structured summary using ONLY the provided context chunks.

OUTPUT FORMAT (use these exact headings in markdown):
## Document Title
(infer from content)

## Key Points
- Point 1
- Point 2
- Point 3
(list all significant points found in the context)

## Summary
(2–4 paragraph detailed summary of the main ideas)

## Conclusion
(1 paragraph covering conclusions, recommendations, or next steps)

RULES:
1. Use ONLY information from the provided context chunks.
2. Be comprehensive — do not truncate or shorten.
3. If context is insufficient, note it under the relevant section.
4. Ensure every response ends with a complete sentence and proper punctuation.
"""

RAG_CONTEXT_TEMPLATE = """
CONTEXT:
{context_block}

QUESTION: {query}

ANSWER:
"""

CONTEXT_CHUNK_TEMPLATE = "[{index}] ({source_file}, p.{page_number}):\n{content}"

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
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        return len(text) // 4

class PromptBuilder:
    def __init__(self, max_context_tokens: int = None):
        self.max_context_tokens = (
            max_context_tokens or settings.retrieval.max_context_tokens
        )

        logger.debug(
            "prompt_builder_initialized",
            max_context_tokens=max_context_tokens
        )

    def _trim_chunks_to_token_limit(
        self,
        chunks: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
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
            logger.debug(
                "chunks_trimmed_to_fit_token_limit",
                original=len(chunks),
                kept=len(selected),
                total_tokens=total_tokens
            )
        
        return selected
    
    def build_rag_prompt(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        max_context_tokens: Optional[int] = None,
        is_summary: bool = False
    ) -> BuiltPrompt:
        if max_context_tokens:
            self.max_context_tokens = max_context_tokens
            
        if not query.strip():
            raise ValueError("Query cannot be empty")
        
        if not chunks:
            logger.warning(
                "build_rag_prompt_no_chunks",
                query=query[:80]
            )

            prompt = NO_CONTEXT_PROMPT.format(query = query)
            return BuiltPrompt(
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

        system_prompt = SUMMARY_SYSTEM_PROMPT if is_summary else RAG_SYSTEM_PROMPT
        full_prompt = system_prompt + context_section

        total_tokens = _estimate_tokens(full_prompt)
        unique_sources = len({c.source_file for c in selected_chunks})

        built = BuiltPrompt(
            prompt=full_prompt,
            query=query,
            chunks_used=selected_chunks,
            total_context_tokens=total_tokens,
            num_sources=unique_sources
        )

        logger.debug(
            "rag_prompt_built",
            query_preview=query[:80],
            is_summary=is_summary,
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