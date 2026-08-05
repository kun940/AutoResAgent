from datetime import datetime, date
from typing import Optional, List, Dict, Any

from pydantic import BaseModel


class QualityTraceQuery(BaseModel):
    """质量追溯查询参数"""
    model_number: Optional[str] = None
    batch_code: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    issue_category: Optional[str] = None
    action_type: Optional[str] = None  # v1.2: 处理动作类型筛选（原 order_type）
    archive_complete: Optional[int] = None  # v1.2 新增：归档完整性筛选 1=完整 0=部分缺失
    group_by: str = "model"  # model/batch/date/category
    page: int = 1
    page_size: int = 20


class QualityDashboardQuery(BaseModel):
    """质量看板查询参数"""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    model_number: Optional[str] = None


class QualityExportQuery(BaseModel):
    """质量报表导出参数"""
    format: str = "xlsx"  # csv/xlsx
    model_number: Optional[str] = None
    batch_code: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class QualityTraceGroup(BaseModel):
    """质量追溯分组数据"""
    dimension: str
    ticket_count: int = 0
    archived_count: int = 0  # v1.2: 归档工单数（原 order_count）
    category_distribution: Optional[Dict[str, int]] = None
    action_type_distribution: Optional[Dict[str, int]] = None  # v1.2: 处理动作分布（原 order_type_distribution）
    urgency_distribution: Optional[Dict[str, int]] = None
    avg_resolution_days: Optional[float] = None
    high_priority_count: int = 0


class QualityTraceResponse(BaseModel):
    """质量追溯响应"""
    summary: Dict[str, Any]
    groups: List[QualityTraceGroup]


class QualityDashboardResponse(BaseModel):
    """质量看板响应"""
    overview: Dict[str, Any]
    trend: Dict[str, Any]
    top_models: List[Dict[str, Any]]
    category_distribution: Dict[str, int]
    action_type_distribution: Dict[str, int]  # v1.2: 处理动作分布（原 order_type_distribution）
