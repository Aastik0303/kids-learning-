"""Where a child's record is read from and written back to.

The services above this one work on a plain dict and mutate it in place -
`child["stars"] += 3`, `progress["completed_topics"].append(topic_id)`. That
worked because the dict lived in `mock_child_profiles` and every reader held the
same object. It also meant a restart lost every child.

The dict is now a row in `child_progress`. Two things keep the old in-place style
working without a rewrite of every caller:

- **an identity map**, so a child read twice inside one process is the same
  object, and a mutation made in `learning_service` is visible in
  `practice_service` exactly as before;
- **`save()` at the end of each mutating entry point**, which writes the whole
  record back in one statement.

The identity map is process-local, so two API workers hold two copies. That is
fine for what lives here - stars, unlock board, rewards - because each is
last-write-wins on data the same child changes one tap at a time. Nothing that
must not be lost lives here: attempts, mastery, teaching events and probes are
written straight to their own tables inside the request that produced them.
"""

from uuid import UUID

from app.db.models import Child
from app.db.repositories import learners, profiles
from app.db.session import session_scope
from app.services.errors import app_error


_cache: dict[str, dict] = {}


def reset_cache() -> None:
    """Drop the identity map. The tests call this between databases."""
    _cache.clear()


def _child_uuid(child_id: str) -> UUID:
    try:
        return UUID(str(child_id))
    except (ValueError, AttributeError, TypeError):
        raise app_error("INVALID_CHILD", "We could not find that child profile.", 404) from None


def create(
    *,
    parent_id: UUID,
    name: str,
    birth_year: int,
    birth_month: int,
    class_id: str,
    experience_mode: str,
    preferred_language: str,
    state: dict,
) -> dict:
    with session_scope() as session:
        parent = session.get(learners.Parent, parent_id)
        if parent is None:
            raise app_error("MISSING_SESSION", "Please log in again.", 401)
        child = learners.create_child(
            session,
            parent=parent,
            name=name,
            birth_year=birth_year,
            birth_month=birth_month,
            class_id=class_id,
            experience_mode=experience_mode,
            preferred_language=preferred_language,
        )
        record = {**state, "child_id": str(child.id), "user_id": str(parent.id)}
        profiles.save_record(session, record)
    _cache[record["child_id"]] = record
    return record


def get(child_id: str) -> dict:
    cached = _cache.get(str(child_id))
    if cached is not None:
        return cached
    with session_scope() as session:
        record = profiles.load_by_id(session, _child_uuid(child_id))
    if record is None:
        raise app_error("INVALID_CHILD", "We could not find that child profile.", 404)
    _cache[record["child_id"]] = record
    return record


def find(child_id: str) -> dict | None:
    """Like `get`, but for callers that answer their own 404."""
    try:
        return get(child_id)
    except Exception:
        return None


def save(record: dict) -> None:
    with session_scope() as session:
        profiles.save_record(session, record)
    _cache[str(record["child_id"])] = record


def records_for_parent(parent_id: UUID) -> list[dict]:
    with session_scope() as session:
        records = profiles.records_for_parent(session, parent_id)
    # A child already in the identity map may carry mutations this request made;
    # prefer that object over the row it was loaded from.
    return [_cache.setdefault(record["child_id"], record) for record in records]


def child_row(child_id: str) -> Child | None:
    """The `children` row itself, for the modules that need a foreign key."""
    with session_scope() as session:
        return session.get(Child, _child_uuid(child_id))
