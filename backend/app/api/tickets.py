import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Form, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.models.models import EvidenceFile
from backend.app.schemas.ticket import (
    TicketResponse,
    TicketStatusUpdateRequest,
    TicketEscalateRequest,
    TicketReassignRequest,
)
from backend.app.schemas.common import ApiResponse, PaginatedResponse
from backend.app.services.ticket_service import TicketService

logger = logging.getLogger(__name__)

router = APIRouter()
ticket_service = TicketService()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads")
MAX_IMAGES = 5
MAX_IMAGE_SIZE = 10 * 1024 * 1024


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


@router.get("/tickets", response_model=PaginatedResponse)
async def list_tickets(
    status: Optional[str] = Query(None),
    urgency_level: Optional[str] = Query(None),
    target_role: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
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


@router.get("/tickets/{ticket_id}", response_model=ApiResponse)
async def get_ticket(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
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
            image_types = {"jpg", "jpeg", "png", "gif", "bmp", "webp"}
            ticket_data.evidence_images = [f.file_path for f in files if f.file_type == "image"]

        return ApiResponse(data=ticket_data)
    except Exception as e:
        logger.error(f"Get ticket failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.put("/tickets/{ticket_id}/status", response_model=ApiResponse)
async def update_ticket_status(
    ticket_id: str,
    request: TicketStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        ticket = await ticket_service.update_status(
            db=db,
            ticket_id=ticket_id,
            status=request.status,
            note=request.note,
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
):
    try:
        ticket = await ticket_service.escalate(
            db=db,
            ticket_id=ticket_id,
            to_level=request.to_level,
            reason=request.reason,
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
):
    try:
        ticket = await ticket_service.reassign(
            db=db,
            ticket_id=ticket_id,
            target_username=request.target_username,
            target_role=request.target_role,
            reason=request.reason,
        )
        if not ticket:
            return ApiResponse(code=1, message=f"工单 {ticket_id} 不存在")
        return ApiResponse(data=TicketResponse.model_validate(ticket))
    except ValueError as e:
        return ApiResponse(code=1, message=str(e))
    except Exception as e:
        logger.error(f"Reassign ticket failed: {e}")
        return ApiResponse(code=1, message=str(e))
