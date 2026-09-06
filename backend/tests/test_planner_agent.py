"""The planner: a LangGraph graph that orders the day, in pure Python.

There used to be a model in here, and most of this file used to be its envelope:
what happens when it answers with a topic this child cannot have, with a
duplicate, or with nothing at all. The model is gone, so those tests are gone
with it, and what is pinned now is the part that decides a child's morning:

* **no model is reachable from the planner at all** - not a fallback, not a
  fenced one;
* **every subject gets a level, every day** - no cap, no rotation, no sample;
* **the order is a rule that can be read** - open on something the child will
  get right, meet the shaky levels early, finish on a win - and it is the same
  order every time the same candidates go in.
"""

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ai.planner import graph as planner_graph
from app.db.models import DailyPlan
from app.db.repositories.plans import PlannedItem
from app.db.session import session_scope
from app.main import app
from app.services import child_service, plan_service, planner_runner


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def make_child(client: TestClient, email: str = "planner@example.com", name: str = "Aaru") -> str:
    auth = client.post("/auth/register", json={"name": "Parent", "email": email, "password": "demo1234"})
    if auth.status_code != 200:
        auth = client.post("/auth/login", json={"email": email, "password": "demo1234"})
    token = auth.json()["session_token"]
    child = client.post(
        "/children",
        json={
            "session_token": token,
            "name": name,
            "birth_year": date.today().year - 4,
            "birth_month": 6,
            "preferred_language": "English",
        },
    )
    return child.json()["child_id"]


def real_topics(child_id: str, count: int = 3) -> list[PlannedItem]:
    """Topic ids from the shipped manifest, so the titles resolve.

    Which topics are legal for this child is `_candidates`' job and is stubbed in
    these tests; what is under test is the ordering and the freeze.
    """
    from app.services import curriculum_service

    child = child_service.get_child(child_id)
    detail = curriculum_service.get_class(child.class_id)
    picked: list[PlannedItem] = []
    for subject in detail.subjects:
        for topic in subject.topics:
            picked.append(
                PlannedItem(
                    topic_id=topic.topic_id,
                    skill_id=f"{subject.subject_id}:{topic.topic_id}",
                    reason="new",
                )
            )
            if len(picked) == count:
                return picked
    return picked


@pytest.fixture()
def planned(client: TestClient, monkeypatch):
    """A child with three known candidates for today."""
    child_id = make_child(client)
    items = real_topics(child_id, 3)
    monkeypatch.setattr(plan_service, "_candidates", lambda _child, *_: items)
    return child_id, items


def candidate(topic_id: str, *, reason: str = "new", mastery: float = 0.0) -> dict:
    """One candidate as the ordering sees it: an id, why it is here, and mastery."""
    return {
        "topic_id": topic_id,
        "skill_id": f"sub:{topic_id}",
        "reason": reason,
        "title": topic_id.replace("_", " ").title(),
        "subject_title": topic_id.split("_")[0].title(),
        "mastery": mastery,
    }


# --------------------------------------------------------------------------
# The graph itself
# --------------------------------------------------------------------------


def test_the_planner_is_actually_a_graph():
    """Three nodes and the edges between them, not a function with a nice name."""
    compiled = planner_graph.build_graph()
    nodes = set(compiled.get_graph().nodes)

    assert {"gather", "order", "freeze"} <= nodes
    # The two nodes that existed only to ask a model and check its answer.
    assert "propose" not in nodes and "validate" not in nodes


def test_no_model_is_reachable_from_the_planner():
    """Not a fenced call, not a fallback: there is no call.

    The module used to import `chat` and `is_configured` from `app.ai.llm` and
    ask Groq for an ordering, validating the reply against the candidate list.
    The fence held and the model still went, so this pins its absence rather
    than its behaviour - a planner that quietly grew a model back would pass
    every other test in this file.
    """
    source = Path(planner_graph.__file__).read_text(encoding="utf-8")

    assert "app.ai.llm" not in source
    for gone in ("chat(", "is_configured", "ChatRequest", "SYSTEM_PROMPT"):
        assert gone not in source, gone
    assert not hasattr(planner_graph, "chat")


