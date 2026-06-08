import logging

import chromadb
from chromadb import PersistentClient

from backend.app.config import settings
from agent.config.agent_config import CHROMA_COLLECTION_NAME

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, embedding_function=None):
        self.client: PersistentClient = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        self._embedding_function = embedding_function
        self._collection = None
        self._init_failed = False

    def _ensure_initialized(self):
        if self._collection is not None:
            return True
        if self._init_failed:
            return False
        try:
            if self._embedding_function is None:
                from agent.rag.embeddings import get_embeddings
                self._embedding_function = get_embeddings()
            self._collection = self.client.get_or_create_collection(
                name=CHROMA_COLLECTION_NAME,
                embedding_function=self._embedding_function,
            )
            return True
        except Exception as e:
            logger.warning(f"VectorStore init failed, RAG disabled: {e}")
            self._init_failed = True
            return False

    @property
    def collection(self):
        self._ensure_initialized()
        return self._collection

    def is_available(self) -> bool:
        return self._ensure_initialized()

    def add_document(self, doc_id: str, content: str, metadata: dict) -> bool:
        if not self._ensure_initialized():
            return False
        try:
            self._collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[metadata],
            )
            logger.info(f"Document added: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add document {doc_id}: {e}")
            return False

    def batch_add(self, documents: list[dict]) -> int:
        if not documents or not self._ensure_initialized():
            return 0
        ids = []
        contents = []
        metadatas = []
        for doc in documents:
            ids.append(doc["id"])
            contents.append(doc["content"])
            metadatas.append(doc.get("metadata", {}))
        try:
            self._collection.add(ids=ids, documents=contents, metadatas=metadatas)
            logger.info(f"Batch added {len(documents)} documents")
            return len(documents)
        except Exception as e:
            logger.error(f"Batch add failed: {e}")
            return 0

    def retrieve(self, query: str, top_k: int = 3, filter_metadata: dict = None) -> list[dict]:
        if not self._ensure_initialized():
            return []
        try:
            kwargs = {
                "query_texts": [query],
                "n_results": top_k,
            }
            if filter_metadata:
                kwargs["where"] = filter_metadata

            result = self._collection.query(**kwargs)

            if not result["ids"] or not result["ids"][0]:
                return []

            records = []
            for i in range(len(result["ids"][0])):
                records.append({
                    "id": result["ids"][0][i],
                    "content": result["documents"][0][i] if result.get("documents") else "",
                    "metadata": result["metadatas"][0][i] if result.get("metadatas") else {},
                    "distance": result["distances"][0][i] if result.get("distances") else None,
                })
            return records
        except Exception as e:
            logger.error(f"Retrieve failed: {e}")
            return []

    def delete_document(self, doc_id: str) -> bool:
        if not self._ensure_initialized():
            return False
        try:
            self._collection.delete(ids=[doc_id])
            logger.info(f"Document deleted: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False

    def rebuild_collection(self):
        if not self._ensure_initialized():
            return
        try:
            self.client.delete_collection(CHROMA_COLLECTION_NAME)
            self._collection = self.client.create_collection(
                name=CHROMA_COLLECTION_NAME,
                embedding_function=self._embedding_function,
            )
            logger.info("Collection rebuilt")
        except Exception as e:
            logger.error(f"Failed to rebuild collection: {e}")
