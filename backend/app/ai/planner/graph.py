"""The planner as a LangGraph state graph, with no model anywhere in it.

    START -> gather -> order -> freeze -> END

Three nodes and no language model:

- **gather** takes the candidate topics the deterministic layer has already
  declared legal for this child today - unlocked, playable, and one level from
  each of their subjects - and puts a ceiling on how many a day may hold.
- **order** decides the shape of the sitting, in pure Python. See `_ordered`.
- **freeze** writes it through `plans.freeze_plan`, whose unique constraint -
  not this code - is what guarantees one plan per child per day.

**There was a model here and it has been taken out.** The planner used to ask
Groq for an ordering and validate the answer against the candidate list, so that
an off-menu, duplicated or malformed reply dropped the whole proposal and the
deterministic order stood. The fence worked; the model was still the wrong tool.
Ordering a handful of known topics is a small, explainable decision, and a rule
that can be read - open on something the child will succeed at, meet the shaky
levels early while attention is fresh, finish on a win - is better than an answer
that has to be checked before it can be trusted. `daily_plans.source` is always
`deterministic` now.

**What this module is not allowed to do**, which has not changed: it does not
grade anything, does not compute mastery, does not decide what is unlocked, and
cannot put a topic in front of a child that `plan_service` did not already offer.
It owns the order and nothing else.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from app.db.repositories import plans
from app.db.repositories.plans import PlannedItem
from app.db.session import session_scope


logger = logging.getLogger(__name__)

# The ceiling on a day, not its length. A day is **one level from every subject**
# - `plan_service._candidates` returns exactly that - so this number is only here
# to stop a manifest that grows a dozen subjects from turning a nursery afternoon
# into a syllabus. The largest class shipped has six.
#
# It used to be 3, with the subjects rotating by the day number so that none was
# starved. That meant a Nursery child met Hindi every other day and EVS every
# third; the rotation existed to share out a cap that should not have been there.
MAX_ITEMS = 8

# Below this, a level counts as shaky whatever its reason says. Mastery is the
# deterministic evaluator's own number, so this is a reading of the child's
# history rather than an opinion about it.
SHAKY_MASTERY = 0.5


class PlannerState(TypedDict, total=False):
    """What flows along the edges. Plain data - no ORM objects, no sessions."""

    child_id: str
    child_name: str
    experience_mode: str
    plan_date: str
    candidates: list[dict]
    order: list[str]
    source: str
    why: str
    frozen: bool


@dataclass(frozen=True)
class PlannerResult:
    """What the caller gets back: the frozen plan, and how it was decided."""

    items: tuple[PlannedItem, ...] = ()
    source: str = "deterministic"
    why: str = ""
    # Kept so the shape of the result does not change under callers that read it.
    # Nothing rejects anything any more: there is no answer to reject.
    rejected: str = ""
    frozen: bool = False


def _as_items(candidates: Sequence[dict], order: Sequence[str]) -> tuple[PlannedItem, ...]:
    by_topic = {candidate["topic_id"]: candidate for candidate in candidates}
    return tuple(
        PlannedItem(
            topic_id=topic_id,
            skill_id=by_topic[topic_id]["skill_id"],
            reason=by_topic[topic_id].get("reason", "new"),
        )
        for topic_id in order
        if topic_id in by_topic
    )


def _mastery_of(candidate: dict) -> float:
    try:
        return float(candidate.get("mastery", 0.0) or 0.0)
    except (TypeError, ValueError):  # pragma: no cover - a mastery that is not a number
        return 0.0


def _is_shaky(candidate: dict) -> bool:
    """Whether this level is one the child has already found hard.

    Two ways to be shaky and either is enough: the candidate was chosen *because*
    the skill is on the child's weak list (`reason == "revisit"`), or its mastery
    is still low. Both come from the deterministic evaluator's own history, so
    this reads that history rather than forming an opinion about it.
    """
    if candidate.get("reason") == "revisit":
        return True
    return _mastery_of(candidate) < SHAKY_MASTERY


def _ordered(candidates: Sequence[dict]) -> list[dict]:
    """The shape of the sitting, in three rules a person can read.

    1. **Open on something the child will get right.** The steadiest level - the
       highest mastery among the ones that are not shaky - goes first. A day that
       starts with the thing they could not do yesterday starts with a struggle.
    2. **Meet the shaky levels early, but never first.** They come straight after
       the opening, while attention is still fresh and before the sitting has
       cost anything.
    3. **Finish on a win.** If a steady level is left over it is kept back for
       the end, so the sitting closes on something that went well.

    A day with nothing shaky in it is left exactly as it came: one level per
    subject, in the class's own order. Reordering levels that are all equally new
    would only make today look different from yesterday for no reason, and the
    routine is the thing a three-year-old is actually building.

    Every tie is broken by the class's own order, so the same candidates always
    produce the same day - which is what makes a frozen plan and a re-read of it
    agree.
    """
    pool = list(candidates)
    if len(pool) < 3:
        return pool

    shaky = [candidate for candidate in pool if _is_shaky(candidate)]
    steady = [candidate for candidate in pool if not _is_shaky(candidate)]
    if not shaky or not steady:
        return pool

    steady.sort(key=lambda candidate: (-_mastery_of(candidate), pool.index(candidate)))
    opening = steady.pop(0)
    closing = steady.pop(0) if steady else None
    middle = sorted(shaky + steady, key=pool.index)
    return [opening, *middle, *([closing] if closing is not None else [])]


def _why(ordered: Sequence[dict]) -> str:
    """One short sentence saying what the order is, for the parent's digest."""
    if not ordered:
        return ""
    opening = ordered[0].get("subject_title") or ordered[0].get("title") or ""
    if not opening:
        return ""
    if not any(_is_shaky(candidate) for candidate in ordered):
        return f"One level from each subject, starting with {opening}."
    return (
        f"Starting with {opening}, then the levels that need another go while "
        "attention is fresh."
    )


