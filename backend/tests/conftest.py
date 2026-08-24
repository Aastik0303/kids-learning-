"""Every test gets its own database.

The suite used to run against dictionaries, so isolation was free: a fresh
process had no state. Now that parents, children, attempts, mastery, probes and
the Q-table are all rows, each test needs its own file - otherwise a child
registered in one test is still registered in the next, and a Q-value learned in
one changes the strategy chosen in another.

SQLite, not PostgreSQL, because the models are written against SQLAlchemy's
portable types and one Alembic migration describes both. What is exercised here
is the same repository code that runs against PostgreSQL in production.

The environment is saved and restored by hand rather than through `monkeypatch`.
An autouse fixture in a conftest is set up before the module's own fixtures, so
requesting `monkeypatch` here would make its teardown the *last* to run - and
`test_curriculum` has module fixtures that reload the manifest on the way out
and need their own patches undone before that happens.
"""

import os
from datetime import date, timedelta

import pytest

from app.config import get_settings
from app.db.bootstrap import ensure_schema
from app.db.session import reset_engine
from app.services import child_store, plan_service


TEST_ENVIRONMENT = {
    # No provider, so the suite never reaches the network. `backend/.env` sets
    # `LLM_PROVIDER=groq` on this machine, and without this every guide test
    # would spend a real call and a six-second timeout on a path whose whole
    # point is that it has a deterministic answer ready.
    "LLM_PROVIDER": "none",
    # PBKDF2 at its production round count costs a few hundred milliseconds per
    # registration, and this suite registers a parent in most of its tests. The
    # code path is identical; only the work factor changes.
    "PASSWORD_HASH_ROUNDS": "1000",
    # Exploration off by default: a policy that sometimes picks a random legal
    # strategy would make every assertion about which strategy was chosen flaky.
    # `test_policy_wiring` turns it back on where that is the thing being tested.
    "POLICY_EXPLORE_RATE": "0",
    # The planner sweeps in the background of a running app. In the suite it is
    # off, so a test that asserts on today's plan is asserting on what its own
    # code did - `test_planner_agent` calls the sweep directly instead.
    "PLANNER_AUTO_RUN": "0",
}


@pytest.fixture(autouse=True)
def durable_database(tmp_path):
    previous = {key: os.environ.get(key) for key in (*TEST_ENVIRONMENT, "DATABASE_URL")}
    os.environ.update(TEST_ENVIRONMENT)
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{(tmp_path / 'saksham-test.db').as_posix()}"

    get_settings.cache_clear()
    reset_engine()
    child_store.reset_cache()
    ensure_schema()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        reset_engine()
        get_settings.cache_clear()
        child_store.reset_cache()


@pytest.fixture()
def next_day(monkeypatch):
    """Roll the calendar forward, the way a child coming back next morning does.

    The day's plan is the day's work: finishing a level unlocks the next one and
    the next one opens *tomorrow*, in tomorrow's plan. A test that plays two
    levels of the same subject is therefore a test about two days, and this is
    how it says so.

    `next_day.until_planned(...)` rolls until the plan actually holds a topic. A
    day is three lessons and a nursery child has six subjects, so the subjects
    take turns - "it opens tomorrow" is really "it opens on the day the plan
    comes round to it", and a test should say the true thing.

    Requested rather than autouse, so it is set up after the module's own
    fixtures and torn down before them.
    """
    offset = {"days": 0}

    def _roll(days: int = 1) -> date:
        offset["days"] += days
        target = date.today() + timedelta(days=offset["days"])
        monkeypatch.setattr(plan_service, "_today", lambda: target)
        return target

    def _until_planned(client, child_id: str, topic_id: str, limit: int = 12) -> dict:
        for _ in range(limit):
            plan = client.get(f"/plans/{child_id}/today").json()
            if any(item["topic_id"] == topic_id for item in plan["items"]):
                return plan
            _roll()
        raise AssertionError(f"{topic_id} was never planned within {limit} days")

    _roll.until_planned = _until_planned
    return _roll
