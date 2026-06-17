from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class OrderCreate(BaseModel):
    """手动创建出单请求"""
    ticket_id: str
    order_type: str
    department: Optional[str] = None
    sla_hours: int = 48
    material_list: Optional[list] = None
    remark: Optional[str] = None


class OrderStatusUpdate(BaseModel):
    """更新出单状态请求"""
    status: str
    note: Optional[str] = None


class OrderResponse(BaseModel):
    """出单响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_no: str
    ticket_id: str
    order_type: str
    order_type_label: str
    status: str
    priority: str
    department: str
    sla_hours: int
    deadline: Optional[datetime] = None
    material_list: Optional[list] = None
    issue_category: Optional[str] = None
    urgency_level: Optional[str] = None
    model_number: Optional[str] = None
    batch_code: Optional[str] = None
    assigned_to: Optional[int] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[int] = None
    remark: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OrderListResponse(BaseModel):
    """出单列表响应"""
    total: int
    page: int
    page_size: int
    data: List[OrderResponse]


class MappingRuleCreate(BaseModel):
    """创建映射规则请求"""
    issue_category: str
    urgency_level: str
    order_type: str
    department: str
    sla_hours: int = 48
    priority: int = 0
    description: Optional[str] = None


class MappingRuleUpdate(BaseModel):
    """更新映射规则请求"""
    order_type: Optional[str] = None
    department: Optional[str] = None
    sla_hours: Optional[int] = None
    is_active: Optional[int] = None
    priority: Optional[int] = None
    description: Optional[str] = None


class MappingRuleResponse(BaseModel):
    """映射规则响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_category: str
    urgency_level: str
    order_type: str
    department: str
    sla_hours: int
    is_active: int
    priority: int
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
