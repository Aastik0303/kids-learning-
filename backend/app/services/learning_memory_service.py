import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.config import get_settings


logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS learning_memories (
    id UUID PRIMARY KEY,
    child_id TEXT NOT NULL,
    path_id TEXT NOT NULL,
    stage_id TEXT NOT NULL,
    stage_number INTEGER NOT NULL CHECK (stage_number > 0),
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    completed_at TIMESTAMPTZ NOT NULL,
    UNIQUE (child_id, stage_id)
)
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS learning_memories_child_completed_idx
ON learning_memories (child_id, completed_at DESC)
"""

UPSERT_SQL = """
INSERT INTO learning_memories (
    id, child_id, path_id, stage_id, stage_number,
    title, objective, score, completed_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (child_id, stage_id) DO UPDATE SET
    path_id = EXCLUDED.path_id,
    stage_number = EXCLUDED.stage_number,
    title = EXCLUDED.title,
    objective = EXCLUDED.objective,
    score = EXCLUDED.score,
    completed_at = EXCLUDED.completed_at
"""

LATEST_SQL = """
SELECT child_id, path_id, stage_id, stage_number,
       title, objective, score, completed_at
FROM learning_memories
WHERE child_id = %s
ORDER BY completed_at DESC
LIMIT 1
"""


@dataclass(frozen=True)
class LearningMemory:
    child_id: str
    path_id: str
    stage_id: str
    stage_number: int
    title: str
    objective: str
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
    path_id: str,
    stage_id: str,
    stage_number: int,
    title: str,
    objective: str,
    score: int,
) -> LearningMemory:
    memory = LearningMemory(
        child_id=child_id,
        path_id=path_id,
        stage_id=stage_id,
        stage_number=stage_number,
        title=title,
        objective=objective,
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
                    memory.path_id,
                    memory.stage_id,
                    memory.stage_number,
                    memory.title,
                    memory.objective,
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
                    path_id=row[1],
                    stage_id=row[2],
                    stage_number=row[3],
                    title=row[4],
                    objective=row[5],
                    score=row[6],
                    completed_at=row[7],
                )
                _session_fallback[child_id] = memory
                return memory
        except Exception:
            logger.exception("Could not read latest learning memory from PostgreSQL")
    return _session_fallback.get(child_id)
