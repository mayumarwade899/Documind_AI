from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import query, ingest, feedback, metrics, evaluation
from api.dependencies import (
    get_answer_generator,
    get_ingestion_pipeline,
    get_metrics_tracker,
    get_feedback_store
)
from config.settings import get_settings
from config.logging_config import setup_logging, get_logger

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(log_level = settings.api.log_level)
    logger =get_logger(__name__)
    logger.info("rag_system_starting_up")

    try:
        get_ingestion_pipeline()
        logger.info("ingestion_pipeline_ready")
    except Exception as e:
        logger.warning("ingestion_pipeline_warmup_failed", error=str(e))

    try:
        get_answer_generator()
        logger.info("answer_generator_ready")
    except Exception as e:
        logger.warning("answer_generator_warmup_failed", error = str(e))

    try:
        get_metrics_tracker()
        get_feedback_store()
        logger.info("monitoring_ready")
    except Exception as e:
        logger.warning("monitoring_warmup_failed", error = str(e))

    logger.info(
        "rag_system_ready",
        host = settings.api.api_host,
        port = settings.api.api_port
    )

    yield

    logger.info("rag_system_shutting_down")

app = FastAPI(
    title = "Production RAG System",
    description = "Retrieval Augmented Generation API with hybrid search, reranking, and citation enforcement",
    version = "1.0.0",
    lifespan = lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(query.router)
app.include_router(ingest.router)
app.include_router(feedback.router)
app.include_router(metrics.router)
app.include_router(evaluation.router)

@app.get("/health", tags = ["System"])
async def health():
    return {
        "status":  "healthy",
        "version": "1.0.0",
        "model":   settings.gemini.gemini_model
    }

@app.get("/", tags = ["System"])
async def root():
    return {
        "message": "Production RAG System",
        "docs": "/docs",
        "health": "/health"
    }