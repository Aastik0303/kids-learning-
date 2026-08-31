"""The daily plan, and the freeze that makes it a routine.

A plan is generated once per `(child_id, plan_date)` and read every time after
that. Refresh, re-login and back-navigation all take the read path. Without the
freeze the Planner Agent produces a slightly different plan on every load, and a
three-year-old never gets the same lesson twice in a row - which is the opposite
of what a routine is.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.models import Child, DailyPlan, DailyPlanItem


@dataclass(frozen=True)
class PlannedItem:
    topic_id: str
    skill_id: str
    reason: str = "new"


def plan_for(session: Session, *, child_id: UUID, plan_date: date) -> DailyPlan | None:
    return session.scalar(
        select(DailyPlan)
        .options(selectinload(DailyPlan.items))
        .where(DailyPlan.child_id == child_id, DailyPlan.plan_date == plan_date)
    )


def freeze_plan(
    session: Session,
    *,
    child_id: UUID,
    plan_date: date,
    items: Sequence[PlannedItem],
    source: str = "deterministic",
) -> DailyPlan:
    """Write the plan, or return the one already frozen for that day.

    The unique constraint, not this read, is what actually guarantees one plan
    per day: two requests can both find nothing and both try to write. The
    IntegrityError path is the real freeze, and it returns the winner's plan
    rather than raising, because from the child's side either plan is the plan.
    """
    existing = plan_for(session, child_id=child_id, plan_date=plan_date)
    if existing is not None:
        return existing

    plan = DailyPlan(child_id=child_id, plan_date=plan_date, source=source)
    plan.items = [
        DailyPlanItem(position=index, topic_id=item.topic_id, skill_id=item.skill_id, reason=item.reason)
        for index, item in enumerate(items)
    ]
    session.add(plan)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        winner = plan_for(session, child_id=child_id, plan_date=plan_date)
        if winner is None:  # pragma: no cover - only if the constraint is gone
            raise
        return winner
    return plan


def recent_plans(session: Session, *, child_id: UUID, since: date, limit: int = 60) -> list[DailyPlan]:
    """The child's plans from `since` onwards, newest first.

    The parent surface reads this to see what the week actually looked like -
    and, because `source` travels with each row, how much of it the Planner
    Agent decided rather than the deterministic fallback.
    """
    return list(
        session.scalars(
            select(DailyPlan)
            .options(selectinload(DailyPlan.items))
            .where(DailyPlan.child_id == child_id, DailyPlan.plan_date >= since)
            .order_by(DailyPlan.plan_date.desc())
            .limit(limit)
        ).all()
    )


def children_missing_a_plan(session: Session, *, plan_date: date, limit: int = 500) -> list[UUID]:
    """Every child with no plan frozen for that date.

    This is what the background planner sweeps. It is a small anti-join rather
    than "load every child and check": the whole point of running it on a timer
    is that it costs nothing on the days it finds nothing to do.
    """
    planned = select(DailyPlan.child_id).where(DailyPlan.plan_date == plan_date)
    return list(
        session.scalars(
            select(Child.id).where(Child.id.not_in(planned)).order_by(Child.created_at).limit(limit)
        ).all()
    )


def mark_item_complete(
    session: Session, *, child_id: UUID, plan_date: date, topic_id: str, at: datetime | None = None
) -> bool:
    """Tick this topic off today's plan. Returns whether an item was ticked.

    Called when a lesson passes. A topic the day did not plan is not an error -
    a child may replay a level they have already finished, and that is revision,
    not the day's work - so it simply ticks nothing.
    """
    plan = plan_for(session, child_id=child_id, plan_date=plan_date)
    if plan is None:
        return False
    ticked = False
    for item in plan.items:
        if item.topic_id == topic_id and item.completed_at is None:
            item.completed_at = at or datetime.now(timezone.utc)
            ticked = True
    return ticked


def plan_cursor(plan: DailyPlan, *, completed_topic_ids: set[str]) -> DailyPlanItem | None:
    """The next item the child has not finished **today**, in plan order.

    Two ways an item counts as finished, and the second one is only a bridge:

    * it carries a `completed_at` - it was ticked off this plan;
    * it is a 'new' item whose topic is in the child's completed list. A fresh
      item is one the child had *not* finished when the day was frozen, so its
      being finished now can only have happened today. This keeps plans frozen
      before `completed_at` existed reading the way they did.

    A 'revisit' item is deliberately not covered by the second rule: it is in
    `completed_topic_ids` from the moment it is frozen - that is what makes it a
    revisit - and treating that as finished ticked the whole day off before the
    child had answered anything.
    """
    for item in plan.items:
        if item.completed_at is not None:
            continue
        if item.reason != "revisit" and item.topic_id in completed_topic_ids:
            continue
        return item
    return None


def item_is_done(item: DailyPlanItem, completed_topic_ids: set[str]) -> bool:
    """The same rule as `plan_cursor`, for the tick beside an item on screen."""
    if item.completed_at is not None:
        return True
    return item.reason != "revisit" and item.topic_id in completed_topic_ids
