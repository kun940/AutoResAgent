import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.models import SopKnowledge

logger = logging.getLogger(__name__)


class KnowledgeService:
    async def rebuild_chroma_index(self):
        try:
            from agent.rag.sop_indexer import SOPIndexer
            indexer = SOPIndexer()
            await indexer.rebuild_index()
            logger.info("ChromaDB index rebuilt successfully")
            return True
        except Exception as e:
            logger.warning(f"ChromaDB index rebuild skipped: {e}")
            return False

    async def search_sop(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = 5,
    ) -> list[SopKnowledge]:
        try:
            from agent.rag.retriever import SOPRetriever
            retriever = SOPRetriever()
            results = await retriever.search(query, top_k=top_k)
            if results:
                return results
        except Exception as e:
            logger.warning(f"ChromaDB search failed, falling back to DB search: {e}")

        return await self._db_search(db, query, top_k)

    async def _db_search(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = 5,
    ) -> list[SopKnowledge]:
        stmt = (
            select(SopKnowledge)
            .where(SopKnowledge.is_active == 1)
            .order_by(SopKnowledge.version.desc())
            .limit(top_k)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def on_knowledge_created(self, db: AsyncSession, knowledge_id: int):
        await self.rebuild_chroma_index()

    async def on_knowledge_updated(self, db: AsyncSession, knowledge_id: int):
        await self.rebuild_chroma_index()

    async def on_knowledge_deleted(self, db: AsyncSession, knowledge_id: int):
        await self.rebuild_chroma_index()