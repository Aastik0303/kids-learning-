"""The three things that were written but not plugged in, and what plugs them.

Before this, `app/policy/` chose nothing, the durable tables were written only by
their own unit tests, and `app/ai/llm/` was an empty package while the guide held
an HTTP client of its own. Each test here fails if one of those regressions comes
back.

Read `test_durable_storage.py` next to this: that one pins the repositories in
isolation, this one pins that the running app actually goes through them.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.ai.llm import client as llm_client
from app.db.models import PolicyEpisode, PolicyQValue, RetentionProbe, TeachingEvent
from app.db.repositories import policy as policy_repo
from app.db.repositories import truth
from app.db.session import session_scope
from app.main import app
from app.policy import actions, selector, state
from app.schemas.guide import GuideRequest
from app.services import child_store, guide_agent_service, retention_service, teaching_policy_service


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def make_child(client: TestClient, email: str = "policy@example.com") -> str:
    auth = client.post("/auth/register", json={"name": "Parent", "email": email, "password": "demo1234"})
    token = auth.json()["session_token"]
    child = client.post(
        "/children",
        json={
            "session_token": token,
            "name": "Aaru",
            "birth_year": date.today().year - 4,
            "birth_month": 6,
            "preferred_language": "English",
        },
    )
    return child.json()["child_id"]


def teaching_turn(child_id: str, attempt: int, *, activity_id: str = "shapes_01", session_id: str = "s1") -> GuideRequest:
    return GuideRequest(
        session_id=session_id,
        child_id=child_id,
        mode="learning",
        event="TOPIC_ANSWER_INCORRECT",
        route="/adventure/shapes",
        screen="topic_session",
        feature="tapped square",
        question={
            "activity_id": activity_id,
            "topic": "identify_shape",
            "concept": "circle",
            "prompt": "Which one is the circle?",
            "answer_type": "identify_shape",
            "options": ["circle", "square"],
            "correct_answer": "circle",
            "child_answer": "square",
            "attempt": attempt,
        },
        progress={"current_subject": "pg_maths", "current_topic": "pg_maths_shapes"},
        available_actions=["none"],
        available_targets=[],
    )


# --------------------------------------------------------------------------
# 1. The policy chooses, and what it chose is written down
# --------------------------------------------------------------------------


def test_a_teaching_turn_is_tagged_and_recorded_without_a_model(client: TestClient):
    """The default configuration has no LLM provider at all.

    That used to mean `teaching_strategy` was never set by anything: the nine
    strategies existed in the schema and in the prompt, and the running app
    chose from them only when a Groq key was present. The policy now chooses on
    the deterministic path too.
    """
    child_id = make_child(client)
    assert not llm_client.is_configured()

    response = guide_agent_service.guide(teaching_turn(child_id, attempt=2))

    assert response.teaching_strategy in actions.ALL_STRATEGIES
    with session_scope() as session:
        events = session.query(TeachingEvent).all()
        episodes = session.query(PolicyEpisode).all()
    assert [event.strategy for event in events] == [response.teaching_strategy]
    assert [episode.action for episode in episodes] == [response.teaching_strategy]
    # The reward is not paid at teach time. It cannot be: nothing has happened
    # yet that could tell this strategy from one that gave the answer away.
    assert episodes[0].reward is None
    assert episodes[0].reward_resolved_at is None


def test_a_spent_strategy_survives_a_restart(client: TestClient):
    """The in-process log this replaces forgot everything on restart, so a child
    coming back after a crash was handed the explanation that had already failed
    them."""
    child_id = make_child(client)
    first = guide_agent_service.guide(teaching_turn(child_id, attempt=2))

    # A restart: nothing in memory survives, the database does.
    guide_agent_service._STRATEGY_LOG.clear()
    child_store.reset_cache()

    second = guide_agent_service.guide(teaching_turn(child_id, attempt=3, session_id="s2"))

    assert second.teaching_strategy != first.teaching_strategy
    assert first.teaching_strategy in teaching_policy_service.spent_strategies(
        child_id=child_id, activity_id="shapes_01"
    )


def test_the_clean_second_try_spends_nothing(client: TestClient):
    """Rung 1 is encouragement by design. Writing an episode for it would train
    the table on a turn the policy never influenced."""
    child_id = make_child(client)

    response = guide_agent_service.guide(teaching_turn(child_id, attempt=1))

    assert response.teaching_strategy is None
    with session_scope() as session:
        assert session.query(PolicyEpisode).count() == 0


def test_a_parked_question_can_only_be_parked(client: TestClient):
    child_id = make_child(client)

    response = guide_agent_service.guide(teaching_turn(child_id, attempt=4))

    assert response.teaching_strategy == actions.PARK
    assert "?" not in response.message


def test_a_child_with_no_durable_row_still_gets_taught():
    """A guide call with no learner behind it - a demo, a test payload - falls
    back to the ladder rather than failing. A child waiting for the screen to
    say something is not a place to surface an infrastructure problem."""
    response = guide_agent_service.guide(teaching_turn("guest_child", attempt=2))

    assert response.message
    assert response.teaching_strategy in actions.ALL_STRATEGIES
    with session_scope() as session:
        assert session.query(PolicyEpisode).count() == 0


# --------------------------------------------------------------------------
# 2. The reward is paid by a probe, days later, and by nothing else
# --------------------------------------------------------------------------


def test_a_correct_answer_schedules_a_probe_and_settles_the_old_one(client: TestClient):
    child_id = make_child(client)
    skill = "pg_maths:pg_maths_shapes"

    guide_agent_service.guide(teaching_turn(child_id, attempt=2))
    first = retention_service.on_attempt(
        child_id=child_id, skill_id=skill, form_signature="identify_shape", is_correct=True
    )

    assert first["scheduled"] == "day2"
    with session_scope() as session:
        episode = session.query(PolicyEpisode).one()
        # The episode was taught before the probe existed; scheduling attaches it.
        assert episode.retention_probe_id is not None
        assert episode.reward is None

    # Two days on, the same skill comes round again - in practice, or in the
    # next lesson - and that attempt is the probe.
    later = datetime.now(timezone.utc) + timedelta(days=2, minutes=1)
    settled = retention_service.on_attempt(
        child_id=child_id, skill_id=skill, form_signature="count_objects", is_correct=True, now=later
    )

    assert settled["settled"] == ["day2"]
    assert settled["scheduled"] == "day7"
    with session_scope() as session:
        episode = session.query(PolicyEpisode).filter(PolicyEpisode.reward.isnot(None)).one()
        # Passed, and in a different form from the one it was taught in: recall
        # plus transfer.
        assert episode.reward == pytest.approx(
            policy_repo.REWARD_RETENTION_PASS + policy_repo.REWARD_TRANSFER_BONUS
        )
        q_row = session.query(PolicyQValue).filter(PolicyQValue.action == episode.action).one()
        assert q_row.q_value > 0
        assert q_row.visits == 1


def test_a_strategy_that_did_not_hold_is_paid_less_than_one_that_did(client: TestClient):
    """The whole reason RLHF was rejected here, made into an assertion.

    Both strategies produce a correct answer on the day. One is still there two
    days later and one is not, and only that difference reaches the table.
    """
    child_id = make_child(client)
    held, faded = "pg_maths:held", "pg_maths:faded"

    for skill in (held, faded):
        with session_scope() as session:
            policy_repo.record_episode(
                session,
                child_id=child_store.child_row(child_id).id,
                skill_id=skill,
                state_key=f"std|m0|r2|n0|{skill}",
                action="S3_EXAMPLE",
                immediate_correct=True,
            )
        retention_service.on_attempt(
            child_id=child_id, skill_id=skill, form_signature="identify_shape", is_correct=True
        )

    later = datetime.now(timezone.utc) + timedelta(days=2, minutes=1)
    retention_service.on_attempt(
        child_id=child_id, skill_id=held, form_signature="count_objects", is_correct=True, now=later
    )
    retention_service.on_attempt(
        child_id=child_id, skill_id=faded, form_signature="count_objects", is_correct=False, now=later
    )

    with session_scope() as session:
        rewards = {
            episode.skill_id: episode.reward
            for episode in session.query(PolicyEpisode).filter(PolicyEpisode.reward.isnot(None))
        }
    assert rewards[held] > 0 > rewards[faded]


def test_answering_correctly_today_pays_nothing_today(client: TestClient):
    """No path writes a reward inside the turn that spent the strategy."""
    child_id = make_child(client)
    guide_agent_service.guide(teaching_turn(child_id, attempt=2))
    retention_service.on_attempt(
        child_id=child_id, skill_id="pg_maths:pg_maths_shapes", form_signature="identify_shape", is_correct=True
    )

    with session_scope() as session:
        assert session.query(PolicyEpisode).filter(PolicyEpisode.reward.isnot(None)).count() == 0
        assert session.query(PolicyQValue).count() == 0
        assert session.query(RetentionProbe).count() == 1


# --------------------------------------------------------------------------
# 3. A lesson writes truth, and the mastery gate reads it
# --------------------------------------------------------------------------


def test_an_answered_lesson_lands_in_the_attempt_log(client: TestClient):
    """`mock_activity_attempts` lost a parent's whole report on restart."""
    child_id = make_child(client)
    subjects = client.get(f"/practice/subjects/{child_id}").json()
    assert subjects  # the class exists even where a subject has no activities

    with session_scope() as session:
        truth.record_attempt(
            session,
            child_id=child_store.child_row(child_id).id,
            topic_id="pg_maths_shapes",
            activity_id="shapes_01",
            skill_id="pg_maths:pg_maths_shapes",
            is_correct=True,
            form_signature="identify_shape",
            forms_available=2,
        )

    history = client.get(f"/history/{child_id}").json()["attempts"]
    assert [attempt["activity_id"] for attempt in history] == ["shapes_01"]
    assert history[0]["level_id"] == "pg_maths"


