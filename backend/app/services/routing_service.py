import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.models import RoutingRule, EscalationRule, Ticket
from shared.constants import URGENCY_ROUTING_MAP

logger = logging.getLogger(__name__)


class RoutingService:
    async def get_route_by_urgency(self, db: AsyncSession, urgency_level: str) -> Optional[dict]:
        try:
            stmt = select(RoutingRule).where(
                RoutingRule.urgency_level == urgency_level,
                RoutingRule.is_active == 1,
            )
            result = await db.execute(stmt)
            rule = result.scalar_one_or_none()
            if rule:
                return {
                    "target_role": rule.target_role,
                    "target_department": rule.target_department,
                    "sla_hours": rule.sla_hours,
                }
        except Exception as e:
            logger.warning(f"DB query routing rule failed: {e}")

        fallback = URGENCY_ROUTING_MAP.get(urgency_level)
        if fallback:
            return {
                "target_role": fallback.replace("_queue", "").replace("_dashboard", ""),
                "target_department": "",
                "sla_hours": 24,
            }
        return None

    async def get_escalation_rule(self, db: AsyncSession, from_level: str) -> Optional[EscalationRule]:
        stmt = select(EscalationRule).where(EscalationRule.from_level == from_level)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def check_sla_timeout(self, db: AsyncSession, ticket: Ticket) -> bool:
        if not ticket.urgency_level or not ticket.created_at:
            return False

        route = await self.get_route_by_urgency(db, ticket.urgency_level)
        if not route:
            return False

        sla_hours = route.get("sla_hours", 24)
        deadline = ticket.created_at + timedelta(hours=sla_hours)
        return datetime.now() > deadline
