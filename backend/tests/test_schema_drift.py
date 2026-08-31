"""The database has to be at the revision the code is written against.

This is the test the project did not have on the day the whole schedule
disappeared. `daily_plan_items.completed_at` had a model column and a migration,
and the developer database had neither, because nothing had run
`alembic upgrade head`. Every read of today's plan raised on the missing column;
`plan_service` catches broadly on purpose - infrastructure must never lock a
child out of their lesson - so the failure came out as *silence*: an empty
schedule strip, a day gate that opened on everything, and an AI Teacher that
taught one stage off the child's current topic instead of the day's plan.

Two things are pinned here, and between them they close both halves of that:

* the migrations and the models describe the same database, so a column added to
  `app/db/models.py` without a migration fails here rather than in front of a
  child;
* the app can *say* it is behind, at boot and on `/health`, instead of degrading
  quietly.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.db.base import Base
from app.db import models  # noqa: F401  - imported so the tables register
from app.db.bootstrap import pending_migrations
from app.main import app


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _scripts() -> ScriptDirectory:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return ScriptDirectory.from_config(config)


def test_the_migrations_have_exactly_one_head():
    """Two heads is a merge nobody wrote, and `upgrade head` then refuses to run."""
    heads = _scripts().get_heads()
    assert len(heads) == 1, f"expected one migration head, found {heads}"


@pytest.fixture(scope="module")
def migrated_database(tmp_path_factory):
    """A database built the way production is: by running the migrations.

    Alembic is driven in a subprocess rather than in-process because `env.py`
    configures logging and its own engine from the environment, and doing that
    inside a test that has already booted the app leaves both changed for
    whatever runs next.
    """
    path = tmp_path_factory.mktemp("migrated") / "migrated.db"
    url = f"sqlite+pysqlite:///{path.as_posix()}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return create_engine(url)


def test_every_model_table_and_column_has_a_migration(migrated_database):
    """The models are what the code selects; the migrations are what exists.

    A column in `models.py` with no migration behind it is invisible until a
    query names it, and by then the failure is a swallowed exception three
    layers away from the thing that broke.
    """
    inspector = inspect(migrated_database)
    migrated_tables = set(inspector.get_table_names())

    missing_tables = sorted(set(Base.metadata.tables) - migrated_tables)
    assert not missing_tables, f"tables the models have and the migrations do not: {missing_tables}"

    missing_columns: list[str] = []
    for name, table in Base.metadata.tables.items():
        migrated_columns = {column["name"] for column in inspector.get_columns(name)}
        for column in table.columns:
            if column.name not in migrated_columns:
                missing_columns.append(f"{name}.{column.name}")

    assert not missing_columns, (
        "columns the models select and the migrations never create: "
        f"{sorted(missing_columns)}. Write a migration for them."
    )


def test_the_plan_cursor_column_is_migrated(migrated_database):
    """The specific column whose absence emptied the schedule.

    Named on its own because it is not interchangeable with the others: the plan
    cursor is what says an item of the day is finished, so without it there is no
    schedule at all.
    """
    columns = {column["name"] for column in inspect(migrated_database).get_columns("daily_plan_items")}
    assert "completed_at" in columns


def test_sqlite_reports_nothing_pending():
    """The suite's own database is created from the models and keeps no history."""
    assert pending_migrations() == []


def test_health_says_whether_the_schema_is_current():
    """So "the scheduling is gone" can be answered days after the boot log scrolled."""
    with TestClient(app) as client:
        body = client.get("/health").json()
    assert body["schema_current"] is True
    assert body["pending_migrations"] == []
