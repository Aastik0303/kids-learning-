"""The production layer around the Q-learning policy.

`test_durable_storage.py` pins the repositories, `test_policy_wiring.py` pins
that the running app goes through them, and this one pins the things that have
to hold before a learned policy may choose what a real four-year-old hears:

- the eligibility filter runs *before* selection, and exploration cannot get
  round it;
- a retention probe pays exactly once, however many times it is settled;
- a reward reaches the teaching action that earned it and not a stale one;
- a corrupt Q-value, a missing row and a dead database all degrade to the
  hand-written ladder rather than to noise or to an error on a child's screen;
- shadow mode teaches with the ladder while recording what the table wanted;
- the offline evaluation refuses to declare a winner without the evidence.

Everything runs on the suite's own SQLite database (`conftest.py`).
"""

import math
import os
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.models import PolicyEpisode, PolicyQValue
from app.db.repositories import policy as policy_repo
from app.db.session import session_scope
from app.main import app
from app.policy import (
    actions,
    eligibility,
    evaluate,
    health,
    leak,
    metrics,
    rollout,
    selector,
    state,
)
from app.services import retention_service, teaching_policy_service


DAY = timedelta(days=1)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_policy_process_state():
    """The breaker, the kill switch and the counters are process-local."""
    health.reset()
    metrics.reset()
    yield
    health.reset()
    metrics.reset()


@pytest.fixture()
def setting():
    """Change one policy setting for the duration of a test."""
    changed: list[str] = []

    def apply(**values: str):
        for key, value in values.items():
            changed.append(key)
            os.environ[key] = value
        get_settings.cache_clear()

    yield apply
    for key in changed:
        os.environ.pop(key, None)
    get_settings.cache_clear()


def make_child(client: TestClient, email: str = "prod-policy@example.com") -> str:
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


# --------------------------------------------------------------------------
# 1. State generation
# --------------------------------------------------------------------------


def test_the_state_key_is_the_four_features_and_never_the_child():
    key = state.state_key(experience_mode="early", mastery=0.55, rung=2, spent=1)
    assert key == "early|m2|r2|n1"
    # Two different children in the same situation share a row. That is the
    # whole reason the table can learn from a nursery's worth of episodes.
    other = state.state_key(experience_mode="early", mastery=0.55, rung=2, spent=1)
    assert key == other


def test_the_state_key_is_clamped_so_a_wild_rung_cannot_invent_rows():
    assert state.state_key(experience_mode="standard", mastery=None, rung=99, spent=99).endswith(
        f"r{state.MAX_RUNG}|n{state.MAX_SPENT}"
    )
    assert state.mastery_bucket(-5.0) == 0
    assert state.mastery_bucket(17.0) == len(state.MASTERY_BUCKETS)


def test_the_next_state_is_the_pessimistic_one():
    assert state.next_state_key(experience_mode="standard", mastery=0.1, rung=1, spent=0) == "std|m0|r2|n1"


# --------------------------------------------------------------------------
# 2. Eligibility filtering - the gate in front of selection
# --------------------------------------------------------------------------


def test_a_spent_strategy_is_removed_with_a_reason():
    verdict = eligibility.decide(
        eligibility.TurnContext(experience_mode="standard", rung=2, spent=("S3_EXAMPLE",))
    )
    assert "S3_EXAMPLE" not in verdict.allowed
    assert verdict.removed["S3_EXAMPLE"] == eligibility.REASON_ALREADY_SPENT


def test_parking_is_off_the_menu_until_the_park_rung_and_the_only_thing_on_it_after():
    early = eligibility.decide(eligibility.TurnContext(rung=0))
    assert actions.PARK not in early.allowed
    assert early.removed[actions.PARK] == eligibility.REASON_PARK_NOT_YET

    late = eligibility.decide(eligibility.TurnContext(rung=actions.PARK_RUNG))
    assert late.allowed == [actions.PARK]


def test_early_mode_loses_the_strategies_that_assume_verbal_reasoning():
    verdict = eligibility.decide(eligibility.TurnContext(experience_mode="early", rung=2))
    assert "S4_STORY" not in verdict.allowed
    assert verdict.removed["S4_STORY"] == eligibility.REASON_MODE_EXCLUDED


