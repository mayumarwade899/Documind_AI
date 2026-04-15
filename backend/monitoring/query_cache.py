import json
import hashlib
import time
from pathlib import Path
from typing import Optional
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

class QueryCache:
    def __init__(self, cache_dir: str = "data/query_cache"):
        self.cache_path = Path(cache_dir)
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self.ttl = settings.cache_ttl_seconds
        
        logger.debug(
            "query_cache_initialized",
            cache_dir=cache_dir,
            ttl_sec=self.ttl
        )

    def _get_hash(self, query: str, document_id: Optional[str] = None) -> str:
        key = f"{query.strip().lower()}:{document_id or 'all'}"
        return hashlib.md5(key.encode()).hexdigest()

    def get(self, query: str, document_id: Optional[str] = None) -> Optional[dict]:
        if not settings.enable_query_cache:
            return None

        cache_id = self._get_hash(query, document_id)
        file_path = self.cache_path / f"{cache_id}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            
            if time.time() - data.get("cached_at", 0) > self.ttl:
                logger.debug("cache_expired", query=query[:50])
                file_path.unlink()
                return None

            logger.info("cache_hit", query=query[:50], cache_id=cache_id)
            return data.get("response")
        
        except Exception as e:
            logger.warning("cache_read_failed", error=str(e))
            return None

    def set(self, query: str, response: dict, document_id: Optional[str] = None):
        if not settings.enable_query_cache:
            return

        cache_id = self._get_hash(query, document_id)
        file_path = self.cache_path / f"{cache_id}.json"

        try:
            data = {
                "query": query,
                "document_id": document_id,
                "cached_at": time.time(),
                "response": response
            }
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
            
            logger.debug("cache_stored", query=query[:50], cache_id=cache_id)
        except Exception as e:
            logger.warning("cache_write_failed", error=str(e))

_global_cache = None

def get_query_cache():
    global _global_cache
    if _global_cache is None:
        _global_cache = QueryCache()
    return _global_cache
