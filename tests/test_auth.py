from app.auth import _login_attempts


async def test_login_success(client):
    response = await client.post("/auth/login", json={"password": "test-password"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_wrong_password(client):
    response = await client.post("/auth/login", json={"password": "wrong"})
    assert response.status_code == 401


async def test_login_rate_limit(client):
    _login_attempts.clear()
    for _ in range(5):
        await client.post("/auth/login", json={"password": "wrong"})
    response = await client.post("/auth/login", json={"password": "wrong"})
    assert response.status_code == 429
    _login_attempts.clear()
