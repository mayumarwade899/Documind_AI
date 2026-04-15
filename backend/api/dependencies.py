from functools import lru_cache
from config.logging_config import get_logger

logger = get_logger(__name__)

@lru_cache(maxsize = 1)
def get_ingestion_pipeline():
    from ingestion.pipeline import IngestionPipeline
    logger.debug("creating_ingestion_pipeline_singleton")
    return IngestionPipeline()

@lru_cache(maxsize = 1)
def get_answer_generator():
    from generation.answer_generator import AnswerGenerator
    logger.debug("creating_answer_generator_singleton")
    return AnswerGenerator()


@lru_cache(maxsize = 1)
def get_answer_verifier():
    from verification.answer_verifier import AnswerVerifier
    logger.debug("creating_answer_verifier_singleton")
    return AnswerVerifier()


@lru_cache(maxsize = 1)
def get_metrics_tracker():
    from monitoring.metrics_tracker import MetricsTracker
    logger.debug("creating_metrics_tracker_singleton")
    return MetricsTracker()


@lru_cache(maxsize = 1)
def get_feedback_store():
    from monitoring.feedback_store import FeedbackStore
    logger.debug("creating_feedback_store_singleton")
    return FeedbackStore()


@lru_cache(maxsize = 1)
def get_session_manager():
    from monitoring.session_manager import SessionManager
    logger.debug("creating_session_manager_singleton")
    return SessionManager()