def test_context_removes_what_the_app_cannot_deliver():
    verdict = eligibility.decide(
        eligibility.TurnContext(rung=2, has_prerequisite=False, has_visual=False, frustrated=True)
    )
    assert "S8_PREREQUISITE" not in verdict.allowed
    assert "S7_SENSE_SWITCH" not in verdict.allowed
    assert not eligibility.HIGH_LOAD_STRATEGIES & set(verdict.allowed)
    assert verdict.allowed, "the filter must never leave the turn with nothing to teach"


def test_the_filter_never_returns_an_empty_set():
    everything = tuple(s for s in actions.ALL_STRATEGIES if s != actions.PARK)
    verdict = eligibility.decide(eligibility.TurnContext(rung=2, spent=everything))
    assert verdict.allowed
    assert verdict.relaxed is True


def test_exploration_cannot_reach_a_filtered_strategy():
    """The point of running the filter first: a random draw is a draw from the
    survivors, not from the action space."""
    allowed = eligibility.decide(eligibility.TurnContext(rung=2, spent=("S3_EXAMPLE",))).allowed
    picks = {
        selector.choose(legal=allowed, stats={}, explore_rate=1.0, rng=_seeded(seed))[0]
        for seed in range(200)
    }
    assert "S3_EXAMPLE" not in picks
    assert actions.PARK not in picks


def _seeded(seed: int):
    import random

    return random.Random(seed)


# --------------------------------------------------------------------------
# 3. Epsilon-greedy, prior decay, corrupt values
# --------------------------------------------------------------------------


def test_epsilon_zero_is_deterministic_and_epsilon_one_explores():
    legal = ["S1_TELL", "S2_SHOW", "S3_EXAMPLE"]
    greedy = {selector.choose(legal=legal, stats={}, preferred=("S2_SHOW",), explore_rate=0.0) for _ in range(20)}
    assert greedy == {("S2_SHOW", False)}
    explored = [selector.choose(legal=legal, stats={}, explore_rate=1.0, rng=_seeded(s))[1] for s in range(10)]
    assert all(explored)


def test_the_prior_decays_as_the_table_gathers_visits():
    fresh = selector.prior_weight(0)
    warm = selector.prior_weight(selector.PRIOR_HALF_LIFE)
    cold = selector.prior_weight(1000)
    assert fresh == pytest.approx(selector.PRIOR_BONUS)
    assert warm == pytest.approx(selector.PRIOR_BONUS / 2)
    assert cold < 0.01
    # Evidence eventually beats the ladder, and not before.
    legal = ["S1_TELL", "S4_STORY"]
    day_one, _ = selector.choose(legal=legal, stats={}, preferred=("S1_TELL",), explore_rate=0.0)
    assert day_one == "S1_TELL"
    later, _ = selector.choose(
        legal=legal, stats={"S4_STORY": (0.9, 40), "S1_TELL": (0.1, 40)}, preferred=("S1_TELL",), explore_rate=0.0
    )
    assert later == "S4_STORY"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), 1e9, None])
def test_a_corrupt_q_value_is_ignored_rather_than_believed(bad):
    assert selector.sane(bad) is False
    clean, dropped = selector.sanitise({"S1_TELL": (bad, 3), "S2_SHOW": (0.4, 2)})
    assert dropped == ["S1_TELL"]
    assert clean == {"S2_SHOW": (0.4, 2)}
    # And the choice falls back to the ladder's own order for the dropped one.
    chosen, _ = selector.choose(
        legal=["S1_TELL", "S2_SHOW"],
        stats={"S1_TELL": (bad, 3), "S2_SHOW": (0.4, 2)},
        preferred=("S1_TELL",),
        explore_rate=0.0,
    )
    assert chosen in {"S1_TELL", "S2_SHOW"}
    assert not isinstance(chosen, float)


