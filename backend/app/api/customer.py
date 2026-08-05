import logging
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.models.models import Ticket, TicketLog, EvidenceFile
from backend.app.schemas.common import ApiResponse
from backend.app.services.ticket_service import TicketService
from shared.constants import TicketStatus, UrgencyLevel, IssueCategory, TicketAction

logger = logging.getLogger(__name__)

router = APIRouter()
ticket_service = TicketService()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads")
MAX_IMAGES = 5
MAX_IMAGE_SIZE = 10 * 1024 * 1024

URGENCY_LABELS = {
    "High_Priority": "高紧急",
    "Medium_Priority": "中紧急",
    "Low_Priority": "低紧急",
}

STATUS_LABELS = {
    "pending": "待处理",
    "processing": "处理中",
    "routed": "已路由",
    "resolved": "已解决",
    "closed": "已关闭",
    "cancelled": "已取消",
}

CATEGORY_LABELS = {
    "Missing_Parts": "配件缺失",
    "Operation_Error": "操作错误",
    "Software_Bug": "软件缺陷",
    "Hardware_Malfunction": "硬件故障",
    "Hardware_Thermal_Runaway": "热失控",
    "Electrical_Leakage": "漏电问题",
    "Batch_Defect": "批次缺陷",
    "Safety_Hazard": "安全隐患",
    "Other": "其他",
}

URGENCY_DEPARTMENT = {
    "Low_Priority": "售后服务部",
    "Medium_Priority": "技术质量部",
    "High_Priority": "总经理办公室",
}

STATUS_ORDER = {
    "pending": 0,
    "processing": 1,
    "routed": 2,
    "resolved": 3,
    "closed": 4,
    "cancelled": 5,
}


@router.post("/submit", response_model=ApiResponse)
async def customer_submit(
    text: str = Form(""),
    customer_phone: str = Form(None),
    images: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
):
    if not text or not text.strip():
        return ApiResponse(code=1, message="客诉内容不能为空")

    if images and len(images) > MAX_IMAGES:
        return ApiResponse(code=1, message=f"最多上传{MAX_IMAGES}张图片")

    image_paths = []
    if images:
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    for idx, img in enumerate(images):
        content = await img.read()
        if len(content) > MAX_IMAGE_SIZE:
            return ApiResponse(code=1, message=f"图片{idx + 1}大小超过10MB限制")

        ext = os.path.splitext(img.filename)[1] if img.filename else ".jpg"
        filename = f"{uuid.uuid4().hex[:8]}_{idx}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(content)

        image_paths.append(filepath)

    result = await ticket_service.submit_complaint(
        db=db,
        text=text,
        customer_phone=customer_phone,
        image_paths=image_paths if image_paths else None,
    )

    for path in image_paths:
        filename = os.path.basename(path)
        ext = os.path.splitext(filename)[1].lstrip(".") if filename else "jpg"
        file_size = os.path.getsize(path) if os.path.exists(path) else None
        evidence = EvidenceFile(
            ticket_id=result["ticket_id"],
            file_path=f"/static/uploads/{filename}",
            file_type="image",
            file_size=file_size,
        )
        db.add(evidence)
    await db.flush()

    ticket = await ticket_service.get_ticket(db=db, ticket_id=result["ticket_id"])
    created_at = ticket.created_at.isoformat() if ticket and ticket.created_at else None

    urgency = result.get("urgency_level", "Medium_Priority")
    status = result.get("status", "routed")
    category = result.get("issue_category", "Other")

    response_data = {
        "ticket_id": result["ticket_id"],
        "urgency_level": urgency,
        "urgency_label": URGENCY_LABELS.get(urgency, urgency),
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "issue_category": category,
        "issue_category_label": CATEGORY_LABELS.get(category, category),
        "auto_reply": result.get("auto_reply_sent", ""),
        "created_at": created_at,
    }

    return ApiResponse(data=response_data)


@router.get("/ticket/{ticket_id}", response_model=ApiResponse)
async def customer_get_ticket(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
):
    ticket = await ticket_service.get_ticket(db=db, ticket_id=ticket_id)
    if not ticket:
        return ApiResponse(code=1, message="工单不存在")

    urgency = ticket.urgency_level or "Medium_Priority"
    status = ticket.status if isinstance(ticket.status, str) else ticket.status.value
    category = ticket.issue_category or "Other"

    stmt = select(TicketLog).where(TicketLog.ticket_id == ticket_id).order_by(TicketLog.created_at)
    log_result = await db.execute(stmt)
    logs = list(log_result.scalars().all())

    timeline = _build_timeline(ticket, logs, status)

    return ApiResponse(data={
        "ticket_id": ticket.ticket_id,
        "urgency_level": urgency,
        "urgency_label": URGENCY_LABELS.get(urgency, urgency),
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "issue_category": category,
        "issue_category_label": CATEGORY_LABELS.get(category, category),
        "auto_reply": ticket.auto_reply_sent or "",
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "timeline": timeline,
    })


def _build_timeline(ticket: Ticket, logs: list, status: str) -> list:
    timeline = []
    status_rank = STATUS_ORDER.get(status, 0)

    created_time = ticket.created_at.strftime("%H:%M") if ticket.created_at else ""

    timeline.append({
        "time": created_time,
        "event": "客诉已接收",
        "status": "done",
    })

    if status_rank >= STATUS_ORDER.get("processing", 1):
        assess_time = created_time
        for log in logs:
            if log.action == TicketAction.STATUS_CHANGE and "创建" in (log.detail or ""):
                assess_time = log.created_at.strftime("%H:%M") if log.created_at else created_time
                break
        timeline.append({
            "time": assess_time,
            "event": "AI智能定级",
            "status": "done",
        })

    if status_rank >= STATUS_ORDER.get("routed", 2):
        route_time = created_time
        for log in logs:
            if log.action == TicketAction.STATUS_CHANGE and "路由" in (log.detail or ""):
                route_time = log.created_at.strftime("%H:%M") if log.created_at else created_time
                break
        department = URGENCY_DEPARTMENT.get(ticket.urgency_level, "技术质量部")
        timeline.append({
            "time": route_time,
            "event": f"路由至{department}",
            "status": "done",
        })

    if status_rank >= STATUS_ORDER.get("resolved", 3):
        resolved_time = ticket.resolved_at.strftime("%H:%M") if ticket.resolved_at else ""
        timeline.append({
            "time": resolved_time,
            "event": "已解决",
            "status": "done",
        })

    if status_rank >= STATUS_ORDER.get("closed", 4):
        closed_time = ""
        for log in reversed(logs):
            if "closed" in (log.detail or "").lower() or "关闭" in (log.detail or ""):
                closed_time = log.created_at.strftime("%H:%M") if log.created_at else ""
                break
        timeline.append({
            "time": closed_time,
            "event": "已关闭",
            "status": "done",
        })

    if status_rank < STATUS_ORDER.get("resolved", 3):
        timeline.append({
            "time": "",
            "event": "等待技术人员处理",
            "status": "active",
        })

    return timeline
