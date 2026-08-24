"""The Planner Agent as a LangGraph state graph.

    START -> gather -> propose -> validate -> freeze -> END
                  \_______________________________/
                     (nothing to plan, or no model)

Four nodes, and only one of them may talk to a model:

- **gather** takes the candidate topics the deterministic layer has already
  declared legal for this child today - unlocked, playable, not finished - and
  puts them in the order the ladder would use: what the child struggled with
  first, then new ground, in manifest order.
- **propose** is the only node that reaches a language model, and the only
  thing it may return is *an ordering of the ids gather produced*. It cannot add
  a topic, invent one, or reach a locked one, because it is never given anything
  outside the candidate list.
- **validate** enforces exactly that. An id that is not a candidate, a
  duplicate, an empty answer, a malformed body: any of them drops the whole
  proposal and the deterministic order stands. The row records which happened,
  as `daily_plans.source`.
- **freeze** writes it through `plans.freeze_plan`, whose unique constraint -
  not this code - is what guarantees one plan per child per day.

**What this agent is not allowed to do**, and the reason it is shaped this way:
it does not grade anything, does not compute mastery, does not decide what is
unlocked, and cannot put a topic in front of a child that the deterministic
layer did not already offer. A model that could do any of those would be
upstream of the child's progress. Here the worst a bad model answer can do is
suggest an order that gets thrown away.
"""

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from app.ai.llm import ChatRequest, LLMUnavailable, chat, is_configured
from app.db.repositories import plans
from app.db.repositories.plans import PlannedItem
from app.db.session import session_scope


logger = logging.getLogger(__name__)

# A nursery afternoon, not a syllabus. The same cap `plan_service` uses.
MAX_ITEMS = 3

PLANNER_SYSTEM_PROMPT = """You are the Saksham IQ planner for one child aged 2 to 6.

You are given the topics this child may study today. They have already been
checked: every one is unlocked, has content, and is age-appropriate. Your only
job is to put them in the best order for one short sitting.

Order them by what will make the sitting go well:
- something the child found hard recently is worth meeting again while it is
  fresh, but never first if it would start the day with a struggle;
- a topic the child is likely to succeed at is a good opening;
- keep subjects varied rather than three of the same in a row.

Return exactly one JSON object: {"order": ["topic_id", ...], "why": "one short sentence"}.
Use only the topic ids you were given. Do not add, invent, rename or repeat one.
Do not return more ids than you were given. If you are unsure, return them in
the order you received them."""


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
    rejected: str
    frozen: bool


@dataclass(frozen=True)
class PlannerResult:
    """What the caller gets back: the frozen plan, and how it was decided."""

    items: tuple[PlannedItem, ...] = ()
    source: str = "deterministic"
    why: str = ""
    # Set when the model answered and was overruled. Read next to the source
    # column, this is how a planner that has quietly stopped being useful shows
    # up before anyone notices it in the plans themselves.
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


# --------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------


def gather(state: PlannerState) -> PlannerState:
    """The deterministic order, and the ceiling on how long a plan may be."""
    candidates = list(state.get("candidates") or ())[:MAX_ITEMS]
    return {
        "candidates": candidates,
        "order": [candidate["topic_id"] for candidate in candidates],
        "source": "deterministic",
    }


def propose(state: PlannerState) -> PlannerState:
    """Ask the model for an ordering. Failure here is normal and quiet."""
    candidates = state.get("candidates") or []
    menu = [
        {
            "topic_id": candidate["topic_id"],
            "title": candidate.get("title", candidate["topic_id"]),
            "subject": candidate.get("subject_title", ""),
            "reason": candidate.get("reason", "new"),
            "mastery": candidate.get("mastery", 0.0),
        }
        for candidate in candidates
    ]
    request = ChatRequest(
        system=[PLANNER_SYSTEM_PROMPT],
        user=[
            json.dumps(
                {
                    "child_name": state.get("child_name", ""),
                    "age_band": state.get("experience_mode", "standard"),
                    "date": state.get("plan_date", ""),
                    "topics": menu,
                },
                ensure_ascii=True,
            )
        ],
        temperature=0.2,
        max_tokens=200,
    )
    try:
        decoded = json.loads(chat(request))
    except (LLMUnavailable, json.JSONDecodeError) as exc:
        logger.info("Planner agent unavailable (%s); keeping the deterministic order", type(exc).__name__)
        return {"rejected": "unavailable"}

    if not isinstance(decoded, dict):
        return {"rejected": "not_an_object"}
    proposed = decoded.get("order")
    why = decoded.get("why")
    return {
        "order": [str(topic_id) for topic_id in proposed] if isinstance(proposed, list) else [],
        "source": "planner_agent",
        "why": why.strip()[:200] if isinstance(why, str) else "",
        "rejected": "" if isinstance(proposed, list) else "no_order",
    }


def validate(state: PlannerState) -> PlannerState:
    """The envelope. Anything off-menu drops the whole proposal.

    Not "drop the bad id and keep the rest": a model that returned one topic
    this child cannot have has told you its answer is not trustworthy, and
    salvaging part of it hides that.
    """
    candidates = state.get("candidates") or []
    legal = [candidate["topic_id"] for candidate in candidates]
    deterministic = {"order": legal, "source": "deterministic", "why": ""}

    if state.get("source") != "planner_agent":
        return {**deterministic, "rejected": state.get("rejected", "")}

    order = state.get("order") or []
    if not order:
        return {**deterministic, "rejected": state.get("rejected") or "empty"}
    if len(order) != len(set(order)):
        return {**deterministic, "rejected": "duplicate"}
    if len(order) > len(legal):
        return {**deterministic, "rejected": "too_long"}
    off_menu = [topic_id for topic_id in order if topic_id not in legal]
    if off_menu:
        logger.warning("Planner agent proposed topics that are not legal today: %s", off_menu)
        return {**deterministic, "rejected": "off_menu"}
    # A short answer is allowed - a planner may decide two topics is enough
    # today - but a missing topic must not silently disappear from the day, so
    # the rest are appended in the deterministic order behind it.
    tail = [topic_id for topic_id in legal if topic_id not in order]
    return {"order": [*order, *tail], "source": "planner_agent", "rejected": ""}


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


def _route_after_gather(state: PlannerState) -> str:
    """No candidates means no plan, and no model call to decide that."""
    if not state.get("candidates"):
        return "freeze"
    return "propose" if is_configured() else "freeze"


def build_graph():
    builder = StateGraph(PlannerState)
    builder.add_node("gather", gather)
    builder.add_node("propose", propose)
    builder.add_node("validate", validate)
    builder.add_node("freeze", freeze)

    builder.add_edge(START, "gather")
    builder.add_conditional_edges("gather", _route_after_gather, {"propose": "propose", "freeze": "freeze"})
    builder.add_edge("propose", "validate")
    builder.add_edge("validate", "freeze")
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
    map; this agent owns only the order.
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
        rejected=state.get("rejected", ""),
        frozen=bool(state.get("frozen")),
    )
