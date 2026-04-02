import time
from dataclasses import dataclass, field
from typing import List, Optional
import google.generativeai as genai
from tenacity import(
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from ingestion.chunker import DocumentChunk
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class EmbeddedChunk:
    """
    A DocumentChunk enhanced with its vector embedding.
    This is the final chunks stored in ChromaDB.
    """
    chunk_id: str
    content: str
    document_id: str
    source_file: str
    page_number: int
    chunk_index: int
    total_chunks: int
    token_count: int
    metadata: dict = field(default_factory=dict)

    embedding: List[float] = field(default_factory=list)
    embedding_model: str = ""

TASK_TYPE_DOCUMENT = "retrieval_document"
TASK_TYPE_QUERY = "retrieval_query"

@retry(
    stop = stop_after_attempt(3),
    wait = wait_exponential(multiplier=1, min=2, max=8),
    retry = retry_if_exception_type(Exception),
    reraise = True
)
def _embed_text(
    text: str,
    task_type: str,
    model_name: str
) -> List[float]:
    """
    Call Gemini embedding API for a single text string.
    """
    result = genai.embed_content(
        model = model_name,
        content = text,
        task_type = task_type
    )
    return result["embedding"]

class GeminiEmbedder:
    """
    Generates vector embeddings for document chunks using Gemini.
    """
    BATCH_SIZE = 10
    BATCH_DELAY_SEC = 1.0

    def __init__(self):
        genai.configure(api_key = settings.gemini.gemini_api_key)
        self.model_name = settings.gemini.gemini_embedding_model

        logger.info(
            "embedder_initialized",
            model=self.model_name
        )
    
    def embed_query(self, query: str) -> List[float]:
        """
        Embed a single search query.
        """
        if not query.strip():
            raise ValueError("Query text cannot be empty.")
        
        logger.debug("embedding_query", query_preview=query[:80])

        try:
            vector = _embed_text(
                text = query,
                task_type = TASK_TYPE_QUERY,
                model_name=self.model_name
            )
            logger.debug(
                "query_embeded",
                dimensions = len(vector)
            )
            return vector
        
        except Exception as e:
            logger.error("query_embedding_failed", error=str(e))
            raise

    def embed_chunk(self, chunk: DocumentChunk) -> EmbeddedChunk:
        """
        Embed a single Document Chunk.
        """
        try:
            vector = _embed_text(
                text=chunk.content,
                task_type=TASK_TYPE_DOCUMENT,
                model_name=self.model_name
            )

            return EmbeddedChunk(
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                document_id=chunk.document_id,
                source_file=chunk.source_file,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                total_chunks=chunk.total_chunks,
                token_count=chunk.token_count,
                metadata=chunk.metadata,
                embedding=vector,
                embedding_model=self.model_name
            )
        
        except Exception as e:
            logger.error(
                "chunk_embedding_failed",
                chunk_id=chunk.chunk_id,
                error=str(e)
            )
            raise
    
    def embed_chunks(
        self,
        chunks: List[DocumentChunk],
        show_progress: bool = True
    ) -> List[EmbeddedChunk]:
        """
        Embed a list of DocumentChunks in batches.
        """
        if not chunks:
            logger.warning("embed_chunks_called_with_empty_list")
            return []
        
        total = len(chunks)
        embedded = []
        failed = 0

        logger.info(
            "embedding_started",
            total_chunks=total,
            batch_size=self.BATCH_SIZE
        )

        start_time = time.time()

        for batch_start in range(0, total, self.BATCH_SIZE):
            batch = chunks[batch_start: batch_start + self.BATCH_SIZE]
            batch_num = (batch_start // self.BATCH_SIZE) + 1
            total_batches = (total + self.BATCH_SIZE - 1) // self.BATCH_SIZE

            if show_progress:
                logger.info(
                    "embedding_batch",
                    batch=batch_num,
                    of=total_batches,
                    chunks_in_batch=len(batch)
                )

            for chunk in batch:
                try:
                    embedded_chunk = self.embed_chunk(chunk)
                    embedded.append(embedded_chunk)

                except Exception as e:
                    logger.error(
                        "chunk_skipped_embedding_failed",
                        chunk_id=chunk.chunk_id,
                        source_file=chunk.source_file,
                        error=str(e)
                    )
                    failed += 1

            if batch_start + self.BATCH_SIZE < total:
                time.sleep(self.BATCH_DELAY_SEC)

        elapsed = round(time.time() - start_time, 2)

        logger.info(
            "embedding_complete",
            total_chunks=total,
            embedded=len(embedded),
            failed=failed,
            elapsed_sec=elapsed,
            avg_sec_per_chunk=round(elapsed / total, 3) if total else 0
        )

        return embedded