# --------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------


def gather(state: PlannerState) -> PlannerState:
    """The candidates as they came, and the ceiling on how long a day may be."""
    candidates = list(state.get("candidates") or ())[:MAX_ITEMS]
    return {
        "candidates": candidates,
        "order": [candidate["topic_id"] for candidate in candidates],
        "source": "deterministic",
    }


def order(state: PlannerState) -> PlannerState:
    """Shape the sitting. Pure Python, and the same answer every time."""
    shaped = _ordered(state.get("candidates") or [])
    return {
        "order": [candidate["topic_id"] for candidate in shaped],
        "source": "deterministic",
        "why": _why(shaped),
    }


def freeze(state: PlannerState) -> PlannerState:
    """Write the plan.

    Idempotent by construction: `freeze_plan` returns the row already written
    for this child and date if there is one, so two tabs, a refresh and the
    background sweep all converge on the same plan instead of racing to rewrite
    it.
    """
    items = _as_items(state.get("candidates") or [], state.get("order") or [])
    if not items:
        return {"frozen": False}

    try:
        with session_scope() as session:
            plans.freeze_plan(
                session,
                child_id=UUID(str(state["child_id"])),
                plan_date=date.fromisoformat(state["plan_date"]),
                items=items,
                source=state.get("source", "deterministic"),
            )
    except Exception:  # pragma: no cover - database unavailable
        logger.exception("Could not freeze today's plan")
        return {"frozen": False}
    return {"frozen": True}


# --------------------------------------------------------------------------
# The graph
# --------------------------------------------------------------------------


def build_graph():
    builder = StateGraph(PlannerState)
    builder.add_node("gather", gather)
    builder.add_node("order", order)
    builder.add_node("freeze", freeze)

    builder.add_edge(START, "gather")
    builder.add_edge("gather", "order")
    builder.add_edge("order", "freeze")
    builder.add_edge("freeze", END)
    return builder.compile()


_graph = None


def graph():
    """Compiled once. Building it per request is pure overhead."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def plan_today(
    *,
    child_id: str,
    child_name: str,
    experience_mode: str,
    plan_date: date,
    candidates: Sequence[dict],
) -> PlannerResult:
    """Run the graph and freeze the result.

    `candidates` are dicts, not ORM rows: `{topic_id, skill_id, reason, title,
    subject_title, mastery}`. The caller owns the curriculum and the mastery
    map; this module owns only the order.
    """
    state = graph().invoke(
        {
            "child_id": str(child_id),
            "child_name": child_name,
            "experience_mode": experience_mode,
            "plan_date": plan_date.isoformat(),
            "candidates": [dict(candidate) for candidate in candidates],
        }
    )

    return PlannerResult(
        items=_as_items(state.get("candidates") or [], state.get("order") or []),
        source=state.get("source", "deterministic"),
        why=state.get("why", ""),
        frozen=bool(state.get("frozen")),
    )
