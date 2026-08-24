from fastapi import APIRouter, Header

from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LogoutRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SessionResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest) -> AuthResponse:
    return auth_service.register(payload)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest) -> AuthResponse:
    return auth_service.login(payload)


@router.post("/logout")
async def logout(payload: LogoutRequest) -> dict:
    auth_service.logout(payload.session_token)
    return {"ok": True}


@router.get("/session", response_model=SessionResponse)
async def session(x_demo_session: str | None = Header(default=None)) -> SessionResponse:
    return auth_service.session(x_demo_session)


@router.post("/password/forgot", response_model=ForgotPasswordResponse)
async def forgot_password(payload: ForgotPasswordRequest) -> ForgotPasswordResponse:
    """Ask for a reset link. Answers the same way whether or not the account exists."""
    return auth_service.forgot_password(payload)


@router.post("/password/reset")
async def reset_password(payload: ResetPasswordRequest) -> dict:
    """Spend a reset token and set a new password. Signs every device out."""
    return auth_service.reset_password(payload)
