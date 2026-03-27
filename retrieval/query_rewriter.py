import re
from typing import List, Optional
from dataclasses import dataclass

import google.generativeai as genai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class RewrittenQuery:
    """
    Contains the original query, the rewritten version,
    and multiple variants for multi-query retrieval.
    """
    original_query : str
    rewritten_query : str
    variants : List[str]
    all_queries: List[str]

REWRITE_PROMPT = """
    You are an expert at reformulating questions to improve document retrieval.

    Your task is to rewrite the user's question to make it:
    1. More specific and precise
    2. Use terminology likely found in technical/legal/research documents
    3. Remove conversational filler words
    4. Expand abbreviations if any
    5. Keep it as a question or search query

    Original question: {query}

    Respond with ONLY the rewritten query. No explanation. No preamble. Just the rewritten query on a single line.
"""

MULTI_QUERY_PROMPT = """
    You are an expert at information retrieval. 

    Given a user question, generate {num_variants} different search queries that would help retrieve relevant information from documents.

    Each variant should:
    - Approach the topic from a different angle
    - Use different terminology or phrasing
    - Cover different aspects of the original question
    - Be specific enough to retrieve precise chunks

    Original question: {query}

    Respond with ONLY the queries, one per line, numbered like:
    1. first query here
    2. second query here
    3. third query here

    No explanations. No extra text. Just the numbered queries.
"""

@retry(
    stop = stop_after_attempt(3),
    wait = wait_exponential(multiplier = 1, min = 2, max = 8),
    retry = retry_if_exception_type(Exception),
    reraise = True
)
def _call_gemini(prompt: str, model_name: str) ->  str:
    """
    Make a single Gemini API call and return the text response.
    Retries up to 3 times on failure with exponential backoff.
    """
    model = genai.GenerativeModel(
        model_name = model_name,
        generation_config = genai.GenerationConfig(
            temperature = 0.2,
            max_output_tokens = 512
        )
    )
    response = model.generate_content(prompt)
    return response.text.strip()

def _parsed_numbered_list(text: str) -> List[str]:
    """
    Parse numbered LLM output into a list of questions.
    """
    lines = text.strip().splitlines()
    parsed = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        cleaned = re.sub(r"^\d+[\.\)]\s*", "", line).strip()

        if cleaned:
            parsed.append(cleaned)

    return parsed

class QueryRewriter:
    """
    Rewrites user queries for better retrieval using Gemini.
    """

    def __init__(self):
        genai.configure(api_key = settings.gemini.gemini_api_key)
        self.model_name = settings.gemini.gemini_model

        logger.info(
            "query_rewriter_initialized",
            model = self.model_name
        )

    def rewrite(self, query: str) -> str:
        """
        Rewrite a single query for better retrieval.
        Falls back to original query if LLM call fails,
        retrieval can still proceed with the original.
        """
        if not query.strip():
            return query
        
        logger.info(
            "query_rewrite_started",
            original = query[:100]
        )

        try:
            prompt = REWRITE_PROMPT.format(query = query)
            rewritten = _call_gemini(prompt, self.model_name)

            if not rewritten or len(rewritten) > 500:
                logger.warning(
                     "rewrite_sanity_check_failed",
                    rewritten_length = len(rewritten) if rewritten else 0
                )
                return query
            
            logger.info(
                "query_rewrite_complete",
                original = query[:80],
                rewritten = rewritten[:80]
            )
            return rewritten
        
        except Exception as e:
            logger.warning(
                "query_rewrite_failed_using_original",
                error=str(e)
            )
            return query
        
    def generate_variants(
            self,
            query: str,
            num_variants: int = None
    ) -> List[str]:
        """
        Generate multiple query variants for multi-query retrieval.
        """
        if not query.strip():
            return []
        
        n = num_variants or settings.retrieval.multi_query_count

        logger.info(
            "variant_generation_started",
            query_preview = query[:80],
            num_variants = n
        )

        try:
            prompt = MULTI_QUERY_PROMPT.format(
                query = query,
                num_variants = n
            )
            raw_response = _call_gemini(prompt, self.model_name)
            variants = _parsed_numbered_list(raw_response)

            if not variants:
                logger.warning(
                    "variant_parsing_returned_empty",
                    raw_response=raw_response[:200]
                )
                return [query]
            
            variants = variants[:n]

            logger.info(
                "variants_generated",
                count=len(variants),
                variants_preview=[v[:60] for v in variants]
            )
            return variants
        
        except Exception as e:
            logger.warning(
                "variant_generation_failed",
                error=str(e)
            )
            return [query]
        
    def rewrite_with_variants(
            self,
            query: str,
            num_variants: int = None
    ) -> RewrittenQuery:
        """
        Main method, rewrites query AND generates variants.
        """
        if not query.strip():
            raise ValueError("Query cannot be empty")

        logger.info(
            "full_query_rewrite_started",
            query = query[:100]
        )

        rewritten = self.rewrite(query)

        variants = self.generate_variants(
            query = rewritten,
            num_variants = num_variants
        )

        all_queries = [rewritten]
        for v in variants:
            if v.lower() != rewritten.lower():
                all_queries.append(v)

        result = RewrittenQuery(
            original_query = query,
            rewritten_query = rewritten,
            variants = variants,
            all_queries = all_queries
        )

        logger.info(
            "full_query_rewrite_complete",
            original = query[:80],
            rewritten = rewritten[:80],
            num_variants = len(variants),
            total_queries = len(all_queries)
        )

        return result