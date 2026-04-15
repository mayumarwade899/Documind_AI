import re
from typing import List, Dict
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
    original_query : str
    rewritten_query : str
    variants : List[str]
    all_queries: List[str]

COMBINED_REWRITE_PROMPT = """
    You are an expert at information retrieval.
    
    TASK 1: Rewrite the User Question to be stand-alone and specific using provided History. Resolve pronouns.
    TASK 2: Generate {num_variants} search variants for Task 1's rewritten query.
    
    Conversation History:
    {history}

    User Question: {query}

    Respond in this exact format:
    REWRITTEN: [Single line rewritten query]
    VARIANTS:
    1. [Variant 1]
    2. [Variant 2]
"""

@retry(
    stop = stop_after_attempt(3),
    wait = wait_exponential(multiplier = 1, min = 2, max = 8),
    retry = retry_if_exception_type(Exception),
    reraise = True
)
def _call_gemini(prompt: str, model_name: str) ->  str:
    model = genai.GenerativeModel(
        model_name = model_name,
        generation_config = genai.GenerationConfig(
            temperature = 0.2,
            max_output_tokens = 512
        )
    )
    response = model.generate_content(prompt)
    return response.text.strip()

class QueryRewriter:

    def __init__(self):
        genai.configure(api_key = settings.gemini.gemini_api_key)
        self.model_name = settings.gemini.gemini_model

        logger.debug(
            "query_rewriter_initialized",
            model = self.model_name
        )

    def rewrite_with_variants(
            self,
            query: str,
            num_variants: int = None,
            history: List[Dict] = []
    ) -> RewrittenQuery:
        if not query.strip():
            raise ValueError("Query cannot be empty")

        n = num_variants or settings.retrieval.multi_query_count
        
        history_str = "\n".join([
            f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['content'][:150]}"
            for h in history[-3:]
        ]) if history else "No history."

        prompt = COMBINED_REWRITE_PROMPT.format(
            query = query,
            history = history_str,
            num_variants = n
        )

        try:
            raw = _call_gemini(prompt, self.model_name, max_tokens=350)
            
            rewritten = query
            variants = []

            lines = raw.strip().splitlines()
            for line in lines:
                if line.startswith("REWRITTEN:"):
                    rewritten = line.replace("REWRITTEN:", "").strip()
                elif re.match(r"^\d+[\.\)]", line.strip()):
                    variants.append(re.sub(r"^\d+[\.\)]\s*", "", line.strip()))

            all_queries = [rewritten]
            for v in variants:
                if v.lower() != rewritten.lower():
                    all_queries.append(v)

            return RewrittenQuery(
                original_query = query,
                rewritten_query = rewritten,
                variants = variants[:n],
                all_queries = all_queries[:n+1]
            )

        except Exception as e:
            logger.warning("combined_rewrite_failed", error=str(e))
            return RewrittenQuery(query, query, [], [query])