def test_a_corrupt_row_in_the_database_does_not_poison_the_update(client):
    child_id = make_child(client, "corrupt@example.com")
    with session_scope() as session:
        # SQLite will not even store a NaN in a NOT NULL float column, which is
        # its own small mercy; an out-of-range value is the corruption that
        # actually survives a write - a bad backfill, a wrong column, a runaway
        # update - and it is the one that would pin a strategy for ever.
        session.add(PolicyQValue(state_key="std|m0|r2|n0", action="S3_EXAMPLE", q_value=1e12, visits=4))
    stats = _action_stats("std|m0|r2|n0")
    assert "S3_EXAMPLE" not in stats, "an unusable row must not reach the selector"
    assert child_id


def _action_stats(key: str) -> dict:
    with session_scope() as session:
        return policy_repo.action_stats(session, state_key=key)


# --------------------------------------------------------------------------
# 4. Reward, the Q update, and paying a probe exactly once
# --------------------------------------------------------------------------


def _one_episode(session, child_id, *, skill="pg_maths:counting", action="S1_TELL", leaked=False):
    return policy_repo.record_episode(
        session,
        child_id=child_id,
        skill_id=skill,
        state_key="std|m0|r2|n0",
        action=action,
        answer_leak_vetoed=leaked,
        activity_id="count_01",
        rung=2,
    )


def test_the_reward_is_the_probes_and_only_the_probes(client):
    from uuid import UUID

    child_id = UUID(make_child(client, "reward@example.com"))
    with session_scope() as session:
        episode = _one_episode(session, child_id)
        assert episode.reward is None, "a teaching turn pays nothing"
        probe = policy_repo.schedule_probe(session, child_id=child_id, skill_id="pg_maths:counting")
        policy_repo.attach_probe(session, child_id=child_id, skill_id="pg_maths:counting", probe=probe)
        paid = policy_repo.settle_probe(session, probe, was_correct=True)
        assert [round(e.reward, 3) for e in paid] == [policy_repo.REWARD_RETENTION_PASS]


def test_a_leaked_answer_costs_more_than_a_passed_probe_pays(client):
    from uuid import UUID

    child_id = UUID(make_child(client, "leakreward@example.com"))
    with session_scope() as session:
        clean = _one_episode(session, child_id, action="S2_SHOW")
        leaked = _one_episode(session, child_id, action="S1_TELL", leaked=True)
        probe = policy_repo.schedule_probe(session, child_id=child_id, skill_id="pg_maths:counting")
        policy_repo.attach_probe(session, child_id=child_id, skill_id="pg_maths:counting", probe=probe)
        policy_repo.settle_probe(session, probe, was_correct=True)
        session.refresh(clean)
        session.refresh(leaked)
        assert clean.reward > 0 > leaked.reward
        assert leaked.reward == pytest.approx(
            policy_repo.REWARD_RETENTION_PASS - policy_repo.PENALTY_ANSWER_LEAK
        )


def test_a_probe_pays_once_however_many_times_it_is_settled(client):
    from uuid import UUID

    child_id = UUID(make_child(client, "idempotent@example.com"))
    with session_scope() as session:
        _one_episode(session, child_id)
        probe = policy_repo.schedule_probe(session, child_id=child_id, skill_id="pg_maths:counting")
        policy_repo.attach_probe(session, child_id=child_id, skill_id="pg_maths:counting", probe=probe)
        first = policy_repo.settle_probe(session, probe, was_correct=True)
        assert len(first) == 1
        after_first = policy_repo.get_q_value(session, state_key="std|m0|r2|n0", action="S1_TELL")
        value, visits = after_first.q_value, after_first.visits

        # The same probe, settled again - a retry, a double-submitted attempt,
        # a second worker. It must move nothing.
        again = policy_repo.settle_probe(session, probe, was_correct=True)
        assert again == []
        row = policy_repo.get_q_value(session, state_key="std|m0|r2|n0", action="S1_TELL")
        assert (row.q_value, row.visits) == (value, visits)


