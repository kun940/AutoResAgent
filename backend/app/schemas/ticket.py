from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field

from shared.constants import UrgencyLevel, TicketStatus, IssueCategory, BusinessImpact, WarrantyStatus


class ExtractedDataSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: Optional[str] = None
    model_number: Optional[str] = None
    batch_code: Optional[str] = None
    core_fault_desc: Optional[str] = None
    evidence_images: Optional[List[str]] = None
    evidence_videos: Optional[List[str]] = None


class AgentAssessmentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    issue_category: Optional[str] = None
    business_impact: Optional[str] = None
    urgency_level: Optional[str] = None
    warranty_status: Optional[str] = None


class ComplaintSubmitRequest(BaseModel):
    text: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticket_id: str
    extracted_data: Optional[ExtractedDataSchema] = None
    agent_business_assessment: Optional[AgentAssessmentSchema] = None
    routing_decision: Optional[str] = None
    auto_reply_sent: Optional[str] = None
    sop_applied: Optional[str] = None
    status: str = TicketStatus.PENDING
    urgency_level: Optional[str] = None
    issue_category: Optional[str] = None
    warranty_status: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    assigned_to: Optional[int] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    evidence_images: Optional[List[str]] = None
    # v1.3: 图片分析结果
    image_analysis: Optional[dict] = None


class TicketListQuery(BaseModel):
    status: Optional[str] = None
    urgency_level: Optional[str] = None
    issue_category: Optional[str] = None
    page: int = 1
    page_size: int = 20


class TicketStatusUpdateRequest(BaseModel):
    status: str
    note: Optional[str] = None


class TicketEscalateRequest(BaseModel):
    to_level: str
    reason: str


class TicketReassignRequest(BaseModel):
    target_username: str
    target_role: str
    reason: str


class ProcessingRecordResponse(BaseModel):
    """工单处理记录响应（当前账号的状态变更/升级/转派操作记录）"""
    model_config = ConfigDict(from_attributes=True)

    log_id: int
    action: str
    action_label: str
    ticket_id: str
    ticket_customer_name: Optional[str] = None
    ticket_issue_category: Optional[str] = None
    ticket_urgency_level: Optional[str] = None
    ticket_status: Optional[str] = None
    operator_id: Optional[int] = None
    operator_username: Optional[str] = None
    change_summary: str
    reason: Optional[str] = None
    detail_raw: Optional[str] = None
    created_at: Optional[datetime] = None
