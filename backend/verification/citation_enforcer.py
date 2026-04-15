import re
from dataclasses import dataclass
from typing import List

from retrieval.vector_store import RetrievedChunk
from config.logging_config import get_logger

logger = get_logger(__name__)

CITATION_PATTERN = r'\[Source:\s*([^,\]]+),\s*Page:\s*(\d+)\]'

@dataclass
class CitationCheckResult:
    original_answer: str
    enforced_answer: str 
    citations_found: List[dict] 
    missing_citations: List[str] 
    phantom_citations: List[dict] 
    is_compliant: bool
    compliance_score: float

class CitationEnforcer:
    def extract_citations(self, text: str) -> List[dict]:
        matches = re.findall(CITATION_PATTERN, text, re.IGNORECASE)
        return [
            {
                "source_file": m[0].strip(),
                "page_number": int(m[1])
            }
            for m in matches
        ]
    
    def find_uncited_sentences(self, answer: str) -> List[str]:
        if "cannot find this information" in answer.lower():
            return []
        
        sentences = re.split(r'(?<=[.!?])\s+', answer)
        uncited   = []

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue

            if re.search(CITATION_PATTERN, sentence, re.IGNORECASE):
                continue

            if any(word in sentence.lower() for word in [
                "is", "are", "was", "were", "has", "have",
                "states", "shows", "indicates", "reports",
                "developed", "created", "used", "includes"
            ]):
                uncited.append(sentence)

        return uncited
    
    def find_phantom_citations(
        self,
        answer: str,
        chunks: List[RetrievedChunk]
    ) -> List[dict]:
        cited = self.extract_citations(answer)

        real_sources = {
            (c.source_file.lower(), c.page_number)
            for c in chunks
        }

        phantoms = []
        for cite in cited:
            key = (cite["source_file"].lower(), cite["page_number"])
            if key not in real_sources:
                phantoms.append(cite)

        return phantoms
    
    def check(
        self,
        answer: str,
        chunks: List[RetrievedChunk]
    ) -> CitationCheckResult:
        if not answer.strip():
            return CitationCheckResult(
                original_answer = "",
                enforced_answer = "",
                citations_found = [],
                missing_citations = [],
                phantom_citations = [],
                is_compliant = False,
                compliance_score = 0.0
            )
        
        citations_found = self.extract_citations(answer)

        missing = self.find_uncited_sentences(answer)

        phantoms = self.find_phantom_citations(answer, chunks)

        total_sentences = max(
            len(re.split(r'(?<=[.!?])\s+', answer)), 1
        )
        issues = len(missing) + len(phantoms)

        compliance_score = round(
            max(0.0, 1.0 - (issues / total_sentences)), 3
        )

        is_compliant = (
            len(missing) == 0 and
            len(phantoms) == 0 and
            len(citations_found) > 0
        )

        logger.info(
            "citation_check_complete",
            citations_found = len(citations_found),
            missing_citations = len(missing),
            phantom_citations = len(phantoms),
            is_compliant = is_compliant,
            compliance_score = compliance_score
        )

        return CitationCheckResult(
            original_answer = answer,
            enforced_answer = answer,
            citations_found = citations_found,
            missing_citations = missing,
            phantom_citations = phantoms,
            is_compliant = is_compliant,
            compliance_score = compliance_score
        )
