from datetime import datetime
from typing import Optional, Any, List

from pydantic import BaseModel, ConfigDict, Field


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None


class PaginatedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: int = 0
    message: str = "success"
    total: int = 0
    page: int = 1
    page_size: int = 20
    data: List[Any] = []
