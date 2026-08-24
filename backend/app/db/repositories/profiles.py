"""The child's progress ledger, loaded and saved as one document.

`child_service` works on a plain dict - stars, rewards, weak skills, and a board
of unlocked topics per subject - and every service downstream mutates it in
place. That dict used to live in `mock_child_profiles` and was lost on restart.
It now lives in `child_progress.state`, and the identity fields inside it are
mirrored onto the `children` row so the rest of the durable layer (plans,
teaching events, probes) has a real learner to point a foreign key at.

The mirror is deliberately one-way: `children` is the identity, `state` is the
ledger, and where a field appears in both the ledger is written from the row on
load. Two writers on one field is how a name change lands in half the app.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Child, ChildProgress


# The fields the `children` table owns. They are copied into the ledger on every
# load, so a row edited elsewhere - a parent renaming a child, a class override -
# is what the child surface reads.
IDENTITY_FIELDS = ("name", "birth_year", "birth_month", "class_id", "experience_mode", "preferred_language")


def _progress_row(session: Session, child_id: UUID) -> ChildProgress:
    row = session.scalar(select(ChildProgress).where(ChildProgress.child_id == child_id))
    if row is None:
        row = ChildProgress(child_id=child_id, state={})
        session.add(row)
        session.flush()
    return row


def load_record(session: Session, child: Child) -> dict:
    """The dict the services expect, rebuilt from the row and its ledger."""
    row = _progress_row(session, child.id)
    record = dict(row.state or {})
    record["child_id"] = str(child.id)
    record["user_id"] = str(child.parent_id)
    for field in IDENTITY_FIELDS:
        record[field] = getattr(child, field)
    return record


def load_by_id(session: Session, child_id: UUID) -> dict | None:
    child = session.get(Child, child_id)
    return load_record(session, child) if child is not None else None


def records_for_parent(session: Session, parent_id: UUID) -> list[dict]:
    children = session.scalars(
        select(Child).where(Child.parent_id == parent_id).order_by(Child.created_at)
    ).all()
    return [load_record(session, child) for child in children]


def save_record(session: Session, record: dict) -> None:
    """Write the ledger back, and mirror the identity fields onto the row.

    Everything except `child_id` and `user_id` is stored: those two are the keys,
    and keeping a copy of a key inside the document it keys is how the two drift.
    """
    child_id = UUID(str(record["child_id"]))
    child = session.get(Child, child_id)
    if child is None:  # pragma: no cover - a record with no learner behind it
        return
    for field in IDENTITY_FIELDS:
        value = record.get(field)
        if value is not None and getattr(child, field) != value:
            setattr(child, field, value)

    row = _progress_row(session, child_id)
    row.state = {key: value for key, value in record.items() if key not in ("child_id", "user_id")}
    session.flush()
