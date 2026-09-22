import os

os.environ.setdefault("DATABASE_URL", "postgresql://ats:ats@localhost:5432/ats_tracker_test")
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.auth import create_access_token, hash_password
from app.db import engine
from app.main import app
from tests.factories import TEST_PASSWORD, TEST_USER_ID, TEST_USERNAME


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def _ensure_test_user():
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
                "VALUES (:id, :username, :password_hash, now(), now()) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {
                "id": TEST_USER_ID,
                "username": TEST_USERNAME,
                "password_hash": hash_password(TEST_PASSWORD),
            },
        )


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {create_access_token(TEST_USER_ID)}"}


@pytest.fixture(autouse=True)
def reset_quota_state():
    from app.services import quota_state

    quota_state._daily_quota_resume_at = None
    yield
    quota_state._daily_quota_resume_at = None


@pytest.fixture(autouse=True)
def reset_login_rate_limit():
    from app.auth import _login_attempts

    _login_attempts.clear()
    yield
    _login_attempts.clear()


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
            # Extra users registered by multi-user tests (e.g. "otheruser-…")
            # also don't cascade from a jobs truncate.
            await conn.execute(
                text("DELETE FROM users WHERE id != :test_user_id"),
                {"test_user_id": TEST_USER_ID},
            )

    await _truncate()
    yield
    await _truncate()
