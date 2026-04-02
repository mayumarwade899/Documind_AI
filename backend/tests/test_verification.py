import pytest
from verification.citation_enforcer import CitationEnforcer
from retrieval.vector_store import RetrievedChunk

def make_chunk(source_file = "test.pdf", page = 1):
    return RetrievedChunk(
        chunk_id = "c1",
        content = "The contract expires in 2025.",
        source_file = source_file,
        page_number = page,
        document_id = "doc1",
        score = 0.9,
        retrieval_method = "hybrid"
    )

def test_citation_extractor_valid():
    """
    Extracts correct citations from answer.
    """
    enforcer = CitationEnforcer()
    answer = "The contract expires in 2025. [Source: test.pdf, Page: 1]"
    citations = enforcer.extract_citations(answer)

    assert len(citations) == 1
    assert citations[0]["source_file"] == "test.pdf"
    assert citations[0]["page_number"] == 1

def test_citation_extractor_none():
    """
    Returns empty list when no citations present.
    """
    enforcer = CitationEnforcer()
    citations = enforcer.extract_citations("No citations here.")
    assert citations == []

def test_phantom_citation_detected():
    """
    Detects citation for source not in retrieved chunks.
    """
    enforcer = CitationEnforcer()
    answer = (
        "Something happened. "
        "[Source: phantom_file.pdf, Page: 99]"
    )
    chunks = [make_chunk("real_file.pdf", 1)]
    phantoms = enforcer.find_phantom_citations(answer, chunks)

    assert len(phantoms) == 1
    assert phantoms[0]["source_file"] == "phantom_file.pdf"

def test_no_phantom_when_source_matches():
    """
    No phantoms when citation matches retrieved chunk.
    """
    enforcer = CitationEnforcer()
    answer = "Expires in 2025. [Source: test.pdf, Page: 1]"
    chunks = [make_chunk("test.pdf", 1)]
    phantoms = enforcer.find_phantom_citations(answer, chunks)
    assert phantoms == []

def test_compliance_check_passing():
    """
    Fully cited answer passes compliance.
    """
    enforcer = CitationEnforcer()
    answer = (
        "The contract expires in 2025. [Source: test.pdf, Page: 1]"
    )
    chunks = [make_chunk("test.pdf", 1)]
    result = enforcer.check(answer, chunks)

    assert result.citations_found != []
    assert result.phantom_citations == []
    assert result.compliance_score > 0.0

def test_compliance_check_empty_answer():
    """
    Empty answer returns zero compliance.
    """
    enforcer = CitationEnforcer()
    result =  enforcer.check("", [])
    assert result.is_compliant == False
    assert result.compliance_score == 0.0
