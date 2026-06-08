import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import pytest

from tests.test_data.sample_complaints import SAMPLE_COMPLAINTS


def pytest_configure(config):
    config.addinivalue_line("markers", "acceptance: acceptance test for A/B/C/D scenarios")


@pytest.fixture
def sample_complaints():
    return SAMPLE_COMPLAINTS


@pytest.fixture
def check_db_ready():
    try:
        import aiomysql
        from backend.app.config import settings
        import asyncio

        async def _check():
            conn = await aiomysql.connect(
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                db=settings.DB_NAME,
                charset=settings.DB_CHARSET,
            )
            conn.close()
            return True

        return asyncio.get_event_loop().run_until_complete(_check())
    except Exception:
        pytest.skip("Database not available")
