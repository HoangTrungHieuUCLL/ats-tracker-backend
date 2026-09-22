import hmac
import time
from collections import defaultdict, deque

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = 7 * 24 * 60 * 60

_bearer_scheme = HTTPBearer(auto_error=False)

# In-memory login rate limiter: IP -> timestamps of recent attempts.
_login_attempts: dict[str, deque] = defaultdict(deque)
LOGIN_RATE_LIMIT = 5
LOGIN_RATE_WINDOW_SECONDS = 60


def verify_password(password: str) -> bool:
    return hmac.compare_digest(password, settings.app_password)


def create_access_token() -> str:
    now = int(time.time())
    payload = {"sub": "single-user", "iat": now, "exp": now + JWT_EXPIRY_SECONDS}
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])


def check_login_rate_limit(client_ip: str) -> None:
    now = time.time()
    attempts = _login_attempts[client_ip]
    while attempts and now - attempts[0] > LOGIN_RATE_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= LOGIN_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )
    attempts.append(now)


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
