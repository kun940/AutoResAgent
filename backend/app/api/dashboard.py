import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.models.models import Ticket, RoutingRule
from backend.app.schemas.common import ApiResponse
from backend.app.services.routing_service import RoutingService
from shared.constants import TicketStatus, UrgencyLevel

logger = logging.getLogger(__name__)

router = APIRouter()
routing_service = RoutingService()

# 角色层级：低 -> 高
ROLE_HIERARCHY = ["frontline_staff", "department_manager", "general_manager"]


def _get_lower_roles(role: str) -> list[str]:
    """获取低于当前角色的所有角色列表"""
    try:
        idx = ROLE_HIERARCHY.index(role)
        return ROLE_HIERARCHY[:idx]
    except ValueError:
        return []


@router.get("/stats", response_model=ApiResponse)
async def get_dashboard_stats(
    target_role: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        # 基础条件：按角色过滤routing_decision
        role_condition = None
        if target_role:
            role_condition = Ticket.routing_decision.contains(target_role)

        # 工单总数
        total_stmt = select(func.count()).select_from(Ticket)
        if role_condition is not None:
            total_stmt = total_stmt.where(role_condition)
        total_result = await db.execute(total_stmt)
        total_tickets = total_result.scalar() or 0

        # 待处理数
        pending_stmt = select(func.count()).select_from(Ticket).where(
            Ticket.status.in_([TicketStatus.PENDING, TicketStatus.PROCESSING, TicketStatus.ROUTED])
        )
        if role_condition is not None:
            pending_stmt = pending_stmt.where(role_condition)
        pending_result = await db.execute(pending_stmt)
        pending_count = pending_result.scalar() or 0

        # 高紧急数
        high_stmt = select(func.count()).select_from(Ticket).where(Ticket.urgency_level == UrgencyLevel.HIGH)
        if role_condition is not None:
            high_stmt = high_stmt.where(role_condition)
        high_result = await db.execute(high_stmt)
        high_priority_count = high_result.scalar() or 0

        # 超时数
        overdue_count = 0
        try:
            routed_stmt = select(Ticket).where(
                Ticket.status.in_([TicketStatus.PENDING, TicketStatus.PROCESSING, TicketStatus.ROUTED]),
                Ticket.urgency_level.isnot(None),
                Ticket.created_at.isnot(None),
            )
            if role_condition is not None:
                routed_stmt = routed_stmt.where(role_condition)
            routed_tickets_result = await db.execute(routed_stmt)
            routed_tickets = list(routed_tickets_result.scalars().all())
            for ticket in routed_tickets:
                is_timeout = await routing_service.check_sla_timeout(db, ticket)
                if is_timeout:
                    overdue_count += 1
        except Exception as e:
            logger.warning(f"SLA check failed: {e}")

        # 分类分布
        category_stmt = select(Ticket.issue_category, func.count()).group_by(Ticket.issue_category)
        if role_condition is not None:
            category_stmt = category_stmt.where(role_condition)
        category_result = await db.execute(category_stmt)
        category_distribution = {row[0] or "Unknown": row[1] for row in category_result.all()}

        # 近7日趋势
        seven_days_ago = datetime.now() - timedelta(days=7)
        daily_stmt = (
            select(func.date(Ticket.created_at), func.count())
            .where(Ticket.created_at >= seven_days_ago)
            .group_by(func.date(Ticket.created_at))
            .order_by(func.date(Ticket.created_at))
        )
        if role_condition is not None:
            daily_stmt = daily_stmt.where(role_condition)
        daily_result = await db.execute(daily_stmt)
        daily_trend = {str(row[0]): row[1] for row in daily_result.all()}

        stats = {
            "total_tickets": total_tickets,
            "pending_count": pending_count,
            "high_priority_count": high_priority_count,
            "overdue_count": overdue_count,
            "category_distribution": category_distribution,
            "daily_trend": daily_trend,
        }
        return ApiResponse(data=stats)
    except Exception as e:
        logger.error(f"Get dashboard stats failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.get("/subordinate-overview", response_model=ApiResponse)
async def get_subordinate_overview(
    role: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """获取下级角色的工单处理概览，高级别可查看低级别的待处理数和工单详情"""
    try:
        lower_roles = _get_lower_roles(role)
        if not lower_roles:
            return ApiResponse(data=[])

        result = []
        for sub_role in lower_roles:
            role_condition = Ticket.routing_decision.contains(sub_role)

            # 该角色工单总数
            total_stmt = select(func.count()).select_from(Ticket).where(role_condition)
            total_result = await db.execute(total_stmt)
            total_count = total_result.scalar() or 0

            # 待处理数
            pending_stmt = select(func.count()).select_from(Ticket).where(
                role_condition,
                Ticket.status.in_([TicketStatus.PENDING, TicketStatus.PROCESSING, TicketStatus.ROUTED]),
            )
            pending_result = await db.execute(pending_stmt)
            pending_count = pending_result.scalar() or 0

            # 已解决数
            resolved_stmt = select(func.count()).select_from(Ticket).where(
                role_condition,
                Ticket.status.in_([TicketStatus.RESOLVED, TicketStatus.CLOSED]),
            )
            resolved_result = await db.execute(resolved_stmt)
            resolved_count = resolved_result.scalar() or 0

            # 待处理工单列表（最多10条）
            pending_list_stmt = (
                select(Ticket)
                .where(
                    role_condition,
                    Ticket.status.in_([TicketStatus.PENDING, TicketStatus.PROCESSING, TicketStatus.ROUTED]),
                )
                .order_by(Ticket.created_at.desc())
                .limit(10)
            )
            pending_list_result = await db.execute(pending_list_stmt)
            pending_tickets = []
            for t in pending_list_result.scalars().all():
                pending_tickets.append({
                    "ticket_id": t.ticket_id,
                    "customer_name": t.customer_name or "未知",
                    "urgency_level": t.urgency_level,
                    "status": t.status,
                    "issue_category": t.issue_category,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                })

            # 角色显示名
            role_display = {
                "frontline_staff": "一线客服",
                "department_manager": "部门主管",
                "general_manager": "总经理",
            }

            result.append({
                "role": sub_role,
                "role_display": role_display.get(sub_role, sub_role),
                "total_count": total_count,
                "pending_count": pending_count,
                "resolved_count": resolved_count,
                "pending_tickets": pending_tickets,
            })

        return ApiResponse(data=result)
    except Exception as e:
        logger.error(f"Get subordinate overview failed: {e}")
        return ApiResponse(code=1, message=str(e))
