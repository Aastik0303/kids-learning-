"""Schema creation for the databases Alembic does not own.

PostgreSQL is migrated with `alembic upgrade head` and nothing here touches it -
two things creating tables in production is how a migration ends up half
applied. A developer's SQLite file and the test database have no migration
history worth keeping, so they are created from the models on startup, which is
what lets `uvicorn app.main:app` work on a clean checkout with no `DATABASE_URL`
set at all.
"""

from sqlalchemy import inspect

from app.db.base import Base
from app.db import models  # noqa: F401  - imported so the tables register
from app.db.session import database_url, get_engine


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
