import logging
from typing import Optional

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.models import Notification
from shared.constants import NotificationType

logger = logging.getLogger(__name__)


class NotificationService:
    async def create_notification(
        self,
        db: AsyncSession,
        ticket_id: str,
        target_user_id: int,
        type: str,
        content: Optional[str] = None,
    ) -> Notification:
        notification = Notification(
            ticket_id=ticket_id,
            target_user_id=target_user_id,
            type=type,
            content=content,
        )
        db.add(notification)
        await db.flush()
        return notification

    async def get_notifications(
        self,
        db: AsyncSession,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list, int]:
        count_stmt = select(func.count()).select_from(Notification).where(Notification.target_user_id == user_id)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = (
            select(Notification)
            .where(Notification.target_user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        notifications = list(result.scalars().all())

        return notifications, total

    async def get_unread_count(self, db: AsyncSession, user_id: int) -> int:
        stmt = select(func.count()).select_from(Notification).where(
            Notification.target_user_id == user_id,
            Notification.is_read == 0,
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def mark_as_read(self, db: AsyncSession, notification_id: int) -> bool:
        stmt = select(Notification).where(Notification.id == notification_id)
        result = await db.execute(stmt)
        notification = result.scalar_one_or_none()
        if not notification:
            return False
        notification.is_read = 1
        await db.flush()
        return True

    async def mark_all_as_read(self, db: AsyncSession, user_id: int) -> bool:
        stmt = (
            update(Notification)
            .where(Notification.target_user_id == user_id, Notification.is_read == 0)
            .values(is_read=1)
        )
        await db.execute(stmt)
        await db.flush()
        return True
