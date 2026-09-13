"""Parent accounts, on the durable layer.

This replaces `mock_auth.py`, which kept accounts in a dictionary and hashed
passwords with a bare sha256. Both are gone: accounts live in `parents`,
sessions in `auth_sessions` with an expiry, and a password is stretched with
PBKDF2-HMAC-SHA256 before it is stored. A single unsalted sha256 of a
four-character password is recoverable in seconds, and this database will hold
the email addresses of parents of small children.

Only a parent ever authenticates. A child has no account, no password and no
token of their own - the child surface is reached through the parent's session,
which is why nothing here takes a child id.

The bearer a client carries is a JWT (`jwt_service`), signed with `JWT_SECRET`
and naming its `auth_sessions` row in the `jti` claim. The row is still what
decides whether the session is open, so signing out and resetting a password
both still end it; the signature is what makes a forged or expired token cheap
to refuse before any query is made. A token issued before this change is an
opaque row key and is still accepted until it expires on its own.
"""

import hashlib
import hmac
import logging
import re
import secrets
from datetime import datetime, timezone
from os import urandom

from app.config import get_settings
from app.db.repositories import learners, security
from app.db.session import session_scope
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GoogleAuthRequest,
    LoginRequest,
    OtpResendRequest,
    OtpResendResponse,
    OtpVerifyRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SessionResponse,
    SignInChallengeResponse,
    UserPublic,
)
from app.services import google_auth_service, jwt_service, mailer, otp_service
from app.services.errors import app_error


logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _throttle_key(scope: str, email: str) -> str:
    return f"{scope}:{email.strip().lower()}"[:200]


PBKDF2_ALGORITHM = "pbkdf2_sha256"


def _rounds() -> int:
    """Settings win, so the test suite can stretch a password 600 times instead
    of 600,000 and still exercise the same code path. Nothing but the tests
    lowers it: `password_hash_rounds` defaults to the full count."""
    return max(1, get_settings().password_hash_rounds)


