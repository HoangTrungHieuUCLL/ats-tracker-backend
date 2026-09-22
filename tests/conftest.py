import os

os.environ.setdefault("DATABASE_URL", "postgresql://ats:ats@localhost:5432/ats_tracker_test")
os.environ.setdefault("APP_PASSWORD", "test-password")
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.auth import create_access_token
from app.db import engine
from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {create_access_token()}"}


@pytest.fixture(autouse=True)
def reset_quota_state():
    from app.services import quota_state

    quota_state._daily_quota_resume_at = None
    yield
    quota_state._daily_quota_resume_at = None


_SEEDED_KEYWORD_KEYS = ["power bi", "excel", "gcp", "aws", "kubernetes", "postgresql"]


@pytest.fixture
async def clean_jobs_table():
    async def _truncate():
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE jobs CASCADE"))
            # Keywords/aliases created by tests (not part of the migration
            # seed) don't cascade from a jobs truncate, so sweep them too —
            # otherwise unique canonical_key/alias_key values collide across
            # test runs against the same persistent test database.
            await conn.execute(
                text("DELETE FROM keywords WHERE canonical_key != ALL(:seed)"),
                {"seed": _SEEDED_KEYWORD_KEYS},
            )

    await _truncate()
    yield
    await _truncate()