def test_one_lucky_answer_does_not_open_the_gate(client: TestClient):
    child_id = make_child(client)
    with session_scope() as session:
        row = truth.record_attempt(
            session,
            child_id=child_store.child_row(child_id).id,
            topic_id="pg_maths_shapes",
            activity_id="shapes_01",
            skill_id="pg_maths:pg_maths_shapes",
            is_correct=True,
            form_signature="identify_shape",
            forms_available=2,
        )
        mastery = truth.mastery_for(session, child_id=row.child_id, skill_id=row.skill_id)
        assert not truth.is_mastered(mastery)


# --------------------------------------------------------------------------
# 3b. Today's plan is frozen, so the app offers the same lesson all day
# --------------------------------------------------------------------------


def test_the_daily_plan_is_frozen_and_read_back(client: TestClient, monkeypatch):
    """Recomputing "what next" on every request is correct and is not a routine.

    A child who refreshes, or comes back from a lesson, was offered whatever the
    board said at that instant. The plan is written once per child per day and
    read every time after that.

    The candidate list is stubbed because the shipped curriculum is taxonomy
    only - what is under test is the freeze, not which topics a manifest with no
    authored activities can offer.
    """
    from app.db.models import DailyPlan
    from app.db.repositories.plans import PlannedItem
    from app.services import child_service, plan_service

    child_id = make_child(client)
    child = child_service.get_child(child_id)
    planned = [
        PlannedItem(topic_id="topic_one", skill_id="nur_maths:topic_one", reason="new"),
        PlannedItem(topic_id="topic_two", skill_id="nur_maths:topic_two", reason="new"),
    ]
    monkeypatch.setattr(plan_service, "_candidates", lambda _child, *_: planned)

    first = plan_service.todays_topic(child)
    second = plan_service.todays_topic(child)

    assert first == ("nur_maths", "topic_one")
    assert second == first
    with session_scope() as session:
        rows = session.query(DailyPlan).all()
        assert len(rows) == 1
        assert rows[0].source == "deterministic"
        assert [item.topic_id for item in rows[0].items] == ["topic_one", "topic_two"]

    # The board changing under the plan does not rewrite it: that is the freeze.
    monkeypatch.setattr(
        plan_service,
        "_candidates",
        lambda _child, *_: [PlannedItem(topic_id="topic_nine", skill_id="nur_maths:topic_nine")],
    )
    assert plan_service.todays_topic(child) == ("nur_maths", "topic_one")


