"""Sign-in throttling and password resets.

Two small tables, both of them about the one endpoint an attacker actually
reaches: `POST /auth/login`. Everything here is written from the auth service
and read nowhere else.
"""

import hashlib
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuthSession, AuthThrottle, PasswordReset


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


def revoke_sessions(session: Session, *, parent_id: UUID) -> int:
    """Sign every device out. A password is reset because it may be known to
    someone else, and leaving their session open defeats the reset."""
    rows = session.scalars(select(AuthSession).where(AuthSession.parent_id == parent_id)).all()
    for row in rows:
        session.delete(row)
    session.flush()
    return len(rows)
