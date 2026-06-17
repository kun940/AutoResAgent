import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.middleware.auth_middleware import get_current_user
from backend.app.models.models import User
from backend.app.schemas.common import ApiResponse, PaginatedResponse
from backend.app.schemas.order import (
    OrderCreate,
    OrderStatusUpdate,
    OrderResponse,
    OrderListResponse,
    MappingRuleCreate,
    MappingRuleUpdate,
    MappingRuleResponse,
)
from backend.app.services.order_service import OrderService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["出单管理"])
order_service = OrderService()


@router.post("", response_model=ApiResponse)
async def create_order(
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动创建出单"""
    try:
        order = await order_service.create_order(db=db, data=data.model_dump())
        return ApiResponse(data=OrderResponse.model_validate(order))
    except Exception as e:
        logger.error(f"Create order failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.get("", response_model=PaginatedResponse)
async def list_orders(
    order_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    ticket_id: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """出单列表查询"""
    try:
        orders, total = await order_service.get_orders(
            db=db,
            order_type=order_type,
            status=status,
            ticket_id=ticket_id,
            department=department,
            page=page,
            page_size=page_size,
        )
        order_list = [OrderResponse.model_validate(o) for o in orders]
        return PaginatedResponse(total=total, page=page, page_size=page_size, data=order_list)
    except Exception as e:
        logger.error(f"List orders failed: {e}")
        return PaginatedResponse(code=1, message=str(e))


@router.get("/mapping-rules", response_model=ApiResponse)
async def list_mapping_rules(
    is_active: Optional[int] = Query(None),
    issue_category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询映射规则列表"""
    try:
        rules = await order_service.get_mapping_rules(
            db=db,
            is_active=is_active,
            issue_category=issue_category,
        )
        rule_list = [MappingRuleResponse.model_validate(r) for r in rules]
        return ApiResponse(data=rule_list)
    except Exception as e:
        logger.error(f"List mapping rules failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.post("/mapping-rules", response_model=ApiResponse)
async def create_mapping_rule(
    data: MappingRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """新增映射规则"""
    try:
        rule = await order_service.create_mapping_rule(db=db, data=data.model_dump())
        return ApiResponse(data=MappingRuleResponse.model_validate(rule))
    except Exception as e:
        logger.error(f"Create mapping rule failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.put("/mapping-rules/{rule_id}", response_model=ApiResponse)
async def update_mapping_rule(
    rule_id: int,
    data: MappingRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新映射规则"""
    try:
        rule = await order_service.update_mapping_rule(db=db, rule_id=rule_id, data=data.model_dump(exclude_none=True))
        if not rule:
            return ApiResponse(code=1, message=f"映射规则 {rule_id} 不存在")
        return ApiResponse(data=MappingRuleResponse.model_validate(rule))
    except Exception as e:
        logger.error(f"Update mapping rule failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.delete("/mapping-rules/{rule_id}", response_model=ApiResponse)
async def delete_mapping_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除映射规则（软删除）"""
    try:
        rule = await order_service.delete_mapping_rule(db=db, rule_id=rule_id)
        if not rule:
            return ApiResponse(code=1, message=f"映射规则 {rule_id} 不存在")
        return ApiResponse(data=MappingRuleResponse.model_validate(rule))
    except Exception as e:
        logger.error(f"Delete mapping rule failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.get("/by-ticket/{ticket_id}", response_model=ApiResponse)
async def get_orders_by_ticket(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """根据工单ID查关联出单"""
    try:
        orders = await order_service.get_orders_by_ticket(db=db, ticket_id=ticket_id)
        order_list = [OrderResponse.model_validate(o) for o in orders]
        return ApiResponse(data=order_list)
    except Exception as e:
        logger.error(f"Get orders by ticket failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.get("/{order_id}", response_model=ApiResponse)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """出单详情"""
    try:
        order = await order_service.get_order(db=db, order_id=order_id)
        if not order:
            return ApiResponse(code=1, message=f"出单 {order_id} 不存在")
        return ApiResponse(data=OrderResponse.model_validate(order))
    except Exception as e:
        logger.error(f"Get order failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.put("/{order_id}/status", response_model=ApiResponse)
async def update_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新出单状态"""
    try:
        order = await order_service.update_order_status(
            db=db,
            order_id=order_id,
            status=data.status,
            note=data.note,
            user_id=current_user.id,
        )
        if not order:
            return ApiResponse(code=1, message=f"出单 {order_id} 不存在")
        return ApiResponse(data=OrderResponse.model_validate(order))
    except ValueError as e:
        return ApiResponse(code=1, message=str(e))
    except Exception as e:
        logger.error(f"Update order status failed: {e}")
        return ApiResponse(code=1, message=str(e))
