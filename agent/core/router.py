import logging

from shared.constants import UrgencyLevel, URGENCY_ROUTING_MAP

logger = logging.getLogger(__name__)


class RoutingAgent:
    async def route(self, urgency_level: str) -> str:
        try:
            level = UrgencyLevel(urgency_level)
        except ValueError:
            logger.warning(f"Unknown urgency_level: {urgency_level}, defaulting to Medium_Priority")
            level = UrgencyLevel.MEDIUM

        try:
            from backend.app.database import async_session
            from backend.app.models.models import RoutingRule
            from sqlalchemy import select

            async with async_session() as session:
                stmt = select(RoutingRule).where(
                    RoutingRule.urgency_level == level.value,
                    RoutingRule.is_active == 1,
                )
                result = await session.execute(stmt)
                rule = result.scalars().first()

                if rule:
                    target_role = rule.target_role
                    if "general_manager" in target_role:
                        queue_name = "general_manager_dashboard"
                    else:
                        queue_name = f"{target_role}_queue"
                    logger.info(f"DB routing: {level.value} → {queue_name} (SLA: {rule.sla_hours}h)")
                    return queue_name
        except Exception as e:
            logger.warning(f"DB routing query failed, falling back to map: {e}")

        route = URGENCY_ROUTING_MAP.get(level, "department_manager_queue")
        logger.info(f"Map routing: {level.value} → {route}")
        return route