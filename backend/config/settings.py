import os
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from pathlib import Path

os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY_ENABLED"] = "False"
os.environ["TELEMETRY_ENABLED"] = "False"

ROOT_DIR = Path(__file__).parent.parent

class GeminiSettings(BaseSettings):
    gemini_api_key: str = Field(..., env = "GEMINI_API_KEY")
    gemini_model: str = Field(default = "gemini-1.5-flash", env = "GEMINI_MODEL")
    gemini_embedding_model: str = Field(
        default = "models/embedding-001", 
        env = "GEMINI_EMBEDDING_MODEL"
    )
    gemini_temperature: float = Field(default = 0.1, env = "GEMINI_TEMPERATURE")
    gemini_max_tokens: int = Field(default = 2500, env = "GEMINI_MAX_TOKENS")

    class Config:
        env_file = ".env"
        extra = "ignore"

class ChromaSettings(BaseSettings):
    chroma_persist_directory: str = Field(
        default = "data/chroma_db", 
        env = "CHROMA_PERSIST_DIR"
    )

    chroma_collection_name: str = Field(
        default = "rag_documents",
        env = "CHROMA_COLLECTION_NAME"
    )

    class Config:
        env_file = ".env"
        extra = "ignore"

class BM25Settings(BaseSettings):
    bm25_index_dir: str = Field(
        default = "data/bm25_index", 
        env = "BM25_INDEX_DIR"
    )

    class Config:
        env_file = ".env"
        extra = "ignore"

class ChunkingSettings(BaseSettings):
    chunk_size: int = Field(default = 500, env = "CHUNK_SIZE")
    chunk_overlap: int = Field(default = 50, env = "CHUNK_OVERLAP")

    class Config:
        env_file = ".env"
        extra = "ignore"

class RetrievalSettings(BaseSettings):

    vector_search_top_k: int = Field(default = 7, env = "VECTOR_SEARCH_TOP_K")
    bm25_search_top_k: int = Field(default = 7, env = "BM25_SEARCH_TOP_K")
    final_top_k: int = Field(default = 6, env = "FINAL_TOP_K")
    summary_final_top_k: int = Field(default = 8, env = "SUMMARY_FINAL_TOP_K")
    
    multi_query_count: int = Field(default = 2, env = "MULTI_QUERY_COUNT")
    
    max_context_tokens: int = Field(default = 2500, env = "MAX_CONTEXT_TOKENS")
    summary_context_tokens: int = Field(default = 4000, env = "SUMMARY_CONTEXT_TOKENS")
    
    rerank_threshold: float = Field(default = 0.1, env = "RERANK_THRESHOLD")
    bm25_weight: float = Field(default = 0.6, env = "BM25_WEIGHT")
    vector_weight: float = Field(default = 0.4, env = "VECTOR_WEIGHT")

    class Config:
        env_file = ".env"
        extra = "ignore"

class RerankerSettings(BaseSettings):
    reranker_model: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        env = "RERANKER_MODEL"
    )

    class Config:
        env_file = ".env"
        extra = "ignore"

class EvaluationSettings(BaseSettings):
    golden_dataset_path: str = Field(
        default = "data/golden_dataset/golden_qa.json", 
        env = "GOLDEN_DATASET_PATH"
    )

    min_faithfulness_score: float = Field(
        default = 0.7, 
        env = "MIN_FAITHFULNESS_SCORE"
    )

    min_context_relevance_score: float = Field(
        default = 0.7, 
        env = "MIN_CONTEXT_RELEVANCE_SCORE"
    )

    min_answer_correctness_score: float = Field(
        default = 0.6, 
        env = "MIN_ANSWER_CORRECTNESS_SCORE"
    )

    class Config:
        env_file = ".env"
        extra = "ignore"

class MonitoringSettings(BaseSettings):
    metrics_log_dir: str = Field(
        default = "data/metrics", 
        env = "METRICS_LOG_DIR"
    )

    feedback_log_dir: str = Field(
        default = "data/feedback",
        env = "FEEDBACK_LOG_DIR"
    )

    session_log_dir: str = Field(
        default = "data/sessions",
        env = "SESSION_LOG_DIR"
    )

    class Config:
        env_file = ".env"
        extra = "ignore" 

class APISettings(BaseSettings):
    api_host: str = Field(default = "0.0.0.0", env = "API_HOST")
    api_port: int = Field(default = 8000, env = "API_PORT")
    api_reload: bool = Field(default = True, env = "API_RELOAD")
    log_level: str = Field(default = "INFO", env = "LOG_LEVEL")

    class Config:
        env_file = ".env"
        extra = "ignore" 

class Settings(BaseSettings):

    gemini: GeminiSettings = Field(default_factory = GeminiSettings)
    chroma: ChromaSettings = Field(default_factory = ChromaSettings)
    bm25: BM25Settings = Field(default_factory = BM25Settings)
    chunking: ChunkingSettings = Field(default_factory = ChunkingSettings)
    retrieval: RetrievalSettings = Field(default_factory = RetrievalSettings)
    reranker: RerankerSettings = Field(default_factory = RerankerSettings)
    evaluation: EvaluationSettings = Field(default_factory = EvaluationSettings)
    monitoring: MonitoringSettings = Field(default_factory = MonitoringSettings)
    api: APISettings = Field(default_factory = APISettings)

    enable_query_cache: bool = Field(default = True, env = "ENABLE_QUERY_CACHE")
    cache_ttl_seconds: int = Field(default = 3600, env = "CACHE_TTL_SECONDS")

    @property
    def chroma_persist_path(self) -> Path:
        return ROOT_DIR / self.chroma.chroma_persist_directory
    
    @property
    def bm25_index_path(self) -> Path:
        return ROOT_DIR / self.bm25.bm25_index_dir
    
    @property
    def metrics_log_path(self) -> Path:
        return ROOT_DIR / self.monitoring.metrics_log_dir
    
    @property
    def feedback_log_path(self) -> Path:
        return ROOT_DIR / self.monitoring.feedback_log_dir
    
    @property
    def session_log_path(self) -> Path:
        return ROOT_DIR / self.monitoring.session_log_dir
    
    @property
    def golden_dataset_path(self) -> Path:
        return ROOT_DIR / self.evaluation.golden_dataset_path
    
    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache(maxsize =1 )
def get_settings() -> Settings:
    return Settings()