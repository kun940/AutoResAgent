import logging

logger = logging.getLogger(__name__)


class SopRetriever:
    def __init__(self, vector_store):
        self.vector_store = vector_store

    def retrieve_sop(
        self,
        issue_description: str,
        urgency_level: str = None,
        issue_category: str = None,
        top_k: int = 2,
        prefer_emergency: bool = False,
    ) -> list[dict]:
        """检索匹配的SOP

        Args:
            issue_description: 问题描述
            urgency_level: 紧急度过滤
            issue_category: 问题分类过滤（v1.4新增，优先按分类精确匹配，
                避免批次缺陷客诉被匹配到漏电SOP等问题）
            top_k: 返回数量
            prefer_emergency: 是否优先返回含紧急止损动作的SOP（v1.3新增）
        """
        try:
            # v1.3: 紧急优先模式 - 扩大检索范围，优先返回含紧急止损动作的SOP
            actual_top_k = top_k * 3 if prefer_emergency else top_k

            # v1.4: 三级回退检索策略，避免跨分类误匹配
            # 1) issue_category + urgency_level 双重过滤（精确分类匹配，优先）
            # 2) 仅 issue_category 过滤（同分类下不受紧急度限制）
            # 3) 仅 urgency_level 过滤（同紧急度范围内的语义匹配）
            # 4) 无过滤（纯语义匹配，兜底）
            # 注意：ChromaDB 多字段 AND 需使用 $and 操作符
            results = []
            if issue_category and urgency_level:
                combined_filter = {
                    "$and": [
                        {"issue_category": issue_category},
                        {"urgency_level": urgency_level},
                    ]
                }
                results = self.vector_store.retrieve(
                    query=issue_description,
                    top_k=actual_top_k,
                    filter_metadata=combined_filter,
                )
            if not results and issue_category:
                results = self.vector_store.retrieve(
                    query=issue_description,
                    top_k=actual_top_k,
                    filter_metadata={"issue_category": issue_category},
                )
            if not results and urgency_level:
                results = self.vector_store.retrieve(
                    query=issue_description,
                    top_k=actual_top_k,
                    filter_metadata={"urgency_level": urgency_level},
                )
            if not results:
                results = self.vector_store.retrieve(
                    query=issue_description,
                    top_k=actual_top_k,
                    filter_metadata=None,
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

    def get_best_sop(
        self,
        issue_description: str,
        urgency_level: str = None,
        issue_category: str = None,
    ) -> dict | None:
        try:
            results = self.retrieve_sop(
                issue_description=issue_description,
                urgency_level=urgency_level,
                issue_category=issue_category,
                top_k=1,
            )
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Get best SOP failed: {e}")
            return None