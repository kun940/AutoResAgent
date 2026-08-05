import logging
import os
import re
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

# ticket_id 仅允许字母/数字/下划线/连字符，杜绝 ../ 路径逃逸
_TICKET_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_save_path(base_dir: str, ticket_id: str, original_filename: str) -> str:
    """构造安全的证据文件保存路径，防止路径遍历。

    - ticket_id 白名单校验；
    - 文件名仅取 basename，并清洗路径分隔符与 .. 残留；
    - 解析真实路径后校验仍位于 base_dir 之下。
    非法输入抛出 ValueError。
    """
    if not ticket_id or not _TICKET_ID_PATTERN.match(ticket_id):
        raise ValueError(f"非法的 ticket_id: {ticket_id!r}")

    safe_name = os.path.basename(original_filename) if original_filename else ""
    if not safe_name:
        raise ValueError("文件名不能为空")
    safe_name = (
        safe_name.replace(os.sep, "_").replace("/", "_")
        .replace("\\", "_").replace("..", "_")
    )
    if not safe_name or safe_name in {".", "_"}:
        raise ValueError("文件名无效")

    save_dir = os.path.join(base_dir, ticket_id)
    os.makedirs(save_dir, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    file_path = os.path.join(save_dir, unique_name)

    base_real = os.path.realpath(os.path.abspath(base_dir))
    file_real = os.path.realpath(os.path.abspath(file_path))
    if not (file_real == base_real or file_real.startswith(base_real + os.sep)):
        raise ValueError("文件保存路径越界，已拒绝")

    return file_path


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

        try:
            file_path = _safe_save_path(settings.EVIDENCE_BASE_DIR, ticket_id, file.filename)
        except ValueError as e:
            return ApiResponse(code=1, message=str(e))

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
