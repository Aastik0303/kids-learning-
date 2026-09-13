from fastapi import APIRouter, Depends

from app.config import get_settings
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GoogleAuthRequest,
    GoogleConfigResponse,
    LoginRequest,
    LogoutRequest,
    OtpResendRequest,
    OtpResendResponse,
    OtpVerifyRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SessionResponse,
    SignInChallengeResponse,
)
from app.api.deps import optional_token
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest) -> AuthResponse:
    return auth_service.register(payload)


@router.post("/login", response_model=AuthResponse | SignInChallengeResponse)
def login(payload: LoginRequest) -> AuthResponse | SignInChallengeResponse:
    """Check the password, then email a code.

    Two possible answers and the client has to read which it got: an
    `AuthResponse` when the emailed code is switched off for this deployment,
    and a `SignInChallengeResponse` - `otp_required: true`, no token anywhere in
    it - when it is on. They are deliberately different shapes rather than one
    shape with empty fields, because a response that merely looked like a
    session is the easiest thing in the world for a client to treat as one.
    """
    return auth_service.login(payload)


@router.post("/otp/verify", response_model=AuthResponse)
def verify_otp(payload: OtpVerifyRequest) -> AuthResponse:
    """Spend the emailed code and issue the session.

    This is the only place a session is minted on the password path once the
    code is switched on.
    """
    return auth_service.sign_in_with_code(payload)


@router.post("/otp/resend", response_model=OtpResendResponse)
def resend_otp(payload: OtpResendRequest) -> OtpResendResponse:
    """Another code on the same challenge. Behind a cooldown, and a ceiling on
    how many times one sign-in may send mail to an address."""
    return auth_service.resend_code(payload)


@router.post("/google", response_model=AuthResponse)
def google(payload: GoogleAuthRequest) -> AuthResponse:
    """Sign in with Google, creating the account if there is not one yet.

    The ID token is verified against Google's own signing keys and pinned to
    this app's client id before it means anything. What comes back is the same
    session every other sign-in issues - the Google token is never a bearer for
    this API.
    """
    return auth_service.sign_in_with_google(payload)


@router.get("/google/config", response_model=GoogleConfigResponse)
def google_config() -> GoogleConfigResponse:
    """Whether to draw Google's button, and with which client id.

    Public on purpose: an OAuth client id is not a secret, and the sign-in
    screen is reached by someone who is not signed in. It answers `enabled:
    false` where the server has no client id, so the button is never shown
    where the sign-in it starts could not be verified.
    """
    settings = get_settings()
    return GoogleConfigResponse(
        enabled=settings.google_sign_in_enabled,
        client_id=settings.google_client_id.strip() if settings.google_sign_in_enabled else "",
    )


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
