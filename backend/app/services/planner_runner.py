"""The planner, running itself.

A plan that is only built when a child opens the app is not a schedule - it is a
lazy computation with a nicer name, and it puts the agent's latency in front of a
three-year-old who is already waiting for the screen. This sweeps instead: every
`planner_interval_seconds`, every child with no plan frozen for today gets one.

Three properties it has to have, because it runs unattended:

- **idempotent** - it asks the database which children are missing a plan, and
  the freeze itself is a unique constraint, so a second sweep (or a second
  worker) writes nothing;
- **quiet on failure** - an unreachable database, or one child whose curriculum
  is in a state this cannot plan, must not take the API process with it. Every
  sweep is wrapped, and a failed child does not stop the ones behind them;
- **off by default in tests**, which is what `PLANNER_AUTO_RUN=0` is for.
"""

import asyncio
import logging
from datetime import date

from app.config import get_settings
from app.db.repositories import plans
from app.db.session import session_scope
from app.services import child_service, plan_service, retention_test_service


logger = logging.getLogger(__name__)

# A sweep touches at most this many children per pass. A backlog is worked
# through over several passes rather than in one long transaction that holds
# connections while the app is trying to serve lessons.
BATCH = 200


def sweep(*, today: date | None = None) -> dict:
    """Freeze today's plan for every child who has not got one.

    ...and schedule the retention tests that have come due, which are part of the
    same schedule: `due_at = the teaching turn + 2 days`, one per teaching
    episode, created by an anti-join so a repeated sweep writes nothing.

    Returns a small summary so the caller can log it and the tests can assert on
    it: `{"considered": n, "planned": n, "skipped": n, "retention_tests": n}`.
    "Skipped" is a child with nothing legal to study today - every unlocked
    topic finished, or a class with no authored content yet - which is a normal
    state, not an error.
    """
    # The schedule's own clock: a sweep that froze `date.today()` while the
    # class asked `plan_service.today()` would plan a day nobody opens.
    plan_date = today or plan_service.today()
    summary = {"considered": 0, "planned": 0, "skipped": 0, "failed": 0, "retention_tests": 0}

    # Retention tests are part of the schedule, so they are created by the same
    # sweep that freezes the day - not by a mechanism of their own running on
    # its own timer. A concept taught two days ago becomes testable here, and
    # the class asks it at the start of the next sitting.
    #
    # First, and outside the per-child loop, because it is one bounded anti-join
    # over `policy_episodes` rather than a query per child, and because a
    # curriculum that cannot be planned must not stop a test being scheduled.
    summary["retention_tests"] = retention_test_service.schedule().get("created", 0)

    try:
        with session_scope() as session:
            child_ids = plans.children_missing_a_plan(session, plan_date=plan_date, limit=BATCH)
    except Exception:  # pragma: no cover - database unavailable
        logger.exception("Planner sweep could not list children")
        return summary

    summary["considered"] = len(child_ids)
    for child_id in child_ids:
        try:
            child = child_service.get_child(str(child_id))
            result = plan_service.freeze_today(child, today=plan_date)
        except Exception:
            # One child's curriculum being in a state this cannot plan must not
            # stop the queue behind them.
            logger.exception("Planner sweep failed for child %s", child_id)
            summary["failed"] += 1
            continue

        if result is None or not result.frozen:
            summary["skipped"] += 1
            continue
        summary["planned"] += 1

    if summary["planned"] or summary["failed"] or summary["retention_tests"]:
        logger.info("Planner sweep for %s: %s", plan_date, summary)
    return summary


async def run_forever() -> None:
    """The background task. Cancelled on shutdown by the lifespan handler."""
    settings = get_settings()
    interval = max(60, settings.planner_interval_seconds)
    while True:
        try:
            # The sweep is blocking database work; running it on a thread keeps
            # the event loop free to serve the lesson that is in progress.
            await asyncio.to_thread(sweep)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - defensive
            logger.exception("Planner sweep raised; the loop continues")
        await asyncio.sleep(interval)


def start(loop_factory=asyncio.create_task):
    """Start the sweep loop if it is enabled. Returns the task, or None."""
    if not get_settings().planner_auto_run:
        logger.info("Planner auto-run is off (PLANNER_AUTO_RUN=0)")
        return None
    return loop_factory(run_forever())
