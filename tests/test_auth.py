import uuid

from tests.factories import TEST_PASSWORD, TEST_USERNAME


def _fresh_username() -> str:
    return f"newuser-{uuid.uuid4().hex[:12]}"


async def test_login_success(client):
    response = await client.post(
        "/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_wrong_password(client):
    response = await client.post(
        "/auth/login", json={"username": TEST_USERNAME, "password": "wrong"}
    )
    assert response.status_code == 401


async def test_login_unknown_username(client):
    response = await client.post(
        "/auth/login", json={"username": "does-not-exist", "password": "whatever"}
    )
    assert response.status_code == 401


async def test_login_rate_limit(client):
    for _ in range(5):
        await client.post("/auth/login", json={"username": TEST_USERNAME, "password": "wrong"})
    response = await client.post(
        "/auth/login", json={"username": TEST_USERNAME, "password": "wrong"}
    )
    assert response.status_code == 429


async def test_register_creates_account_and_logs_in(client):
    username = _fresh_username()
    response = await client.post(
        "/auth/register", json={"username": username, "password": "a-strong-password"}
    )
    assert response.status_code == 201
    assert response.json()["access_token"]

    login_response = await client.post(
        "/auth/login", json={"username": username, "password": "a-strong-password"}
    )
    assert login_response.status_code == 200


async def test_register_rejects_duplicate_username(client):
    username = _fresh_username()
    await client.post("/auth/register", json={"username": username, "password": "password123"})
    response = await client.post(
        "/auth/register", json={"username": username, "password": "different123"}
    )
    assert response.status_code == 409


async def test_register_rejects_short_password(client):
    response = await client.post(
        "/auth/register", json={"username": _fresh_username(), "password": "short"}
    )
    assert response.status_code == 422
