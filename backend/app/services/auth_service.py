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
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SessionResponse,
    UserPublic,
)
from app.services import jwt_service
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


def verify_password(password: str, stored: str) -> bool:
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


def _authorised(parent, auth) -> AuthResponse:
    """The answer to a successful sign-in or registration.

    `session_token` and `access_token` are the same signed string. The older
    field keeps its name because the web and mobile clients both send it back
    as `X-Demo-Session` and a rename would sign every one of them out; the new
    pair says what it actually is, so a client can send `Authorization: Bearer`
    instead.
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
        return _authorised(parent, auth)


def login(payload: LoginRequest) -> AuthResponse:
    """Sign in, behind a failure counter.

    The password hash is deliberately expensive, which makes each guess slow but
    does not make guessing pointless. The counter does: eight wrong passwords in
    fifteen minutes and the account stops answering for fifteen, whatever the
    guess is.
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
            security.clear(session, key=key)
            auth = learners.open_session(session, parent)
            return _authorised(parent, auth)

    # The failure is written in a transaction of its own, and only then is the
    # refusal raised. Counting it inside the transaction above would have been
    # rolled back by the very exception it exists to count - which is to say,
    # the lockout would never have locked anything.
    with session_scope() as session:
        security.record_failure(session, key=key, now=now)

    # One message for both cases. Saying "no such account" tells whoever asked
    # which emails are registered here.
    raise app_error("INVALID_LOGIN", "Those login details did not match.", 401)


def forgot_password(payload: ForgotPasswordRequest) -> ForgotPasswordResponse:
    """Start a password reset. The answer never says whether the account exists.

    There is no mailer in this system yet, so outside production the token comes
    back in the response and is also logged. That is the honest shape of an
    unfinished feature: the flow works end to end and is testable, and the one
    place it must not do this - production - is checked here rather than
    remembered later.
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
    if get_settings().env.lower() != "production":
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


