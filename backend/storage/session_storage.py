"""
Session-scoped storage manager.
Provides isolation of all data per session_id.
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SessionPaths:
    """All storage paths for a specific session."""
    session_id: str
    root: Path
    documents: Path
    chroma_db: Path
    bm25_index: Path
    evaluations: Path
    metrics: Path
    feedback: Path
    history: Path

    def __post_init__(self):
        """Create all directories if they don't exist."""
        for path in [self.documents, self.chroma_db, self.bm25_index, 
                     self.evaluations, self.metrics, self.feedback]:
            path.mkdir(parents=True, exist_ok=True)


class SessionStorageManager:
    """Manages session-scoped storage paths and directory creation."""
    
    def __init__(self, base_sessions_dir: Path):
        """
        Initialize storage manager.
        
        Args:
            base_sessions_dir: Root directory for all sessions (typically data/sessions/)
        """
        self.base_sessions_dir = Path(base_sessions_dir)
        self.base_sessions_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("session_storage_manager_initialized", base_dir=str(self.base_sessions_dir))

    def get_session_paths(self, session_id: str) -> SessionPaths:
        """Get or create all paths for a session."""
        if not session_id:
            raise ValueError("session_id cannot be empty")
        
        session_root = self.base_sessions_dir / session_id
        
        paths = SessionPaths(
            session_id=session_id,
            root=session_root,
            documents=session_root / "documents",
            chroma_db=session_root / "chroma_db",
            bm25_index=session_root / "bm25_index",
            evaluations=session_root / "evaluations",
            metrics=session_root / "metrics",
            feedback=session_root / "feedback",
            history=session_root / "history.json"
        )
        
        logger.debug("session_paths_created", session_id=session_id, root=str(session_root))
        return paths

    def get_documents_dir(self, session_id: str) -> Path:
        """Get documents directory for a session."""
        return self.get_session_paths(session_id).documents

    def get_chroma_db_dir(self, session_id: str) -> Path:
        """Get ChromaDB directory for a session."""
        return self.get_session_paths(session_id).chroma_db

    def get_bm25_dir(self, session_id: str) -> Path:
        """Get BM25 index directory for a session."""
        return self.get_session_paths(session_id).bm25_index

    def get_metrics_dir(self, session_id: str) -> Path:
        """Get metrics directory for a session."""
        return self.get_session_paths(session_id).metrics

    def get_feedback_dir(self, session_id: str) -> Path:
        """Get feedback directory for a session."""
        return self.get_session_paths(session_id).feedback

    def get_evaluations_dir(self, session_id: str) -> Path:
        """Get evaluations directory for a session."""
        return self.get_session_paths(session_id).evaluations

    def get_history_file(self, session_id: str) -> Path:
        """Get history file for a session."""
        return self.get_session_paths(session_id).history

    def session_exists(self, session_id: str) -> bool:
        """Check if a session directory exists."""
        return (self.base_sessions_dir / session_id).exists()

    def clear_session(self, session_id: str) -> bool:
        """Delete all data for a session."""
        session_root = self.base_sessions_dir / session_id
        if session_root.exists():
            try:
                import shutil
                shutil.rmtree(session_root)
                logger.debug("session_cleared", session_id=session_id)
                return True
            except Exception as e:
                logger.error("failed_to_clear_session", session_id=session_id, error=str(e))
                return False
        return True

    def list_sessions(self) -> list[str]:
        """List all session IDs."""
        try:
            return [d.name for d in self.base_sessions_dir.iterdir() if d.is_dir()]
        except Exception as e:
            logger.error("failed_to_list_sessions", error=str(e))
            return []
