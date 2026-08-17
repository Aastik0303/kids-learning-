import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.config import get_settings


logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS topic_memories (
    id UUID PRIMARY KEY,
    child_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    title TEXT NOT NULL,
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    completed_at TIMESTAMPTZ NOT NULL,
    UNIQUE (child_id, topic_id)
)
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS topic_memories_child_completed_idx
ON topic_memories (child_id, completed_at DESC)
"""

UPSERT_SQL = """
INSERT INTO topic_memories (
    id, child_id, subject_id, topic_id, title, score, completed_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (child_id, topic_id) DO UPDATE SET
    subject_id = EXCLUDED.subject_id,
    title = EXCLUDED.title,
    score = EXCLUDED.score,
    completed_at = EXCLUDED.completed_at
"""

LATEST_SQL = """
SELECT child_id, subject_id, topic_id, title, score, completed_at
FROM topic_memories
WHERE child_id = %s
ORDER BY completed_at DESC
LIMIT 1
"""


@dataclass(frozen=True)
class LearningMemory:
    child_id: str
    subject_id: str
    topic_id: str
    title: str
    score: int
    completed_at: datetime


_session_fallback: dict[str, LearningMemory] = {}
_schema_ready = False
_schema_lock = Lock()


def postgres_enabled() -> bool:
    return bool(get_settings().database_url.strip())


def _connect():
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("PostgreSQL memory needs the psycopg package") from exc

    settings = get_settings()
    return psycopg.connect(
        settings.database_url,
        connect_timeout=settings.database_connect_timeout,
    )


def initialize_learning_memory_store() -> bool:
    global _schema_ready

    if not postgres_enabled():
        return False
    if _schema_ready:
        return True

    with _schema_lock:
        if _schema_ready:
            return True
        try:
            with _connect() as connection:
                connection.execute(CREATE_TABLE_SQL)
                connection.execute(CREATE_INDEX_SQL)
            _schema_ready = True
        except Exception:
            logger.exception("Could not initialize PostgreSQL learning memory")
            return False
    return True


def record_completed_lesson(
    *,
    child_id: str,
    subject_id: str,
    topic_id: str,
    title: str,
    score: int,
) -> LearningMemory:
    memory = LearningMemory(
        child_id=child_id,
        subject_id=subject_id,
        topic_id=topic_id,
        title=title,
        score=score,
        completed_at=datetime.now(timezone.utc),
    )
    _session_fallback[child_id] = memory

    if not initialize_learning_memory_store():
        return memory

    try:
        with _connect() as connection:
            connection.execute(
                UPSERT_SQL,
                (
                    uuid4(),
                    memory.child_id,
                    memory.subject_id,
                    memory.topic_id,
                    memory.title,
                    memory.score,
                    memory.completed_at,
                ),
            )
    except Exception:
        logger.exception("Could not save completed lesson to PostgreSQL")
    return memory


def get_latest_learning_memory(child_id: str) -> LearningMemory | None:
    if initialize_learning_memory_store():
        try:
            with _connect() as connection:
                row = connection.execute(LATEST_SQL, (child_id,)).fetchone()
            if row:
                memory = LearningMemory(
                    child_id=row[0],
                    subject_id=row[1],
                    topic_id=row[2],
                    title=row[3],
                    score=row[4],
                    completed_at=row[5],
                )
                _session_fallback[child_id] = memory
                return memory
        except Exception:
            logger.exception("Could not read latest learning memory from PostgreSQL")
    return _session_fallback.get(child_id)
