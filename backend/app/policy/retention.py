"""When a taught concept becomes testable, and in what order the due tests run.

Pure rules, no database and no clock of its own - the same shape as
`eligibility.py` and `leak.py`. Everything here is a function of a timestamp and
a row, so the scheduler's decisions can be read and asserted without a session.

**The scheduler owns "when".** Q-learning chooses *how* to teach and is paid for
it days later; it has no say in when the payment is collected, because a policy
that could choose when it is tested could choose to be tested on the concepts it
happens to have taught well. So the delay is a setting, the ordering is a total
order over columns, and neither reads a Q-value.

The ordering is deterministic on purpose. "If multiple retention tests are due,
do not randomly select" is not a style preference: a child's morning must be the
same shape whichever worker serves it, and an evaluation that replays episodes
cannot separate a policy's effect from a shuffle's.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import get_settings


# The statuses a retention test row can be in.
PENDING = "pending"
SETTLED = "settled"
# The concept's syllabus has no question that can be asked of a child - all
# tracing, or a topic whose authored questions have gone. Marked rather than
# left pending, so an unanswerable test does not sit at the head of the queue
# for ever holding up the ones behind it.
VOID = "void"

STATUSES = (PENDING, SETTLED, VOID)


def delay() -> timedelta:
    """How long after teaching a concept becomes eligible to be tested.

    Two days by default, and a setting rather than a constant because it is the
    one number the whole feature is defined by.
    """
    return timedelta(days=max(0, int(get_settings().retention_test_delay_days)))


def per_sitting() -> int:
    """How many due tests one sitting opens with."""
    return max(0, int(get_settings().retention_tests_per_sitting))


def due_at(taught_at: datetime) -> datetime:
    """`due_at = teaching_time + 2 days`, in UTC.

    A naive timestamp is read as UTC rather than as local time. SQLite hands
    back naive datetimes for a column PostgreSQL makes aware, and comparing one
    of each is a `TypeError` in the middle of a sweep.
    """
    return as_utc(taught_at) + delay()


def as_utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def is_due(test, *, now: datetime) -> bool:
    """Whether this pending test may be asked yet."""
    return test.status == PENDING and as_utc(test.due_at) <= as_utc(now)


def order_key(test) -> tuple:
    """The order due tests are asked in, and it is a total order.

    Oldest debt first, then the concept's own name, then the row id - so two
    tests that came due in the same second still have one answer, and it is the
    same answer on every worker and after every restart.
    """
    return (as_utc(test.due_at), test.concept_id or "", str(test.id))


def is_transfer(*, taught_question_ref: str, asked_question_ref: str) -> bool:
    """Whether answering this test is evidence of transfer rather than recall.

    True when the test asked a *different* authored question about the same
    concept from the one the episode was taught with. With nothing recorded
    about the teaching question the answer is False: an unproven transfer is not
    paid for.
    """
    taught = (taught_question_ref or "").strip()
    asked = (asked_question_ref or "").strip()
    return bool(taught and asked and taught != asked)


__all__ = [
    "PENDING",
    "SETTLED",
    "STATUSES",
    "VOID",
    "as_utc",
    "delay",
    "due_at",
    "is_due",
    "is_transfer",
    "order_key",
    "per_sitting",
]
