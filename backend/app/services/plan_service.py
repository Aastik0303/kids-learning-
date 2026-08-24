"""Today's plan, frozen once and read all day.

`daily_recommendation_service` recomputed "what next" on every request. That is
correct and it is not a routine: a child who refreshes, comes back from a lesson,
or opens the app twice in an afternoon could be offered a different thing each
time, and a three-year-old builds nothing out of that.

The plan is written once per `(child_id, plan_date)` - the unique constraint in
`daily_plans` is the freeze, not this code - and every read after that returns
the same list in the same order. The cursor moves through it as topics are
completed, so finishing today's first lesson advances the plan rather than
regenerating it.

This module owns the *candidates*: which topics are legal for this child today,
which is a pure function of the manifest and the child's own board. The Planner
Agent in `app/ai/planner/` owns the *order*, and can only order what is handed
to it here. `daily_plans.source` records which of the two decided the day.
"""

import logging
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.ai.planner import plan_today
from app.db.repositories import plans, truth
from app.db.repositories.plans import PlannedItem
from app.db.session import session_scope
from app.schemas.child import ChildProfile
from app.services import curriculum_service


logger = logging.getLogger(__name__)

# One lesson per subject, and never more than this many in a day. Subjects run in
# parallel in this curriculum - a child who loves numbers should not have to
# finish English first - so the day covers the subjects rather than racing ahead
# inside one of them. What the plan deliberately does *not* contain is the topic
# that today's lesson unlocks: that is tomorrow's, which is the whole point of
# freezing a day.
PLAN_LENGTH = 8

# What the child hears when they reach for something the day does not hold.
# Never "locked", never a refusal that sounds like a punishment.
TOMORROW_MESSAGE = "We saved that one for tomorrow. Let us finish today first."
DAY_DONE_MESSAGE = "Today's plan is all done! That one is waiting for tomorrow."


@dataclass(frozen=True)
class DayGate:
    """Whether a topic may be opened today, and what to say if not."""

    allowed: bool
    reason: str
    message: str = ""


@dataclass(frozen=True)
class TodayPlan:
    """A frozen plan, as the parent surface and the child's home screen read it."""

    plan_date: date
    source: str
    items: tuple[dict, ...] = ()
    current_topic_id: str | None = None
    completed: int = 0


def _today() -> date:
    """The day the plan belongs to, in one place.

    Everything that asks "what is today?" goes through here: the freeze, the
    read, and the gate that decides whether a topic belongs to today. One clock
    means a test can roll the day forward, and a future timezone-per-family
    setting has one function to change rather than six call sites.
    """
    return date.today()


def _child_uuid(child_id: str) -> UUID | None:
    try:
        return UUID(str(child_id))
    except (ValueError, AttributeError, TypeError):
        return None


def _mastery_map(child_id: UUID) -> dict[str, float]:
    try:
        with session_scope() as session:
            return truth.mastery_map(session, child_id=child_id)
    except Exception:  # pragma: no cover - database unavailable
        return {}


def _candidates(child: ChildProfile, today: date | None = None) -> list[PlannedItem]:
    """What the child could do today: one live topic per subject, rotated.

    Weak skills first - a topic the child struggled with is revisited before new
    ground is broken - then the first unfinished topic of each subject.

    The rotation matters as much as the selection. The planner keeps a day to
    three lessons, and a nursery child has six subjects; without rotation the
    first three in manifest order would be the only three ever planned, and
    Hindi, EVS and Art would wait until Maths ran out of topics. Rotating by the
    day number gives every subject its turn, and does it deterministically - the
    same child on the same date gets the same day, however many times the plan
    is read.
    """
    detail = curriculum_service.get_class(child.class_id)
    weak = set(child.weak_skills)
    revisit: list[PlannedItem] = []
    fresh: list[PlannedItem] = []

    for subject in detail.subjects:
        progress = child.subject_progress.get(subject.subject_id)
        completed = set(progress.completed_topics) if progress else set()
        unlocked = set(progress.unlocked_topics) if progress else set()
        subject_weak: list[PlannedItem] = []
        subject_fresh: PlannedItem | None = None

        for topic in subject.topics:
            if not topic.available or topic.topic_id not in unlocked:
                continue
            skill_id = f"{subject.subject_id}:{topic.topic_id}"
            if skill_id in weak:
                subject_weak.append(PlannedItem(topic_id=topic.topic_id, skill_id=skill_id, reason="revisit"))
            elif topic.topic_id not in completed and subject_fresh is None:
                # The first unfinished topic in this subject, and only that one.
                # Taking two would let a child finish a level and walk straight
                # into the one it just unlocked, which is the thing the day is
                # meant to hold back.
                subject_fresh = PlannedItem(topic_id=topic.topic_id, skill_id=skill_id, reason="new")

        revisit.extend(subject_weak)
        if subject_fresh is not None:
            fresh.append(subject_fresh)

    if fresh:
        offset = (today or _today()).toordinal() % len(fresh)
        fresh = fresh[offset:] + fresh[:offset]

    return (revisit + fresh)[:PLAN_LENGTH]


