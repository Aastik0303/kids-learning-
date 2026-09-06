"""What the guide remembers about finished lessons.

One row per child per topic - the last one they completed and how it went - so a
returning child is greeted with "you finished Shapes yesterday" instead of as a
stranger.

This module used to speak psycopg directly: its own connection, its own
`CREATE TABLE IF NOT EXISTS`, its own hand-written SQL, and a `postgres_enabled`
flag that turned the whole feature off whenever `DATABASE_URL` was not
PostgreSQL. It was the last thing in the codebase outside the SQLAlchemy layer,
which meant it had its own failure modes, its own connection pool, no migration
covering its table, and nothing on SQLite - so a developer running locally never
exercised the code at all.

It now goes through `app/db/repositories/memories.py` like everything else. The
table shape is unchanged, so an existing `topic_memories` is picked up as it is.

The in-process fallback stays for one reason: this is a greeting. If the
database is unreachable, the right behaviour is a slightly less personal hello,
not a failed lesson.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.db.repositories import memories
from app.db.session import database_url, session_scope


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LearningMemory:
    child_id: str
    subject_id: str
    topic_id: str
    title: str
    score: int
    completed_at: datetime


# Last resort only: what this process has seen since it started. Used when the
# database cannot be reached, so the guide degrades to a warm greeting rather
# than an error in front of a child.
_session_fallback: dict[str, LearningMemory] = {}


def store_enabled() -> bool:
    """There is always a database now - PostgreSQL in production, a local SQLite
    file otherwise - so the store is always on."""
    return bool(database_url())


def initialize_learning_memory_store() -> bool:
    """Kept for the startup hook. The schema is Alembic's job, or
    `db.bootstrap`'s on SQLite; there is nothing to create here any more."""
    return store_enabled()


def _as_memory(row) -> LearningMemory:
    return LearningMemory(
        child_id=row.child_id,
        subject_id=row.subject_id,
        topic_id=row.topic_id,
        title=row.title,
        score=row.score,
        completed_at=row.completed_at,
    )


def record_completed_lesson(
    *,
    child_id: str,
    subject_id: str,
    topic_id: str,
    title: str,
    score: int,
    completed_at: datetime | None = None,
) -> LearningMemory:
    memory = LearningMemory(
        child_id=child_id,
        subject_id=subject_id,
        topic_id=topic_id,
        title=title,
        score=score,
        completed_at=completed_at or datetime.now(timezone.utc),
    )
    _session_fallback[child_id] = memory

    try:
        with session_scope() as session:
            memories.record_completed_lesson(
                session,
                child_id=child_id,
                subject_id=subject_id,
                topic_id=topic_id,
                title=title,
                score=score,
                completed_at=memory.completed_at,
            )
    except Exception:
        # The lesson itself is already saved - the attempt log and the mastery
        # roll-up were committed before this was called. Losing the greeting is
        # not worth failing the response for.
        logger.exception("Could not save the completed lesson to the memory store")
    return memory


def get_latest_learning_memory(child_id: str) -> LearningMemory | None:
    try:
        with session_scope() as session:
            row = memories.latest_for(session, child_id=child_id)
        if row is not None:
            memory = _as_memory(row)
            _session_fallback[child_id] = memory
            return memory
    except Exception:
        logger.exception("Could not read the latest learning memory")
    return _session_fallback.get(child_id)


