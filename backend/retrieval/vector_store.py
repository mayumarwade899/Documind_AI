from dataclasses import dataclass, field
from typing import List, Optional

import chromadb
from chromadb.config import Settings as ChromaInternalSettings

from ingestion.embedder import EmbeddedChunk
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class RetrievedChunk:
    chunk_id: str
    content: str
    source_file: str
    page_number: int 
    document_id: str 
    score: float 
    retrieval_method: str 
    metadata: dict = field(default_factory=dict)

class VectorStore:
    def __init__(self):
        self.persist_path = settings.chroma_persist_path
        self.persist_path.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            if self._client is None:
                self._client = chromadb.PersistentClient(
                    path = str(self.persist_path),
                    settings = ChromaInternalSettings(
                        anonymized_telemetry = False
                    )
                )
            
            self._collection = self._client.get_or_create_collection(
                name = settings.chroma.chroma_collection_name,
                metadata = {
                    "hnsw:space": "cosine"
                }
            )

            logger.debug(
                "vector_store_lazy_initialized",
                persist_path = str(self.persist_path),
                collection = settings.chroma.chroma_collection_name,
                existing_chunks = self._collection.count()
            )
        
        return self._collection

    def _add_chunks(self, chunks: List[EmbeddedChunk]) -> int:
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

            self._get_collection().upsert(
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
            total_in_collection = self._get_collection().count()
        )

        return stored

    def search(
        self,
        query_vector: List[float],
        top_k: int = None,
        filter_document_id: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        if not query_vector:
            raise ValueError("query_vector cannot be empty")
        
        k = top_k or settings.retrieval.vector_search_top_k

        where_filter = None
        if filter_document_id:
            where_filter = {"document_id": {"$eq": filter_document_id}}

        try:
            results = self._get_collection().query(
                query_embeddings = [query_vector],
                n_results = min(k, self._get_collection().count()),
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

        logger.debug(
            "vector_search_complete",
            top_k=k,
            results_found=len(retrieved),
            top_score=retrieved[0].score if retrieved else 0
        )

        return retrieved
    
    def delete_document(self, document_id: str) -> int:
        try:
            existing = self._get_collection().get(
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

            self._get_collection().delete(
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
        try:
            results = self._get_collection().get(
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
        
    def list_documents(self) -> list:
        try:
            all_data = self._get_collection().get(include=["metadatas"])
            doc_map = {}

            for meta in all_data["metadatas"]:
                doc_id = meta.get("document_id", "")
                if doc_id and doc_id not in doc_map:
                    doc_map[doc_id] = {
                        "document_id": doc_id,
                        "source_file": meta.get("source_file", ""),
                        "chunk_count": 0,
                    }
                if doc_id:
                    doc_map[doc_id]["chunk_count"] += 1

            documents = sorted(doc_map.values(), key=lambda d: d["source_file"])

            logger.debug("list_documents", total=len(documents))
            return documents

        except Exception as e:
            logger.error("list_documents_failed", error=str(e))
            return []

    def get_collection_stats(self) -> dict:
        count = self._get_collection().count()
        logger.debug("collection_stats", total_chunks = count)
        return {
            "collection_name": settings.chroma.chroma_collection_name,
            "total_chunks": count,
            "persist_path": str(settings.chroma_persist_path)
        }

    def get_random_chunks(self, limit: int = 1) -> List[RetrievedChunk]:
        """Fetch a random sample of chunks from the entire collection."""
        total = self._get_collection().count()
        if total == 0:
            return []
        
        import random
        all_ids = self._get_collection().get(include=[])["ids"]
        sampled_ids = random.sample(all_ids, min(limit, total))
        
        results = self._get_collection().get(
            ids=sampled_ids,
            include=["documents", "metadatas"]
        )
        
        retrieved = []
        for chunk_id, content, meta in zip(results["ids"], results["documents"], results["metadatas"]):
            retrieved.append(RetrievedChunk(
                chunk_id=chunk_id,
                content=content,
                source_file=meta.get("source_file", ""),
                page_number=int(meta.get("page_number", 0)),
                document_id=meta.get("document_id", ""),
                score=1.0, 
                retrieval_method="sample_random",
                metadata=meta
            ))
        return retrieved

    def get_recent_chunks(self, limit: int = 5) -> List[RetrievedChunk]:
        """Fetch chunks from the most recently ingested documents."""
        total = self._get_collection().count()
        if total == 0:
            return []

        results = self._get_collection().get(
            include=["documents", "metadatas"]
        )
        
        chunks = []
        for chunk_id, content, meta in zip(results["ids"], results["documents"], results["metadatas"]):
            chunks.append({
                "chunk_id": chunk_id,
                "content": content,
                "meta": meta,
                "timestamp": float(meta.get("ingested_at", 0))
            })
        
        sorted_chunks = sorted(chunks, key=lambda x: x["timestamp"], reverse=True)
        recent = sorted_chunks[:limit]
        
        retrieved = []
        for r in recent:
            retrieved.append(RetrievedChunk(
                chunk_id=r["chunk_id"],
                content=r["content"],
                source_file=r["meta"].get("source_file", ""),
                page_number=int(r["meta"].get("page_number", 0)),
                document_id=r["meta"].get("document_id", ""),
                score=1.0,
                retrieval_method="sample_recent",
                metadata=r["meta"]
            ))
        return retrieved
    