def _candidate_menu(child: ChildProfile, items: list[PlannedItem]) -> list[dict]:
    """The candidates as the agent sees them: titles and mastery, no answer keys.

    The planner is given what a teacher would need to order a sitting and
    nothing else. There is no correct answer anywhere in this payload, and no
    way to name a topic that is not already in it.
    """
    mastery = _mastery_map(_child_uuid(child.child_id)) if _child_uuid(child.child_id) else {}
    menu = []
    for item in items:
        # The manifest is a file that changes underneath a plan. A topic id that
        # no longer resolves still belongs in the day - the ids are what the
        # cursor and the freeze work on - so the label degrades to the id rather
        # than taking the whole plan down with it.
        title, subject_title = item.topic_id, ""
        try:
            topic = curriculum_service.get_topic(item.topic_id)
            title = topic.title
            subject_title = curriculum_service.get_subject(topic.subject_id).title
        except Exception:
            logger.debug("Planner candidate %s is not in the manifest any more", item.topic_id)

        menu.append(
            {
                "topic_id": item.topic_id,
                "skill_id": item.skill_id,
                "reason": item.reason,
                "title": title,
                "subject_title": subject_title,
                "mastery": round(mastery.get(item.skill_id, 0.0), 2),
            }
        )
    return menu


def freeze_today(child: ChildProfile, *, today: date | None = None):
    """Run the Planner Agent for this child and freeze what it returns.

    Safe to call as often as you like: the write is idempotent, so the first
    call of the day decides the plan and the rest read it back.
    """
    child_uuid = _child_uuid(child.child_id)
    if child_uuid is None:
        return None

    plan_date = today or _today()
    items = _candidates(child, plan_date)
    if not items:
        return None

    return plan_today(
        child_id=child.child_id,
        child_name=child.name,
        experience_mode=child.experience_mode,
        plan_date=plan_date,
        candidates=_candidate_menu(child, items),
    )


def _completed_topics(child: ChildProfile) -> set[str]:
    return {
        topic_id
        for progress in child.subject_progress.values()
        for topic_id in progress.completed_topics
    }


def todays_plan(child: ChildProfile, *, today: date | None = None) -> TodayPlan | None:
    """The frozen plan, with the cursor resolved. None when there is nothing to plan."""
    child_uuid = _child_uuid(child.child_id)
    if child_uuid is None:
        return None

    plan_date = today or _today()
    try:
        with session_scope() as session:
            plan = plans.plan_for(session, child_id=child_uuid, plan_date=plan_date)
            if plan is None:
                # Nothing frozen yet: this read is what starts the day.
                if freeze_today(child, today=plan_date) is None:
                    return None
                plan = plans.plan_for(session, child_id=child_uuid, plan_date=plan_date)
            if plan is None:  # pragma: no cover - freeze failed and said so
                return None

            done = _completed_topics(child)
            cursor = plans.plan_cursor(plan, completed_topic_ids=done)
            items = tuple(
                {
                    "topic_id": item.topic_id,
                    "skill_id": item.skill_id,
                    "reason": item.reason,
                    "title": topic_title(item.topic_id),
                    "done": item.topic_id in done,
                    "current": cursor is not None and item.topic_id == cursor.topic_id,
                }
                for item in plan.items
            )
            return TodayPlan(
                plan_date=plan.plan_date,
                source=plan.source,
                items=items,
                current_topic_id=cursor.topic_id if cursor else None,
                completed=sum(1 for item in items if item["done"]),
            )
    except Exception:  # pragma: no cover - database unavailable
        logger.exception("Could not read today's plan")
        return None


def is_day_complete(child: ChildProfile, *, today: date | None = None) -> bool:
    """Whether every item in today's plan is finished."""
    plan = todays_plan(child, today=today)
    return plan is not None and bool(plan.items) and plan.current_topic_id is None


def may_open(child: ChildProfile, topic_id: str, *, today: date | None = None) -> DayGate:
    """Whether this child may open this topic today.

    The day's plan is the day's work. Three answers, and the order matters:

    - **the plan holds it** - open it;
    - **the child has already finished it** - open it. Going back over something
      that is already done is not racing ahead, and a favourite lesson being
      refused would be a strange thing to explain to a four-year-old;
    - **anything else** - it is tomorrow's. This is the rule the whole schedule
      rests on: finishing today's level unlocks the next one, and the next one
      opens the day after, in its own plan.

    With no plan at all - a class with nothing authored, or a database that is
    not answering - the gate opens. A child must never be locked out of their
    lesson by infrastructure.
    """
    plan = todays_plan(child, today=today)
    if plan is None or not plan.items:
        return DayGate(True, reason="no_plan")

    if any(item["topic_id"] == topic_id for item in plan.items):
        return DayGate(True, reason="planned")

    if topic_id in _completed_topics(child):
        return DayGate(True, reason="revision")

    complete = plan.current_topic_id is None
    return DayGate(
        False,
        reason="tomorrow",
        message=DAY_DONE_MESSAGE if complete else TOMORROW_MESSAGE,
    )


def planned_topic_ids(child: ChildProfile, *, today: date | None = None) -> set[str]:
    """The topics today's plan holds, for a client that wants to grey out the rest."""
    plan = todays_plan(child, today=today)
    return {item["topic_id"] for item in plan.items} if plan else set()


def topic_title(topic_id: str) -> str:
    """A plan can outlive a topic: the manifest is a file that changes."""
    try:
        return curriculum_service.get_topic(topic_id).title
    except Exception:
        return topic_id


def todays_topic(child: ChildProfile, *, today: date | None = None) -> tuple[str | None, str | None]:
    """The subject and topic today's plan is pointing at, or `(None, None)`.

    Returns nothing rather than raising when the plan cannot be reached or has
    been worked through; the caller falls back to computing the next topic
    directly, which is what it did before this existed.
    """
    plan = todays_plan(child, today=today)
    if plan is None or plan.current_topic_id is None:
        return None, None
    for item in plan.items:
        if item["topic_id"] == plan.current_topic_id:
            skill_id = item["skill_id"]
            return (skill_id.split(":")[0] if ":" in skill_id else None), item["topic_id"]
    return None, None
