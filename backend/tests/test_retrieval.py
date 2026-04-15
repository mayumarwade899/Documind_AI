import pytest
from retrieval.vector_store import VectorStore, RetrievedChunk
from retrieval.bm25_retriever import BM25Retriever
from retrieval.hybrid_retriever import _reciprocal_rank_fusion

def test_vector_store_stats():
    store = VectorStore()
    stats = store.get_collection_stats()
    assert "total_chunks" in stats
    assert isinstance(stats["total_chunks"], int)

def test_bm25_stats():
    bm25  = BM25Retriever()
    stats = bm25.get_stats()
    assert "total_chunks" in stats
    assert "index_built" in stats

def test_bm25_search_empty_query():
    bm25 = BM25Retriever()
    results = bm25.search("")
    assert results == []

def test_vector_store_search_requires_vector():
    store = VectorStore()
    with pytest.raises((ValueError, Exception)):
        store.search(query_vector=[])

def test_rrf_merging():
    def make_chunk(chunk_id, score, method):
        return RetrievedChunk(
            chunk_id = chunk_id,
            content = f"content {chunk_id}",
            source_file = "test.pdf",
            page_number = 1,
            document_id = "doc1",
            score = score,
            retrieval_method = method
        )
    
    bm25_results = [
        make_chunk("A", 8.3, "bm25"),
        make_chunk("C", 7.1, "bm25"),
        make_chunk("B", 4.2, "bm25"),
    ]

    vector_results = [
        make_chunk("C", 0.91, "vector"),
        make_chunk("D", 0.87, "vector"),
        make_chunk("A", 0.81, "vector"),
    ]

    merged = _reciprocal_rank_fusion(bm25_results, vector_results)

    assert len(merged) > 0
    top_ids = [c.chunk_id for c in merged[:2]]
    assert "C" in top_ids or "A" in top_ids

def test_bm25_search_with_index():
    bm25 = BM25Retriever()
    if not bm25.bm25:
        pytest.skip("BM25 index not built yet, run ingestion first")

    results = bm25.search("document model report", top_k = 3)
    assert isinstance(results, list)