def test_the_q_update_is_the_written_arithmetic_and_records_both_sides(client):
    from uuid import UUID

    child_id = UUID(make_child(client, "qupdate@example.com"))
    with session_scope() as session:
        episode = _one_episode(session, child_id)
        probe = policy_repo.schedule_probe(session, child_id=child_id, skill_id="pg_maths:counting")
        policy_repo.attach_probe(session, child_id=child_id, skill_id="pg_maths:counting", probe=probe)
        policy_repo.settle_probe(session, probe, was_correct=True)
        session.refresh(episode)

        expected = 0.0 + policy_repo.LEARNING_RATE * (policy_repo.REWARD_RETENTION_PASS - 0.0)
        row = policy_repo.get_q_value(session, state_key="std|m0|r2|n0", action="S1_TELL")
        assert row.q_value == pytest.approx(expected)
        assert row.visits == 1
        assert episode.q_before == pytest.approx(0.0)
        assert episode.q_after == pytest.approx(expected)
        assert episode.probe_kind == "day2"
        assert episode.probe_passed is True


def test_an_unpaid_episode_cannot_update_the_table(client):
    from uuid import UUID

    child_id = UUID(make_child(client, "unpaid@example.com"))
    with session_scope() as session:
        episode = _one_episode(session, child_id)
        with pytest.raises(ValueError):
            policy_repo._apply_q_update(session, episode)


# --------------------------------------------------------------------------
# 5. Attribution - the right teaching action, not a stale one
# --------------------------------------------------------------------------


def test_a_probe_does_not_reach_back_past_the_attribution_window(client):
    from uuid import UUID

    child_id = UUID(make_child(client, "attribution@example.com"))
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        recent = _one_episode(session, child_id, action="S2_SHOW")
        ancient = _one_episode(session, child_id, action="S4_STORY")
        ancient.taken_at = now - policy_repo.ATTRIBUTION_WINDOW - 3 * DAY
        session.flush()

        probe = policy_repo.schedule_probe(session, child_id=child_id, skill_id="pg_maths:counting", now=now)
        attached = policy_repo.attach_probe(
            session, child_id=child_id, skill_id="pg_maths:counting", probe=probe, now=now
        )
        assert attached == 1

        policy_repo.settle_probe(session, probe, was_correct=True, now=now)
        session.refresh(recent)
        session.refresh(ancient)
        assert recent.reward is not None
        assert ancient.reward is None, "April's strategy must not be paid by June's probe"


def test_an_episode_already_pointed_at_a_probe_is_not_repointed(client):
    from uuid import UUID

    child_id = UUID(make_child(client, "repoint@example.com"))
    with session_scope() as session:
        episode = _one_episode(session, child_id)
        first = policy_repo.schedule_probe(session, child_id=child_id, skill_id="pg_maths:counting")
        policy_repo.attach_probe(session, child_id=child_id, skill_id="pg_maths:counting", probe=first)
        second = policy_repo.schedule_probe(
            session, child_id=child_id, skill_id="pg_maths:counting", kind="day7"
        )
        moved = policy_repo.attach_probe(
            session, child_id=child_id, skill_id="pg_maths:counting", probe=second
        )
        assert moved == 0
        session.refresh(episode)
        assert episode.retention_probe_id == first.id


# --------------------------------------------------------------------------
# 6. Answer-leak classification
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message,expected",
    [
        ("The answer is the circle.", leak.LEAK),
        ("Tap the circle!", leak.LEAK),
        ("It's a circle.", leak.LEAK),
        ("Circle is the correct answer.", leak.LEAK),
        ("Is it round like a ball, or does it have corners?", leak.NONE),
        ("It starts with the same sound as cat.", leak.PARTIAL),
        ("Look carefully at both shapes and count the corners.", leak.NONE),
    ],
)
def test_a_leak_is_told_apart_from_scaffolding(message, expected):
    verdict = leak.classify(message, correct_answer="circle", prompt="Which shape has no corners?")
    assert verdict.kind == expected


def test_repeating_the_question_is_not_a_leak():
    """Every identify-the-shape level names its own answer in the prompt.
    Marking those as leaks would veto the whole subject."""
    verdict = leak.classify(
        "Which one is the circle? Have a look at both.",
        correct_answer="circle",
        prompt="Which one is the circle?",
    )
    assert verdict.kind == leak.SCAFFOLD


