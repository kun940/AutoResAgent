from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class SopKnowledgeCreate(BaseModel):
    issue_category: str
    title: str
    content: str
    urgency_level: Optional[str] = None
    keywords: Optional[List[str]] = None
    # v1.3: 紧急止损动作列表
    emergency_actions: Optional[List[str]] = None
    # v1.3: 适用场景标签
    scenario_tags: Optional[List[str]] = None


class SopKnowledgeUpdate(BaseModel):
    issue_category: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    urgency_level: Optional[str] = None
    keywords: Optional[List[str]] = None
    is_active: Optional[int] = None


class SopKnowledgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_category: str
    title: str
    content: str
    urgency_level: Optional[str] = None
    keywords: Optional[List[str]] = None
    # v1.3: 紧急止损动作列表
    emergency_actions: Optional[List[str]] = None
    # v1.3: 适用场景标签
    scenario_tags: Optional[List[str]] = None
    is_active: int = 1
    version: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
