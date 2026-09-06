"""The AI Teacher is wired to the learned policy, and the wiring is load-bearing.

Everything in `app/policy/` - the rollout, the failure breaker, the leak veto,
the offline evaluation, the attribution columns - hangs off two calls. Before
these tests, neither of them was made by the class that actually teaches on the
web: a whole sitting produced no episode and no retention probe, so the reward
was never paid, the table never moved, and `pending_episodes` grew for ever
without anything erroring.

These pin the loop end to end: taught, recorded, probed, and paid.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ai.llm import client as llm_client
from app.db.models import Attempt, PlaygroundSession, PolicyEpisode, RetentionProbe
from app.db.repositories import policy as policy_repo
from app.db.session import session_scope
from app.main import app
from app.playground import lesson
from app.playground.stage import contains_answer
from app.policy import eligibility, health, leak, metrics
from app.services import retention_service, teaching_policy_service


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def make_child(client: TestClient, email: str) -> str:
    token = client.post(
        "/auth/register", json={"name": "P", "email": email, "password": "demo1234"}
    ).json()["session_token"]
    return client.post(
        "/children",
        json={
            "session_token": token,
            "name": "Aaru",
            "birth_year": date.today().year - 4,
            "birth_month": 6,
            "preferred_language": "English",
        },
    ).json()["child_id"]


def play(client: TestClient, session_id: str, turns: int = 24) -> dict:
    """Play a sitting through, answering correctly wherever the server has a key.

    The answer is read out of the server's own row rather than guessed, because
    the client is never told it - which is the whole point of keeping it
    server-side.
    """
    turn: dict = {}
    for _ in range(turns):
        with session_scope() as session:
            row = session.scalar(
                select(PlaygroundSession).where(PlaygroundSession.session_id == session_id)
            )
            answer, options = (row.pending_answer or ""), list(row.pending_options or [])
        said = "ready"
        if answer:
            said = next((option for option in options if contains_answer(option, answer)), answer)
        turn = client.post(
            f"/playground/teacher/sessions/{session_id}/answer", json={"answer": said}
        ).json()
        if turn.get("expects") == "done" or turn.get("day_complete"):
            break
    return turn


# --------------------------------------------------------------------------
# The loop: taught -> episode -> probe -> reward -> Q-table
# --------------------------------------------------------------------------


def test_a_sitting_writes_episodes_and_schedules_a_probe(client: TestClient):
    child_id = make_child(client, "feeds-policy@example.com")
    opened = client.post(f"/playground/teacher/{child_id}/open").json()
    play(client, opened["session_id"])

    with session_scope() as session:
        episodes = list(session.scalars(select(PolicyEpisode)).all())
        probes = list(session.scalars(select(RetentionProbe)).all())

    assert episodes, "the class taught and the policy recorded nothing"
    assert probes, "a correct answer earned no retention probe"
    assert any(episode.retention_probe_id for episode in episodes), (
        "no episode was attached to the probe that will pay it"
    )
    # Every one of them carries the attribution the audit trail exists for.
    assert all(episode.state_key and episode.action for episode in episodes)
    assert all(episode.activity_id.startswith("teacher_") for episode in episodes)


def test_a_probe_coming_due_pays_the_episodes_and_moves_the_table(client: TestClient):
    """Two days later the child meets the skill again. That attempt is the probe."""
    child_id = make_child(client, "pays-policy@example.com")
    opened = client.post(f"/playground/teacher/{child_id}/open").json()
    play(client, opened["session_id"])

    with session_scope() as session:
        probe = session.scalars(select(RetentionProbe)).first()
        assert probe is not None
        skill_id = probe.skill_id

    settled = retention_service.on_attempt(
        child_id=child_id,
        skill_id=skill_id,
        form_signature="quiz",
        is_correct=True,
        now=datetime.now(timezone.utc) + timedelta(days=3),
    )

    assert settled["settled"] == ["day2"]
    assert settled["scheduled"] == "day7", "a probe that held for two days is asked again at seven"

    with session_scope() as session:
        paid = [
            episode
            for episode in session.scalars(select(PolicyEpisode)).all()
            if episode.reward is not None
        ]
        table = policy_repo.q_table(session)

    assert paid, "the probe settled and paid nothing"
    assert table, "the Q-table did not move"
    # The reward came from the probe and from nothing that happened in the turn.
    assert all(episode.probe_kind == "day2" for episode in paid)
    assert all(episode.q_before is not None and episode.q_after is not None for episode in paid)


def test_teaching_a_concept_is_not_recorded_as_leaking_its_name(client: TestClient):
    """The `match` turn explains the thing and then asks about it.

    Naming what you are teaching is the lesson. Charging it the answer-leak
    penalty - which is larger than a passed probe pays - would teach the table
    to stop explaining, which is the opposite of what the veto is for.
    """
    child_id = make_child(client, "not-a-leak@example.com")
    opened = client.post(f"/playground/teacher/{child_id}/open").json()
    play(client, opened["session_id"])

    with session_scope() as session:
        episodes = list(session.scalars(select(PolicyEpisode)).all())

    assert episodes
    assert not [episode for episode in episodes if episode.answer_leak_vetoed], (
        "an ordinary explain-then-ask turn was recorded as an answer leak"
    )


def test_an_outright_telling_is_still_a_leak_while_teaching():
    """The flag softens a bare mention. It never softens a frame."""
    told = leak.classify(
        "Look at the shapes. The answer is the square.",
        correct_answer="square",
        prompt="Which one has four equal sides?",
        teaching=True,
    )
    named = leak.classify(
        "This is a square. A square has four straight sides the same length.",
        correct_answer="square",
        prompt="Which one has four equal sides?",
        teaching=True,
    )

    assert told.is_leak
    assert not named.is_leak and named.kind == leak.SCAFFOLD


# --------------------------------------------------------------------------
# The echo is taught, and it is never marked
# --------------------------------------------------------------------------


def test_the_echo_is_never_written_to_the_attempt_log(client: TestClient):
    """Speech-to-text mishears a three-year-old constantly. A level that failed
    because a microphone did not catch a small voice is the app marking its own
    hardware, which is why `app/conductor/echo.py` never scored one either."""
    child_id = make_child(client, "echo-unmarked@example.com")
    opened = client.post(f"/playground/teacher/{child_id}/open").json()
    play(client, opened["session_id"])

    with session_scope() as session:
        attempts = list(session.scalars(select(Attempt)).all())

    assert attempts, "the sitting recorded nothing at all"
    assert not [
        attempt for attempt in attempts if attempt.activity_id == f"teacher_{lesson.SAY_IT}"
    ]


def test_the_echo_is_still_taught_and_still_repaired():
    """Unmarked is not unasked. It keeps its hint and its reveal."""
    step = lesson.Step(name=lesson.SAY_IT, index=1)

    assert step.asks_a_question is True
    assert step.is_scored is True, "it is still a question that can be repaired"
    assert step.is_marked is False, "and it never moves the level's score"

    # A match question is the other way round on its reveal: not scored, and it
    # still counts against the level.
    revealed = lesson.Step(name=lesson.MATCH, index=3, tries=lesson.TRIES_PER_QUESTION)
    assert revealed.is_scored is False and revealed.is_marked is True


# --------------------------------------------------------------------------
# What the health endpoint reports
# --------------------------------------------------------------------------


def test_the_probe_and_leak_rates_are_actually_computed():
    """Both were a flat 0.0 whatever happened: the lookups matched on a label
    prefix, and `_key` sorts the labels, so the real key never began that way."""
    metrics.reset()
    metrics.count(metrics.PROBE, kind="day2", passed=True, episodes=2)
    metrics.count(metrics.PROBE, kind="day7", passed=False, episodes=1)
    metrics.count(metrics.LEAK_VERDICT, kind="leak", strategy="S1_TELL")
    metrics.count(metrics.LEAK_VERDICT, kind="none", strategy="S2_SHOW")
    metrics.count(metrics.LEAK_VERDICT, kind="none", strategy="S1_TELL")

    rates = metrics.rates()
    metrics.reset()

    assert rates["probe_pass_rate"] == 0.5
    assert rates["answer_leak_rate"] == pytest.approx(1 / 3, abs=1e-4)


def test_a_rate_that_cannot_be_computed_is_absent_rather_than_zero():
    metrics.reset()

    assert "probe_pass_rate" not in metrics.rates()
    assert "answer_leak_rate" not in metrics.rates()


# --------------------------------------------------------------------------
# The fences
# --------------------------------------------------------------------------


def test_the_substitution_is_judged_against_the_turn_that_happened():
    """`commit()` rebuilt the eligibility context out of the three things it
    happened to know, so a strategy removed because the child was close to tears
    passed the re-check - the re-check no longer knew they were."""
    frustrated = eligibility.TurnContext(experience_mode="standard", rung=2, frustrated=True)
    allowed = eligibility.decide(frustrated).allowed

    assert "S4_STORY" not in allowed, "a story is not what a frustrated child needs"
    # The context `commit()` used to rebuild lets it straight back in, which is
    # why the decision now carries the set it was actually chosen from.
    assert eligibility.permits(
        "S4_STORY", eligibility.TurnContext(experience_mode="standard", rung=2)
    )

    decision = teaching_policy_service.TeachingDecision(
        strategy="S3_EXAMPLE", eligible=tuple(allowed), durable=True, rung=2
    )

    assert "S4_STORY" not in decision.eligible


def test_an_empty_model_answer_counts_against_the_breaker():
    """The one failure mode this breaker was written for: a reasoning model that
    spends its whole budget thinking and returns nothing. Recording the success
    before the emptiness check reset the counter on every call, so the breaker
    never opened and every turn went on paying a full round trip."""

    class _Empty:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "   "}}]}

    class _Http:
        def post(self, *args, **kwargs):
            return _Empty()

    llm_client.reset_breaker()
    before = llm_client._breaker.failures
    original_http, original_configured = llm_client._http, llm_client.is_configured
    llm_client._http = lambda: _Http()
    llm_client.is_configured = lambda: True
    try:
        with pytest.raises(llm_client.LLMUnavailable):
            llm_client.chat(llm_client.ChatRequest(system=["s"], user=["u"]))
        assert llm_client._breaker.failures == before + 1
    finally:
        llm_client._http, llm_client.is_configured = original_http, original_configured
        llm_client.reset_breaker()


def test_the_kill_switch_is_not_open_to_anybody(client: TestClient, monkeypatch):
    """`POST /policy/disable` changes server state and had no caller check on it
    at all. It stays one curl away in development and wants the operator's token
    everywhere else."""
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "env", "production", raising=False)
    monkeypatch.setattr(settings, "policy_admin_token", "s3cret", raising=False)

    try:
        assert client.post("/policy/disable").status_code == 403
        assert client.post("/policy/disable", headers={"X-Policy-Token": "guess"}).status_code == 403
        assert client.post("/policy/disable", headers={"X-Policy-Token": "s3cret"}).status_code == 200
    finally:
        health.reset()


def test_an_unset_token_closes_the_switch_rather_than_opening_it(client: TestClient, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "env", "production", raising=False)
    monkeypatch.setattr(settings, "policy_admin_token", "", raising=False)

    assert client.post("/policy/disable").status_code == 403
