import logging
from datetime import datetime, timedelta

import bcrypt
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt

from backend.app.database import get_db
from backend.app.models.models import User
from backend.app.config import settings
from backend.app.schemas.common import ApiResponse

logger = logging.getLogger(__name__)
router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login", response_model=ApiResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(User).where(User.username == request.username, User.is_active == 1)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return ApiResponse(code=1, message="用户名或密码错误")

        stored_hash = user.password_hash.encode("utf-8") if isinstance(user.password_hash, str) else user.password_hash
        if not bcrypt.checkpw(request.password.encode("utf-8"), stored_hash):
            return ApiResponse(code=1, message="用户名或密码错误")

        expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRE_HOURS)
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
            "exp": expire,
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

        return ApiResponse(data={
            "token": token,
            "role": user.role,
            "user_id": user.id,
            "username": user.username,
            "expires_at": expire.isoformat(),
        })
    except Exception as e:
        logger.error(f"Login failed: {e}")
        return ApiResponse(code=1, message="登录失败，请稍后重试")


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "frontline_staff"


@router.post("/register", response_model=ApiResponse)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(User).where(User.username == request.username)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            return ApiResponse(code=1, message="用户名已存在")

        password_hash = bcrypt.hashpw(request.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user = User(
            username=request.username,
            password_hash=password_hash,
            role=request.role,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

        return ApiResponse(data={
            "user_id": user.id,
            "username": user.username,
        })
    except Exception as e:
        logger.error(f"Register failed: {e}")
        return ApiResponse(code=1, message="注册失败，请稍后重试")