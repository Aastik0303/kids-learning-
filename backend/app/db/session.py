"""Engine and session handling.

`DATABASE_URL` is PostgreSQL in every real environment. It falls back to a local
SQLite file so a developer can run the suite without a server, and the tests use
an in-memory SQLite database of their own - the models are written against
SQLAlchemy's portable types (`Uuid`, `DateTime(timezone=True)`) so the same
migration describes both.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


DEFAULT_SQLITE_URL = "sqlite+pysqlite:///./saksham.db"


def database_url() -> str:
    """The URL SQLAlchemy should open, with the driver spelled out.

    `requirements.txt` pins psycopg 3, but SQLAlchemy still reads a bare
    `postgresql://` as psycopg *2* and fails with `No module named psycopg2` -
    which is what a `DATABASE_URL` copied from any PostgreSQL tutorial looks
    like, and what `backend/.env` holds. Normalising here rather than asking
    every environment to write `postgresql+psycopg://` keeps one connection
    string working for Alembic, the app and psql alike.
    """
    raw = get_settings().database_url.strip() or DEFAULT_SQLITE_URL
    if raw.startswith("postgres://"):
        raw = f"postgresql://{raw[len('postgres://'):]}"
    if raw.startswith("postgresql://"):
        return f"postgresql+psycopg://{raw[len('postgresql://'):]}"
    return raw


def libpq_url() -> str:
    """The same URL as libpq wants it: no SQLAlchemy driver token.

    `psycopg.connect()` rejects `postgresql+psycopg://`, so the one module that
    speaks psycopg directly asks for this form.
    """
    return database_url().replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache
def get_engine() -> Engine:
    url = database_url()
    if url.startswith("sqlite"):
        engine = create_engine(url, future=True, connect_args={"check_same_thread": False})
        _enable_sqlite_foreign_keys(engine)
        return engine
    return create_engine(
        url,
        future=True,
        pool_pre_ping=True,
        connect_args={"connect_timeout": get_settings().database_connect_timeout},
    )


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """SQLite ignores foreign keys unless asked, per connection.

    Without this a developer's local run silently accepts rows PostgreSQL would
    reject, and the difference only surfaces in production.
    """

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _record):  # pragma: no cover - driver hook
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """A unit of work that commits on success and rolls back on any exception.

    Every write that must not half-land - an attempt and the mastery row it
    moves, a plan and its items - belongs inside one of these.
    """
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as session:
        yield session


def reset_engine() -> None:
    """Drop the cached engine so a changed `DATABASE_URL` is picked up.

    Only the tests and a process-level reconfiguration should call this.
    """
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
