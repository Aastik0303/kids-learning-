"""P1: the durable layer that replaces `mock_storage`.

The tests that matter most here are not the CRUD ones. They are the two that pin
the boundaries the whole design rests on:

- mastery is a function of the attempt log and of nothing else, and one lucky
  answer does not open the gate;
- a policy reward can only be paid by a retention probe, so a strategy that
  reaches today's right answer by giving it away is paid *less*, not more.

Everything runs on in-memory SQLite. The models use SQLAlchemy's portable types,
so the same Alembic migration describes this and production PostgreSQL.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db import models  # noqa: F401  - registers the tables
from app.db.repositories import learners, plans, policy, truth


DAY = timedelta(days=1)


@pytest.fixture()
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def child(db):
    parent = learners.create_parent(db, email="Parent@Example.com", name="Test Parent", password_hash="x")
    return learners.create_child(
        db, parent=parent, name="Aaru", birth_year=2022, birth_month=6, class_id="nursery", experience_mode="early"
    )


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------


def test_a_parent_email_is_stored_folded():
    """Two families cannot register the same address in different cases."""
    assert "Parent@Example.com".strip().lower() == "parent@example.com"


def test_one_family_cannot_read_another_familys_child(db, child):
    stranger = learners.create_parent(db, email="other@example.com", name="Other", password_hash="x")

    assert learners.owned_child(db, parent=stranger, child_id=child.id) is None
    assert learners.owned_child(db, parent=child.parent, child_id=child.id) is not None


def test_an_expired_token_stops_working(db, child):
    auth = learners.open_session(db, child.parent)
    later = datetime.now(timezone.utc) + timedelta(days=31)

    assert learners.parent_for_token(db, auth.token) is not None
    assert learners.parent_for_token(db, auth.token, now=later) is None


def test_consent_is_never_set_by_default(db, child):
    """Automating consent is illegal under DPDP and COPPA, so it starts unset
    and only the parent surface may set it."""
    assert child.parent.consent_granted_at is None

    learners.grant_consent(db, child.parent)
    assert child.parent.consent_granted_at is not None


# --------------------------------------------------------------------------
# Truth
# --------------------------------------------------------------------------


def test_the_server_counts_attempts_itself(db, child):
    """The repair ladder used to take the attempt count from the client, so a
    client stuck at zero silently defeated every escalation."""
    for index in range(3):
        truth.record_attempt(
            db, child_id=child.id, topic_id="t", activity_id="a1", skill_id="s1",
            is_correct=False, attempt_index=index,
        )

    assert truth.server_attempt_index(db, child_id=child.id, activity_id="a1") == 3
    assert truth.server_attempt_index(db, child_id=child.id, activity_id="a2") == 0


def test_one_lucky_answer_does_not_open_the_gate(db, child):
    truth.record_attempt(
        db, child_id=child.id, topic_id="t", activity_id="a1", skill_id="s1",
        is_correct=True, form_signature="pick-picture",
    )
    row = truth.mastery_for(db, child_id=child.id, skill_id="s1")

    assert row.mastery > 0
    assert not truth.is_mastered(row)
    assert row.mastered_at is None


def test_mastery_needs_attempts_forms_and_days(db, child):
    """All four clauses, not just the average: a skill that only survives inside
    one afternoon on one kind of question is not a skill the child has."""
    start = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)
    for index in range(6):
        truth.record_attempt(
            db, child_id=child.id, topic_id="t", activity_id=f"a{index}", skill_id="s1",
            is_correct=True,
            form_signature="pick-picture" if index % 2 else "say-it",
            now=start + index * DAY,
        )

    row = truth.mastery_for(db, child_id=child.id, skill_id="s1")

    assert truth.is_mastered(row)
    assert row.distinct_forms == 2
    assert row.distinct_days == 6
    assert row.mastered_at is not None


def test_a_supported_answer_counts_for_less(db, child):
    """Otherwise the fastest route to "mastered" is to leave the scaffolding up."""
    for index in range(4):
        truth.record_attempt(
            db, child_id=child.id, topic_id="t", activity_id=f"u{index}", skill_id="unaided",
            is_correct=True, scaffold_level=0, form_signature=f"f{index % 2}",
        )
        truth.record_attempt(
            db, child_id=child.id, topic_id="t", activity_id=f"s{index}", skill_id="supported",
            is_correct=True, scaffold_level=4, form_signature=f"f{index % 2}",
        )

    unaided = truth.mastery_for(db, child_id=child.id, skill_id="unaided")
    supported = truth.mastery_for(db, child_id=child.id, skill_id="supported")

    assert unaided.mastery > supported.mastery
    assert not truth.is_mastered(supported)


def test_a_lesson_resumes_where_it_stopped(db, child):
    truth.save_lesson_state(db, child_id=child.id, topic_id="nur_ga_safety", cursor=4, scaffold_level=2)
    truth.save_lesson_state(db, child_id=child.id, topic_id="nur_ga_safety", cursor=7)

    row = truth.resume_point(db, child_id=child.id, topic_id="nur_ga_safety")

    assert row.cursor == 7
    assert db.query(models.LessonState).count() == 1


# --------------------------------------------------------------------------
# The plan
# --------------------------------------------------------------------------


def test_a_plan_is_frozen_for_the_day(db, child):
    """Without the freeze the planner writes a slightly different plan on every
    refresh, and the child never gets a routine."""
    today = date(2026, 8, 23)
    first = plans.freeze_plan(
        db, child_id=child.id, plan_date=today,
        items=[plans.PlannedItem("t1", "s1"), plans.PlannedItem("t2", "s2", reason="revisit")],
        source="planner_agent",
    )
    second = plans.freeze_plan(
        db, child_id=child.id, plan_date=today, items=[plans.PlannedItem("totally", "different")]
    )

    assert second.id == first.id
    assert [item.topic_id for item in second.items] == ["t1", "t2"]
    assert second.source == "planner_agent"


def test_two_plans_for_one_day_are_refused_by_the_database(db, child):
    today = date(2026, 8, 23)
    db.add(models.DailyPlan(child_id=child.id, plan_date=today))
    db.flush()
    db.add(models.DailyPlan(child_id=child.id, plan_date=today))

    with pytest.raises(IntegrityError):
        db.flush()


def test_the_cursor_skips_what_is_done(db, child):
    plan = plans.freeze_plan(
        db, child_id=child.id, plan_date=date(2026, 8, 23),
        items=[plans.PlannedItem("t1", "s1"), plans.PlannedItem("t2", "s2")],
    )

    assert plans.plan_cursor(plan, completed_topic_ids={"t1"}).topic_id == "t2"
    assert plans.plan_cursor(plan, completed_topic_ids={"t1", "t2"}) is None


# --------------------------------------------------------------------------
# Learning to teach - the reward boundary
# --------------------------------------------------------------------------


def test_a_spent_strategy_survives_a_restart(db, child):
    """The in-process dict this replaces forgot everything on restart, so a child
    coming back got the same explanation that had already failed them."""
    for strategy in ("S1_TELL", "S3_EXAMPLE", "S1_TELL"):
        policy.record_teaching_event(
            db, child_id=child.id, skill_id="s1", activity_id="a1", strategy=strategy
        )

    assert policy.strategies_spent(db, child_id=child.id, activity_id="a1") == ["S1_TELL", "S3_EXAMPLE"]
    assert policy.strategies_spent(db, child_id=child.id, activity_id="a2") == []


def test_an_episode_cannot_be_born_with_a_reward(db, child):
    """`record_episode` takes no reward argument at all. That is the guard: the
    reward for a teaching decision does not exist yet when the decision is made."""
    probe = policy.schedule_probe(db, child_id=child.id, skill_id="s1")
    episode = policy.record_episode(
        db, child_id=child.id, skill_id="s1", state_key="early|low|r2", action="S5_CONTRAST",
        probe=probe, immediate_correct=True,
    )

    assert episode.reward is None
    assert episode.reward_resolved_at is None
    assert episode.immediate_correct is True


def test_leaking_the_answer_is_paid_less_than_teaching_it(db, child):
    """The reason RLHF was rejected, expressed as a test.

    Both episodes got the child to the right answer in the moment. The leaking
    one fails its probe two days later and carries a veto; the teaching one
    holds. If this assertion ever flips, the policy is being trained to cheat.
    """
    leak_probe = policy.schedule_probe(db, child_id=child.id, skill_id="leaked")
    leaked = policy.record_episode(
        db, child_id=child.id, skill_id="leaked", state_key="s", action="S1_TELL",
        probe=leak_probe, immediate_correct=True, answer_leak_vetoed=True,
    )

    taught_probe = policy.schedule_probe(db, child_id=child.id, skill_id="taught", form_signature="new-form")
    taught = policy.record_episode(
        db, child_id=child.id, skill_id="taught", state_key="s", action="S5_CONTRAST",
        probe=taught_probe, immediate_correct=True,
    )

    policy.settle_probe(db, leak_probe, was_correct=False)
    policy.settle_probe(db, taught_probe, was_correct=True)

    assert leaked.reward < 0
    assert taught.reward > 0
    assert taught.reward > leaked.reward


def test_settling_a_probe_moves_the_q_table(db, child):
    probe = policy.schedule_probe(db, child_id=child.id, skill_id="s1", form_signature="new-form")
    episode = policy.record_episode(
        db, child_id=child.id, skill_id="s1", state_key="early|low|r2", action="S6_DO_TOGETHER", probe=probe
    )
    policy.close_episode(db, episode, next_state_key="early|mid|r0")

    before = policy.action_values(db, state_key="early|low|r2")
    policy.settle_probe(db, probe, was_correct=True)
    after = policy.action_values(db, state_key="early|low|r2")

    assert before == {}
    assert after["S6_DO_TOGETHER"] > 0
    assert policy.get_q_value(db, state_key="early|low|r2", action="S6_DO_TOGETHER").visits == 1


def test_an_unsettled_episode_cannot_touch_the_table(db, child):
    episode = policy.record_episode(
        db, child_id=child.id, skill_id="s1", state_key="s", action="S1_TELL"
    )

    with pytest.raises(ValueError):
        policy._apply_q_update(db, episode)


def test_pending_episodes_are_visible(db, child):
    """A pile of these means probes are scheduled and never asked - the policy
    has stopped learning without anything raising."""
    probe = policy.schedule_probe(db, child_id=child.id, skill_id="s1")
    policy.record_episode(db, child_id=child.id, skill_id="s1", state_key="s", action="S1_TELL", probe=probe)

    assert len(policy.pending_episodes(db)) == 1
    policy.settle_probe(db, probe, was_correct=True)
    assert policy.pending_episodes(db) == []


def test_a_probe_is_not_due_before_its_time(db, child):
    now = datetime(2026, 8, 23, 9, 0, tzinfo=timezone.utc)
    policy.schedule_probe(db, child_id=child.id, skill_id="s1", kind="day2", now=now)

    assert policy.due_probes(db, child_id=child.id, now=now + DAY) == []
    assert len(policy.due_probes(db, child_id=child.id, now=now + 3 * DAY)) == 1


def test_an_unknown_probe_kind_is_refused(db, child):
    with pytest.raises(ValueError):
        policy.schedule_probe(db, child_id=child.id, skill_id="s1", kind="day90")


def test_a_single_form_skill_can_still_be_mastered(db, child):
    """48% of authored skills have exactly one activity. A flat two-form gate
    leaves those unmasterable for ever, and every topic depending on them locked
    - a child answering perfectly would simply stop being able to progress."""
    start = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)
    for index in range(4):
        truth.record_attempt(
            db, child_id=child.id, topic_id="t", activity_id="only_one", skill_id="lonely",
            is_correct=True, form_signature="the-only-form", forms_available=1,
            now=start + index * DAY,
        )

    row = truth.mastery_for(db, child_id=child.id, skill_id="lonely")

    assert row.distinct_forms == 1
    assert truth.required_forms(row) == 1
    assert truth.is_mastered(row)


def test_a_two_form_skill_still_needs_both(db, child):
    """The gate loosens only where the curriculum forces it to."""
    start = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)
    for index in range(4):
        truth.record_attempt(
            db, child_id=child.id, topic_id="t", activity_id=f"a{index}", skill_id="rich",
            is_correct=True, form_signature="one-form-only", forms_available=2,
            now=start + index * DAY,
        )

    row = truth.mastery_for(db, child_id=child.id, skill_id="rich")

    assert truth.required_forms(row) == 2
    assert not truth.is_mastered(row)
