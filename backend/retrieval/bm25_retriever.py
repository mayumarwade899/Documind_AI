import os
import json
import pickle
from pathlib import Path
from typing import List, Optional

from rank_bm25 import BM25Okapi
from retrieval.vector_store import RetrievedChunk
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

BM25_INDEX_FILE = "bm25_index.pkl"
BM25_METADATA_FILE = "bm25_metadata.json"

def _tokenize(text: str) -> List[str]:
    """
    Simple whitespace + lowercase tokenizer for BM25.
    """
    text = text.lower()

    for char in ['.', ',', '!', '?', ';', ':', '(', ')', '[', ']', '"', "'"]:
        text = text.replace(char, ' ')

    tokens = [t for t in text.split() if t]
    return tokens

class BM25Retriever:
    """
    BM25 keyword search over document chunks.
    """
    def __init__(self):
        self.index_dir = settings.bm25_index_path
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.index_path = self.index_dir / BM25_INDEX_FILE
        self.metadata_path = self.index_dir / BM25_METADATA_FILE

        self.bm25: Optional[BM25Okapi] = None
        self.chunk_metadata: List[dict] = []
        self.corpus_tokens: List[List[str]] = []

        self._load_index()

        logger.info(
            "bm25_retriever_initialized",
            index_exists=self.bm25 is not None,
            total_chunks=len(self.chunk_metadata)
        )

    def _save_index(self) -> None:
        """
        Save BM25 model and metadata to disk.
        Called after build_index() and add_chunks().
        """
        with open(self.index_path, 'wb') as f:
            pickle.dump({
                "bm25": self.bm25,
                "corpus_tokens": self.corpus_tokens
            }, f)

        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.chunk_metadata, f, indent = 2, ensure_ascii = False)

        logger.info(
            "bm25_index_saved",
            path=str(self.index_dir),
            total_chunks=len(self.chunk_metadata)
        )

    def _load_index(self) -> None:
        """
        Load BM25 index from disk if it exists.
        Called automatically on initialization.
        """
        if not self.index_path.exists() or not self.metadata_path.exists():
            logger.info("bm25_no_existing_index_found")
            return
        
        try:
            with open(self.index_path, "rb") as f:
                data = pickle.load(f)
                self.bm25 = data["bm25"]
                self.corpus_tokens = data["corpus_tokens"]

            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self.chunk_metadata = json.load(f)

            logger.info(
                "bm25_index_loaded",
                total_chunks=len(self.chunk_metadata)
            )
        
        except Exception as e:
            logger.error("bm25_index_load_failed", error=str(e))
            self.bm25 = None
            self.chunk_metadata = []
            self.corpus_tokens  = []

    def build_index(self, chunks: List) -> None:
        """
        Build a fresh BM25 index from a list of chunks.
        Replaces any existing index completely.
        """
        if not chunks:
            logger.warning("build_index_called_with_empty_chunks")
            return
        
        logger.info("bm25_build_index_started", total_chunks=len(chunks))

        self.corpus_tokens  = []
        self.chunk_metadata = []

        for chunk in chunks:
            tokens = _tokenize(chunk.content)
            self.corpus_tokens.append(tokens)

            self.chunk_metadata.append({
                "chunk_id":    chunk.chunk_id,
                "content":     chunk.content,
                "source_file": chunk.source_file,
                "page_number": chunk.page_number,
                "document_id": chunk.document_id,
                "metadata":    chunk.metadata if hasattr(chunk, "metadata") else {}
            })
        
        self.bm25 = BM25Okapi(
            self.corpus_tokens,
            k1 = 1.5,
            b = 0.75
        )

        self._save_index()

        logger.info(
            "bm25_index_built",
            total_chunks=len(chunks),
            vocab_size=len(self.bm25.idf)
        )

    def add_chunks(self, chunks: List) -> None:
        """
        Add new chunks to an existing BM25 index.
        Rebuilds the model with all old + new chunks combined.
        """
        if not chunks:
            return

        logger.info(
            "bm25_adding_chunks",
            new_chunks=len(chunks),
            existing_chunks = len(self.chunk_metadata)
        )

        new_tokens = []
        new_metadata = []

        existing_ids = {m["chunk_id"] for m in self.chunk_metadata}

        for chunk in chunks:
            if chunk.chunk_id in existing_ids:
                logger.debug(
                    "bm25_chunk_already_indexed",
                    chunk_id = chunk.chunk_id
                )
                continue

            new_tokens.append(_tokenize(chunk.content))
            new_metadata.append({
                "chunk_id":    chunk.chunk_id,
                "content":     chunk.content,
                "source_file": chunk.source_file,
                "page_number": chunk.page_number,
                "document_id": chunk.document_id,
                "metadata":    chunk.metadata if hasattr(chunk, "metadata") else {}
            })
        
        if not new_tokens:
            logger.info("bm25_no_new_chunks_to_add")
            return
        
        self.corpus_tokens.extend(new_tokens)
        self.chunk_metadata.extend(new_metadata)

        self.bm25 = BM25Okapi(
            self.corpus_tokens,
            k1 = 1.5,
            b = 0.75
        )

        self._save_index()

        logger.info(
            "bm25_chunks_added",
            added = len(new_tokens),
            total_chunks = len(self.chunk_metadata)
        )

    def delete_document(self, document_id: str) -> int:
        """
        Remove all chunks of a document from the BM25 index.
        Called when re-ingesting an updated document.
        """
        original_count = len(self.chunk_metadata)

        filtered_metadata = []
        filtered_tokens = []

        for meta, tokens in zip(self.chunk_metadata, self.corpus_tokens):
            if meta["document_id"] != document_id:
                filtered_metadata.append(meta)
                filtered_tokens.append(tokens)

        removed = original_count - len(filtered_metadata)

        if removed == 0:
            logger.info(
                "bm25_delete_document_not_found",
                document_id = document_id
            )
            return 0
        
        self.chunk_metadata = filtered_metadata
        self.corpus_tokens = filtered_tokens

        if self.corpus_tokens:
            self.bm25 = BM25Okapi(
                self.corpus_tokens,
                k1 = 1.5,
                b = 0.75
            )
        else:
            self.bm25 = None

        self._save_index()

        logger.info(
            "bm25_document_deleted",
            document_id=document_id,
            chunks_removed=removed
        )

        return removed
    
    def search(
            self,
            query: str,
            top_k: int = None,
            filter_document_id: Optional[str] = None
    ) -> List[RetrievedChunk]:
        """
        Search for chunks matching the query using BM25 scoring.
        Optionally filter results to a specific document.
        """
        if self.bm25 is None:
            logger.warning("bm25_search_called_but_no_index_built")
            return []

        if not query.strip():
            logger.warning("bm25_search_called_with_empty_query")
            return []

        k = top_k or settings.retrieval.bm25_search_top_k

        query_tokens = _tokenize(query)

        if not query_tokens:
            logger.warning("bm25_query_produced_no_tokens", query=query)
            return []
        
        scores = self.bm25.get_scores(query_tokens)

        top_indices = sorted(
            range(len(scores)),
            key = lambda i: scores[i],
            reverse = True
        )

        results = []

        for idx in top_indices:
            if len(results) >= k:
                break

            score = float(scores[idx])

            if score <= 0:
                continue

            meta = self.chunk_metadata[idx]

            if filter_document_id and meta["document_id"] != filter_document_id:
                continue

            results.append(RetrievedChunk(
                chunk_id=meta["chunk_id"],
                content=meta["content"],
                source_file=meta["source_file"],
                page_number=int(meta["page_number"]),
                document_id=meta["document_id"],
                score=round(score, 4),
                retrieval_method="bm25",
                metadata=meta.get("metadata", {})
            ))

        logger.info(
            "bm25_search_complete",
            query_preview = query[:60],
            results_found = len(results),
            top_score = results[0].score if results else 0,
            filter_document_id = filter_document_id or "none"
        )

        return results
    
    def get_stats(self) -> dict:
        """
        Return BM25 index statistics.
        Used by /metrics API endpoint.
        """
        return {
            "total_chunks": len(self.chunk_metadata),
            "index_built": self.bm25 is not None,
            "vocab_size": len(self.bm25.idf) if self.bm25 else 0,
            "index_path": str(self.index_dir)
        }
