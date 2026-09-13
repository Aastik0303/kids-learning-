"""Sign-in throttling, password resets, and the emailed sign-in code.

Three small tables, all of them about the one endpoint an attacker actually
reaches: `POST /auth/login`. Everything here is written from the auth service
and read nowhere else.
"""

import hashlib
import hmac
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import AuthSession, AuthThrottle, PasswordReset, SignInChallenge


# Eight wrong passwords inside fifteen minutes locks the account for fifteen.
# Low enough to make guessing pointless, high enough that a tired parent
# mistyping their password at bedtime is not locked out of their child's app.
FAILURE_LIMIT = 8
FAILURE_WINDOW = timedelta(minutes=15)
LOCKOUT = timedelta(minutes=15)

RESET_TTL = timedelta(hours=1)


def token_hash(token: str) -> str:
    """A reset token is a random secret, not a password: one hash is enough, and
    what matters is that the raw token is never stored."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def keyed_hash(value: str) -> str:
    """For secrets small enough to guess offline - which is the sign-in code.

    A reset token is 32 random bytes and a plain digest of it is unguessable. A
    six-digit code is one of a million, and a million SHA-256s is under a second
    on any laptop: a stolen database would hand over every code in flight. So
    these are HMAC'd with the server's signing key, which is not in the
    database, and a dump on its own is not enough to grind them.

    Falls back to a plain digest when no key is configured - development, where
    there may be no `JWT_SECRET` - rather than refusing to store anything.
    """
    key = get_settings().jwt_secret.strip()
    if not key:
        return token_hash(value)
    return hmac.new(key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


# --------------------------------------------------------------------------
# Throttling
# --------------------------------------------------------------------------


def _row(session: Session, key: str, now: datetime) -> AuthThrottle:
    row = session.get(AuthThrottle, key)
    if row is None:
        # `window_started_at` is stamped from the caller's clock, not the
        # database's: the server default would open the window at "now" even for
        # a failure being recorded as of an earlier moment, which is the
        # difference between a window that expires and one that never does.
        row = AuthThrottle(key=key, failures=0, window_started_at=now)
        session.add(row)
        session.flush()
    return row


def locked_until(session: Session, *, key: str, now: datetime) -> datetime | None:
    """When this key may try again, or None if it may try now."""
    row = session.get(AuthThrottle, key)
    if row is None or row.locked_until is None:
        return None
    return row.locked_until if row.locked_until > now else None


def record_failure(
    session: Session,
    *,
    key: str,
    now: datetime,
    limit: int = FAILURE_LIMIT,
    window: timedelta = FAILURE_WINDOW,
    lockout: timedelta = LOCKOUT,
) -> AuthThrottle:
    row = _row(session, key, now)
    # A window that has already expired starts again rather than accumulating:
    # eight failures spread over a week is a forgetful parent, not an attack.
    if row.window_started_at is None or now - row.window_started_at > window:
        row.window_started_at = now
        row.failures = 0
        row.locked_until = None

    row.failures += 1
    if row.failures >= limit:
        row.locked_until = now + lockout
    session.flush()
    return row


def clear(session: Session, *, key: str) -> None:
    """A successful sign-in forgets the failures before it."""
    row = session.get(AuthThrottle, key)
    if row is not None:
        session.delete(row)
        session.flush()


# --------------------------------------------------------------------------
# Password resets
# --------------------------------------------------------------------------


def create_reset(session: Session, *, parent_id: UUID, token: str, now: datetime) -> PasswordReset:
    # Any reset still outstanding for this parent is spent: asking for a new
    # link must invalidate the last one, or a leaked old email stays usable.
    for row in session.scalars(
        select(PasswordReset).where(
            PasswordReset.parent_id == parent_id, PasswordReset.used_at.is_(None)
        )
    ).all():
        row.used_at = now

    reset = PasswordReset(parent_id=parent_id, token_hash=token_hash(token), expires_at=now + RESET_TTL)
    session.add(reset)
    session.flush()
    return reset


def consume_reset(session: Session, *, token: str, now: datetime) -> PasswordReset | None:
    """Spend a reset token. Returns None for unknown, used or expired ones."""
    reset = session.scalar(select(PasswordReset).where(PasswordReset.token_hash == token_hash(token)))
    if reset is None or reset.used_at is not None or reset.expires_at <= now:
        return None
    reset.used_at = now
    session.flush()
    return reset


# --------------------------------------------------------------------------
# The emailed sign-in code
# --------------------------------------------------------------------------


def create_challenge(
    session: Session,
    *,
    parent_id: UUID,
    challenge_id: str,
    code: str,
    now: datetime,
    ttl: timedelta,
) -> SignInChallenge:
    """Open a sign-in that is waiting on a code.

    Any challenge still outstanding for this parent is spent first. Two live
    challenges means two live codes, and the older one is usually the one an
    attacker caused to be sent.
    """
    for row in open_challenges(session, parent_id=parent_id):
        row.consumed_at = now

    challenge = SignInChallenge(
        parent_id=parent_id,
        challenge_hash=token_hash(challenge_id),
        code_hash=keyed_hash(code),
        expires_at=now + ttl,
        attempts=0,
        sends=1,
        last_sent_at=now,
    )
    session.add(challenge)
    session.flush()
    return challenge


def open_challenges(session: Session, *, parent_id: UUID) -> list[SignInChallenge]:
    return list(
        session.scalars(
            select(SignInChallenge).where(
                SignInChallenge.parent_id == parent_id,
                SignInChallenge.consumed_at.is_(None),
            )
        ).all()
    )


def challenge_for(session: Session, *, challenge_id: str, now: datetime) -> SignInChallenge | None:
    """The live challenge behind this handle, or None.

    None for unknown, already spent and expired alike - the caller must not be
    able to tell those apart, or the endpoint says which handles are real.
    """
    row = session.scalar(
        select(SignInChallenge).where(SignInChallenge.challenge_hash == token_hash(challenge_id))
    )
    if row is None or row.consumed_at is not None or row.expires_at <= now:
        return None
    return row


def verify_challenge(
    session: Session, *, challenge: SignInChallenge, code: str, now: datetime, max_attempts: int
) -> bool:
    """Spend one attempt against this challenge. True only if the code matched.

    A wrong guess is counted whether or not it was close, and the challenge dies
    on the last one: without that, six digits is a million tries rather than a
    secret.
    """
    challenge.attempts += 1
    matched = hmac.compare_digest(challenge.code_hash, keyed_hash(code))
    if matched:
        challenge.consumed_at = now
    elif challenge.attempts >= max_attempts:
        # Out of guesses. Spent, so the next attempt finds nothing at all.
        challenge.consumed_at = now
    session.flush()
    return matched


def record_resend(
    session: Session, *, challenge: SignInChallenge, code: str, now: datetime
) -> SignInChallenge:
    """Replace the code on a live challenge and count the send.

    The handle stays the same, so a client waiting on one screen does not have
    to start again; the previous code stops working the moment this is written,
    which is what "send it again" has to mean.
    """
    challenge.code_hash = keyed_hash(code)
    challenge.sends += 1
    challenge.last_sent_at = now
    session.flush()
    return challenge


def revoke_sessions(session: Session, *, parent_id: UUID) -> int:
    """Sign every device out. A password is reset because it may be known to
    someone else, and leaving their session open defeats the reset."""
    rows = session.scalars(select(AuthSession).where(AuthSession.parent_id == parent_id)).all()
    for row in rows:
        session.delete(row)
    session.flush()
    return len(rows)
