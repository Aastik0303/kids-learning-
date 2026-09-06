from fastapi import APIRouter, Depends

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
from app.api.deps import optional_token
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest) -> AuthResponse:
    return auth_service.register(payload)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    return auth_service.login(payload)


@router.post("/logout")
def logout(payload: LogoutRequest) -> dict:
    auth_service.logout(payload.session_token)
    return {"ok": True}


@router.get("/session", response_model=SessionResponse)
def session(token: str | None = Depends(optional_token)) -> SessionResponse:
    """Who is signed in, if anyone. Asked on every load, so an unknown or
    expired token is an empty answer rather than an error."""
    return auth_service.session(token)


@router.post("/password/forgot", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest) -> ForgotPasswordResponse:
    """Ask for a reset link. Answers the same way whether or not the account exists."""
    return auth_service.forgot_password(payload)


@router.post("/password/reset")
def reset_password(payload: ResetPasswordRequest) -> dict:
    """Spend a reset token and set a new password. Signs every device out."""
    return auth_service.reset_password(payload)
