import csv
import io
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, Form, File, UploadFile, Response
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.middleware.auth_middleware import get_current_user
from backend.app.models.models import EvidenceFile, Ticket, TicketLog, User
from backend.app.schemas.ticket import (
    TicketResponse,
    TicketStatusUpdateRequest,
    TicketEscalateRequest,
    TicketReassignRequest,
    ProcessingRecordResponse,
)
from backend.app.schemas.common import ApiResponse, PaginatedResponse
from backend.app.services.ticket_service import TicketService
from shared.constants import TicketStatus, TicketAction, UrgencyLevel

logger = logging.getLogger(__name__)

router = APIRouter()
ticket_service = TicketService()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads")
MAX_IMAGES = 5
MAX_IMAGE_SIZE = 10 * 1024 * 1024

# 批量操作单次最大数量
BATCH_MAX_SIZE = 50


# 处理记录：操作类型 -> 中文标签
ACTION_LABEL_MAP = {
    TicketAction.STATUS_CHANGE.value: "变更状态",
    TicketAction.ESCALATION.value: "升级工单",
    TicketAction.REASSIGN.value: "转派工单",
}


def _parse_log_detail(action: str, detail: Optional[str]) -> tuple[str, Optional[str]]:
    """从 TicketLog.detail 解析出 (change_summary, reason)。

    处理三种已知格式：
      status_change: "状态变更：a → b，备注：xxx"  或  "状态变更：a → b"
      escalation:    "紧急度升级：a → b，原因：xxx"
      reassign:      "转派：a → b(role)，原因：xxx"
    无法匹配时返回 (detail or "", None)。
    """
    if not detail:
        return "", None

    # 前缀 -> (前缀字符串, 原因分隔符)
    prefixes = {
        TicketAction.STATUS_CHANGE.value: ("状态变更：", "，备注："),
        TicketAction.ESCALATION.value: ("紧急度升级：", "，原因："),
        TicketAction.REASSIGN.value: ("转派：", "，原因："),
    }
    prefix, sep = prefixes.get(action, (None, None))
    if prefix is None or not detail.startswith(prefix):
        return detail, None

    body = detail[len(prefix):]
    if sep and sep in body:
        change_summary, reason = body.split(sep, 1)
        return change_summary, reason
    return body, None


# ===== 批量操作请求体 =====

class BatchReassignRequest(BaseModel):
    """批量转派请求"""
    ticket_ids: List[str]
    target_username: str
    target_role: str
    reason: str


class BatchEscalateRequest(BaseModel):
    """批量升级请求"""
    ticket_ids: List[str]
    reason: str


class BatchCloseRequest(BaseModel):
    """批量关闭请求"""
    ticket_ids: List[str]
    reason: str


# ===== 客诉提交接口 =====

@router.post("/complaints/submit", response_model=ApiResponse)
async def submit_complaint(
    text: str = Form(...),
    customer_name: Optional[str] = Form(None),
    customer_phone: Optional[str] = Form(None),
    images: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
):
    try:
        image_paths = []
        if images:
            if len(images) > MAX_IMAGES:
                return ApiResponse(code=1, message=f"最多上传{MAX_IMAGES}张图片")
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            for idx, img in enumerate(images):
                content = await img.read()
                if content:
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
            customer_name=customer_name,
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

        return ApiResponse(data=result)
    except Exception as e:
        logger.error(f"Submit complaint failed: {e}")
        return ApiResponse(code=1, message=str(e))


# ===== 工单列表接口 =====

