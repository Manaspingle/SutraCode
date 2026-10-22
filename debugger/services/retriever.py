import os
import logging
from typing import List, Dict, Any, Optional
from django.conf import settings
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)

class VectorStoreError(Exception):
    """Raised when ChromaDB index or query operation fails."""
    pass

class VectorRetriever:
    """Manages persistent ChromaDB vector store for evidence-grounded RAG."""

    COLLECTION_NAME = "sutratrace_documents"

    def __init__(self):
        self.persist_dir = getattr(settings, 'CHROMA_PERSIST_DIR', 'data/chromadb')
        os.makedirs(self.persist_dir, exist_ok=True)

        # Persistent ChromaDB client
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False)
        )

        # ONNX implementation of sentence-transformers/all-MiniLM-L6-v2
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()

        # Get or create collection with cosine distance
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )

    def index_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """
        Indexes a list of document chunks into ChromaDB with metadata.
        Returns the number of indexed chunks.
        """
        if not chunks:
            return 0

        ids = []
        documents = []
        metadatas = []

        for c in chunks:
            ids.append(c['chunk_id'])
            documents.append(c['content'])
            metadatas.append({
                'user_id': str(c['user_id']),
                'doc_id': str(c['doc_id']),
                'filename': str(c['filename']),
                'page_number': int(c['page_number']) if c.get('page_number') is not None else 1,
                'chunk_index': int(c['chunk_index']),
                'char_count': int(c['char_count'])
            })

        try:
            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            logger.info("Successfully indexed %d chunks in ChromaDB.", len(ids))
            return len(ids)
        except Exception as e:
            logger.error("Failed to index chunks in ChromaDB: %s", str(e))
            raise VectorStoreError(f"Vector indexing failed: {str(e)}")

    def delete_document_chunks(self, doc_id: str, user_id: str) -> None:
        """Removes all chunks belonging to a specific document for a user."""
        try:
            # Query and delete by document ID and user ID
            self.collection.delete(
                where={"$and": [{"user_id": str(user_id)}, {"doc_id": str(doc_id)}]}
            )
            logger.info("Deleted chunks for doc_id=%s, user_id=%s", doc_id, user_id)
        except Exception as e:
            # Fallback if where filter on delete has single condition or syntax variant
            try:
                self.collection.delete(where={"doc_id": str(doc_id)})
            except Exception as inner_e:
                logger.warning("Could not delete from vector collection: %s", str(inner_e))

    def retrieve_relevant_passages(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
        threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top relevant passages for the given query, restricted to the user's documents.
        Applies similarity threshold filtering.
        """
        if not query or not query.strip():
            return []

        if threshold is None:
            threshold = getattr(settings, 'SIMILARITY_THRESHOLD', 0.35)

        # Check total count for this user
        try:
            user_count = self.collection.count()
            if user_count == 0:
                logger.info("No documents in vector collection.")
                return []

            results = self.collection.query(
                query_texts=[query],
                n_results=min(top_k, max(user_count, 1)),
                where={"user_id": str(user_id)} if user_id != 'all' else None
            )
        except Exception as e:
            logger.error("Vector retrieval query error: %s", str(e))
            return []

        retrieved = []
        if not results or not results.get('documents') or not results['documents'][0]:
            return []

        doc_texts = results['documents'][0]
        metadatas = results['metadatas'][0] if results.get('metadatas') else [{}] * len(doc_texts)
        distances = results['distances'][0] if results.get('distances') else [0.0] * len(doc_texts)
        ids = results['ids'][0] if results.get('ids') else [''] * len(doc_texts)

        for text, meta, dist, chunk_id in zip(doc_texts, metadatas, distances, ids):
            # For cosine distance: distance is in [0, 2]. Similarity = 1 - (distance / 2) or 1 - distance
            # Closer to 0 distance means higher similarity.
            similarity = max(0.0, 1.0 - (dist if dist <= 1.0 else dist / 2.0))

            if similarity >= threshold:
                retrieved.append({
                    'chunk_id': chunk_id,
                    'filename': meta.get('filename', 'Unknown Document'),
                    'page_number': meta.get('page_number', 1),
                    'content': text,
                    'relevance_score': round(similarity, 3),
                    'distance': round(dist, 4)
                })

        # Sort by relevance descending
        retrieved.sort(key=lambda x: x['relevance_score'], reverse=True)
        return retrieved

    def get_user_document_count(self, user_id: str) -> int:
        """Returns the number of indexed chunks belonging to a user."""
        try:
            results = self.collection.get(where={"user_id": str(user_id)})
            return len(results.get('ids', []))
        except Exception:
            return 0

# Singleton instance
retriever = VectorRetriever()