def test_finishing_a_lesson_advances_the_plan_instead_of_regenerating_it(client: TestClient, monkeypatch):
    from app.db.repositories.plans import PlannedItem
    from app.schemas.child import SubjectProgress
    from app.services import child_service, plan_service

    child_id = make_child(client)
    child = child_service.get_child(child_id)
    monkeypatch.setattr(
        plan_service,
        "_candidates",
        lambda _child, *_: [
            PlannedItem(topic_id="topic_one", skill_id="nur_maths:topic_one"),
            PlannedItem(topic_id="topic_two", skill_id="nur_maths:topic_two"),
        ],
    )

    assert plan_service.todays_topic(child)[1] == "topic_one"

    finished = child.model_copy(
        update={"subject_progress": {"nur_maths": SubjectProgress(completed_topics=["topic_one"])}}
    )
    assert plan_service.todays_topic(finished)[1] == "topic_two"


# --------------------------------------------------------------------------
# 4. The model client, and the boundary it must not cross
# --------------------------------------------------------------------------


def test_no_provider_configured_means_no_call_and_no_failure():
    llm_client.reset_breaker()
    with pytest.raises(llm_client.LLMUnavailable):
        llm_client.chat(llm_client.ChatRequest(system=["s"], user=["u"]))


def test_the_breaker_stops_a_dead_provider_from_costing_every_turn(monkeypatch):
    """An outage should degrade the class to the deterministic guide, not stall
    it six seconds at a time."""
    llm_client.reset_breaker()
    monkeypatch.setattr(llm_client, "provider_name", lambda: "groq")
    monkeypatch.setattr(llm_client, "api_key", lambda: "test-key")
    assert llm_client.is_configured()

    calls = []

    def _fail(*args, **kwargs):
        calls.append(1)
        raise llm_client.httpx.ConnectError("down")

    monkeypatch.setattr(llm_client.httpx, "post", _fail)

    for _ in range(5):
        with pytest.raises(llm_client.LLMUnavailable):
            llm_client.chat(llm_client.ChatRequest(user=["u"]))

    assert len(calls) == llm_client.BREAKER_THRESHOLD
    llm_client.reset_breaker()


