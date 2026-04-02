import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from retrieval.vector_store import RetrievedChunk
from generation.llm_client import GeminiClient
from generation.prompt_builder import PromptBuilder
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class ClaimVerification:
    """
    Verification result for a single claim extracted from answer.
    """
    claim: str
    is_supported: bool
    supporting_chunk_ids: List[str] = field(default_factory = list)
    confidence: float = 0.0

@dataclass
class VerificationResult:
    """
    Complete verification result for a full answer.
    """
    is_fully_supported: bool 
    support_ratio: float 
    confidence: float 

    unsupported_claims: List[str] 
    all_claims: List[str] 
    claim_verifications: List[ClaimVerification]

    has_citations: bool 
    citation_count: int 

    verification_latency_ms: float
    reasoning: str 
    verified_answer: str 
    metadata: dict = field(default_factory=dict)

def _check_citations(answer: str) -> Tuple[bool, int]:
    """
    Check if answer contains [Source: ...] citation patterns.
    """
    citation_pattern = r'\[Source:\s*.+?,\s*Page:\s*\d+\]'
    citations = re.findall(citation_pattern, answer, re.IGNORECASE)

    return len(citations) > 0, len(citations)

def _extract_cited_sources(answer: str) -> List[dict]:
    """
    Extract all cited sources from answer text.
    Returns list of dicts with filename and page number.
    Used to cross-check against actual retrieved chunks.
    """
    pattern = r'\[Source:\s*(.+?),\s*Page:\s*(\d+)\]'
    matches = re.findall(pattern, answer, re.IGNORECASE)

    return [
        {
            "source_file": match[0].strip(),
            "page_number": int(match[1])
        }
        for match in matches
    ]

def _validate_citations_against_chunks(
    answer: str,
    chunks: List[RetrievedChunk]
) -> Tuple[List[dict], List[dict]]:
    """
    Check that cited sources actually exist in retrieved chunks.
    """
    cited = _extract_cited_sources(answer)

    real_sources = {
        (c.source_file.lower(), c.page_number)
        for c in chunks
    }

    valid = []
    phantoms = []

    for cite in cited:
        key = (cite["source_file"].lower(), cite["page_number"])
        if key in real_sources:
            valid.append(cite)
        else:
            phantoms.append(cite)

    return valid, phantoms

class AnswerVerifier:
    """
    Verifies generated answers are grounded in retrieved chunks.
    """
    def __int__(
        self,
        llm_client: Optional[GeminiClient] = None,
        prompt_builder: Optional[PromptBuilder] = None
    ):
        self.llm_client = llm_client or GeminiClient(
            temperature = 0.1
        )
        self.prompt_builder = prompt_builder or PromptBuilder()

        logger.info("answer_verifier_initialized")

    def _verify_with_llm(
        self,
        answer: str,
        chunks: List[RetrievedChunk]
    ) -> dict:
        """
        Use Gemini to verify answer claims against chunks.
        """
        verification_prompt = self.prompt_builder.build_verification_prompt(
            answer = answer,
            chunks = chunks
        )

        parsed, llm_response = self.llm_client.generate_json(
            prompt = verification_prompt,
            metadata = {"task": "answer_verification"}
        )

        logger.debug(
            "llm_verification_complete",
            tokens_used = llm_response.total_tokens,
            cost_usd = llm_response.cost_usd,
            parsed_keys = list(parsed.keys()) if parsed else []
        )

        return parsed
    
    def _build_claim_verifications(
        self,
        llm_result: dict,
        chunks: List[RetrievedChunk]
    ) -> List[ClaimVerification]:
        
        """
        Convert LLM verification result into ClaimVerification objects.
        """
        unsupported = llm_result.get("unsupported_claims", [])
        confidence  = float(llm_result.get("confidence", 0.5))

        all_chunk_ids = [c.chunk_id for c in chunks]

        claim_verification = []
        for claim in unsupported:
            claim_verification.append(ClaimVerification(
                claim = claim,
                is_supported = False,
                supporting_chunk_ids = [],
                confidence = confidence
            ))

        return claim_verification
    
    def verify(
        self,
        answer: str,
        chunks: List[RetrievedChunk],
        query: str = ""
    ) -> VerificationResult:
        """
        Run full verification on a generated answer.
        """
        start_time = time.time()

        if not answer.strip():
            logger.warning("verify_called_with_empty_answer")
            return self._empty_result()
        
        logger.info(
            "verification_started",
            query_preview = query[:80],
            answer_preview = answer[:80],
            num_chunks = len(chunks)
        )

        has_citations, citation_count = _check_citations(answer)

        valid_cites, phantom_cites = _validate_citations_against_chunks(
            answer, chunks
        )

        if phantom_cites:
            logger.warning(
                "phantom_citations_detected",
                phantom_sources = [p["source_file"] for p in phantom_cites],
                count = len(phantom_cites)
            )

        llm_result   = {}
        is_supported = True
        unsupported  = []
        confidence   = 1.0
        reasoning    = ""

        if chunks:
            try:
                llm_result = self._verify_with_llm(answer, chunks)

                is_supported = bool(
                    llm_result.get("is_supported", True)
                )
                unsupported = llm_result.get(
                    "unsupported_claims", []
                )
                confidence = float(
                    llm_result.get("confidence", 0.5)
                )
                reasoning = llm_result.get("reasoning", "")

            except Exception as e:
                logger.warning(
                    "llm_verification_failed_skipping",
                    error = str(e)
                )

                confidence = 0.5
                reasoning  = "Verification could not be completed."

        answer_sentences = [
            s.strip() for s in re.split(r'[.!?]', answer)
            if s.strip() and len(s.strip()) > 20
        ]
        total_claims = max(len(answer_sentences), 1)
        num_unsupported = len(unsupported)
        support_ratio = round(
            max(0.0, (total_claims - num_unsupported) / total_claims),
            3
        )

        claim_verifications = self._build_claim_verifications(
            llm_result, chunks
        )

        is_fully_supported = (
            is_supported
            and len(phantom_cites) == 0
            and has_citations
        )

        latency_ms = round((time.time() - start_time) * 1000, 2)

        result = VerificationResult(
            is_fully_supported = is_fully_supported,
            support_ratio = support_ratio,
            confidence = confidence,
            unsupported_claims = unsupported,
            all_claims = answer_sentences,
            claim_verifications = claim_verifications,
            has_citations = has_citations,
            citation_count = citation_count,
            verification_latency_ms = latency_ms,
            reasoning = reasoning,
            verified_answer = answer,
            metadata={
                "valid_citations": len(valid_cites),
                "phantom_citations": len(phantom_cites),
                "phantom_sources": phantom_cites,
                "num_chunks_checked": len(chunks)
            }
        )

        logger.info(
            "verification_complete",
            is_fully_supported = is_fully_supported,
            support_ratio = support_ratio,
            confidence = confidence,
            citation_count = citation_count,
            unsupported_count = len(unsupported),
            phantom_citations = len(phantom_cites),
            latency_ms = latency_ms
        )

        return result
    
    def _empty_result(self) -> VerificationResult:
        """
        Return a neutral result for empty answers.
        """
        return VerificationResult(
            is_fully_supported = False,
            support_ratio = 0.0,
            confidence = 0.0,
            unsupported_claims = [],
            all_claims = [],
            claim_verifications = [],
            has_citations = False,
            citation_count = 0,
            verification_latency_ms = 0.0,
            reasoning = "Empty answer provided.",
            verified_answer = "",
            metadata = {}
        )
    