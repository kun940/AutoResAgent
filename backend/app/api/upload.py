import logging
import os
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.models.models import EvidenceFile
from backend.app.schemas.common import ApiResponse
from backend.app.config import settings
from shared.constants import FileType

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".mp4", ".avi", ".mov", ".pdf", ".doc", ".docx"}
MAX_FILE_SIZE = 50 * 1024 * 1024


@router.post("/evidence", response_model=ApiResponse)
async def upload_evidence(
    ticket_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        if not file.filename:
            return ApiResponse(code=1, message="文件名不能为空")

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return ApiResponse(code=1, message=f"不支持的文件类型：{ext}")

        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            return ApiResponse(code=1, message="文件大小超过50MB限制")

        file_type = _determine_file_type(ext)

        save_dir = os.path.join(settings.EVIDENCE_BASE_DIR, ticket_id)
        os.makedirs(save_dir, exist_ok=True)

        unique_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
        file_path = os.path.join(save_dir, unique_name)

        import aiofiles
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        evidence = EvidenceFile(
            ticket_id=ticket_id,
            file_path=file_path,
            file_type=file_type,
            file_size=len(content),
        )
        db.add(evidence)
        await db.flush()

        return ApiResponse(data={
            "id": evidence.id,
            "ticket_id": ticket_id,
            "file_path": file_path,
            "file_type": file_type,
            "file_size": len(content),
        })
    except Exception as e:
        logger.error(f"Upload evidence failed: {e}")
        return ApiResponse(code=1, message=str(e))


def _determine_file_type(ext: str) -> str:
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
    video_exts = {".mp4", ".avi", ".mov"}
    if ext in image_exts:
        return FileType.IMAGE
    elif ext in video_exts:
        return FileType.VIDEO
    else:
        return FileType.DOCUMENT
