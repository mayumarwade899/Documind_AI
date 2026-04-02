from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaInternalSettings

from ingestion.embedder import EmbeddedChunk
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class RetrievedChunk:
    """
    A chunk returned by any retrieval method
    (vector search, BM25, or hybrid).
    """
    chunk_id: str
    content: str
    source_file: str
    page_number: int 
    document_id: str 
    score: float 
    retrieval_method: str 
    metadata: dict = field(default_factory=dict)

class VectorStore:
    """
    Manages all ChromaDB operations like storing, retrieving, and deleting.
    """
    def __init__(self):
        """
        Initialize ChromaDB with persistent storage on disk.
        Data survives across restarts — stored in data/chroma_db/
        """
        persist_path = settings.chroma_persist_path
        persist_path.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path = str(persist_path),
            settings = ChromaInternalSettings(
                anonymized_telemetry = False
            )
        )

        self.collection = self.client.get_or_create_collection(
            name = settings.chroma.chroma_collection_name,
            metadata = {
                "hnsw:space": "cosine"
            }
        )

        logger.info(
            "vector_store_initialized",
            persist_path = str(persist_path),
            collection = settings.chroma.chroma_collection_name,
            existing_chunks = self.collection.count()
        )

    def _add_chunks(self, chunks: List[EmbeddedChunk]) -> int:
        """
        Store a list of EmbeddedChunks in ChromaDB.
        """
        if not chunks:
            logger.warning("add_chunks_called_with_empty_list")
            return 0

        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for chunk in chunks:
            ids.append(chunk.chunk_id)
            embeddings.append(chunk.embedding)
            documents.append(chunk.content)
            metadatas.append({
                "document_id": chunk.document_id,
                "source_file":  chunk.source_file,
                "page_number":  chunk.page_number,
                "chunk_index":  chunk.chunk_index,
                "total_chunks": chunk.total_chunks,
                "token_count":  chunk.token_count,
                "embedding_model": chunk.embedding_model,
                **chunk.metadata
            })

        BATCH_SIZE = 100
        stored = 0

        for i in range(0, len(ids), BATCH_SIZE):
            batch_ids = ids[i:i + BATCH_SIZE]
            batch_embeddings = embeddings[i:i + BATCH_SIZE]
            batch_documents = documents[i:i + BATCH_SIZE]
            batch_metadatas = metadatas[i:i + BATCH_SIZE]

            self.collection.upsert(
                ids = batch_ids,
                embeddings = batch_embeddings,
                documents = batch_documents,
                metadatas = batch_metadatas
            )
            stored += len(batch_ids)

            logger.debug(
                "chroma_batch_upserted",
                batch_start = 1,
                batch_size = len(batch_ids)
            )
        
        logger.info(
            "chunks_stored",
            stored = stored,
            total_in_collection = self.collection.count()
        )

        return stored

    def search(
        self,
        query_vector: List[float],
        top_k: int = None,
        filter_document_id: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        """
        Search ChromaDB for chunks similar to the query vector.
        """
        if not query_vector:
            raise ValueError("query_vector cannot be empty")
        
        k = top_k or settings.retrieval.vector_search_top_k

        where_filter = None
        if filter_document_id:
            where_filter = {"document_id": {"$eq": filter_document_id}}

        try:
            results = self.collection.query(
                query_embeddings = [query_vector],
                n_results = min(k, self.collection.count()),
                where = where_filter,
                include = ["documents", "metadatas", "distances"] 
            )
        except Exception as e:
            logger.error("vector_search_failed", error=str(e))
            raise

        retrieved = []

        ids = results["ids"][0]
        documents  = results["documents"][0]
        metadatas  = results["metadatas"][0]
        distances  = results["distances"][0]

        for chunk_id, content, meta, distance in zip(
            ids, documents, metadatas, distances
        ):
            similarity_score = 1 - (distance/2)

            retrieved.append(RetrievedChunk(
                chunk_id=chunk_id,
                content=content,
                source_file=meta.get("source_file", ""),
                page_number=int(meta.get("page_number", 0)),
                document_id=meta.get("document_id", ""),
                score=round(similarity_score, 4),
                retrieval_method="vector",
                metadata=meta
            ))

        logger.info(
            "vector_search_complete",
            top_k=k,
            results_found=len(retrieved),
            top_score=retrieved[0].score if retrieved else 0
        )

        return retrieved
    
    def delete_document(self, document_id: str) -> int:
        """
        Delete all chunks belonging to a document.
        Called when re-ingesting an updated document.
        """
        try:
            existing = self.collection.get(
                where = {"document_id": {"$eq": document_id}},
                include = ["metadatas"]
            )

            chunk_count = len(existing["ids"])

            if chunk_count == 0:
                logger.info(
                    "delete_document_not_found",
                    document_id = document_id
                )
                return 0

            self.collection.delete(
                where = {"document_id": {"$eq": document_id}}
            )

            logger.info(
                "document_deleted",
                document_id=document_id,
                chunks_deleted=chunk_count
            )

            return chunk_count

        except Exception as e:
            logger.error(
                "document_delete_failed",
                document_id=document_id,
                error=str(e)
            )
            raise

    def document_exists(self, document_id: str) -> bool:
        """
        Check if a document is already stored in ChromaDB.
        Used by ingestion pipeline to skip re-processing.
        """
        try:
            results = self.collection.get(
                where = {"document_id": {"$eq": document_id}},
                include = ["metadatas"],
                limit = 1
            )
            exists = len(results["ids"]) > 0

            logger.debug(
                "document_exists_check",
                document_id=document_id,
                exists=exists
            )
            return exists
        
        except Exception as e:
            logger.error(
                "document_exists_check_failed",
                document_id=document_id,
                error=str(e)
            )
            return False
        
    def get_collection_stats(self) -> dict:
        """
        Return basic stats about the collection.
        Used by the metrics API endpoint.
        """
        count = self.collection.count()
        logger.info("collection_stats_failed", total_chunks = count)
        return {
            "collection_name": settings.chroma.chroma_collection_name,
            "total_chunks": count,
            "persist_path": str(settings.chroma_persist_path)
        }
    