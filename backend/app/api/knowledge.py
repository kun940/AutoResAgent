import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.models.models import SopKnowledge
from backend.app.schemas.sop_knowledge import SopKnowledgeCreate, SopKnowledgeUpdate, SopKnowledgeResponse
from backend.app.schemas.common import ApiResponse, PaginatedResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_knowledge(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        count_stmt = select(func.count()).select_from(SopKnowledge).where(SopKnowledge.is_active == 1)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = (
            select(SopKnowledge)
            .where(SopKnowledge.is_active == 1)
            .order_by(SopKnowledge.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        items = list(result.scalars().all())
        data = [SopKnowledgeResponse.model_validate(item) for item in items]

        return PaginatedResponse(total=total, page=page, page_size=page_size, data=data)
    except Exception as e:
        logger.error(f"List knowledge failed: {e}")
        return PaginatedResponse(code=1, message=str(e))


@router.get("/{knowledge_id}", response_model=ApiResponse)
async def get_knowledge(
    knowledge_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(SopKnowledge).where(SopKnowledge.id == knowledge_id, SopKnowledge.is_active == 1)
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()
        if not item:
            return ApiResponse(code=1, message=f"SOP {knowledge_id} 不存在")
        return ApiResponse(data=SopKnowledgeResponse.model_validate(item))
    except Exception as e:
        logger.error(f"Get knowledge failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.post("", response_model=ApiResponse)
async def create_knowledge(
    request: SopKnowledgeCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = SopKnowledge(
            issue_category=request.issue_category,
            title=request.title,
            content=request.content,
            urgency_level=request.urgency_level,
            keywords=request.keywords,
        )
        db.add(item)
        await db.flush()

        stmt = select(SopKnowledge).where(SopKnowledge.id == item.id)
        result = await db.execute(stmt)
        created = result.scalar_one()
        return ApiResponse(data=SopKnowledgeResponse.model_validate(created))
    except Exception as e:
        logger.error(f"Create knowledge failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.put("/{knowledge_id}", response_model=ApiResponse)
async def update_knowledge(
    knowledge_id: int,
    request: SopKnowledgeUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(SopKnowledge).where(SopKnowledge.id == knowledge_id, SopKnowledge.is_active == 1)
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()
        if not item:
            return ApiResponse(code=1, message=f"SOP {knowledge_id} 不存在")

        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)

        if any(key in update_data for key in ("content", "title", "issue_category")):
            item.version += 1

        await db.flush()
        return ApiResponse(data=SopKnowledgeResponse.model_validate(item))
    except Exception as e:
        logger.error(f"Update knowledge failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.delete("/{knowledge_id}", response_model=ApiResponse)
async def delete_knowledge(
    knowledge_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(SopKnowledge).where(SopKnowledge.id == knowledge_id, SopKnowledge.is_active == 1)
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()
        if not item:
            return ApiResponse(code=1, message=f"SOP {knowledge_id} 不存在")

        item.is_active = 0
        await db.flush()
        return ApiResponse(message="删除成功")
    except Exception as e:
        logger.error(f"Delete knowledge failed: {e}")
        return ApiResponse(code=1, message=str(e))
