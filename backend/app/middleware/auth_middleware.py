import logging
from typing import Optional

from fastapi import Depends, HTTPException, Header
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.database import get_db
from backend.app.models.models import User
from backend.app.config import settings

logger = logging.getLogger(__name__)


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="认证令牌格式无效")

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="认证令牌无效")
    except JWTError as e:
        logger.warning(f"JWT decode failed: {e}")
        raise HTTPException(status_code=401, detail="认证令牌已过期或无效")

    stmt = select(User).where(User.id == int(user_id), User.is_active == 1)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")

    return user