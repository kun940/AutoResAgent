import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.models import ServiceOrder, OrderMappingRule, Ticket, TicketLog, Notification
from shared.constants import OrderStatus, ORDER_STATUS_TRANSITIONS, ORDER_TYPE_PREFIX, ORDER_TYPE_LABELS, OrderType, NotificationType, TicketAction

logger = logging.getLogger(__name__)


def _generate_order_no(order_type: str) -> str:
    """生成出单编号，格式：{类型前缀}-{日期}-{序号}"""
    now = datetime.now()
    prefix = ORDER_TYPE_PREFIX.get(OrderType(order_type), "ORD") if order_type in [e.value for e in OrderType] else "ORD"
    seq = random.randint(1000, 9999)
    return f"{prefix}-{now.strftime('%Y%m%d')}-{seq}"


class OrderService:
    """出单管理服务"""

    async def get_orders(
        self,
        db: AsyncSession,
        order_type: Optional[str] = None,
        status: Optional[str] = None,
        ticket_id: Optional[str] = None,
        department: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list, int]:
        """分页查询出单列表"""
        conditions = []
        if order_type:
            conditions.append(ServiceOrder.order_type == order_type)
        if status:
            conditions.append(ServiceOrder.status == status)
        if ticket_id:
            conditions.append(ServiceOrder.ticket_id == ticket_id)
        if department:
            conditions.append(ServiceOrder.department == department)

        # 查询总数
        count_stmt = select(func.count()).select_from(ServiceOrder)
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        # 分页查询
        stmt = (
            select(ServiceOrder)
            .order_by(ServiceOrder.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if conditions:
            stmt = stmt.where(*conditions)
        result = await db.execute(stmt)
        orders = list(result.scalars().all())

        return orders, total

    async def get_order(self, db: AsyncSession, order_id: int) -> Optional[ServiceOrder]:
        """获取单个出单详情"""
        stmt = select(ServiceOrder).where(ServiceOrder.id == order_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_order(self, db: AsyncSession, data: dict) -> ServiceOrder:
        """手动创建出单"""
        order_type = data.get("order_type", "")
        ticket_id = data.get("ticket_id", "")

        # 查询关联工单，获取问题分类、紧急度等信息
        ticket_stmt = select(Ticket).where(Ticket.ticket_id == ticket_id)
        ticket_result = await db.execute(ticket_stmt)
        ticket = ticket_result.scalar_one_or_none()

        # 生成出单编号
        order_no = _generate_order_no(order_type)

        # 获取出单类型标签
        order_type_label = ""
        try:
            order_type_label = ORDER_TYPE_LABELS.get(OrderType(order_type), order_type)
        except ValueError:
            order_type_label = order_type

        # 查询映射规则获取部门和SLA
        department = data.get("department", "")
        sla_hours = data.get("sla_hours", 48)
        if ticket:
            issue_category = ticket.issue_category
            urgency_level = ticket.urgency_level
            if not department and issue_category and urgency_level:
                rule = await self._find_mapping_rule(db, issue_category, urgency_level)
                if rule:
                    department = rule.department
                    sla_hours = rule.sla_hours
        else:
            issue_category = None
            urgency_level = None

        # 计算截止时间
        deadline = datetime.now() + timedelta(hours=sla_hours)

        # 确定优先级
        priority = "Medium_Priority"
        if urgency_level == "High_Priority":
            priority = "High_Priority"
        elif urgency_level == "Low_Priority":
            priority = "Low_Priority"

        order = ServiceOrder(
            order_no=order_no,
            ticket_id=ticket_id,
            order_type=order_type,
            order_type_label=order_type_label,
            status=OrderStatus.PENDING,
            priority=priority,
            department=department,
            sla_hours=sla_hours,
            deadline=deadline,
            material_list=data.get("material_list"),
            issue_category=issue_category,
            urgency_level=urgency_level,
            model_number=ticket.extracted_data.get("model_number") if ticket and ticket.extracted_data else None,
            batch_code=ticket.extracted_data.get("batch_code") if ticket and ticket.extracted_data else None,
            remark=data.get("remark"),
        )
        db.add(order)

        # 更新工单的出单状态
        if ticket:
            ticket.order_status = "ordered"

        # 记录工单日志
        log = TicketLog(
            ticket_id=ticket_id,
            action=TicketAction.ORDER_CREATED,
            detail=f"创建出单 {order_no}，类型：{order_type_label}，部门：{department}",
        )
        db.add(log)

        await db.flush()
        await db.refresh(order)

        return order

    async def update_order_status(
        self,
        db: AsyncSession,
        order_id: int,
        status: str,
        note: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Optional[ServiceOrder]:
        """更新出单状态（含状态流转校验）"""
        order = await self.get_order(db, order_id)
        if not order:
            return None

        # 状态流转校验
        current_status = OrderStatus(order.status) if isinstance(order.status, str) else order.status
        new_status = OrderStatus(status)

        allowed = ORDER_STATUS_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"非法状态流转：{current_status.value} -> {new_status.value}，"
                f"允许的目标状态：{[s.value for s in allowed]}"
            )

        order.status = new_status

        # 完成状态时记录完成信息
        if new_status == OrderStatus.COMPLETED:
            order.completed_at = datetime.now()
            if user_id:
                order.completed_by = user_id

        # 记录日志
        log = TicketLog(
            ticket_id=order.ticket_id,
            action=TicketAction.STATUS_CHANGE,
            detail=f"出单 {order.order_no} 状态变更：{current_status.value} -> {new_status.value}" + (f"，备注：{note}" if note else ""),
        )
        db.add(log)

        await db.flush()
        await db.refresh(order)

        return order

    async def get_orders_by_ticket(self, db: AsyncSession, ticket_id: str) -> list:
        """根据工单ID查关联出单"""
        stmt = select(ServiceOrder).where(ServiceOrder.ticket_id == ticket_id).order_by(ServiceOrder.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_mapping_rules(
        self,
        db: AsyncSession,
        is_active: Optional[int] = None,
        issue_category: Optional[str] = None,
    ) -> list:
        """查询映射规则列表"""
        conditions = []
        if is_active is not None:
            conditions.append(OrderMappingRule.is_active == is_active)
        if issue_category:
            conditions.append(OrderMappingRule.issue_category == issue_category)

        stmt = select(OrderMappingRule).order_by(OrderMappingRule.priority.desc(), OrderMappingRule.created_at.desc())
        if conditions:
            stmt = stmt.where(*conditions)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create_mapping_rule(self, db: AsyncSession, data: dict) -> OrderMappingRule:
        """创建映射规则"""
        rule = OrderMappingRule(
            issue_category=data["issue_category"],
            urgency_level=data["urgency_level"],
            order_type=data["order_type"],
            department=data["department"],
            sla_hours=data.get("sla_hours", 48),
            priority=data.get("priority", 0),
            description=data.get("description"),
        )
        db.add(rule)
        await db.flush()
        await db.refresh(rule)
        return rule

    async def update_mapping_rule(self, db: AsyncSession, rule_id: int, data: dict) -> Optional[OrderMappingRule]:
        """更新映射规则"""
        stmt = select(OrderMappingRule).where(OrderMappingRule.id == rule_id)
        result = await db.execute(stmt)
        rule = result.scalar_one_or_none()
        if not rule:
            return None

        # 只更新传入的字段
        update_fields = ["order_type", "department", "sla_hours", "is_active", "priority", "description"]
        for field in update_fields:
            if field in data and data[field] is not None:
                setattr(rule, field, data[field])

        await db.flush()
        await db.refresh(rule)
        return rule

    async def delete_mapping_rule(self, db: AsyncSession, rule_id: int) -> Optional[OrderMappingRule]:
        """软删除映射规则（设置is_active=0）"""
        stmt = select(OrderMappingRule).where(OrderMappingRule.id == rule_id)
        result = await db.execute(stmt)
        rule = result.scalar_one_or_none()
        if not rule:
            return None

        rule.is_active = 0
        await db.flush()
        await db.refresh(rule)
        return rule

    async def _find_mapping_rule(
        self,
        db: AsyncSession,
        issue_category: str,
        urgency_level: str,
    ) -> Optional[OrderMappingRule]:
        """根据问题分类和紧急度查找映射规则"""
        stmt = select(OrderMappingRule).where(
            OrderMappingRule.issue_category == issue_category,
            OrderMappingRule.urgency_level == urgency_level,
            OrderMappingRule.is_active == 1,
        ).order_by(OrderMappingRule.priority.desc()).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
