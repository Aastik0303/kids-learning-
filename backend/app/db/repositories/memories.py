"""The guide's memory of finished lessons.

One row per child per topic, overwritten when the topic is replayed. It is a
convenience for the greeting - "you finished Shapes yesterday" - and never a
source of truth: `attempts` and `skill_mastery` are truth, and nothing here is
read to decide correctness, mastery or unlocking.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TopicMemory


def record_completed_lesson(
    session: Session,
    *,
    child_id: str,
    subject_id: str,
    topic_id: str,
    title: str,
    score: int,
    completed_at: datetime,
) -> TopicMemory:
    row = session.scalar(
        select(TopicMemory).where(TopicMemory.child_id == child_id, TopicMemory.topic_id == topic_id)
    )
    if row is None:
        row = TopicMemory(child_id=child_id, topic_id=topic_id)
        session.add(row)
    row.subject_id = subject_id
    row.title = title
    # Clamped rather than rejected: a caller that computed 101 has a bug, and
    # refusing to remember the lesson is a worse answer than remembering 100.
    row.score = max(0, min(100, int(score)))
    row.completed_at = completed_at
    session.flush()
    return row


def latest_for(session: Session, *, child_id: str) -> TopicMemory | None:
    return session.scalar(
        select(TopicMemory)
        .where(TopicMemory.child_id == child_id)
        .order_by(TopicMemory.completed_at.desc())
    )


def memories_for(session: Session, *, child_id: str, limit: int = 20) -> list[TopicMemory]:
    return list(
        session.scalars(
            select(TopicMemory)
            .where(TopicMemory.child_id == child_id)
            .order_by(TopicMemory.completed_at.desc())
            .limit(limit)
        ).all()
    )


def forget_child(session: Session, *, child_id: UUID | str) -> int:
    """Erase one child's lesson memory. The parent-facing delete path uses this."""
    rows = session.scalars(select(TopicMemory).where(TopicMemory.child_id == str(child_id))).all()
    for row in rows:
        session.delete(row)
    session.flush()
    return len(rows)
