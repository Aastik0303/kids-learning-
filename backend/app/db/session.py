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


@lru_cache
def get_engine() -> Engine:
    url = database_url()
    if url.startswith("sqlite"):
        engine = create_engine(url, future=True, connect_args={"check_same_thread": False})
        _enable_sqlite_foreign_keys(engine)
        return engine
    settings = get_settings()
    return create_engine(
        url,
        future=True,
        # A managed Postgres closes an idle connection on its own side without
        # telling the pool, and the first query on a dead one fails. `pre_ping`
        # is the safety net - one cheap round trip per checkout - and
        # `pool_recycle` is what keeps it from being needed, by retiring a
        # connection before the server gets round to it.
        pool_pre_ping=True,
        pool_recycle=settings.database_pool_recycle_seconds,
        # Sized rather than left at the default. The default pool is five with
        # ten overflow, which on a managed instance with a low connection cap is
        # two workers away from "too many clients already" - and a request that
        # cannot get a connection should find that out in `pool_timeout` seconds
        # rather than holding a worker until something else gives up.
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        connect_args={"connect_timeout": settings.database_connect_timeout},
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


@contextmanager
def session_or(existing: Session | None) -> Iterator[Session]:
    """Work on the caller's session when there is one, or open a unit of work.

    Opening a second session inside a request that already holds one is not free
    and on SQLite it is not even fast: the outer session's read transaction is
    still open, so the inner one waits the driver's whole five-second busy
    timeout for a write lock before it gets anywhere. That is five seconds per
    teaching turn, on every turn, and it does not show up as an error - only as
    a class that has become unusably slow.

    So a caller that is already inside a `session_scope` passes its session in
    and the work joins that transaction: one lock, one commit, and the episode
    lands or rolls back with the turn that produced it. A caller with nothing
    open - a background sweep, a test - passes `None` and gets the scope.
    """
    if existing is not None:
        yield existing
        # No commit here: the transaction belongs to whoever opened it, and
        # committing it from underneath them would half-land their own work.
        return
    with session_scope() as session:
        yield session


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
