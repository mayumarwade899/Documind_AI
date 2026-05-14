from functools import lru_cache
from typing import Dict, Any
from config.logging_config import get_logger

logger = get_logger(__name__)

# Session-scoped service caches: {session_id: {service_name: instance}}
_SESSION_SERVICES: Dict[str, Dict[str, Any]] = {}

def get_session_services(session_id: str) -> Dict[str, Any]:
    """
    Get or create the service cache for a specific session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Dictionary of cached services for this session
    """
    if session_id not in _SESSION_SERVICES:
        _SESSION_SERVICES[session_id] = {}
    return _SESSION_SERVICES[session_id]

def clear_session_services(session_id: str) -> None:
    """
    Clear all cached services for a session (cleanup on session end).
    
    Args:
        session_id: Session identifier
    """
    if session_id in _SESSION_SERVICES:
        del _SESSION_SERVICES[session_id]
        logger.debug(
            "session_services_cleared",
            session_id=session_id
        )

def get_ingestion_pipeline(session_id: str):
    """
    Get or create session-scoped ingestion pipeline.
    
    Args:
        session_id: Session identifier
        
    Returns:
        IngestionPipeline instance for this session
    """
    if not session_id:
        raise ValueError("session_id is required for get_ingestion_pipeline")
    
    services = get_session_services(session_id)
    
    if "ingestion_pipeline" not in services:
        from ingestion.pipeline import IngestionPipeline
        logger.debug(
            "creating_ingestion_pipeline",
            session_id=session_id
        )
        services["ingestion_pipeline"] = IngestionPipeline(session_id)
    
    return services["ingestion_pipeline"]

def get_answer_generator(session_id: str):
    """
    Get or create session-scoped answer generator.
    
    Args:
        session_id: Session identifier
        
    Returns:
        AnswerGenerator instance for this session
    """
    if not session_id:
        raise ValueError("session_id is required for get_answer_generator")
    
    services = get_session_services(session_id)
    
    if "answer_generator" not in services:
        from generation.answer_generator import AnswerGenerator
        logger.debug(
            "creating_answer_generator",
            session_id=session_id
        )
        services["answer_generator"] = AnswerGenerator(session_id)
    
    return services["answer_generator"]

def get_answer_verifier(session_id: str):
    """
    Get or create session-scoped answer verifier.
    
    Args:
        session_id: Session identifier
        
    Returns:
        AnswerVerifier instance for this session
    """
    if not session_id:
        raise ValueError("session_id is required for get_answer_verifier")
    
    services = get_session_services(session_id)
    
    if "answer_verifier" not in services:
        from verification.answer_verifier import AnswerVerifier
        logger.debug(
            "creating_answer_verifier",
            session_id=session_id
        )
        services["answer_verifier"] = AnswerVerifier()
    
    return services["answer_verifier"]

def get_metrics_tracker(session_id: str):
    """
    Get or create session-scoped metrics tracker.
    
    Args:
        session_id: Session identifier
        
    Returns:
        MetricsTracker instance for this session
    """
    if not session_id:
        raise ValueError("session_id is required for get_metrics_tracker")
    
    services = get_session_services(session_id)
    
    if "metrics_tracker" not in services:
        from monitoring.metrics_tracker import MetricsTracker
        logger.debug(
            "creating_metrics_tracker",
            session_id=session_id
        )
        services["metrics_tracker"] = MetricsTracker(session_id)
    
    return services["metrics_tracker"]

def get_feedback_store(session_id: str):
    """
    Get or create session-scoped feedback store.
    
    Args:
        session_id: Session identifier
        
    Returns:
        FeedbackStore instance for this session
    """
    if not session_id:
        raise ValueError("session_id is required for get_feedback_store")
    
    services = get_session_services(session_id)
    
    if "feedback_store" not in services:
        from monitoring.feedback_store import FeedbackStore
        logger.debug(
            "creating_feedback_store",
            session_id=session_id
        )
        services["feedback_store"] = FeedbackStore(session_id)
    
    return services["feedback_store"]

def get_session_manager():
    """
    Get or create global session manager (not session-scoped).
    
    Returns:
        SessionManager singleton
    """
    # Session manager itself is global, not per-session
    if "session_manager" not in _SESSION_SERVICES.get("_global", {}):
        if "_global" not in _SESSION_SERVICES:
            _SESSION_SERVICES["_global"] = {}
        
        from monitoring.session_manager import SessionManager
        logger.debug("creating_session_manager_singleton")
        _SESSION_SERVICES["_global"]["session_manager"] = SessionManager()
    
    return _SESSION_SERVICES["_global"]["session_manager"]