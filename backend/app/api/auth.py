from fastapi import APIRouter, Header

from app.schemas.auth import AuthResponse, LoginRequest, LogoutRequest, RegisterRequest, SessionResponse
from app.services import mock_auth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest) -> AuthResponse:
    return mock_auth.register(payload)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest) -> AuthResponse:
    return mock_auth.login(payload)


@router.post("/logout")
async def logout(payload: LogoutRequest) -> dict:
    mock_auth.logout(payload.session_token)
    return {"ok": True}


@router.get("/session", response_model=SessionResponse)
async def session(x_demo_session: str | None = Header(default=None)) -> SessionResponse:
    return mock_auth.session(x_demo_session)
