import logging
import os
import uvicorn
from contextlib import asynccontextmanager

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.api import tickets, notifications, knowledge, dashboard, upload, auth, customer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("客诉自动回复出单智能体 API 启动中...")
    logger.info(f"监听地址: {settings.FASTAPI_HOST}:{settings.FASTAPI_PORT}")
    yield
    logger.info("客诉自动回复出单智能体 API 关闭")


app = FastAPI(
    title="客诉自动回复出单智能体 API",
    description="基于大模型Agent的客诉自动回复、智能定级与工单分发系统 v1.0",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tickets.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1/notifications")
app.include_router(knowledge.router, prefix="/api/v1/knowledge")
app.include_router(dashboard.router, prefix="/api/v1/dashboard")
app.include_router(upload.router, prefix="/api/v1/upload")
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(customer.router, prefix="/api/v1/customer")

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(os.path.join(static_dir, "h5"), exist_ok=True)
os.makedirs(os.path.join(static_dir, "uploads"), exist_ok=True)
app.mount("/h5", StaticFiles(directory=os.path.join(static_dir, "h5"), html=True), name="h5")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    return {"message": "客诉自动回复出单智能体 API v1.0", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host=settings.FASTAPI_HOST,
        port=settings.FASTAPI_PORT,
        reload=False,
    )
