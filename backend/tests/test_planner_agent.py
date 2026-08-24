"""The Planner Agent: a LangGraph graph that may order the day and nothing else.

The tests that matter here are not the happy path. They are the envelope: what
happens when the model answers with a topic this child cannot have, with a
duplicate, with a list longer than the menu, or with nothing at all. In every one
of those the deterministic order has to stand, and the row has to say so.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.ai.llm import LLMUnavailable
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


def model_answer(monkeypatch, payload: str | Exception):
    """Point the graph's model call at a fixed answer, with no network."""
    seen: list = []

    def _chat(request):
        seen.append(request)
        if isinstance(payload, Exception):
            raise payload
        return payload

    monkeypatch.setattr(planner_graph, "is_configured", lambda: True)
    monkeypatch.setattr(planner_graph, "chat", _chat)
    return seen


# --------------------------------------------------------------------------
# The graph itself
# --------------------------------------------------------------------------


def test_the_planner_is_actually_a_graph():
    """Four nodes and the edges between them, not a function with a nice name."""
    compiled = planner_graph.build_graph()
    nodes = set(compiled.get_graph().nodes)

    assert {"gather", "propose", "validate", "freeze"} <= nodes


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


def test_a_model_ordering_is_used_when_it_stays_on_the_menu(planned, monkeypatch):
    child_id, items = planned
    reversed_ids = [item.topic_id for item in reversed(items)]
    seen = model_answer(monkeypatch, '{"order": %s, "why": "start with the easy one"}' % str(reversed_ids).replace("'", '"'))

    result = plan_service.freeze_today(child_service.get_child(child_id))

    assert seen, "the graph never called the model"
    assert result.source == "planner_agent"
    assert [item.topic_id for item in result.items] == reversed_ids
    assert result.why == "start with the easy one"


def test_an_off_menu_topic_drops_the_whole_proposal(planned, monkeypatch):
    """Not "drop the bad id and keep the rest".

    A model that named a topic this child cannot have has told you its answer is
    not trustworthy, and salvaging half of it hides that.
    """
    child_id, items = planned
    model_answer(monkeypatch, '{"order": ["%s", "some_locked_topic"]}' % items[1].topic_id)

    result = plan_service.freeze_today(child_service.get_child(child_id))

    assert result.source == "deterministic"
    assert result.rejected == "off_menu"
    assert [item.topic_id for item in result.items] == [item.topic_id for item in items]


@pytest.mark.parametrize(
    ("answer", "rejected"),
    [
        ('{"order": []}', "empty"),
        ('{"order": ["<first>", "<first>"]}', "duplicate"),
        ('{"order": ["<first>", "<second>", "<third>", "<first>"]}', "duplicate"),
        ('{"nope": 1}', "no_order"),
        ("not json at all", "unavailable"),
    ],
)
def test_a_malformed_answer_keeps_the_deterministic_order(planned, monkeypatch, answer, rejected):
    child_id, items = planned
    third = items[2].topic_id if len(items) > 2 else items[0].topic_id
    filled = (
        answer.replace("<first>", items[0].topic_id)
        .replace("<second>", items[1].topic_id)
        .replace("<third>", third)
    )
    model_answer(monkeypatch, filled)

    result = plan_service.freeze_today(child_service.get_child(child_id))

    assert result.source == "deterministic"
    assert result.rejected == rejected


def test_a_model_that_is_down_costs_the_child_nothing(planned, monkeypatch):
    child_id, items = planned
    model_answer(monkeypatch, LLMUnavailable("provider down"))

    result = plan_service.freeze_today(child_service.get_child(child_id))

    assert result.frozen is True
    assert result.source == "deterministic"
    assert result.rejected == "unavailable"


def test_a_short_answer_keeps_the_rest_of_the_day_behind_it(planned, monkeypatch):
    """A planner may decide two topics is enough. A topic must not vanish."""
    child_id, items = planned
    model_answer(monkeypatch, '{"order": ["%s"]}' % items[2].topic_id)

    result = plan_service.freeze_today(child_service.get_child(child_id))

    assert result.source == "planner_agent"
    assert [item.topic_id for item in result.items][0] == items[2].topic_id
    assert len(result.items) == len(items)


def test_the_planner_is_never_shown_an_answer_key(planned, monkeypatch):
    """It is given titles, a reason and a mastery number. Nothing else.

    An agent that could see the answer key could put it in the plan's reason
    text, which the parent digest reads back out loud.
    """
    child_id, _ = planned
    seen = model_answer(monkeypatch, '{"order": []}')

    plan_service.freeze_today(child_service.get_child(child_id))

    payload = " ".join(seen[0].user).lower()
    for forbidden in ("correct_answer", "accepted_answers", "answer_key"):
        assert forbidden not in payload


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
    assert planner_runner.sweep() == {"considered": 0, "planned": 0, "skipped": 0, "failed": 0}
    assert second


def test_a_child_with_nothing_to_study_is_skipped_not_failed(client: TestClient, monkeypatch):
    make_child(client, "empty@example.com")
    monkeypatch.setattr(plan_service, "_candidates", lambda _child, *_: [])

    summary = planner_runner.sweep()

    assert summary == {"considered": 1, "planned": 0, "skipped": 1, "failed": 0}


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
