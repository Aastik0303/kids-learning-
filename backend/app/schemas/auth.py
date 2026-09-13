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
    """What a successful sign-in or registration hands back.

    `session_token` and `access_token` hold the same signed JWT. Clients send it
    back as `Authorization: Bearer <token>`, and `token_type` and `expires_in`
    say what it is and when to sign in again. The first field keeps its older
    name because a shipped mobile build still reads it, and renaming it would
    sign those installs out at once.
    """

    session_token: str
    access_token: str
    token_type: str = "Bearer"
    # Seconds, matching the `auth_sessions` row the token names.
    expires_in: int
    user: UserPublic
    # Whether this call created the account. The client sends a brand-new
    # parent to set their child up and a returning one straight to the class;
    # with Google there is one button for both, so the server is the only thing
    # that knows which just happened.
    is_new_account: bool = False


class SignInChallengeResponse(BaseModel):
    """What `POST /auth/login` answers when the password was right and a code
    has been emailed.

    Deliberately not an `AuthResponse` with empty fields: there is no session
    here, nothing in this can be turned into one, and a shape that merely looked
    like a session would be the easiest possible thing for a client to treat as
    one by accident.
    """

    otp_required: bool = True
    # The handle for this sign-in. Half of what verifying needs; the code that
    # went to the parent's inbox is the other half.
    challenge_id: str
    # Enough of the address to recognise, not enough to learn - whoever is
    # looking at this screen is whoever has the password.
    email_hint: str
    expires_in: int
    resend_after: int
    # Only ever filled in on a development machine with no SMTP configured, so
    # the flow can be finished without a mail account. `app/services/otp_service.py`
    # refuses to reach this line in production.
    dev_code: str | None = None


class OtpVerifyRequest(BaseModel):
    challenge_id: str = Field(min_length=8)
    # Whitespace and the dashes people paste out of an email are stripped before
    # this is compared; the floor is here only to refuse an empty box.
    code: str = Field(min_length=4, max_length=16)


class OtpResendRequest(BaseModel):
    challenge_id: str = Field(min_length=8)


class OtpResendResponse(BaseModel):
    ok: bool = True
    message: str = "We have sent another code."
    resend_after: int = 60
    dev_code: str | None = None


class GoogleAuthRequest(BaseModel):
    """The ID token Google handed the client.

    It is a JWT signed by Google and it is verified on the server - see
    `app/services/google_auth_service.py`. Nothing about the parent is taken
    from the client here: not the email, not the name, not an id. Accepting any
    of those alongside the token would be accepting them *instead* of it, since
    the client could then simply say whose account to open.
    """

    credential: str = Field(min_length=1)


class GoogleConfigResponse(BaseModel):
    """What the sign-in screen needs to draw Google's button, if anything.

    The client id is public by design - it travels in the URL of every OAuth
    flow - and asking the server for it means one configured value rather than
    the same secret-looking string in two places, and a button that appears
    only where the server can actually verify what comes back.
    """

    enabled: bool = False
    client_id: str = ""


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
