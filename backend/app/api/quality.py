import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.middleware.auth_middleware import get_current_user
from backend.app.models.models import User
from backend.app.schemas.common import ApiResponse
from backend.app.schemas.quality import (
    QualityTraceQuery,
    QualityDashboardQuery,
    QualityExportQuery,
    QualityTraceResponse,
    QualityDashboardResponse,
)
from backend.app.services.quality_service import QualityService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["质量追溯"])
quality_service = QualityService()


@router.get("/trace", response_model=ApiResponse)
async def quality_trace(
    model_number: Optional[str] = Query(None),
    batch_code: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    issue_category: Optional[str] = Query(None),
    order_type: Optional[str] = Query(None),
    group_by: str = Query("model"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """质量追溯查询"""
    try:
        query = QualityTraceQuery(
            model_number=model_number,
            batch_code=batch_code,
            start_date=start_date,
            end_date=end_date,
            issue_category=issue_category,
            order_type=order_type,
            group_by=group_by,
            page=page,
            page_size=page_size,
        )
        result = await quality_service.get_trace_data(db=db, query=query)
        return ApiResponse(data=result)
    except Exception as e:
        logger.error(f"Quality trace failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.get("/dashboard", response_model=ApiResponse)
async def quality_dashboard(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    model_number: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """质量分析看板数据"""
    try:
        query = QualityDashboardQuery(
            start_date=start_date,
            end_date=end_date,
            model_number=model_number,
        )
        result = await quality_service.get_dashboard_data(db=db, query=query)
        return ApiResponse(data=result)
    except Exception as e:
        logger.error(f"Quality dashboard failed: {e}")
        return ApiResponse(code=1, message=str(e))


@router.get("/export")
async def quality_export(
    format: str = Query("xlsx"),
    model_number: Optional[str] = Query(None),
    batch_code: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """质量报表导出（返回文件流）"""
    try:
        query = QualityExportQuery(
            format=format,
            model_number=model_number,
            batch_code=batch_code,
            start_date=start_date,
            end_date=end_date,
        )
        file_bytes = await quality_service.export_report(db=db, query=query)

        if format == "xlsx":
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = "quality_report.xlsx"
        else:
            media_type = "text/csv"
            filename = "quality_report.csv"

        return Response(
            content=file_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
            },
        )
    except Exception as e:
        logger.error(f"Quality export failed: {e}")
        raise e