def test_offering_the_answer_against_another_option_is_scaffolding():
    verdict = leak.classify(
        "Is this a circle or a square?",
        correct_answer="circle",
        prompt="Pick the round one.",
        options=("circle", "square"),
    )
    assert verdict.kind == leak.SCAFFOLD


def test_underscored_syllabus_answers_are_matched_as_words():
    assert leak.vetoes(
        "The answer is a standing line.",
        correct_answer="standing_line",
        prompt="Which stroke is this?",
    )


# --------------------------------------------------------------------------
# 7. Rollout, shadow mode and the kill switch
# --------------------------------------------------------------------------


def test_the_bucket_is_stable_for_a_child_and_spread_across_children():
    assert rollout.bucket("abc") == rollout.bucket("abc")
    spread = [rollout.bucket(f"child-{n}") for n in range(400)]
    assert 0.0 <= min(spread) and max(spread) < 1.0
    assert 0.4 < sum(1 for b in spread if b < 0.5) / len(spread) < 0.6


def test_the_rollout_fraction_decides_who_the_policy_teaches(setting):
    setting(POLICY_MODE="on", POLICY_ROLLOUT_FRACTION="0")
    assert all(not rollout.arm_for(f"c{n}").teaches for n in range(50))
    setting(POLICY_ROLLOUT_FRACTION="1")
    assert all(rollout.arm_for(f"c{n}").teaches for n in range(50))


def test_shadow_mode_teaches_with_the_ladder_and_records_the_recommendation(client, setting):
    setting(POLICY_MODE="shadow")
    child_id = make_child(client, "shadow@example.com")

    # Give the table a strong opinion the ladder does not share.
    key = state.state_key(experience_mode="standard", mastery=None, rung=2, spent=0)
    with session_scope() as session:
        row = policy_repo.get_q_value(session, state_key=key, action="S6_DO_TOGETHER")
        row.q_value, row.visits = 5.0, 50

    decision = teaching_policy_service.decide(
        child_id=child_id,
        skill_id="pg_maths:counting",
        activity_id="count_01",
        experience_mode="standard",
        rung=2,
    )
    assert decision.arm == rollout.SHADOW
    assert decision.strategy in actions.LADDER_PRIOR[2], "the child is taught by the ladder"
    assert decision.shadow_strategy == "S6_DO_TOGETHER", "the table's choice is recorded, not served"
    assert decision.durable is True


def test_the_learned_policy_teaches_when_it_is_rolled_out(client, setting):
    setting(POLICY_MODE="on", POLICY_ROLLOUT_FRACTION="1")
    child_id = make_child(client, "rolledout@example.com")
    key = state.state_key(experience_mode="standard", mastery=None, rung=2, spent=0)
    with session_scope() as session:
        row = policy_repo.get_q_value(session, state_key=key, action="S6_DO_TOGETHER")
        row.q_value, row.visits = 5.0, 50

    decision = teaching_policy_service.decide(
        child_id=child_id,
        skill_id="pg_maths:counting",
        activity_id="count_01",
        experience_mode="standard",
        rung=2,
    )
    assert decision.arm == rollout.RL
    assert decision.strategy == "S6_DO_TOGETHER"
    assert decision.shadow_strategy in actions.LADDER_PRIOR[2]


def test_the_kill_switch_sends_every_child_back_to_the_ladder(client, setting):
    setting(POLICY_MODE="on", POLICY_ROLLOUT_FRACTION="1")
    child_id = make_child(client, "killswitch@example.com")
    rollout.disable("test", seconds=300)

    decision = teaching_policy_service.decide(
        child_id=child_id,
        skill_id="pg_maths:counting",
        activity_id="count_01",
        experience_mode="standard",
        rung=2,
    )
    assert decision.arm == rollout.LADDER
    assert decision.durable is False, "a decision the policy did not make must not train it"
    assert decision.strategy in actions.LADDER_PRIOR[2]


