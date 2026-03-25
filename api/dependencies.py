from functools import lru_cache
from ingestion.pipeline import IngestionPipeline
from generation.answer_generator import AnswerGenerator
from verification.answer_verifier import AnswerVerifier
from monitoring.metrics_tracker import MetricsTracker
from monitoring.feedback_store import FeedbackStore
from config.logging_config import get_logger

logger = get_logger(__name__)

@lru_cache(maxsize = 1)
def get_ingestion_pipeline() -> IngestionPipeline:
    logger.info("creating_ingestion_pipeline_singleton")
    return IngestionPipeline()

@lru_cache(maxsize = 1)
def get_answer_generator() -> AnswerGenerator:
    logger.info("creating_answer_generator_singleton")
    return AnswerGenerator()


@lru_cache(maxsize = 1)
def get_answer_verifier() -> AnswerVerifier:
    logger.info("creating_answer_verifier_singleton")
    return AnswerVerifier()


@lru_cache(maxsize = 1)
def get_metrics_tracker() -> MetricsTracker:
    logger.info("creating_metrics_tracker_singleton")
    return MetricsTracker()


@lru_cache(maxsize = 1)
def get_feedback_store() -> FeedbackStore:
    logger.info("creating_feedback_store_singleton")
    return FeedbackStore()