def test_a_planner_run_never_calls_out(planned, monkeypatch):
    """The same thing again, from the other end: the provider is booby-trapped."""
    from app.ai import llm

    def _explode(*_args, **_kwargs):  # pragma: no cover - it must never run
        raise AssertionError("the planner called a language model")

    monkeypatch.setattr(llm, "chat", _explode)

    result = plan_service.freeze_today(child_service.get_child(planned[0]))

    assert result.frozen is True
    assert result.source == "deterministic"


def test_with_no_model_the_deterministic_order_is_frozen(planned):
    child_id, items = planned
    child = child_service.get_child(child_id)

    result = plan_service.freeze_today(child)

    assert result.source == "deterministic"
    assert result.frozen is True
    assert [item.topic_id for item in result.items] == [item.topic_id for item in items]
    with session_scope() as session:
        rows = session.query(DailyPlan).all()
        assert len(rows) == 1
        assert rows[0].source == "deterministic"


# --------------------------------------------------------------------------
# The order itself
# --------------------------------------------------------------------------


def test_a_day_of_new_levels_is_left_in_the_class_order():
    """Nothing shaky, nothing to spread: the day is the subjects, in order.

    Shuffling levels that are all equally new would make today look different
    from yesterday for no reason, and the routine is the thing a three-year-old
    is building.
    """
    day = [candidate("maths_one"), candidate("english_a"), candidate("ga_body")]

    assert planner_graph._ordered(day) == day


def test_the_day_opens_on_a_win_and_meets_the_shaky_level_second():
    """A day must not start with the thing the child could not do yesterday."""
    day = [
        candidate("maths_count", reason="revisit", mastery=0.2),
        candidate("english_a", mastery=0.9),
        candidate("ga_body", mastery=0.8),
    ]

    ordered = [item["topic_id"] for item in planner_graph._ordered(day)]

    assert ordered[0] == "english_a", "the steadiest level opens the sitting"
    assert ordered[1] == "maths_count", "the shaky one is met early, never first"
    assert ordered[-1] == "ga_body", "and the sitting finishes on a win"


def test_a_low_mastery_level_counts_as_shaky_even_when_it_is_new():
    """`revisit` is not the only way to be struggling; mastery says so too."""
    assert planner_graph._is_shaky(candidate("x", mastery=0.1)) is True
    assert planner_graph._is_shaky(candidate("x", mastery=0.9)) is False
    assert planner_graph._is_shaky(candidate("x", reason="revisit", mastery=1.0)) is True


def test_the_same_candidates_always_make_the_same_day():
    """A frozen plan and a re-read of it have to agree, so ties break the same way."""
    day = [
        candidate("maths_count", reason="revisit", mastery=0.5),
        candidate("english_a", mastery=0.7),
        candidate("ga_body", mastery=0.7),
        candidate("evs_plants", reason="revisit", mastery=0.5),
    ]

    once = [item["topic_id"] for item in planner_graph._ordered(list(day))]
    twice = [item["topic_id"] for item in planner_graph._ordered(list(day))]

    assert once == twice


def test_a_day_where_everything_is_shaky_is_still_the_whole_day():
    """No steady level to open on is not a reason to drop anybody's subject."""
    day = [
        candidate("maths_count", reason="revisit"),
        candidate("english_a", reason="revisit"),
        candidate("ga_body", reason="revisit"),
    ]

    ordered = planner_graph._ordered(day)

    assert [item["topic_id"] for item in ordered] == [item["topic_id"] for item in day]


def test_the_order_never_loses_or_repeats_a_subject():
    day = [
        candidate("maths_count", reason="revisit", mastery=0.1),
        candidate("english_a", mastery=0.9),
        candidate("ga_body", mastery=0.6),
        candidate("evs_plants", reason="revisit", mastery=0.3),
        candidate("art_lines", mastery=0.55),
        candidate("hindi_swar", reason="revisit", mastery=0.2),
    ]

    ordered = planner_graph._ordered(day)

    assert sorted(item["topic_id"] for item in ordered) == sorted(
        item["topic_id"] for item in day
    )
    assert len(ordered) == len(day)


