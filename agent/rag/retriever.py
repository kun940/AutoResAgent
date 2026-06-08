import logging

logger = logging.getLogger(__name__)


class SopRetriever:
    def __init__(self, vector_store):
        self.vector_store = vector_store

    def retrieve_sop(self, issue_description: str, urgency_level: str = None, top_k: int = 2) -> list[dict]:
        try:
            filter_metadata = None
            if urgency_level:
                filter_metadata = {"urgency_level": urgency_level}
            return self.vector_store.retrieve(
                query=issue_description,
                top_k=top_k,
                filter_metadata=filter_metadata,
            )
        except Exception as e:
            logger.error(f"SOP retrieval failed: {e}")
            return []

    def get_best_sop(self, issue_description: str, urgency_level: str = None) -> dict | None:
        try:
            results = self.retrieve_sop(
                issue_description=issue_description,
                urgency_level=urgency_level,
                top_k=1,
            )
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Get best SOP failed: {e}")
            return None