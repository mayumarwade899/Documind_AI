import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ingestion.pipeline import IngestionPipeline
from api.dependencies import get_ingestion_pipeline
from config.settings import get_settings
from config.logging_config import get_logger

router = APIRouter(prefix="/ingest", tags=["Ingestion"])
logger = get_logger(__name__)
settings = get_settings()

UPLOAD_DIR = Path("data/documents")
UPLOAD_DIR.mkdir(parents = True, exist_ok = True)

class DirectoryIngestRequest(BaseModel):
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
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline)
):
    allowed = {".pdf", ".txt", ".docx"}
    suffix  = Path(file.filename).suffix.lower()

    if suffix not in allowed:
        raise HTTPException(
            status_code = 400,
            detail = f"File type '{suffix}' not supported. Allowed files: {allowed}"
        )
    
    save_path = UPLOAD_DIR / file.filename
    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(
            "file_uploaded",
            filename = file.filename,
            path = str(save_path)
        )
    except Exception as e:
        raise HTTPException(
            status_code = 500,
            detail = f"Failed to save file: {str(e)}"
        )
    
    try:
        result = pipeline.ingest_file(
            str(save_path),
            force_reingest = force_reingest
        )
    except Exception as e:
        logger.error("ingest_file_failed", error = str(e))
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
async def ingest_directory(
    request:  DirectoryIngestRequest,
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline)
):
    try:
        result = pipeline.ingest_directory(
            request.dir_path,
            force_reingest = request.force_reingest
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code = 404, detail = str(e))
    except Exception as e:
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

@router.get("/status")
async def ingest_status(
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline)
):
    stats = pipeline.vector_store.get_collection_stats()
    bm25  = pipeline.bm25.get_stats()
    return {
        "vector_store": stats,
        "bm25_index":   bm25
    }

@router.get("/documents")
async def get_ingested_documents(
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline)
):
    try:
        documents = pipeline.vector_store.list_documents()
        return {"documents": documents}
    except Exception as e:
        logger.error("get_ingested_documents_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))