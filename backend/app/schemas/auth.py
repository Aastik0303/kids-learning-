from pydantic import BaseModel, Field


class UserPublic(BaseModel):
    id: str
    name: str
    email: str


class RegisterRequest(BaseModel):
    email: str
    name: str = Field(min_length=1)
    # Eight, not four. The account holds a child's name, birth month and whole
    # learning history, and a four-character password survives a lockout window
    # of guessing.
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: str
    # Deliberately not raised to eight: an account created before the floor
    # moved must still be able to sign in and change its password.
    password: str = Field(min_length=4)


class AuthResponse(BaseModel):
    session_token: str
    user: UserPublic


class LogoutRequest(BaseModel):
    session_token: str


class SessionResponse(BaseModel):
    user: UserPublic | None = None


class ForgotPasswordRequest(BaseModel):
    email: str


class ForgotPasswordResponse(BaseModel):
    """Always the same answer, whether or not the address is registered.

    Saying "no such account" here turns the endpoint into a way to find out
    which parents use the app.
    """

    ok: bool = True
    message: str = "If that address is registered, a reset link is on its way."
    # Only outside production, and only because there is no mailer yet: without
    # this the reset flow could not be completed or tested at all. In production
    # this is never filled in.
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=8)
    password: str = Field(min_length=8)
