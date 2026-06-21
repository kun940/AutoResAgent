import logging

logger = logging.getLogger(__name__)


class SopRetriever:
    def __init__(self, vector_store):
        self.vector_store = vector_store

    def retrieve_sop(
        self,
        issue_description: str,
        urgency_level: str = None,
        top_k: int = 2,
        prefer_emergency: bool = False,
    ) -> list[dict]:
        """检索匹配的SOP

        Args:
            issue_description: 问题描述
            urgency_level: 紧急度过滤
            top_k: 返回数量
            prefer_emergency: 是否优先返回含紧急止损动作的SOP（v1.3新增）
        """
        try:
            filter_metadata = None
            if urgency_level:
                filter_metadata = {"urgency_level": urgency_level}

            # v1.3: 紧急优先模式 - 扩大检索范围，优先返回含紧急止损动作的SOP
            actual_top_k = top_k * 3 if prefer_emergency else top_k

            results = self.vector_store.retrieve(
                query=issue_description,
                top_k=actual_top_k,
                filter_metadata=filter_metadata,
            )

            if prefer_emergency and results:
                # 按是否含紧急止损动作排序：has_emergency_actions=1 排前面
                results.sort(
                    key=lambda r: r.get("metadata", {}).get("has_emergency_actions", 0),
                    reverse=True,
                )
                # 截取到原始 top_k
                results = results[:top_k]

            return results
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