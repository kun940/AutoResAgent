import logging

logger = logging.getLogger(__name__)


class SopIndexer:
    def __init__(self, vector_store):
        self.vector_store = vector_store

    async def build_index_from_db(self):
        try:
            from backend.app.database import async_session
            from backend.app.models.models import SopKnowledge
            from sqlalchemy import select

            async with async_session() as session:
                stmt = select(SopKnowledge).where(SopKnowledge.is_active == 1)
                result = await session.execute(stmt)
                sops = result.scalars().all()

            documents = []
            for sop in sops:
                doc_id = f"sop_{sop.id}"
                # v1.3: 索引内容纳入 emergency_actions 和 scenario_tags
                content = f"{sop.title}\n{sop.content}"
                if hasattr(sop, "keywords") and sop.keywords:
                    content = f"{sop.title} 关键词:{sop.keywords}\n{sop.content}"
                if hasattr(sop, "emergency_actions") and sop.emergency_actions:
                    content += f"\n紧急止损动作:{sop.emergency_actions}"
                if hasattr(sop, "scenario_tags") and sop.scenario_tags:
                    content += f"\n适用场景:{sop.scenario_tags}"
                # v1.3: metadata 新增 has_emergency_actions 标记
                metadata = {
                    "mysql_id": sop.id,
                    "issue_category": sop.issue_category,
                    "title": sop.title,
                    "urgency_level": sop.urgency_level or "",
                    "has_emergency_actions": 1 if (hasattr(sop, "emergency_actions") and sop.emergency_actions) else 0,
                }
                documents.append({"id": doc_id, "content": content, "metadata": metadata})

            if documents:
                count = self.vector_store.batch_add(documents)
                logger.info(f"Index built: {count} SOPs loaded from DB")
                return count
            return 0
        except Exception as e:
            logger.error(f"Build index from DB failed: {e}")
            return 0

    async def sync_single_sop(self, sop_id: int, content: str, metadata: dict):
        try:
            doc_id = f"sop_{sop_id}"
            self.vector_store.add_document(doc_id, content, metadata)
            logger.info(f"SOP synced: {doc_id}")
        except Exception as e:
            logger.error(f"Sync single SOP {sop_id} failed: {e}")

    async def remove_sop(self, sop_id: int):
        try:
            doc_id = f"sop_{sop_id}"
            self.vector_store.delete_document(doc_id)
            logger.info(f"SOP removed: {doc_id}")
        except Exception as e:
            logger.error(f"Remove SOP {sop_id} failed: {e}")