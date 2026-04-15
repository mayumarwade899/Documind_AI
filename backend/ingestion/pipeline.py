import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ingestion.document_loader import DocumentLoader
from ingestion.chunker import DocumentChunker, DocumentChunk
from ingestion.embedder import GeminiEmbedder, EmbeddedChunk
from retrieval.vector_store import VectorStore
from retrieval.bm25_retriever import BM25Retriever
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class IngestionResult:
    total_files: int
    successful_files: int
    failed_files: int
    skipped_files: int 

    total_chunks: int
    total_pages: int

    total_latency_ms: float

    file_results: List[dict] = field(default_factory=list)
    errors: List[dict] = field(default_factory=list)

@dataclass
class FileIngestionResult:
    filename: str
    document_id: str
    success: bool
    pages: int
    chunks: int
    latency_ms: float
    skipped: bool = False
    error: Optional[str] = None

class IngestionPipeline:
    def __init__(
        self,
        loader: Optional[DocumentLoader] = None,
        chunker: Optional[DocumentChunker] = None,
        embedder: Optional[GeminiEmbedder] = None,
        vector_store: Optional[VectorStore] = None,
        bm25: Optional[BM25Retriever] = None,
    ):
        self.loader = loader or DocumentLoader()
        self.chunker = chunker or DocumentChunker()
        self.embedder = embedder or GeminiEmbedder()
        self.vector_store = vector_store or VectorStore()
        self.bm25 = bm25 or BM25Retriever()

        logger.debug("ingestion_pipeline_initialized")

    def _ingest_single_file(
        self,
        file_path: str,
        force_reingest: bool = False
    ) -> FileIngestionResult:
        start_time = time.time()
        filename = Path(file_path).name

        logger.debug(
            "file_ingestion_started",
            filename=filename,
            force_reingest=force_reingest
        )

        try:
            loaded_doc = LoadedDocument = self.loader.load(file_path)
            document_id = loaded_doc.document_id

            already_exists = self.vector_store.document_exists(
                document_id
            )

            if already_exists and not force_reingest:
                latency = round((time.time() - start_time) * 1000, 2)
                logger.debug(
                    "file_already_ingested_skipping",
                    filename = filename,
                    document_id = document_id
                )
                return FileIngestionResult(
                    filename = filename,
                    document_id = document_id,
                    success = True,
                    pages = loaded_doc.total_pages,
                    chunks = 0,
                    latency_ms = latency,
                    skipped = True
                )
            
            if already_exists and force_reingest:
                logger.info(
                    "deleting_existing_document_for_reingest",
                    document_id = document_id
                )
                self.vector_store.delete_document(document_id)
                self.bm25.delete_document(document_id)
            
            chunks: List[DocumentChunk] = self.chunker.chunk_document(
                loaded_doc.pages
            )

            if not chunks:
                logger.warning(
                    "file_produced_no_chunks",
                    filename = filename
                )
                return FileIngestionResult(
                    filename = filename,
                    document_id = document_id,
                    success = False,
                    pages = loaded_doc.total_pages,
                    chunks = 0,
                    latency_ms = round(
                        (time.time() - start_time) * 1000, 2
                    ),
                    error = "Document produced no chunks after processing"
                )
            
            logger.info(
                "embedding_chunks",
                filename = filename,
                num_chunks = len(chunks)
            )

            embedded_chunks: List[EmbeddedChunk] = (
                self.embedder.embed_chunks(chunks)
            )

            if not embedded_chunks:
                return FileIngestionResult(
                    filename = filename,
                    document_id = document_id,
                    success = False,
                    pages = loaded_doc.total_pages,
                    chunks = 0,
                    latency_ms = round(
                        (time.time() - start_time) * 1000, 2
                    ),
                    error = "Embedding generation failed for all chunks"
                )
            
            ingested_at = time.time()
            for chunk in embedded_chunks:
                chunk.metadata["ingested_at"] = ingested_at
            
            stored_count = self.vector_store._add_chunks(embedded_chunks)

            logger.info(
                "chunks_stored_in_chromadb",
                filename = filename,
                stored = stored_count
            )

            self.bm25.add_chunks(embedded_chunks)

            logger.info(
                "chunks_added_to_bm25",
                filename = filename,
                count = len(embedded_chunks)
            )

            latency = round((time.time() - start_time) * 1000, 2)

            logger.info(
                "file_ingestion_complete",
                filename = filename,
                document_id = document_id,
                pages = loaded_doc.total_pages,
                chunks = len(embedded_chunks),
                latency_ms = latency
            )

            return FileIngestionResult(
                filename = filename,
                document_id = document_id,
                success = True,
                pages = loaded_doc.total_pages,
                chunks = len(embedded_chunks),
                latency_ms = latency,
                skipped = False
            )
        
        except Exception as e:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(
                "file_ingestion_failed",
                filename = filename,
                error = str(e),
                latency_ms = latency
            )
            return FileIngestionResult(
                filename = filename,
                document_id = "",
                success = False,
                pages = 0,
                chunks = 0,
                latency_ms = latency,
                error = str(e)
            )
        
    def ingest_file(
        self,
        file_path: str,
        force_reingest: bool = False
    ) -> IngestionResult:
        start_time = time.time()

        result = self._ingest_single_file(file_path, force_reingest)

        return IngestionResult(
            total_files = 1,
            successful_files = 1 if result.success else 0,
            failed_files = 0 if result.success else 1,
            skipped_files = 1 if result.skipped else 0,
            total_chunks = result.chunks,
            total_pages = result.pages,
            total_latency_ms = round((time.time() - start_time) * 1000, 2),
            file_results = [{
                "filename": result.filename,
                "document_id": result.document_id,
                "success": result.success,
                "skipped": result.skipped,
                "pages": result.pages,
                "chunks": result.chunks,
                "latency_ms": result.latency_ms,
                "error": result.error
            }],
            errors = [{
                "filename": result.filename,
                "error": result.error
            }] if not result.success else []
        )
    
    def ingest_directory(
        self,
        dir_path: str,
        force_reingest: bool = False
    ) -> IngestionResult:
        start_time = time.time()
        directory = Path(dir_path)

        if not directory.exists():
            raise FileNotFoundError(
                f"Directory not found: {dir_path}"
            )

        supported_extensions = {".pdf", ".txt", ".docx"}
        files = [
            f for f in directory.iterdir()
            if f.suffix.lower() in supported_extensions
            and f.is_file()
        ]

        if not files:
            logger.warning(
                "no_supported_files_found",
                dir_path = dir_path,
                supported = list(supported_extensions)
            )
            return IngestionResult(
                total_files = 0,
                successful_files = 0,
                failed_files = 0,
                skipped_files = 0,
                total_chunks = 0,
                total_pages = 0,
                total_latency_ms = 0,
            )

        logger.info(
            "directory_ingestion_started",
            dir_path = dir_path,
            total_files = len(files),
            force_reingest = force_reingest
        )

        file_results = []
        errors = []
        total_chunks = 0
        total_pages = 0
        success_count = 0
        failed_count = 0
        skipped_count = 0

        for i, file_path in enumerate(files, start = 1):
            logger.info(
                "processing_file",
                file = file_path.name,
                progress = f"{i}/{len(files)}"
            )

            result = self._ingest_single_file(
                str(file_path),
                force_reingest
            )

            file_results.append({
                "filename": result.filename,
                "document_id": result.document_id,
                "success": result.success,
                "skipped": result.skipped,
                "pages": result.pages,
                "chunks": result.chunks,
                "latency_ms": result.latency_ms,
                "error": result.error
            })

            if result.success:
                success_count += 1
                total_chunks += result.chunks
                total_pages += result.pages
                if result.skipped:
                    skipped_count += 1
            else:
                failed_count += 1
                errors.append({
                    "filename": result.filename,
                    "error": result.error
                })

        total_latency = round(
            (time.time() - start_time) * 1000, 2
        )

        logger.info(
            "directory_ingestion_complete",
            total_files = len(files),
            successful = success_count,
            failed = failed_count,
            skipped = skipped_count,
            total_chunks = total_chunks,
            total_pages = total_pages,
            total_latency_ms = total_latency
        )

        return IngestionResult(
            total_files = len(files),
            successful_files = success_count,
            failed_files = failed_count,
            skipped_files = skipped_count,
            total_chunks = total_chunks,
            total_pages = total_pages,
            total_latency_ms = total_latency,
            file_results = file_results,
            errors = errors
        )
