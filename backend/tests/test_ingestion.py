import pytest
from pathlib import Path
from ingestion.document_loader import DocumentLoader
from ingestion.chunker import DocumentChunker

def test_document_loader_pdf():
    loader = DocumentLoader()
    pdf_files = list(Path("data/documents").glob("*.pdf"))

    if not pdf_files:
        pytest.skip("No PDF files in data/documents/")

    doc = loader.load(str(pdf_files[0]))
    assert doc.total_pages > 0
    assert len(doc.pages) > 0
    assert doc.document_id != ""
    assert all(p.content for p in doc.pages)

def test_document_loader_unsupported():
    loader = DocumentLoader()
    with pytest.raises(ValueError):
        loader.load("test.xyz")

def test_document_loader_missing_file():
    loader = DocumentLoader()
    with pytest.raises(FileNotFoundError):
        loader.load("nonexistent.pdf")

def test_chunker_basic():
    loader = DocumentLoader()
    chunker = DocumentChunker(chunk_size = 200, chunk_overlap = 50)

    pdf_files = list(Path("data/documents").glob("*.pdf"))
    if not pdf_files:
        pytest.skip("No PDF files in data/documents/")

    doc = loader.load(str(pdf_files[0]))
    chunks = chunker.chunk_document(doc.pages)

    assert len(chunks) > 0
    assert all(c.content for c in chunks)
    assert all(c.chunk_id for c in chunks)
    assert all(c.document_id == doc.document_id for c in chunks)

def test_chunker_token_limit():
    loader = DocumentLoader()
    chunker = DocumentChunker(chunk_size = 200, chunk_overlap = 50)

    pdf_files = list(Path("data/documents").glob("*.pdf"))
    if not pdf_files:
        pytest.skip("No PDF files in data/documents/")

    doc = loader.load(str(pdf_files[0]))
    chunks = chunker.chunk_document(doc.pages)

    for chunk in chunks:
        assert chunk.token_count < 400, (
            f"Chunk {chunk.chunk_id} too large: {chunk.token_count}"
        )

def test_chunk_ids_unique():
    loader = DocumentLoader()
    chunker = DocumentChunker()

    pdf_files = list(Path("data/documents").glob("*.pdf"))
    if not pdf_files:
        pytest.skip("No PDF files in data/documents/")

    doc = loader.load(str(pdf_files[0]))
    chunks = chunker.chunk_document(doc.pages)

    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "Duplicate chunk IDs found"