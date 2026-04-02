import pytest
from unittest.mock import MagicMock, patch
from generation.prompt_builder import PromptBuilder
from generation.llm_client import GeminiClient, _calculate_cost
from retrieval.vector_store import RetrievedChunk

def make_chunk(
    chunk_id = "c1",
    content = "Test Content",
    page = 1
):
    return RetrievedChunk(
        chunk_id = chunk_id,
        content = content,
        source_file = "test.pdf",
        page_number = page,
        document_id = "doc1",
        score = 0.9,
        retrieval_method = "hybrid"
    )

def test_prompt_builder_empty_chunks():
    """
    Empty chunks returns no-context prompt.
    """
    builder = PromptBuilder()
    built = builder.build_rag_prompt(
        query = "What is this?",
        chunks = []
    )
    assert "cannot find" in built.prompt.lower()
    assert built.num_sources == 0

def test_prompt_builder_with_chunks():
    """
    Chunks are included in prompt with source labels.
    """
    builder = PromptBuilder()
    chunks = [make_chunk("c1", "The sky is blue.", 1)]
    built = builder.build_rag_prompt(
        query = "What color is the sky?",
        chunks = chunks
    )
    assert "test.pdf" in built.prompt
    assert "The sky is blue" in built.prompt
    assert built.num_sources == 1

def test_prompt_builder_token_limit():
    """
    Long chunks are trimmed to fit token budget.
    """
    builder = PromptBuilder(max_context_tokens = 100)
    chunks = [
        make_chunk(f"c{i}", "word " * 200, i)
        for i in range(10)
    ]
    built = builder.build_rag_prompt(
        query = "test query",
        chunks = chunks
    )
    assert built.total_context_tokens <= 600

def test_format_chunks_as_sources():
    """
    Sources are correctly formatted.
    """
    builder = PromptBuilder()
    chunks = [
        make_chunk("c1", "Content A", 1),
        make_chunk("c2", "Content B", 2),
    ]
    sources = builder.format_chunk_as_sources(chunks)
    assert len(sources) == 2
    assert sources[0]["source_file"] == "test.pdf"
    assert sources[0]["page_number"] in [1, 2]

def test_cost_calculation():
    """
    Cost calculation uses correct pricing.
    """
    cost = _calculate_cost(
        model = "gemini-2.5-flash",
        input_tokens = 1000,
        output_tokens = 1000
    )
    assert cost == pytest.approx(0.0005, rel = 1e-3)

def test_verification_prompt_built():
    """
    Verification prompt contains answer and context.
    """
    builder = PromptBuilder()
    chunks = [make_chunk("c1", "The contract expires in 2025.")]
    prompt = builder.build_verification_prompt(
        answer = "The contract expires in 2025. [Source: test.pdf, Page: 1]",
        chunks = chunks
    )
    assert "2025" in prompt
    assert "verify" in prompt.lower() or "fact" in prompt.lower()