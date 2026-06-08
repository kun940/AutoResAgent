from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from shared.constants import NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: str
    target_user_id: int
    type: str
    content: Optional[str] = None
    is_read: int = 0
    created_at: Optional[datetime] = None


class UnreadCountResponse(BaseModel):
    count: int = 0
