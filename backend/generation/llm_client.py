import time
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

import google.generativeai as genai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
import logging
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

COST_PER_1K_TOKENS = {
    "gemini-1.5-flash": {
        "input": 0.0001,
        "output": 0.0004
    },
    "gemini-1.5-pro": {
        "input": 0.002,
        "output": 0.008
    }
}

DEFAULT_COST = {"input": 0.0001, "output": 0.0004}

@dataclass
class LLMResponse:
    """
    Structured response from every Gemini API call.
    Carries the answer text plus all metadata needed
    for monitoring, cost tracking, and observability.
    """
    text: str
    model: str 
    input_tokens: int 
    output_tokens: int 
    total_tokens: int 
    latency_ms: float 
    cost_usd: float 
    finish_reason: str 
    metadata: dict = field(default_factory=dict)

def _calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int
) -> float:
    """
    Estimate cost of a Gemini API call in USD.
    """
    pricing = DEFAULT_COST
    for model_key in COST_PER_1K_TOKENS:
        if model_key in model:
            pricing = COST_PER_1K_TOKENS[model_key]
            break

    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]

    return round(input_cost + output_cost, 8)

class GeminiClient:
    """
    Clean wrapper around the Gemini API.
    """
    def __init__(
        self,
        model_name: str = None,
        temperature: float = None,
        max_tokens: int = None
    ):
        """
        Initialize Gemini client with settings from config.
        """
        genai.configure(api_key=settings.gemini.gemini_api_key)

        self.model_name  = model_name  or settings.gemini.gemini_model
        self.temperature = temperature or settings.gemini.gemini_temperature
        self.max_tokens  = max_tokens  or settings.gemini.gemini_max_tokens

        self.model = genai.GenerativeModel(
            model_name = self.model_name,
            generation_config = genai.GenerationConfig(
                temperature = self.temperature,
                max_output_tokens = self.max_tokens,
                top_p = 0.95,
                top_k = 40,
            )
        )

        logger.info(
            "gemini_client_initialized",
            model = self.model_name,
            temperature = self.temperature,
            max_tokens = self.max_tokens
        )

    @retry(
        stop = stop_after_attempt(3),
        wait = wait_exponential(multiplier = 1, min = 2, max = 10),
        retry = retry_if_exception_type(Exception),
        before_sleep = before_sleep_log(
            logging.getLogger(__name__), logging.WARNING
        ),
        reraise = True
    )
    def _raw_generate(self, prompt: str) -> Any:
        """
        Make raw Gemini API call with retry logic.
        """
        return self.model.generate_content(prompt)
    
    def generate(
        self,
        prompt: str,
        metadata: Optional[dict] = None
    ) -> LLMResponse:
        """
        Generate a response from Gemini.
        Measures latency, extracts token counts,
        calculates cost, and returns a structured LLMResponse.
        """
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        logger.debug(
            "llm_generate_started",
            model = self.model_name,
            prompt_length = len(prompt),
            estimated_input_tokens = len(prompt) // 4
        )

        start_time =  time.time()

        try:
            raw_response = self._raw_generate(prompt)
        except Exception as e:
            logger.error(
                "llm_generate_failed_all_retries",
                model=self.model_name,
                error=str(e)
            )
            raise

        latency_ms = round((time.time() - start_time) * 1000, 2)

        try:
            response_text = raw_response.text.strip()
        except Exception:
            response_text = ""
            logger.warning(
                "llm_response_text_extraction_failed",
                finish_reason=str(
                    raw_response.candidates[0].finish_reason
                    if raw_response.candidates else "unknown"
                )
            )

        input_tokens  = 0
        output_tokens = 0
        finish_reason = "UNKNOWN"

        try:
            usage = raw_response.usage_metadata
            input_tokens  = usage.prompt_token_count or 0
            output_tokens = usage.candidates_token_count or 0
        except Exception:
            input_tokens  = len(prompt) // 4
            output_tokens = len(response_text) // 4
            logger.debug("token_count_estimated_from_length")

        try:
            if raw_response.candidates:
                finish_reason = str(
                    raw_response.candidates[0].finish_reason
                )
        except Exception:
            pass

        total_tokens = input_tokens + output_tokens

        cost_usd = _calculate_cost(
            model = self.model_name,
            input_tokens = input_tokens,
            output_tokens = output_tokens
        )

        response = LLMResponse(
            text = response_text,
            model = self.model_name,
            input_tokens = input_tokens,
            output_tokens = output_tokens,
            total_tokens = total_tokens,
            latency_ms = latency_ms,
            cost_usd = cost_usd,
            finish_reason = finish_reason,
            metadata = metadata or {}
        )

        logger.info(
            "llm_generate_complete",
            model = self.model_name,
            input_tokens = input_tokens,
            output_tokens = output_tokens,
            total_tokens = total_tokens,
            latency_ms = latency_ms,
            cost_usd = cost_usd,
            finish_reason = finish_reason
        )

        return response
    
    def generate_json(
        self,
        prompt: str,
        metadata: Optional[dict] = None
    ) -> tuple[dict, LLMResponse]:
        """
        Generate a response and parse it as JSON.
        Used by the answer verifier which expects
        structured JSON back from Gemini.
        """
        response = self.generate(prompt=prompt, metadata=metadata)
        text = response.text.strip()

        try:
            parsed = json.loads(text)
            logger.debug(
                "json_response_parsed",
                keys=list(parsed.keys()) if isinstance(parsed, dict) else "list"
            )
            return parsed, response

        except json.JSONDecodeError as e:
            logger.error(
                "json_parse_failed",
                error = str(e),
                raw_text = response.text[:200]
            )
            return {}, response
        
    def count_tokens(self, text: str) -> int:
        """
        Count tokens for a text string using Gemini's tokenizer.
        Useful for pre-checking prompt size before sending.
        """
        try:
            result = self.model.count_tokens(text)
            return result.total_tokens
        except Exception:
            return len(text) // 4