def test_the_evaluator_and_the_truth_layer_reach_no_model():
    """The one rule that never moves, checked on the import graph itself.

    Correctness, mastery, unlocking and certificate eligibility are decided in
    pure Python. If any of these modules can reach `app.ai` or an HTTP client,
    every number downstream is downstream of a hallucination.
    """
    import ast
    from pathlib import Path

    for path in (
        Path("app/services/activity_evaluators.py"),
        Path("app/db/repositories/truth.py"),
        Path("app/db/repositories/policy.py"),
        Path("app/policy/actions.py"),
        Path("app/policy/selector.py"),
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert not any(
            name.startswith(("app.ai", "app.agents", "httpx", "openai", "anthropic")) for name in imported
        ), f"{path} must not be able to reach a model"


# --------------------------------------------------------------------------
# 5. The selector's own contract
# --------------------------------------------------------------------------


def test_the_policy_starts_from_the_ladder_and_can_be_overturned():
    """Day one behaviour is today's behaviour; evidence changes it."""
    legal = list(actions.ALL_STRATEGIES[:-1])
    preferred = actions.LADDER_PRIOR[2]

    cold, _ = selector.choose(legal=legal, stats={}, preferred=preferred)
    assert cold in preferred

    warm, _ = selector.choose(
        legal=legal, stats={"S6_DO_TOGETHER": (0.9, 30)}, preferred=preferred
    )
    assert warm == "S6_DO_TOGETHER"


def test_exploration_never_leaves_the_legal_set():
    legal = actions.legal_actions(experience_mode="early", rung=3, spent=["S1_TELL"])
    assert "S1_TELL" not in legal
    assert actions.PARK not in legal

    import random

    for seed in range(25):
        chosen, _ = selector.choose(
            legal=legal, stats={}, preferred=(), explore_rate=1.0, rng=random.Random(seed)
        )
        assert chosen in legal


def test_the_state_key_is_small_enough_to_revisit():
    keys = {
        state.state_key(experience_mode=mode, mastery=mastery, rung=rung, spent=spent)
        for mode in ("early", "standard")
        for mastery in (0.0, 0.35, 0.75, 1.0)
        for rung in range(5)
        for spent in range(5)
    }
    # Small and enumerable on purpose: a person can read this table, diff it and
    # revert it. A per-child key would never be revisited at all.
    assert len(keys) <= 200
    assert all(len(key) <= 128 for key in keys)
