import os

os.environ.setdefault("DATABASE_URL", "postgresql://ats:ats@localhost:5432/ats_tracker_test")
os.environ.setdefault("APP_PASSWORD", "test-password")
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
