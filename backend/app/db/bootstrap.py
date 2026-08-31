"""Schema creation for the databases Alembic does not own.

PostgreSQL is migrated with `alembic upgrade head` and nothing here touches it -
two things creating tables in production is how a migration ends up half
applied. A developer's SQLite file and the test database have no migration
history worth keeping, so they are created from the models on startup, which is
what lets `uvicorn app.main:app` work on a clean checkout with no `DATABASE_URL`
set at all.
"""

import logging
from pathlib import Path

from sqlalchemy import inspect

from app.db.base import Base
from app.db import models  # noqa: F401  - imported so the tables register
from app.db.session import database_url, get_engine


logger = logging.getLogger(__name__)


def ensure_schema() -> bool:
    """Create the tables when the database is a local SQLite file.

    Returns whether it did, so the caller can log the difference between "schema
    ready" and "schema is Alembic's problem".
    """
    if not database_url().startswith("sqlite"):
        return False
    Base.metadata.create_all(get_engine())
    return True


def schema_ready() -> bool:
    """Whether the tables the app needs actually exist.

    A PostgreSQL URL with no migration run yet fails on the first write, deep
    inside a request. Checking once at startup turns that into a log line at
    boot with the fix in it.
    """
    try:
        return "children" in set(inspect(get_engine()).get_table_names())
    except Exception:  # pragma: no cover - unreachable database
        return False


def pending_migrations() -> list[str]:
    """The revisions the code carries that this database has not run yet.

    `schema_ready` only asks whether the tables exist, and that is not the
    failure that actually happens. A database one migration behind has every
    table it ever had - it answers `/health` cheerfully - and fails only on the
    column the new code selects. When that column was
    `daily_plan_items.completed_at`, *every* read of today's plan raised inside
    `plan_service`, which catches broadly so that infrastructure can never lock a
    child out of their lesson. The catch worked exactly as written: the schedule
    strip drew nothing, the day's gate opened on everything, and the AI Teacher
    quietly fell back to a one-stage sitting on the child's current topic. From
    the outside the scheduling had simply been removed, and nothing anywhere said
    why.

    So the check is the revision, not the table list. Empty means up to date, and
    empty is also what a SQLite developer file returns - that one is created from
    the models by `ensure_schema` and keeps no migration history worth comparing.
    """
    if database_url().startswith("sqlite"):
        return []
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext

        backend_root = Path(__file__).resolve().parents[2]
        config = Config(str(backend_root / "alembic.ini"))
        # `script_location` in the ini is relative to whatever directory the
        # process was started in, and the server is not always started from
        # `backend/`. Spell it out.
        config.set_main_option("script_location", str(backend_root / "alembic"))
        scripts = ScriptDirectory.from_config(config)

        with get_engine().connect() as connection:
            applied = MigrationContext.configure(connection).get_current_revision()

        head = scripts.get_current_head()
        if head is None or applied == head:
            return []
        # Oldest first, so the log line reads in the order they will run.
        return [
            revision.revision
            for revision in reversed(list(scripts.iterate_revisions(head, applied)))
        ]
    except Exception:  # pragma: no cover - alembic or the database unavailable
        # A check that cannot run must never stop the server: the app booted
        # without this for its whole life.
        logger.exception("Could not compare the database against the migrations")
        return []
