"""Signed session tokens.

`auth_sessions` is still the truth about whether a sitting is open: the row is
created at sign-in, deleted at sign-out, and wiped for every device when a
password is reset. What changed is the *bearer* the client carries. It used to
be the row's primary key in the clear - a bare 32-character hex string that
says nothing, can be replayed until it expires, and has to be looked up before
anything at all is known about it.

A JWT carries who it is for and when it stops being valid, signed with a secret
only this server holds, so a tampered or home-made token is rejected before a
query is made. The `jti` claim is the `auth_sessions` token, and it is still
checked against the row on every request. That is deliberate and it is not a
misunderstanding of what JWTs are for: a stateless token cannot be signed out,
and a parent tapping "sign out" - or resetting a password because someone else
may know it - has to actually end the session, on this app more than most.
The signature is what makes an unknown token cheap to refuse; the row is what
makes a known one revocable.

The secret comes from `JWT_SECRET` in the environment and from nowhere else.
Outside development an unset secret refuses to issue or accept anything rather
than falling back to a default, because a signing key with a known value is the
same as no signature at all.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings
from app.services.errors import app_error


logger = logging.getLogger(__name__)

TOKEN_TYPE = "Bearer"

# Development only, and only when `JWT_SECRET` is unset: a random key made once
# per process so a developer who has not written a `.env` still gets working
# tokens. It dies with the process, so every restart signs everybody out - which
# is a nuisance in development and unacceptable anywhere else, hence the refusal
# below rather than this fallback.
_EPHEMERAL_SECRET = secrets.token_urlsafe(48)
_warned_about_missing_secret = False


def _secret() -> str:
    global _warned_about_missing_secret
    settings = get_settings()
    if settings.jwt_secret:
        return settings.jwt_secret
    if settings.env.lower() == "development":
        if not _warned_about_missing_secret:
            logger.warning(
                "JWT_SECRET is not set. Signing with a throwaway key that changes "
                "on every restart. Set JWT_SECRET in backend/.env."
            )
            _warned_about_missing_secret = True
        return _EPHEMERAL_SECRET
    raise app_error(
        "JWT_NOT_CONFIGURED",
        "Sign-in is unavailable right now. Please try again later.",
        503,
    )


def ttl() -> timedelta:
    """How long an issued token stays valid.

    It matches `learners.SESSION_TTL` by default so the signature and the row
    stop being valid at the same moment; a token that outlives its row is a
    token that is refused for a reason the client cannot see.
    """
    return timedelta(minutes=max(1, get_settings().jwt_ttl_minutes))


def issue(*, session_token: str, parent_id: str, email: str, now: datetime | None = None) -> str:
    """Sign a bearer token for an `auth_sessions` row that already exists.

    Nothing secret goes in the payload. A JWT is signed, not encrypted, and
    anybody holding one can read every claim in it - so this carries the
    parent's id and email, which they already know, and never a password hash,
    a child's name or anything about a child at all.
    """
    settings = get_settings()
    issued_at = now or datetime.now(timezone.utc)
    claims = {
        "sub": parent_id,
        "email": email,
        # The session row. This is what makes the token revocable.
        "jti": session_token,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": issued_at,
        "exp": issued_at + ttl(),
    }
    return jwt.encode(claims, _secret(), algorithm=settings.jwt_algorithm)


def decode(token: str) -> dict | None:
    """The claims of a well-signed, unexpired token, or `None`.

    `None` rather than an exception because the caller has a second thing to
    try: a token issued before this existed is an opaque `auth_sessions` key,
    not a malformed JWT, and it must keep working until it expires on its own.

    The algorithm is pinned to the configured one. Letting the token name its
    own algorithm is how a JWT verifier is talked into accepting `alg: none`.
    """
    if not token:
        return None
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            _secret(),
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp", "sub", "jti"]},
        )
    except jwt.PyJWTError:
        return None


def session_token_of(token: str) -> str:
    """The `auth_sessions` key a bearer stands for.

    A valid JWT resolves to its `jti`. Anything else is handed back unchanged,
    so an opaque token from before this change - and the tokens the test suite
    and the mobile client still hold - go on being looked up as they always
    were. Whatever comes back is looked up in the database either way, so an
    unsigned string is not trusted by being passed through here; it is simply
    not recognised as a JWT.
    """
    claims = decode(token)
    if claims is None:
        return token
    return str(claims.get("jti") or "")