def test_the_plan_is_frozen_once_however_many_times_it_runs(planned):
    child_id, _ = planned
    child = child_service.get_child(child_id)

    first = plan_service.freeze_today(child)
    plan_service.freeze_today(child)
    plan_service.freeze_today(child)

    with session_scope() as session:
        assert session.query(DailyPlan).count() == 1
    assert first.frozen is True


# --------------------------------------------------------------------------
# Running itself
# --------------------------------------------------------------------------


def test_the_sweep_plans_every_child_who_has_none(client: TestClient, monkeypatch):
    first = make_child(client, "sweep1@example.com", "Aaru")
    second = make_child(client, "sweep2@example.com", "Vihaan")
    monkeypatch.setattr(plan_service, "_candidates", lambda _child, *_: real_topics(first, 2))

    summary = planner_runner.sweep()

    assert summary["considered"] == 2
    assert summary["planned"] == 2
    with session_scope() as session:
        assert session.query(DailyPlan).count() == 2

    # The second sweep finds nothing to do: that is what makes it safe to run on
    # a timer, and what stops two workers writing two plans.
    # The sweep also schedules the retention tests that have come due; on a
    # database whose teaching all happened today there are none.
    assert planner_runner.sweep() == {
        "considered": 0,
        "planned": 0,
        "skipped": 0,
        "failed": 0,
        "retention_tests": 0,
    }
    assert second


def test_a_child_with_nothing_to_study_is_skipped_not_failed(client: TestClient, monkeypatch):
    make_child(client, "empty@example.com")
    monkeypatch.setattr(plan_service, "_candidates", lambda _child, *_: [])

    summary = planner_runner.sweep()

    assert summary == {
        "considered": 1,
        "planned": 0,
        "skipped": 1,
        "failed": 0,
        "retention_tests": 0,
    }


def test_the_sweep_does_not_stop_at_a_child_it_cannot_plan(client: TestClient, monkeypatch):
    good = make_child(client, "good@example.com", "Aaru")
    make_child(client, "bad@example.com", "Vihaan")
    items = real_topics(good, 2)
    calls = {"n": 0}

    def _candidates(child, *_):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("this child's curriculum is in a state we cannot plan")
        return items

    monkeypatch.setattr(plan_service, "_candidates", _candidates)

    summary = planner_runner.sweep()

    assert summary["failed"] == 1
    assert summary["planned"] == 1


def test_auto_run_is_off_in_the_suite():
    """If this ever fails, every plan assertion in the suite is racing a sweep."""
    assert planner_runner.start() is None


# --------------------------------------------------------------------------
# What the client reads
# --------------------------------------------------------------------------


def test_the_today_endpoint_shows_the_plan_with_a_cursor(client: TestClient, planned):
    child_id, items = planned

    body = client.get(f"/plans/{child_id}/today").json()

    assert body["total"] == len(items)
    assert body["source"] == "deterministic"
    assert body["current_topic_id"] == items[0].topic_id
    assert body["items"][0]["current"] is True
    assert body["items"][0]["title"]
    assert body["completed"] == 0


def test_an_empty_day_is_an_honest_answer(client: TestClient, monkeypatch):
    child_id = make_child(client, "clear@example.com")
    monkeypatch.setattr(plan_service, "_candidates", lambda _child, *_: [])

    body = client.get(f"/plans/{child_id}/today").json()

    assert body["items"] == []
    assert body["total"] == 0
    assert body["current_topic_id"] is None


def test_the_history_endpoint_reads_the_week_back(client: TestClient, planned):
    child_id, items = planned
    child = child_service.get_child(child_id)
    plan_service.freeze_today(child, today=date.today() - timedelta(days=1))
    plan_service.freeze_today(child)

    body = client.get(f"/plans/{child_id}/history?days=7").json()

    assert len(body["plans"]) == 2
    # Newest first, so a parent opening the report sees today at the top.
    assert body["plans"][0]["plan_date"] == date.today().isoformat()
    assert body["plans"][0]["items"][0]["topic_id"] == items[0].topic_id
