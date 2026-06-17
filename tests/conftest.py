import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import pytest
import pytest_asyncio

from tests.test_data.sample_complaints import SAMPLE_COMPLAINTS


def pytest_configure(config):
    config.addinivalue_line("markers", "acceptance: acceptance test for A/B/C/D scenarios")
    config.addinivalue_line("markers", "integration: integration tests requiring database or server")


@pytest.fixture
def sample_complaints():
    return SAMPLE_COMPLAINTS


@pytest.fixture
def check_db_ready():
    try:
        import pymysql
        from backend.app.config import settings

        conn = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            charset=settings.DB_CHARSET,
            connect_timeout=3,
        )
        conn.close()
        return True
    except Exception:
        pytest.skip("Database not available")


@pytest_asyncio.fixture
async def db_session():
    """提供数据库异步会话，测试结束后自动清理"""
    from backend.app.database import async_session

    session = async_session()
    try:
        yield session
    finally:
        await session.close()
        from backend.app.database import engine
        await engine.dispose()