def test_mode_off_disables_the_policy_without_touching_the_code(setting):
    setting(POLICY_MODE="off")
    assert rollout.arm_for("any-child").name == rollout.LADDER


def test_repeated_failures_trip_the_breaker_on_their_own(setting):
    setting(POLICY_BREAKER_THRESHOLD="3")
    for _ in range(2):
        health.record_failure("db")
    assert not rollout.disabled_reason()
    health.record_failure("db")
    assert rollout.disabled_reason(), "three failures in a row take the policy out of the loop"
    assert rollout.arm_for("child").name == rollout.LADDER


def test_a_success_clears_the_breakers_count():
    health.record_failure("db")
    health.record_success()
    assert health.consecutive_failures() == 0


def test_exploration_is_off_in_every_arm_but_the_live_one(setting):
    setting(POLICY_EXPLORE_RATE="0.08")
    assert rollout.explore_rate(rollout.Arm(rollout.SHADOW)) == 0.0
    assert rollout.explore_rate(rollout.Arm(rollout.LADDER)) == 0.0
    assert rollout.explore_rate(rollout.Arm(rollout.RL)) == pytest.approx(0.08)


def test_the_minimum_exploration_floor_applies_only_while_exploring(setting):
    setting(POLICY_EXPLORE_RATE="0.01", POLICY_EXPLORE_MIN="0.05")
    assert rollout.explore_rate(rollout.Arm(rollout.RL)) == pytest.approx(0.05)
    setting(POLICY_EXPLORE_RATE="0")
    assert rollout.explore_rate(rollout.Arm(rollout.RL)) == 0.0


# --------------------------------------------------------------------------
# 8. Fallback: a database that will not answer must not stop the lesson
# --------------------------------------------------------------------------


