from dataclasses import dataclass, field
from typing import List
import re

from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class DocumentChunk:
    chunk_id: str
    content: str
    document_id: str
    source_file: str
    page_number: int
    chunk_index: int
    total_chunks: int
    token_count: int
    metadata: dict = field(default_factory=dict)

def _estimate_tokens(text: str) -> int:
    return len(text) // 4

def _split_into_chunks(
        text: str,
        chunk_size: int,
        chunk_overlap: int
) -> List[str]:
    if not text.strip():
        return []
    
    sentences = re.split(r'(?<=[.!?])\s+|\n\n+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return []
    
    chunks = []
    current_sentences = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = _estimate_tokens(sentence)

        if sentence_tokens > chunk_size:
            if current_sentences:
                chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_tokens = 0

            words = sentence.split()
            word_buffer = []
            word_tokens = 0

            for word in words:
                word_tokens += _estimate_tokens(word + " ")
                if word_tokens > chunk_size:
                    if word_buffer:
                        chunks.append(" ".join(word_buffer))
                    word_buffer = [word]
                    word_tokens = _estimate_tokens(word + " ")
                else:
                    word_buffer.append(word)

            if word_buffer:
                current_sentences = word_buffer
                current_tokens = word_tokens
            continue

        if current_tokens + sentence_tokens > chunk_size:
            if current_sentences:
                chunks.append(" ".join(current_sentences))

            overlap_sentences = []
            overlap_tokens = 0

            for prev_sentence in reversed(current_sentences):
                prev_tokens = _estimate_tokens(prev_sentence)
                if overlap_tokens + prev_tokens <= chunk_overlap:
                    overlap_sentences.insert(0, prev_sentence)
                    overlap_tokens += prev_tokens
                else:
                    break
            
            current_sentences = overlap_sentences + [sentence]
            current_tokens = overlap_tokens + sentence_tokens

        else:
            current_sentences.append(sentence)
            current_tokens += sentence_tokens

    if current_sentences:
        chunks.append(" ".join(current_sentences))
    
    return chunks

class DocumentChunker:

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        self.chunk_size = chunk_size or settings.chunking.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunking.chunk_overlap

        logger.debug(
            "chunker initialized",
            chunk_size = self.chunk_size,
            chunk_overlap = self.chunk_overlap
        )
    
    def chunk_page(self, page) -> List[DocumentChunk]:
        raw_chunks = _split_into_chunks(
            text = page.content,
            chunk_size = self.chunk_size,
            chunk_overlap = self.chunk_overlap
        )

        chunks = []
        for idx, chunk_text in enumerate(raw_chunks):
            chunk = DocumentChunk(
                chunk_id = f"{page.document_id}_p{page.page_number}_c{idx}",
                content = chunk_text,
                document_id = page.document_id,
                source_file = page.source_file,
                page_number = page.page_number,
                chunk_index = idx,
                total_chunks = 0,
                token_count = _estimate_tokens(chunk_text),
                metadata={
                    **page.metadata,
                    "file_type": page.file_type,
                }
            )
            chunks.append(chunk)
        
        return chunks
    
    def chunk_document(self, pages: List) -> List[DocumentChunk]:
        if not pages:
            logger.warning("chunk_document_called_with_empty_pages")
            return []
        
        source_file = pages[0].source_file
        logger.debug(
            "chunking_started",
            source_file = source_file,
            total_pages = len(pages)
        )

        all_chunks = []

        for page in pages:
            page_chunks = self.chunk_page(page)
            all_chunks.extend(page_chunks)

        total = len(all_chunks)
        for chunk in all_chunks:
            chunk.total_chunks = total

        logger.debug(
            "chunking_complete",
            source_file = source_file,
            total_chunks = total,
            avg_tokens = round(
                sum(c.token_count for c in all_chunks) / total, 1
            ) if total else 0
        )

        return all_chunks
    
    def chunk_documents(self, documents: List) -> List[DocumentChunk]:
        all_chunks = []

        for doc in documents:
            try:
                chunks = self.chunk_document(doc.pages)
                all_chunks.extend(chunks)
            except Exception as e:
                logger.error(
                    "chunking_document_failed",
                    filename=doc.filename,
                    error=str(e)
                )

        logger.debug(
            "all_documents_chunked",
            total_documents=len(documents),
            total_chunks=len(all_chunks)
        )

        return all_chunks
    