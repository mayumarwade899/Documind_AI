import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from ingestion.pipeline import IngestionPipeline
from api.dependencies import get_ingestion_pipeline
from config.settings import get_settings, get_session_storage_manager
from config.logging_config import get_logger

router = APIRouter(prefix="/ingest", tags=["Ingestion"])
logger = get_logger(__name__)
settings = get_settings()

class DirectoryIngestRequest(BaseModel):
    session_id: str
    dir_path: str = "data/documents"
    force_reingest: bool = False

class IngestResponse(BaseModel):
    success: bool
    total_files: int
    successful_files: int
    failed_files: int
    skipped_files: int
    total_chunks: int
    total_pages: int
    total_latency_ms: float
    file_results: list
    errors: list

@router.post("/file", response_model = IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    force_reingest: bool = False,
    session_id: str = None
):
    """
    Ingest a single file into the session-scoped retrieval system.
    Generates session_id if not provided.
    """
    # Use provided session_id or generate a new one
    session_id = session_id or str(uuid.uuid4())
    
    allowed = {".pdf", ".txt", ".docx"}
    suffix  = Path(file.filename).suffix.lower()

    if suffix not in allowed:
        raise HTTPException(
            status_code = 400,
            detail = f"File type '{suffix}' not supported. Allowed files: {allowed}"
        )
    
    # Get session-scoped storage directory
    storage_manager = get_session_storage_manager()
    upload_dir = storage_manager.get_documents_dir(session_id)
    save_path = upload_dir / file.filename
    
    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(
            "file_uploaded",
            session_id=session_id,
            filename = file.filename,
            path = str(save_path)
        )
    except Exception as e:
        raise HTTPException(
            status_code = 500,
            detail = f"Failed to save file: {str(e)}"
        )
    
    try:
        pipeline = get_ingestion_pipeline(session_id)
        result = pipeline.ingest_file(
            str(save_path),
            force_reingest = force_reingest
        )
    except Exception as e:
        logger.error(
            "ingest_file_failed",
            session_id=session_id,
            error = str(e)
        )
        raise HTTPException(
            status_code = 500,
            detail = f"Ingestion failed: {str(e)}"
        )
    
    return IngestResponse(
        success = result.successful_files > 0,
        total_files = result.total_files,
        successful_files = result.successful_files,
        failed_files = result.failed_files,
        skipped_files = result.skipped_files,
        total_chunks = result.total_chunks,
        total_pages = result.total_pages,
        total_latency_ms = result.total_latency_ms,
        file_results = result.file_results,
        errors= result.errors
    )

@router.post("/directory", response_model = IngestResponse)
async def ingest_directory(request: DirectoryIngestRequest):
    """Ingest all documents from a directory (requires session_id)."""
    try:
        pipeline = get_ingestion_pipeline(request.session_id)
        result = pipeline.ingest_directory(
            request.dir_path,
            force_reingest = request.force_reingest
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code = 404, detail = str(e))
    except Exception as e:
        logger.error(
            "ingest_directory_failed",
            session_id=request.session_id,
            error=str(e)
        )
        raise HTTPException(status_code = 500, detail = str(e))
    
    return IngestResponse(
        success = result.failed_files == 0,
        total_files = result.total_files,
        successful_files = result.successful_files,
        failed_files = result.failed_files,
        skipped_files = result.skipped_files,
        total_chunks = result.total_chunks,
        total_pages = result.total_pages,
        total_latency_ms = result.total_latency_ms,
        file_results = result.file_results,
        errors = result.errors
    )

@router.get("/status/{session_id}")
async def ingest_status(session_id: str):
    """Get ingestion status for a session."""
    try:
        pipeline = get_ingestion_pipeline(session_id)
        stats = pipeline.vector_store.get_collection_stats()
        bm25  = pipeline.bm25.get_stats()
        return {
            "session_id": session_id,
            "vector_store": stats,
            "bm25_index":   bm25
        }
    except Exception as e:
        logger.error(
            "ingest_status_failed",
            session_id=session_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents/{session_id}")
async def get_ingested_documents(session_id: str):
    """Get list of ingested documents for a session."""
    try:
        pipeline = get_ingestion_pipeline(session_id)
        documents = pipeline.vector_store.list_documents()
        return {
            "session_id": session_id,
            "documents": documents
        }
    except Exception as e:
        logger.error(
            "get_ingested_documents_failed",
            session_id=session_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/documents/{session_id}/{document_id}")
async def delete_document(session_id: str, document_id: str):
    """Delete a document from a session's retrieval system."""
    try:
        pipeline = get_ingestion_pipeline(session_id)
        deleted = pipeline.vector_store.delete_document(document_id)
        if deleted == 0:
            raise HTTPException(status_code=404, detail="Document not found")

        try:
            bm25_removed = pipeline.bm25.delete_document(document_id)
            logger.info(
                "bm25_delete_synced",
                session_id=session_id,
                document_id=document_id,
                chunks_removed=bm25_removed
            )
        except Exception as e:
            logger.warning(
                "bm25_delete_after_vector_delete_failed",
                session_id=session_id,
                error=str(e)
            )

        return {
            "success": True,
            "session_id": session_id,
            "document_id": document_id,
            "chunks_deleted": deleted
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "delete_document_failed",
            session_id=session_id,
            document_id=document_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))