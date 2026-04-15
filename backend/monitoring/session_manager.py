import json
import os
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

class SessionManager:
    def __init__(self):
        self.log_dir = settings.session_log_path
        self._ensure_log_dir()
        logger.debug("session_manager_initialized", log_dir=str(self.log_dir))

    def _ensure_log_dir(self):
        if not self.log_dir.exists():
            self.log_dir.mkdir(parents=True, exist_ok=True)
            logger.debug("session_log_dir_created", dir=str(self.log_dir))

    def _get_session_path(self, session_id: str) -> Path:
        return self.log_dir / f"{session_id}.json"

    def save_interaction(
        self, 
        session_id: str, 
        interaction: Dict[str, Any]
    ):
        """Save a new interaction (Q&A with full trace) to session history."""
        if not session_id:
            logger.warning("save_interaction_skipped_no_session_id")
            return

        session_path = self._get_session_path(session_id)
        
        interaction["timestamp"] = datetime.utcnow().isoformat() + "Z"

        try:
            history = self.get_history(session_id)
            history.append(interaction)

            with open(session_path, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            
            logger.debug(
                "interaction_saved_to_session",
                session_id=session_id,
                total_messages=len(history)
            )
        except Exception as e:
            logger.error(
                "failed_to_save_session_interaction",
                session_id=session_id,
                error=str(e)
            )

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve full history for a given session."""
        if not session_id:
            return []

        session_path = self._get_session_path(session_id)
        if not session_path.exists():
            return []

        try:
            with open(session_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(
                "failed_to_read_session_history",
                session_id=session_id,
                error=str(e)
            )
            return []

    def clear_session(self, session_id: str) -> bool:
        """Clear (delete) the session history file."""
        if not session_id:
            return False

        session_path = self._get_session_path(session_id)
        if session_path.exists():
            try:
                os.remove(session_path)
                logger.debug("session_history_cleared", session_id=session_id)
                return True
            except Exception as e:
                logger.error(
                    "failed_to_clear_session",
                    session_id=session_id,
                    error=str(e)
                )
        return False
