import os
import logging

from agent.config.agent_config import CHROMA_EMBEDDING_MODEL

logger = logging.getLogger(__name__)

_embeddings_instance = None
_init_failed = False


def get_embeddings():
    global _embeddings_instance, _init_failed

    if _embeddings_instance is not None:
        return _embeddings_instance
    if _init_failed:
        raise RuntimeError("Embedding function unavailable (init previously failed)")

    try:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")

        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        _embeddings_instance = SentenceTransformerEmbeddingFunction(model_name=CHROMA_EMBEDDING_MODEL)
        return _embeddings_instance
    except Exception as e:
        logger.warning(f"Embedding function init failed: {e}")
        _init_failed = True
        raise
