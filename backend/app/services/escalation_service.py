import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.models import Ticket, Notification, TicketLog, EscalationRule, User
from shared.constants import NotificationType, TicketAction

logger = logging.getLogger(__name__)


class EscalationService:
    async def check_and_escalate(self, db: AsyncSession, ticket: Ticket) -> bool:
        if not ticket.urgency_level or not ticket.created_at:
            return False

        stmt = select(EscalationRule).where(EscalationRule.from_level == ticket.urgency_level)
        result = await db.execute(stmt)
        rule = result.scalar_one_or_none()

        if not rule or not rule.auto_escalate_hours:
            return False

        deadline = ticket.created_at + timedelta(hours=rule.auto_escalate_hours)
        if datetime.now() <= deadline:
            return False

        old_level = ticket.urgency_level
        ticket.urgency_level = rule.to_level

        target_user = await self._find_user_for_level(db, rule.to_level)
        if target_user:
            ticket.assigned_to = target_user.id
            notification = Notification(
                ticket_id=ticket.ticket_id,
                target_user_id=target_user.id,
                type=NotificationType.SLA_WARNING,
                content=f"工单 {ticket.ticket_id} 因SLA超时自动升级至 {rule.to_level}",
            )
            db.add(notification)

        log = TicketLog(
            ticket_id=ticket.ticket_id,
            action=TicketAction.ESCALATION,
            detail=f"SLA超时自动升级：{old_level} → {rule.to_level}",
        )
        db.add(log)
        await db.flush()

        logger.info(f"Ticket {ticket.ticket_id} auto-escalated: {old_level} -> {rule.to_level}")
        return True

    async def check_all_overdue(self, db: AsyncSession) -> int:
        stmt = select(Ticket).where(
            Ticket.status.in_(["pending", "processing", "routed"]),
            Ticket.created_at.isnot(None),
        )
        result = await db.execute(stmt)
        tickets = list(result.scalars().all())

        escalated_count = 0
        for ticket in tickets:
            try:
                if await self.check_and_escalate(db, ticket):
                    escalated_count += 1
            except Exception as e:
                logger.error(f"Check escalation failed for ticket {ticket.ticket_id}: {e}")

        return escalated_count

    async def _find_user_for_level(self, db: AsyncSession, urgency_level: str) -> Optional[User]:
        from backend.app.services.routing_service import RoutingService
        route = await RoutingService().get_route_by_urgency(db, urgency_level)
        if not route:
            return None
        stmt = select(User).where(
            User.role == route["target_role"],
            User.is_active == 1,
        ).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()