from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.auth import check_login_rate_limit, create_access_token, get_client_ip, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request) -> LoginResponse:
    check_login_rate_limit(get_client_ip(request))
    if not verify_password(body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
    return LoginResponse(access_token=create_access_token())
