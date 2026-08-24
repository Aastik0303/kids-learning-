"""The declarative base every table hangs off.

The naming convention matters more than it looks: Alembic autogenerate can only
write a `DROP CONSTRAINT` for a constraint it can name, and SQLite never names
them the same way PostgreSQL does. Fixing the convention here means a migration
generated against a developer's SQLite file still applies to production
PostgreSQL.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, MetaData, TypeDecorator
from sqlalchemy.orm import DeclarativeBase


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UTCDateTime(TypeDecorator):
    """A timestamp that is always aware, and always UTC, on the way out.

    PostgreSQL stores the offset; SQLite does not, and hands back a naive
    datetime. Comparing one of those to `datetime.now(timezone.utc)` raises
    `TypeError: can't compare offset-naive and offset-aware datetimes` - which
    is not a test-only nuisance, because it lands on session expiry and on
    whether a retention probe is due. Normalising in one place means every
    column that stores a moment behaves the same way on both backends.

    The stored type is unchanged - `DateTime(timezone=True)` - so the existing
    migrations describe it exactly as they did.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        # A naive value is taken as UTC: everything in this codebase that makes
        # a timestamp makes it with `datetime.now(timezone.utc)`.
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