def hash_password(password: str, *, salt: bytes | None = None, rounds: int | None = None) -> str:
    rounds = rounds or _rounds()
    salt = salt or urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return f"{PBKDF2_ALGORITHM}${rounds}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    """Whether this password matches the stored hash.

    `stored` may be empty: an account created through Google has no password
    until its owner sets one. There is nothing to match against, so nothing
    matches - a blank password must never be a way into such an account.
    """
    if not stored:
        return False
    try:
        algorithm, rounds, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algorithm != PBKDF2_ALGORITHM:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds))
    # Constant time: a timing signal on a password digest is a slow password
    # oracle, and comparing bytes with == is exactly that.
    return hmac.compare_digest(candidate.hex(), digest_hex)


def _validate_email(email: str) -> None:
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise app_error("INVALID_EMAIL", "Use a well-formed email address.")


def _public(parent) -> UserPublic:
    return UserPublic(id=str(parent.id), name=parent.name, email=parent.email)


def _authorised(parent, auth, *, is_new_account: bool = False) -> AuthResponse:
    """The answer to a successful sign-in or registration.

    `session_token` and `access_token` are the same signed string. Clients send
    it back as `Authorization: Bearer`; the older field name is kept on the
    response because a shipped mobile build still reads it, and renaming it
    would sign those installs out.
    """
    token = jwt_service.issue(
        session_token=auth.token, parent_id=str(parent.id), email=parent.email
    )
    return AuthResponse(
        session_token=token,
        access_token=token,
        token_type=jwt_service.TOKEN_TYPE,
        expires_in=int(jwt_service.ttl().total_seconds()),
        user=_public(parent),
        is_new_account=is_new_account,
    )


def register(payload: RegisterRequest) -> AuthResponse:
    _validate_email(payload.email)
    with session_scope() as session:
        if learners.parent_by_email(session, payload.email) is not None:
            raise app_error("EMAIL_EXISTS", "This email is already registered.")
        parent = learners.create_parent(
            session,
            email=payload.email,
            name=payload.name,
            password_hash=hash_password(payload.password),
        )
        auth = learners.open_session(session, parent)
        return _authorised(parent, auth, is_new_account=True)


def login(payload: LoginRequest) -> AuthResponse | SignInChallengeResponse:
    """Sign in, behind a failure counter, and then behind an emailed code.

    The password hash is deliberately expensive, which makes each guess slow but
    does not make guessing pointless. The counter does: eight wrong passwords in
    fifteen minutes and the account stops answering for fifteen, whatever the
    guess is.

    A right password is no longer a session. It opens a **challenge**, and the
    code that finishes it goes to the account's own address - so a password that
    has leaked, been reused from another site or been read off a note by the
    router is not on its own a way into a child's record. What comes back says
    which of the two happened, and only `sign_in_with_code` mints a token here.

    The throttle is cleared by the *code*, not by the password. Clearing it on a
    correct password would let whoever holds that password reset the counter at
    will and grind the second factor for as long as they liked.
    """
    now = _now()
    key = _throttle_key("login", payload.email)

    with session_scope() as session:
        locked = security.locked_until(session, key=key, now=now)
        if locked is not None:
            minutes = max(1, round((locked - now).total_seconds() / 60))
            raise app_error(
                "TOO_MANY_ATTEMPTS",
                f"Too many sign-in attempts. Please try again in about {minutes} minutes.",
                429,
            )

        parent = learners.parent_by_email(session, payload.email)
        if parent is not None and verify_password(payload.password, parent.password_hash):
            if not otp_service.enabled():
                security.clear(session, key=key)
                auth = learners.open_session(session, parent)
                return _authorised(parent, auth)

            challenge_id, dev_code = otp_service.issue(session, parent=parent, now=now)
            settings = get_settings()
            return SignInChallengeResponse(
                challenge_id=challenge_id,
                email_hint=otp_service.masked(parent.email),
                expires_in=int(otp_service.ttl().total_seconds()),
                resend_after=settings.auth_otp_resend_cooldown_seconds,
                dev_code=dev_code,
            )

    # The failure is written in a transaction of its own, and only then is the
    # refusal raised. Counting it inside the transaction above would have been
    # rolled back by the very exception it exists to count - which is to say,
    # the lockout would never have locked anything.
    with session_scope() as session:
        security.record_failure(session, key=key, now=now)

    # One message for both cases. Saying "no such account" tells whoever asked
    # which emails are registered here.
    raise app_error("INVALID_LOGIN", "Those login details did not match.", 401)


def sign_in_with_code(payload: OtpVerifyRequest) -> AuthResponse:
    """Spend a sign-in code and issue the session.

    An unknown, expired, already-spent or out-of-guesses challenge all answer
    the same way. Telling them apart would say which handles are real and how
    many guesses are left, and neither is any of the caller's business.

    A wrong code is counted twice over: against the challenge, which dies after
    a handful of guesses, and against the account's own throttle - the same
    counter password guesses land on - so somebody holding the password cannot
    open a fresh challenge per guess and grind the code that way.
    """
    now = _now()
    code = _clean_code(payload.code)
    max_attempts = max(1, get_settings().auth_otp_max_attempts)

    with session_scope() as session:
        challenge = security.challenge_for(session, challenge_id=payload.challenge_id, now=now)
        if challenge is None:
            raise app_error("INVALID_CODE", "That code has expired. Please sign in again.", 401)

        parent = session.get(learners.Parent, challenge.parent_id)
        if parent is None:  # pragma: no cover - cascade-deleted with the parent
            raise app_error("INVALID_CODE", "That code has expired. Please sign in again.", 401)

        key = _throttle_key("login", parent.email)
        locked = security.locked_until(session, key=key, now=now)
        if locked is not None:
            minutes = max(1, round((locked - now).total_seconds() / 60))
            raise app_error(
                "TOO_MANY_ATTEMPTS",
                f"Too many sign-in attempts. Please try again in about {minutes} minutes.",
                429,
            )

        if security.verify_challenge(
            session, challenge=challenge, code=code, now=now, max_attempts=max_attempts
        ):
            # The sign-in as a whole succeeded, so the counter behind it is
            # cleared here rather than when the password was accepted.
            security.clear(session, key=key)
            auth = learners.open_session(session, parent)
            return _authorised(parent, auth)

        email = parent.email

    with session_scope() as session:
        # Its own transaction, for the same reason the password counter is: the
        # refusal below would roll back the very failure it exists to count.
        security.record_failure(session, key=_throttle_key("login", email), now=now)

    raise app_error("INVALID_CODE", "That code did not match. Please check and try again.", 401)


def resend_code(payload: OtpResendRequest) -> OtpResendResponse:
    """Another code on the same challenge, behind a cooldown and a ceiling."""
    now = _now()
    with session_scope() as session:
        challenge = security.challenge_for(session, challenge_id=payload.challenge_id, now=now)
        if challenge is None:
            raise app_error("INVALID_CODE", "That sign-in has expired. Please sign in again.", 401)

        parent = session.get(learners.Parent, challenge.parent_id)
        if parent is None:  # pragma: no cover - cascade-deleted with the parent
            raise app_error("INVALID_CODE", "That sign-in has expired. Please sign in again.", 401)

        dev_code = otp_service.resend(session, challenge=challenge, email=parent.email, now=now)
        return OtpResendResponse(
            resend_after=get_settings().auth_otp_resend_cooldown_seconds, dev_code=dev_code
        )


def _clean_code(code: str) -> str:
    """What a parent actually types or pastes.

    Mail clients and phone keyboards put spaces and dashes through the middle of
    a six-digit number, and a code refused over a space the parent cannot see is
    the app blaming them for its own strictness.
    """
    return "".join(character for character in code if character.isdigit())


def sign_in_with_google(payload: GoogleAuthRequest) -> AuthResponse:
    """Sign in - or sign up - with a verified Google account.

    One endpoint for both, because from the parent's side there is one action:
    they tap the Google button and end up signed in. Which of the two happened
    is answered in `is_new_account`, so the client knows whether to send them
    through setting a child up.

    Three cases, in this order:

    * **already linked** - matched on Google's `sub`, which does not change when
      the parent changes the address on their Google account.
    * **same verified email, not yet linked** - the parent registered with a
      password and is now using the Google button on the same address. It is
      the same account and it is linked here rather than duplicated. This is
      only safe because `google_auth_service` refuses a token whose email is
      not verified: an unverified address would be a way into somebody else's
      account.
    * **neither** - a new account with no password. It can be signed into with
      Google, and with a password only once its owner sets one through the
      reset flow.

    There is no throttle here and none is needed: the expensive thing this
    guards is a password guess, and no password is checked on this path. What
    is checked is a signature Google holds the key to.
    """
    identity = google_auth_service.verify(payload.credential)

    with session_scope() as session:
        parent = learners.parent_by_google_subject(session, identity.subject)
        if parent is not None:
            auth = learners.open_session(session, parent)
            return _authorised(parent, auth)

        parent = learners.parent_by_email(session, identity.email)
        if parent is not None:
            learners.link_google_subject(session, parent, identity.subject)
            # The email is proven, so a lockout from guessing at this account's
            # password should not outlive a successful sign-in to it.
            security.clear(session, key=_throttle_key("login", parent.email))
            auth = learners.open_session(session, parent)
            return _authorised(parent, auth)

        parent = learners.create_parent(
            session,
            email=identity.email,
            name=identity.name,
            google_subject=identity.subject,
        )
        auth = learners.open_session(session, parent)
        return _authorised(parent, auth, is_new_account=True)


def forgot_password(payload: ForgotPasswordRequest) -> ForgotPasswordResponse:
    """Start a password reset. The answer never says whether the account exists.

    The link is emailed now that there is a mailer. Two things stay as they
    were, and both are about not turning this into a way to find out who has an
    account here: the answer is identical whether or not the address is
    registered, and a failure to send is swallowed rather than reported - "we
    could not send that" would say the address exists.

    Outside production, a machine with no SMTP configured still hands the token
    back in the response so the flow can be finished without a mail account.
    That door is checked against `ENV` here rather than remembered later.
    """
    now = _now()
    key = _throttle_key("forgot", payload.email)
    response = ForgotPasswordResponse()

    with session_scope() as session:
        if security.locked_until(session, key=key, now=now) is not None:
            # Same answer as the happy path: a lockout that announced itself
            # would tell an attacker which addresses are worth asking about.
            return response

        parent = learners.parent_by_email(session, payload.email)
        security.record_failure(session, key=key, now=now, limit=5)
        if parent is None:
            return response

        token = secrets.token_urlsafe(32)
        security.create_reset(session, parent_id=parent.id, token=token, now=now)

    logger.info("Password reset requested for %s", payload.email.strip().lower())
    settings = get_settings()

    if mailer.configured(settings):
        try:
            mailer.send(
                mailer.password_reset(
                    to=payload.email.strip().lower(),
                    link=f"{settings.password_reset_url.rstrip('/')}?token={token}",
                    minutes=int(security.RESET_TTL.total_seconds() // 60),
                )
            )
        except mailer.MailNotSent:
            # Logged inside the mailer. Not reported: an answer that differed
            # when the send failed would differ only for addresses that exist.
            pass
        return response

    if settings.env.lower() != "production":
        # No mailer on this machine. The token comes back so the flow can still
        # be completed and tested; `mailer.configured` is false in production
        # only if somebody deployed without SMTP, and then this is not reached.
        return response.model_copy(update={"reset_token": token})
    return response


def reset_password(payload: ResetPasswordRequest) -> dict:
    """Spend a reset token, set the new password, and sign every device out."""
    now = _now()
    with session_scope() as session:
        reset = security.consume_reset(session, token=payload.token, now=now)
        if reset is None:
            raise app_error("INVALID_RESET", "That reset link is no longer valid.", 400)

        parent = session.get(learners.Parent, reset.parent_id)
        if parent is None:  # pragma: no cover - the row is cascade-deleted with the parent
            raise app_error("INVALID_RESET", "That reset link is no longer valid.", 400)

        parent.password_hash = hash_password(payload.password)
        # A password is reset because it may be known to someone else. Leaving
        # their session open would defeat the reset.
        security.revoke_sessions(session, parent_id=parent.id)
        security.clear(session, key=_throttle_key("login", parent.email))

    return {"ok": True, "message": "Your password is changed. Please sign in again."}


def logout(session_token: str) -> None:
    with session_scope() as session:
        learners.close_session(session, jwt_service.session_token_of(session_token))


def get_user_for_token(session_token: str) -> dict:
    """The parent behind a session token, as the plain dict the services use."""
    with session_scope() as session:
        row_token = jwt_service.session_token_of(session_token) if session_token else ""
        parent = learners.parent_for_token(session, row_token) if row_token else None
        if parent is None:
            raise app_error("MISSING_SESSION", "Please log in again.", 401)
        return {"id": str(parent.id), "name": parent.name, "email": parent.email}


def session(session_token: str | None) -> SessionResponse:
    if not session_token:
        return SessionResponse()
    with session_scope() as db:
        parent = learners.parent_for_token(db, jwt_service.session_token_of(session_token))
        # An expired or unknown token is not an error here: the client asks this
        # on every load to find out whether it is signed in.
        return SessionResponse(user=_public(parent)) if parent else SessionResponse()


def grant_consent(session_token: str) -> None:
    """Written when a parent taps the consent control, and from nowhere else.

    DPDP and COPPA both require an explicit act by a person, so no automation
    path may call this - not the planner, not the conductor, not a migration.
    """
    with session_scope() as db:
        parent = learners.parent_for_token(db, jwt_service.session_token_of(session_token))
        if parent is None:
            raise app_error("MISSING_SESSION", "Please log in again.", 401)
        learners.grant_consent(db, parent)