@router.get("/tickets", response_model=PaginatedResponse)
async def list_tickets(
    status: Optional[str] = Query(None),
    urgency_level: Optional[str] = Query(None),
    target_role: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        tickets, total = await ticket_service.list_tickets(
            db=db,
            status=status,
            urgency_level=urgency_level,
            target_role=target_role,
            page=page,
            page_size=page_size,
        )
        ticket_list = [TicketResponse.model_validate(t) for t in tickets]
        return PaginatedResponse(total=total, page=page, page_size=page_size, data=ticket_list)
    except Exception as e:
        logger.error(f"List tickets failed: {e}")
        return PaginatedResponse(code=1, message=str(e))


# ===== v1.1 搜索接口（必须在 /tickets/{ticket_id} 之前定义）=====

@router.get("/tickets/search", response_model=PaginatedResponse)
async def search_tickets(
    keyword: str = Query(..., min_length=2),
    status: Optional[str] = Query(None),
    urgency_level: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """关键词搜索工单（搜索范围：ticket_id, customer_name, customer_phone, raw_input）"""
    try:
        conditions = [
            or_(
                Ticket.ticket_id.contains(keyword),
                Ticket.customer_name.contains(keyword),
                Ticket.customer_phone.contains(keyword),
                Ticket.raw_input.contains(keyword),
            )
        ]
        if status:
            conditions.append(Ticket.status == status)
        if urgency_level:
            conditions.append(Ticket.urgency_level == urgency_level)

        # 查询总数
        count_stmt = select(func.count()).select_from(Ticket).where(*conditions)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        # 分页查询
        stmt = (
            select(Ticket)
            .where(*conditions)
            .order_by(Ticket.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        tickets = list(result.scalars().all())

        ticket_list = [TicketResponse.model_validate(t) for t in tickets]
        return PaginatedResponse(total=total, page=page, page_size=page_size, data=ticket_list)
    except Exception as e:
        logger.error(f"Search tickets failed: {e}")
        return PaginatedResponse(code=1, message=str(e))


# ===== v1.1 导出接口（必须在 /tickets/{ticket_id} 之前定义）=====

@router.get("/tickets/export")
async def export_tickets(
    format: str = Query("xlsx"),
    status: Optional[str] = Query(None),
    urgency_level: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出工单数据"""
    # 中文映射表
    _CATEGORY_MAP = {
        "Missing_Parts": "配件缺失", "Operation_Error": "操作错误",
        "Software_Bug": "软件缺陷", "Hardware_Malfunction": "硬件故障",
        "Hardware_Thermal_Runaway": "热失控", "Electrical_Leakage": "漏电问题",
        "Batch_Defect": "批次缺陷", "Safety_Hazard": "安全隐患", "Other": "其他",
    }
    _URGENCY_MAP = {
        "High_Priority": "高紧急", "Medium_Priority": "中紧急", "Low_Priority": "低紧急",
    }
    _WARRANTY_MAP = {
        "In_Warranty": "保内", "Out_of_Warranty": "保外", "Unknown": "未知",
    }
    _ROUTING_MAP = {
        "frontline_staff_queue": "一线客服队列",
        "department_manager_queue": "部门主管队列",
        "general_manager_dashboard": "总经理看板",
    }
    _STATUS_MAP = {
        "pending": "待处理", "processing": "处理中", "routed": "已路由",
        "resolved": "已解决", "closed": "已关闭", "cancelled": "已取消",
    }

    try:
        conditions = []
        if status:
            conditions.append(Ticket.status == status)
        if urgency_level:
            conditions.append(Ticket.urgency_level == urgency_level)
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            conditions.append(Ticket.created_at >= start_dt)
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt + timedelta(days=1)
            conditions.append(Ticket.created_at < end_dt)

        stmt = select(Ticket).order_by(Ticket.created_at.desc())
        if conditions:
            stmt = stmt.where(*conditions)
        result = await db.execute(stmt)
        tickets = list(result.scalars().all())

        # 表头
        headers = [
            "工单编号", "客户姓名", "客户电话", "客诉内容",
            "问题分类", "紧急度", "质保状态", "路由决策",
            "状态", "创建时间", "解决时间",
        ]

        # 数据行
        rows = []
        for t in tickets:
            raw_status = t.status if isinstance(t.status, str) else t.status.value
            rows.append([
                t.ticket_id or "",
                t.customer_name or "",
                t.customer_phone or "",
                (t.raw_input or "")[:200],  # 截断过长内容
                _CATEGORY_MAP.get(t.issue_category, t.issue_category or ""),
                _URGENCY_MAP.get(t.urgency_level, t.urgency_level or ""),
                _WARRANTY_MAP.get(t.warranty_status, t.warranty_status or ""),
                _ROUTING_MAP.get(t.routing_decision, t.routing_decision or ""),
                _STATUS_MAP.get(raw_status, raw_status),
                t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "",
                t.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if t.resolved_at else "",
            ])

        if format == "xlsx":
            try:
                file_bytes = _export_xlsx(headers, rows)
            except ImportError:
                # openpyxl 未安装，自动降级为 CSV
                file_bytes = _export_csv(headers, rows)
                media_type = "text/csv"
                filename = "tickets_export.csv"
            else:
                media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                filename = "tickets_export.xlsx"
        else:
            file_bytes = _export_csv(headers, rows)
            media_type = "text/csv"
            filename = "tickets_export.csv"

        return Response(
            content=file_bytes,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.error(f"Export tickets failed: {e}")
        raise e


# ===== v1.1 批量操作接口（必须在 /tickets/{ticket_id} 之前定义）=====

@router.post("/tickets/batch/reassign", response_model=ApiResponse)
async def batch_reassign(
    request: BatchReassignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量转派工单"""
    try:
        if len(request.ticket_ids) > BATCH_MAX_SIZE:
            return ApiResponse(code=1, message=f"单次最多操作{BATCH_MAX_SIZE}条工单")

        success_count = 0
        failed_list = []

        for ticket_id in request.ticket_ids:
            try:
                ticket = await ticket_service.reassign(
                    db=db,
                    ticket_id=ticket_id,
                    target_username=request.target_username,
                    target_role=request.target_role,
                    reason=request.reason,
                    operator_id=current_user.id,
                )
                if ticket:
                    success_count += 1
                else:
                    failed_list.append({"ticket_id": ticket_id, "reason": "工单不存在"})
            except ValueError as e:
                failed_list.append({"ticket_id": ticket_id, "reason": str(e)})
            except Exception as e:
                failed_list.append({"ticket_id": ticket_id, "reason": str(e)})

        return ApiResponse(data={
            "success_count": success_count,
            "failed_count": len(failed_list),
            "failed_list": failed_list,
        })
    except Exception as e:
        logger.error(f"Batch reassign failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.post("/tickets/batch/escalate", response_model=ApiResponse)
async def batch_escalate(
    request: BatchEscalateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量升级工单"""
    try:
        if len(request.ticket_ids) > BATCH_MAX_SIZE:
            return ApiResponse(code=1, message=f"单次最多操作{BATCH_MAX_SIZE}条工单")

        success_count = 0
        failed_list = []

        for ticket_id in request.ticket_ids:
            try:
                # 查询工单当前紧急度，自动升级一级
                ticket = await ticket_service.get_ticket(db=db, ticket_id=ticket_id)
                if not ticket:
                    failed_list.append({"ticket_id": ticket_id, "reason": "工单不存在"})
                    continue

                # 根据当前紧急度确定升级目标
                current_level = ticket.urgency_level
                if current_level == UrgencyLevel.LOW.value:
                    to_level = UrgencyLevel.MEDIUM.value
                elif current_level == UrgencyLevel.MEDIUM.value:
                    to_level = UrgencyLevel.HIGH.value
                else:
                    failed_list.append({"ticket_id": ticket_id, "reason": "已是最高紧急度，无法继续升级"})
                    continue

                result = await ticket_service.escalate(
                    db=db,
                    ticket_id=ticket_id,
                    to_level=to_level,
                    reason=request.reason,
                    operator_id=current_user.id,
                )
                if result:
                    success_count += 1
                else:
                    failed_list.append({"ticket_id": ticket_id, "reason": "升级失败"})
            except Exception as e:
                failed_list.append({"ticket_id": ticket_id, "reason": str(e)})

        return ApiResponse(data={
            "success_count": success_count,
            "failed_count": len(failed_list),
            "failed_list": failed_list,
        })
    except Exception as e:
        logger.error(f"Batch escalate failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.post("/tickets/batch/close", response_model=ApiResponse)
async def batch_close(
    request: BatchCloseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量关闭工单"""
    try:
        if len(request.ticket_ids) > BATCH_MAX_SIZE:
            return ApiResponse(code=1, message=f"单次最多操作{BATCH_MAX_SIZE}条工单")

        success_count = 0
        failed_list = []

        for ticket_id in request.ticket_ids:
            try:
                # 先将工单状态更新为resolved
                ticket = await ticket_service.get_ticket(db=db, ticket_id=ticket_id)
                if not ticket:
                    failed_list.append({"ticket_id": ticket_id, "reason": "工单不存在"})
                    continue

                # 根据当前状态逐步流转到closed
                current_status = ticket.status if isinstance(ticket.status, str) else ticket.status.value
                if current_status == TicketStatus.RESOLVED.value:
                    # resolved -> closed
                    result = await ticket_service.update_status(
                        db=db, ticket_id=ticket_id, status=TicketStatus.CLOSED.value, note=request.reason, operator_id=current_user.id,
                    )
                    if result:
                        success_count += 1
                    else:
                        failed_list.append({"ticket_id": ticket_id, "reason": "关闭失败"})
                elif current_status == TicketStatus.ROUTED.value:
                    # routed -> resolved -> closed
                    result1 = await ticket_service.update_status(
                        db=db, ticket_id=ticket_id, status=TicketStatus.RESOLVED.value, note=request.reason, operator_id=current_user.id,
                    )
                    if result1:
                        result2 = await ticket_service.update_status(
                            db=db, ticket_id=ticket_id, status=TicketStatus.CLOSED.value, note=request.reason, operator_id=current_user.id,
                        )
                        if result2:
                            success_count += 1
                        else:
                            failed_list.append({"ticket_id": ticket_id, "reason": "关闭失败"})
                    else:
                        failed_list.append({"ticket_id": ticket_id, "reason": "解决失败"})
                else:
                    failed_list.append({"ticket_id": ticket_id, "reason": f"当前状态 {current_status} 不可直接关闭"})
            except ValueError as e:
                failed_list.append({"ticket_id": ticket_id, "reason": str(e)})
            except Exception as e:
                failed_list.append({"ticket_id": ticket_id, "reason": str(e)})

        return ApiResponse(data={
            "success_count": success_count,
            "failed_count": len(failed_list),
            "failed_list": failed_list,
        })
    except Exception as e:
        logger.error(f"Batch close failed: {e}")
        return ApiResponse(code=1, message=str(e))


# ===== v2.1 处理记录接口（固定路由，必须放在 /tickets/{ticket_id} 之前）=====

@router.get("/tickets/processing-records", response_model=PaginatedResponse)
async def get_processing_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前账号的工单处理记录（变更状态/升级/转派）"""
    try:
        # 日期解析
        start_dt = None
        end_dt = None
        try:
            if start_date:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            if end_date:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            return PaginatedResponse(code=1, message="日期格式需为 YYYY-MM-DD")

        # 过滤条件
        conditions = [
            TicketLog.operator_id == current_user.id,
            TicketLog.action.in_([
                TicketAction.STATUS_CHANGE.value,
                TicketAction.ESCALATION.value,
                TicketAction.REASSIGN.value,
            ]),
        ]
        if start_dt:
            conditions.append(TicketLog.created_at >= start_dt)
        if end_dt:
            conditions.append(TicketLog.created_at < end_dt)

        # 计数
        count_stmt = (
            select(func.count())
            .select_from(TicketLog)
            .join(Ticket, TicketLog.ticket_id == Ticket.ticket_id)
            .where(*conditions)
        )
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        # 分页查询（关联工单与操作人）
        stmt = (
            select(TicketLog, Ticket, User)
            .join(Ticket, TicketLog.ticket_id == Ticket.ticket_id)
            .outerjoin(User, TicketLog.operator_id == User.id)
            .where(*conditions)
            .order_by(TicketLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        rows = list(result.all())

        records = []
        for log, ticket, operator in rows:
            change_summary, reason = _parse_log_detail(log.action, log.detail)
            raw_status = ticket.status if isinstance(ticket.status, str) else (
                ticket.status.value if ticket.status else None
            )
            records.append(ProcessingRecordResponse(
                log_id=log.id,
                action=log.action,
                action_label=ACTION_LABEL_MAP.get(log.action, log.action or ""),
                ticket_id=log.ticket_id,
                ticket_customer_name=ticket.customer_name,
                ticket_issue_category=ticket.issue_category,
                ticket_urgency_level=ticket.urgency_level,
                ticket_status=raw_status,
                operator_id=log.operator_id,
                operator_username=operator.username if operator else None,
                change_summary=change_summary,
                reason=reason,
                detail_raw=log.detail,
                created_at=log.created_at,
            ).model_dump())

        return PaginatedResponse(total=total, page=page, page_size=page_size, data=records)
    except Exception as e:
        logger.error(f"Get processing records failed: {e}")
        return PaginatedResponse(code=1, message=str(e))


# ===== 工单详情/操作接口（参数化路由，必须放在固定路由之后）=====

@router.get("/tickets/{ticket_id}", response_model=ApiResponse)
async def get_ticket(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        ticket = await ticket_service.get_ticket(db=db, ticket_id=ticket_id)
        if not ticket:
            return ApiResponse(code=1, message=f"工单 {ticket_id} 不存在")
        ticket_data = TicketResponse.model_validate(ticket)

        stmt = select(EvidenceFile).where(EvidenceFile.ticket_id == ticket_id)
        result = await db.execute(stmt)
        files = list(result.scalars().all())
        if files:
            ticket_data.evidence_images = [f.file_path for f in files if f.file_type == "image"]

        return ApiResponse(data=ticket_data.model_dump())
    except Exception as e:
        logger.error(f"Get ticket failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.put("/tickets/{ticket_id}/status", response_model=ApiResponse)
async def update_ticket_status(
    ticket_id: str,
    request: TicketStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        ticket = await ticket_service.update_status(
            db=db,
            ticket_id=ticket_id,
            status=request.status,
            note=request.note,
            operator_id=current_user.id,
        )
        if not ticket:
            return ApiResponse(code=1, message=f"工单 {ticket_id} 不存在")
        return ApiResponse(data=TicketResponse.model_validate(ticket))
    except ValueError as e:
        return ApiResponse(code=1, message=str(e))
    except Exception as e:
        logger.error(f"Update status failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.post("/tickets/{ticket_id}/escalate", response_model=ApiResponse)
async def escalate_ticket(
    ticket_id: str,
    request: TicketEscalateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        ticket = await ticket_service.escalate(
            db=db,
            ticket_id=ticket_id,
            to_level=request.to_level,
            reason=request.reason,
            operator_id=current_user.id,
        )
        if not ticket:
            return ApiResponse(code=1, message=f"工单 {ticket_id} 不存在")
        return ApiResponse(data=TicketResponse.model_validate(ticket))
    except Exception as e:
        logger.error(f"Escalate ticket failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.post("/tickets/{ticket_id}/reassign", response_model=ApiResponse)
async def reassign_ticket(
    ticket_id: str,
    request: TicketReassignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        ticket = await ticket_service.reassign(
            db=db,
            ticket_id=ticket_id,
            target_username=request.target_username,
            target_role=request.target_role,
            reason=request.reason,
            operator_id=current_user.id,
        )
        if not ticket:
            return ApiResponse(code=1, message=f"工单 {ticket_id} 不存在")
        return ApiResponse(data=TicketResponse.model_validate(ticket))
    except ValueError as e:
        return ApiResponse(code=1, message=str(e))
    except Exception as e:
        logger.error(f"Reassign ticket failed: {e}")
        return ApiResponse(code=1, message=str(e))


# ===== 导出辅助函数 =====

def _export_xlsx(headers: list, rows: list) -> bytes:
    """使用openpyxl导出Excel"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "工单数据"

    # 写入表头
    ws.append(headers)
    header_font_white = Font(bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    for cell in ws[1]:
        cell.font = header_font_white
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # 写入数据
    for row in rows:
        ws.append(row)

    # 自动调整列宽
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except Exception:
                pass
        adjusted_width = min(max_length + 4, 50)
        ws.column_dimensions[column].width = adjusted_width

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def _export_csv(headers: list, rows: list) -> bytes:
    """使用csv模块导出CSV（UTF-8 BOM编码）"""
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")
