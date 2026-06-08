import logging
import random
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.models import Ticket, TicketLog, Notification, RoutingRule, User
from shared.constants import TicketStatus, TICKET_STATUS_TRANSITIONS, NotificationType, TicketAction

logger = logging.getLogger(__name__)


def _generate_ticket_id() -> str:
    now = datetime.now()
    seq = random.randint(1000, 9999)
    return f"CS-{now.strftime('%Y%m%d')}-{seq}"


class TicketService:
    def __init__(self):
        self._agent_engine = None

    @property
    def agent_engine(self):
        if self._agent_engine is None:
            try:
                from agent.core.agent_engine import ComplaintAgentEngine
                self._agent_engine = ComplaintAgentEngine()
            except Exception as e:
                logger.warning(f"Agent engine init failed: {e}")
                self._agent_engine = None
        return self._agent_engine

    async def submit_complaint(
        self,
        db: AsyncSession,
        text: str,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        image_paths: Optional[list] = None,
    ) -> dict:
        try:
            if self.agent_engine is not None:
                result = await self.agent_engine.process_complaint(
                    text=text,
                    image_paths=image_paths,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                )
            else:
                raise RuntimeError("Agent engine not available")
        except Exception as e:
            logger.error(f"Agent pipeline failed: {e}")
            result = {
                "ticket_id": _generate_ticket_id(),
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "raw_input": text,
                "extracted_data": {"core_fault_desc": text},
                "agent_business_assessment": {
                    "issue_category": "Other",
                    "business_impact": "Minor_Inconvenience",
                    "urgency_level": "Medium_Priority",
                    "warranty_status": "Unknown",
                },
                "urgency_level": "Medium_Priority",
                "issue_category": "Other",
                "warranty_status": "Unknown",
                "routing_decision": "department_manager_queue",
                "auto_reply_sent": "您好，已收到您的反馈，我们正在紧急处理中。由于系统繁忙，我们的专业客服人员将在30分钟内与您联系。",
                "sop_applied": None,
                "status": "routed",
            }

        ticket = Ticket(
            ticket_id=result["ticket_id"],
            customer_name=result.get("customer_name"),
            customer_phone=result.get("customer_phone"),
            raw_input=result["raw_input"],
            extracted_data=result.get("extracted_data"),
            agent_business_assessment=result.get("agent_business_assessment"),
            urgency_level=result.get("urgency_level"),
            issue_category=result.get("issue_category"),
            warranty_status=result.get("warranty_status"),
            routing_decision=result.get("routing_decision"),
            auto_reply_sent=result.get("auto_reply_sent"),
            sop_applied=result.get("sop_applied"),
            status=TicketStatus.ROUTED,
        )
        db.add(ticket)

        routing_rule = await self._get_routing_rule(db, ticket.urgency_level)
        if routing_rule:
            target_user = await self._find_user_by_role(db, routing_rule.target_role)
            if target_user:
                ticket.assigned_to = target_user.id
                notification = Notification(
                    ticket_id=ticket.ticket_id,
                    target_user_id=target_user.id,
                    type=NotificationType.NEW_TICKET,
                    content=f"新工单 {ticket.ticket_id} 已路由至您，紧急度：{ticket.urgency_level}",
                )
                db.add(notification)

        log = TicketLog(
            ticket_id=ticket.ticket_id,
            action=TicketAction.STATUS_CHANGE,
            detail=f"工单创建，状态：routed，紧急度：{ticket.urgency_level}",
        )
        db.add(log)
        await db.flush()

        return result

    async def get_ticket(self, db: AsyncSession, ticket_id: str) -> Optional[Ticket]:
        stmt = select(Ticket).where(Ticket.ticket_id == ticket_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_tickets(
        self,
        db: AsyncSession,
        status: Optional[str] = None,
        urgency_level: Optional[str] = None,
        target_role: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list, int]:
        conditions = []
        if status:
            conditions.append(Ticket.status == status)
        if urgency_level:
            conditions.append(Ticket.urgency_level == urgency_level)
        if target_role:
            conditions.append(Ticket.routing_decision.contains(target_role))

        count_stmt = select(func.count()).select_from(Ticket)
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = select(Ticket).order_by(Ticket.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        if conditions:
            stmt = stmt.where(*conditions)
        result = await db.execute(stmt)
        tickets = list(result.scalars().all())

        return tickets, total

    async def update_status(
        self,
        db: AsyncSession,
        ticket_id: str,
        status: str,
        note: Optional[str] = None,
    ) -> Optional[Ticket]:
        ticket = await self.get_ticket(db, ticket_id)
        if not ticket:
            return None

        current_status = TicketStatus(ticket.status) if isinstance(ticket.status, str) else ticket.status
        new_status = TicketStatus(status)

        allowed = TICKET_STATUS_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise ValueError(f"非法状态流转：{current_status.value} → {new_status.value}，允许的目标状态：{[s.value for s in allowed]}")

        ticket.status = new_status
        if new_status == TicketStatus.RESOLVED:
            ticket.resolved_at = datetime.now()

        log = TicketLog(
            ticket_id=ticket_id,
            action=TicketAction.STATUS_CHANGE,
            detail=f"状态变更：{current_status.value} → {new_status.value}" + (f"，备注：{note}" if note else ""),
        )
        db.add(log)
        await db.flush()
        return ticket

    async def escalate(
        self,
        db: AsyncSession,
        ticket_id: str,
        to_level: str,
        reason: str,
    ) -> Optional[Ticket]:
        ticket = await self.get_ticket(db, ticket_id)
        if not ticket:
            return None

        old_level = ticket.urgency_level
        ticket.urgency_level = to_level

        routing_rule = await self._get_routing_rule(db, to_level)
        if routing_rule:
            target_user = await self._find_user_by_role(db, routing_rule.target_role)
            if target_user:
                ticket.assigned_to = target_user.id
                notification = Notification(
                    ticket_id=ticket_id,
                    target_user_id=target_user.id,
                    type=NotificationType.ESCALATION,
                    content=f"工单 {ticket_id} 已升级至 {to_level}，原因：{reason}",
                )
                db.add(notification)

        log = TicketLog(
            ticket_id=ticket_id,
            action=TicketAction.ESCALATION,
            detail=f"紧急度升级：{old_level} → {to_level}，原因：{reason}",
        )
        db.add(log)
        await db.flush()
        return ticket

    async def reassign(
        self,
        db: AsyncSession,
        ticket_id: str,
        target_username: str,
        target_role: str,
        reason: str,
    ) -> Optional[Ticket]:
        ticket = await self.get_ticket(db, ticket_id)
        if not ticket:
            return None

        stmt = select(User).where(
            User.username == target_username,
            User.role == target_role,
            User.is_active == 1,
        )
        result = await db.execute(stmt)
        target_user = result.scalar_one_or_none()

        if not target_user:
            raise ValueError(f"未找到角色为「{target_role}」且用户名为「{target_username}」的活跃用户")

        old_assignee = ticket.assigned_to
        ticket.assigned_to = target_user.id

        notification = Notification(
            ticket_id=ticket_id,
            target_user_id=target_user.id,
            type=NotificationType.REASSIGN,
            content=f"工单 {ticket_id} 已转派给您，原因：{reason}",
        )
        db.add(notification)

        log = TicketLog(
            ticket_id=ticket_id,
            action=TicketAction.REASSIGN,
            detail=f"转派：{old_assignee} → {target_user.username}({target_user.role})，原因：{reason}",
        )
        db.add(log)
        await db.flush()
        return ticket

    async def _get_routing_rule(self, db: AsyncSession, urgency_level: Optional[str]) -> Optional[RoutingRule]:
        if not urgency_level:
            return None
        stmt = select(RoutingRule).where(RoutingRule.urgency_level == urgency_level, RoutingRule.is_active == 1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _find_user_by_role(self, db: AsyncSession, role: str) -> Optional[User]:
        stmt = select(User).where(User.role == role, User.is_active == 1).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