def test_a_dead_database_still_teaches(monkeypatch, setting):
    setting(POLICY_MODE="on", POLICY_ROLLOUT_FRACTION="1")

    def explode(*_args, **_kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(teaching_policy_service, "session_scope", explode)
    decision = teaching_policy_service.decide(
        child_id="6a5f1c2e-0d3b-4a7e-9c11-2f8b4d6e7a90",
        skill_id="pg_maths:counting",
        activity_id="count_01",
        experience_mode="standard",
        rung=2,
    )
    assert decision.strategy in actions.LADDER_PRIOR[2]
    assert decision.durable is False
    assert decision.fallback_reason == "db_error"
    assert health.consecutive_failures() == 1


def test_a_dead_database_does_not_raise_out_of_commit(monkeypatch):
    def explode(*_args, **_kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(teaching_policy_service, "session_scope", explode)
    written = teaching_policy_service.commit(
        child_id="6a5f1c2e-0d3b-4a7e-9c11-2f8b4d6e7a90",
        skill_id="pg_maths:counting",
        activity_id="count_01",
        decision=teaching_policy_service.TeachingDecision(
            strategy="S1_TELL", durable=True, state_key="std|m0|r2|n0"
        ),
        strategy="S1_TELL",
        experience_mode="standard",
        rung=2,
    )
    assert written is False


def test_a_substituted_strategy_must_pass_the_same_filter(client, setting):
    """The model may swap the policy's choice. It may not swap in one the
    eligibility filter had removed."""
    setting(POLICY_MODE="on", POLICY_ROLLOUT_FRACTION="1")
    child_id = make_child(client, "substitution@example.com")
    decision = teaching_policy_service.TeachingDecision(
        strategy="S1_TELL",
        spent=("S3_EXAMPLE",),
        state_key="std|m0|r2|n1",
        durable=True,
        arm=rollout.RL,
    )
    assert teaching_policy_service.commit(
        child_id=child_id,
        skill_id="pg_maths:counting",
        activity_id="count_01",
        decision=decision,
        strategy="S3_EXAMPLE",  # already spent - the filter removed it
        experience_mode="standard",
        rung=2,
    )
    with session_scope() as session:
        episode = session.query(PolicyEpisode).one()
    assert episode.action == "S1_TELL", "the rejected substitution is not what trains the table"


# --------------------------------------------------------------------------
# 9. Attribution columns, end to end
# --------------------------------------------------------------------------


def test_the_episode_records_enough_to_be_audited(client, setting):
    setting(POLICY_MODE="on", POLICY_ROLLOUT_FRACTION="1")
    child_id = make_child(client, "audit@example.com")
    decision = teaching_policy_service.decide(
        child_id=child_id,
        skill_id="pg_maths:counting",
        activity_id="count_01",
        experience_mode="standard",
        rung=2,
    )
    teaching_policy_service.commit(
        child_id=child_id,
        skill_id="pg_maths:counting",
        activity_id="count_01",
        decision=decision,
        strategy=decision.strategy,
        experience_mode="standard",
        rung=2,
        leak_kind=leak.SCAFFOLD,
    )
    with session_scope() as session:
        episode = session.query(PolicyEpisode).one()
        assert episode.activity_id == "count_01"
        assert episode.rung == 2
        assert episode.spent_count == 0
        assert episode.arm == rollout.RL
        assert episode.shadow_action
        assert episode.leak_kind == leak.SCAFFOLD
        assert episode.explore_rate == pytest.approx(0.0)
        assert episode.reward is None, "still nothing paid inside the teaching turn"


# --------------------------------------------------------------------------
# 10. The integration: teaching -> delayed probe -> reward -> Q update
# --------------------------------------------------------------------------


def test_teaching_then_a_probe_two_days_later_moves_the_table(client, setting):
    setting(POLICY_MODE="on", POLICY_ROLLOUT_FRACTION="1")
    child_id = make_child(client, "integration@example.com")
    skill = "pg_maths:counting"

    decision = teaching_policy_service.decide(
        child_id=child_id,
        skill_id=skill,
        activity_id="count_01",
        experience_mode="standard",
        rung=2,
    )
    assert teaching_policy_service.commit(
        child_id=child_id,
        skill_id=skill,
        activity_id="count_01",
        decision=decision,
        strategy=decision.strategy,
        experience_mode="standard",
        rung=2,
    )

    # The child gets it right today. That schedules the probe and pays nothing.
    day_zero = datetime.now(timezone.utc)
    retention_service.on_attempt(
        child_id=child_id, skill_id=skill, form_signature="tap", is_correct=True, now=day_zero
    )
    with session_scope() as session:
        episode = session.query(PolicyEpisode).one()
        assert episode.reward is None
        assert episode.retention_probe_id is not None

    # Two days later the skill comes round again, in a different form.
    result = retention_service.on_attempt(
        child_id=child_id, skill_id=skill, form_signature="voice", is_correct=True, now=day_zero + 2 * DAY
    )
    assert result["settled"] == ["day2"]
    assert result["scheduled"] == "day7"

    with session_scope() as session:
        episode = session.query(PolicyEpisode).one()
        assert episode.reward == pytest.approx(
            policy_repo.REWARD_RETENTION_PASS + policy_repo.REWARD_TRANSFER_BONUS
        )
        assert episode.probe_kind == "day2"
        row = policy_repo.get_q_value(session, state_key=episode.state_key, action=episode.action)
        assert row.q_value > 0
        assert row.visits == 1
        assert episode.q_after == pytest.approx(row.q_value)


def test_a_strategy_that_did_not_hold_is_paid_less_than_one_that_did(client):
    """The design in one test: the same correct answer today, two different
    Tuesdays, and the reward tells them apart."""
    from uuid import UUID

    child_id = UUID(make_child(client, "held@example.com"))
    with session_scope() as session:
        held = _one_episode(session, child_id, skill="a", action="S2_SHOW")
        lost = _one_episode(session, child_id, skill="b", action="S1_TELL")
        for skill, episode, passed in (("a", held, True), ("b", lost, False)):
            probe = policy_repo.schedule_probe(session, child_id=child_id, skill_id=skill)
            policy_repo.attach_probe(session, child_id=child_id, skill_id=skill, probe=probe)
            policy_repo.settle_probe(session, probe, was_correct=passed)
        session.refresh(held)
        session.refresh(lost)
    assert held.reward > 0 > lost.reward


# --------------------------------------------------------------------------
# 11. Monitoring and the operator's endpoints
# --------------------------------------------------------------------------


def test_the_metrics_separate_exploration_from_exploitation():
    metrics.count(metrics.DECISION, arm="rl")
    metrics.count(metrics.DECISION, arm="rl")
    metrics.count(metrics.EXPLORE, arm="rl")
    metrics.count(metrics.EXPLOIT, arm="rl")
    rates = metrics.rates()
    assert rates["exploration_rate"] == 0.5
    assert rates["exploitation_rate"] == 0.5


def test_rates_are_absent_rather_than_zero_before_there_is_evidence():
    assert "exploration_rate" not in metrics.rates()


def test_the_health_endpoint_answers_without_the_database(client):
    body = client.get("/policy/health").json()
    assert body["mode"]
    assert "consecutive_failures" in body
    assert "rates" in body


def test_the_evaluation_endpoint_reports_a_verdict(client):
    body = client.get("/policy/evaluation").json()
    assert body["verdict"]["conclusion"] == "no difference demonstrated"
    assert body["settled_episodes"] == 0


def test_disabling_the_policy_over_http_takes_effect_immediately(client, setting):
    setting(POLICY_MODE="on", POLICY_ROLLOUT_FRACTION="1")
    assert rollout.arm_for("child").teaches
    client.post("/policy/disable", params={"reason": "smoke"})
    assert not rollout.arm_for("child").teaches


# --------------------------------------------------------------------------
# 12. Offline evaluation - it must not claim a win it has not earned
# --------------------------------------------------------------------------


def test_the_evaluation_refuses_to_call_a_winner_on_thin_evidence(client):
    from uuid import UUID

    child_id = UUID(make_child(client, "evaluation@example.com"))
    with session_scope() as session:
        for index in range(5):
            episode = _one_episode(session, child_id, skill=f"s{index}", action="S1_TELL")
            probe = policy_repo.schedule_probe(session, child_id=child_id, skill_id=f"s{index}")
            policy_repo.attach_probe(session, child_id=child_id, skill_id=f"s{index}", probe=probe)
            policy_repo.settle_probe(session, probe, was_correct=True)
            assert episode

        report = evaluate.run(session)

    assert report.episodes == 5
    assert report.verdict()["conclusion"] == "no difference demonstrated"
    assert any("below the" in warning for warning in report.warnings)
    assert any("no exploration" in warning for warning in report.warnings)


def test_the_evaluation_rejects_a_candidate_that_leaks_more():
    ladder = evaluate.ArmResult(evaluate.LADDER, matched=100, total_reward=50.0, rewards=[0.5] * 100)
    learned = evaluate.ArmResult(
        evaluate.LEARNED, matched=100, total_reward=90.0, rewards=[0.9] * 100, leaks=20
    )
    report = evaluate.Report(arms={evaluate.LADDER: ladder, evaluate.LEARNED: learned}, episodes=200)
    assert report.verdict()["conclusion"] == "candidate rejected"


def test_the_evaluation_calls_a_win_only_when_it_clears_the_noise():
    ladder = evaluate.ArmResult(
        evaluate.LADDER, matched=200, total_reward=0.0, rewards=[0.1, -0.1] * 100
    )
    learned = evaluate.ArmResult(
        evaluate.LEARNED, matched=200, total_reward=180.0, rewards=[0.9] * 200
    )
    report = evaluate.Report(arms={evaluate.LADDER: ladder, evaluate.LEARNED: learned}, episodes=400)
    verdict = report.verdict()
    assert verdict["conclusion"] == f"{evaluate.LEARNED} better"
    assert verdict["reward_difference"] == pytest.approx(0.9, abs=0.01)


def test_the_standard_error_is_the_real_one():
    arm = evaluate.ArmResult("x", matched=4, total_reward=2.0, rewards=[0.0, 0.0, 1.0, 1.0])
    assert arm.mean_reward == pytest.approx(0.5)
    assert arm.standard_error == pytest.approx(math.sqrt((4 / 3) / 4) * 0.5, rel=0.1)
