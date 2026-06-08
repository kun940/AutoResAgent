import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.notification import NotificationResponse, UnreadCountResponse
from backend.app.schemas.common import ApiResponse, PaginatedResponse
from backend.app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter()
notification_service = NotificationService()


@router.get("", response_model=PaginatedResponse)
async def list_notifications(
    user_id: int = Query(..., description="用户ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        notifications, total = await notification_service.get_notifications(
            db=db,
            user_id=user_id,
            page=page,
            page_size=page_size,
        )
        notification_list = [NotificationResponse.model_validate(n) for n in notifications]
        return PaginatedResponse(total=total, page=page, page_size=page_size, data=notification_list)
    except Exception as e:
        logger.error(f"List notifications failed: {e}")
        return PaginatedResponse(code=1, message=str(e))


@router.get("/unread-count", response_model=ApiResponse)
async def get_unread_count(
    user_id: int = Query(..., description="用户ID"),
    db: AsyncSession = Depends(get_db),
):
    try:
        count = await notification_service.get_unread_count(db=db, user_id=user_id)
        return ApiResponse(data=UnreadCountResponse(count=count))
    except Exception as e:
        logger.error(f"Get unread count failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.put("/{notification_id}/read", response_model=ApiResponse)
async def mark_as_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        success = await notification_service.mark_as_read(db=db, notification_id=notification_id)
        if not success:
            return ApiResponse(code=1, message=f"通知 {notification_id} 不存在")
        return ApiResponse(message="已标记为已读")
    except Exception as e:
        logger.error(f"Mark as read failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.put("/read-all", response_model=ApiResponse)
async def mark_all_as_read(
    user_id: int = Query(..., description="用户ID"),
    db: AsyncSession = Depends(get_db),
):
    try:
        await notification_service.mark_all_as_read(db=db, user_id=user_id)
        return ApiResponse(message="全部标记为已读")
    except Exception as e:
        logger.error(f"Mark all as read failed: {e}")
        return ApiResponse(code=1, message=str(e))
