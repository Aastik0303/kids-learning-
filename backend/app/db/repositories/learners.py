"""Parents, auth sessions and children.

Replaces `mock_auth.py` and the `mock_users` / `mock_child_profiles` dicts. The
password hashing here is still a placeholder for the real one - see the note on
`set_password` - but the *storage* is no longer a dictionary that forgets every
family when the process restarts.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuthSession, Child, Parent


SESSION_TTL = timedelta(days=30)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_parent(session: Session, *, email: str, name: str, password_hash: str) -> Parent:
    parent = Parent(email=email.strip().lower(), name=name, password_hash=password_hash)
    session.add(parent)
    session.flush()
    return parent


def parent_by_email(session: Session, email: str) -> Parent | None:
    return session.scalar(select(Parent).where(Parent.email == email.strip().lower()))


def grant_consent(session: Session, parent: Parent, *, now: datetime | None = None) -> Parent:
    """Consent is set by a person tapping a control, and never by the app.

    DPDP and COPPA both require an explicit act, so nothing in the automation
    path may call this - it exists so the parent surface can.
    """
    parent.consent_granted_at = now or _now()
    session.flush()
    return parent


def open_session(session: Session, parent: Parent, *, now: datetime | None = None) -> AuthSession:
    started = now or _now()
    auth = AuthSession(token=uuid4().hex, parent_id=parent.id, expires_at=started + SESSION_TTL)
    session.add(auth)
    session.flush()
    return auth


def parent_for_token(session: Session, token: str, *, now: datetime | None = None) -> Parent | None:
    auth = session.get(AuthSession, token)
    if auth is None or auth.expires_at <= (now or _now()):
        return None
    return session.get(Parent, auth.parent_id)


def close_session(session: Session, token: str) -> None:
    auth = session.get(AuthSession, token)
    if auth is not None:
        session.delete(auth)
        session.flush()


def create_child(
    session: Session,
    *,
    parent: Parent,
    name: str,
    birth_year: int,
    birth_month: int,
    class_id: str,
    experience_mode: str = "standard",
    preferred_language: str = "en",
) -> Child:
    child = Child(
        parent_id=parent.id,
        name=name,
        birth_year=birth_year,
        birth_month=birth_month,
        class_id=class_id,
        experience_mode=experience_mode,
        preferred_language=preferred_language,
    )
    session.add(child)
    session.flush()
    return child


def owned_child(session: Session, *, parent: Parent, child_id: UUID) -> Child | None:
    """The authorisation check every child-scoped endpoint needs.

    Returning None rather than raising keeps the decision at the call site: a
    route answers 404, a background job skips the row.
    """
    child = session.get(Child, child_id)
    if child is None or child.parent_id != parent.id:
        return None
    return child
