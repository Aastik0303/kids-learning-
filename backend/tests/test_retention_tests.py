"""Retention tests: scheduled deterministically, judged in Python, paid backwards.

The chain these pin, end to end:

    teaching episode -> concept -> retention test (due_at = taught + 2 days)
    -> the child answers a *different* question about the same concept
    -> stage.judge -> reward -> the ORIGINAL episode's (state, action) -> Q-value

Four properties are load-bearing and each has its own test:

* the scheduler, and only the scheduler, decides **when** - `due_at` is the
  teaching time plus two days, and a Q-value is never consulted;
* the question is a **different** authored one about the same concept;
* the reward lands on the **teaching** episode, not on the asking of the test;
* it lands **once** - a repeated sweep creates no second test, and a repeated
  settlement pays no second reward.

And one property that is about what a retention test must *not* do: the
curriculum is untouched by it. No stars, no unlock, no stage, no attempt row.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Attempt, PlaygroundSession, PolicyEpisode, PolicyQValue, RetentionTest
from app.db.repositories import policy as policy_repo
from app.db.repositories import retention_tests as retention_repo
from app.db.session import session_scope
from app.main import app
from app.playground import retention as retention_questions
from app.playground.stage import contains_answer
from app.policy import retention as retention_rules
from app.policy import reward as reward_rules
from app.services import planner_runner, retention_test_service


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


def play(client: TestClient, session_id: str, turns: int = 30) -> dict:
    """Answer whatever is in front of the child, using the server's own key.

    The key is never sent to the client, so it is read out of the row - which is
    also how a test can tell a check-in (judged from the retention test) from a
    lesson question (judged from `pending_answer`).
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


def age_episodes(days: int = 3) -> None:
    """Move every teaching episode back in time, the way waiting two days does.

    The scheduler reads `taken_at`, so this is the whole of "it is now Day 3"
    for the purposes of these tests - and it is the honest way to say it,
    because `due_at` is computed from when the teaching happened rather than
    from when the sweep runs.
    """
    moved = datetime.now(timezone.utc) - timedelta(days=days)
    with session_scope() as session:
        for episode in session.scalars(select(PolicyEpisode)).all():
            episode.taken_at = moved


def next_morning() -> None:
    """Close last night's sitting, the way the calendar does.

    A sitting belongs to the day it was opened on: `open_session` sees a row
    whose `plan_date` is not today and starts a clean one. Backdating the row is
    how the rest of this suite says "the next morning", and it is what makes the
    class open a *new* sitting - which is the only moment check-ins are taken.
    """
    with session_scope() as session:
        for row in session.scalars(select(PlaygroundSession)).all():
            row.plan_date = date.today() - timedelta(days=1)


def teach_a_day(client: TestClient, email: str, turns: int = 8) -> str:
    """Day 1: a child is taught, episodes are written, and the day is left open.

    Deliberately not played to the end. A finished day shuts the class until
    tomorrow - that lock is older than this feature and this feature does not
    lift it - so a child whose plan is complete meets their check-ins in
    tomorrow's sitting rather than in a class that has already said goodbye.
    """
    child_id = make_child(client, email)
    opened = client.post(f"/playground/teacher/{child_id}/open").json()
    play(client, opened["session_id"], turns=turns)
    return child_id


def _every_topic() -> list[str]:
    """Every topic the shipped manifest holds, in class order."""
    from app.services import curriculum_service

    return [
        topic.topic_id
        for summary in curriculum_service.list_classes()
        for subject in curriculum_service.get_class(summary.class_id).subjects
        for topic in subject.topics
    ]


def _a_topic_with_two_questions():
    """The first topic whose author wrote at least two questions.

    Named rather than hard-coded: which topic that is depends on the shipped
    syllabus, and the property being tested is about *any* such topic.
    """
    from app.playground import questions

    for topic_id in _every_topic():
        pool = questions.for_topic(topic_id)
        if len(pool) >= 2:
            return topic_id, pool
    return "", ()


# --------------------------------------------------------------------------
# The scheduler decides when
# --------------------------------------------------------------------------


def test_a_taught_concept_becomes_due_two_days_later(client: TestClient):
    child_id = teach_a_day(client, "retention-due@example.com")

    # Day 1: nothing is due yet, and nothing has been scheduled.
    assert retention_test_service.schedule()["created"] == 0
    assert retention_test_service.due_for_child(child_id) == []

    age_episodes(days=3)
    created = retention_test_service.schedule()["created"]
    assert created > 0

    with session_scope() as session:
        tests = list(session.scalars(select(RetentionTest)).all())
        episodes = {
            episode.id: episode for episode in session.scalars(select(PolicyEpisode)).all()
        }
        assert tests
        for test in tests:
            episode = episodes[test.source_teaching_episode_id]
            # due_at is the teaching time plus the configured delay, computed
            # from when the teaching happened and not from when the sweep ran.
            assert retention_rules.as_utc(test.due_at) == retention_rules.due_at(episode.taken_at)
            assert test.concept_id == episode.skill_id
            assert test.status == retention_rules.PENDING


def test_the_scheduler_is_idempotent(client: TestClient):
    """A sweep that runs twice writes one test per episode. This is the whole
    of "prevent duplicate reward settlement" at its source."""
    teach_a_day(client, "retention-idempotent@example.com")
    age_episodes(days=3)

    first = retention_test_service.schedule()["created"]
    second = retention_test_service.schedule()["created"]
    third = retention_test_service.schedule()["created"]

    assert first > 0
    assert (second, third) == (0, 0)

    with session_scope() as session:
        tests = list(session.scalars(select(RetentionTest)).all())
        sources = [test.source_teaching_episode_id for test in tests]
        assert len(sources) == len(set(sources))


def test_the_planner_sweep_schedules_them(client: TestClient):
    """Retention tests are part of the schedule, created by the schedule's own
    sweep - not by a separate background mechanism."""
    teach_a_day(client, "retention-sweep@example.com")
    age_episodes(days=3)

    summary = planner_runner.sweep()
    assert summary["retention_tests"] > 0

    with session_scope() as session:
        assert session.scalars(select(RetentionTest)).first() is not None


def test_due_tests_come_back_in_a_deterministic_order(client: TestClient):
    child_id = teach_a_day(client, "retention-order@example.com")
    age_episodes(days=3)
    retention_test_service.schedule()

    first = [test.test_id for test in retention_test_service.due_for_child(child_id, limit=5)]
    second = [test.test_id for test in retention_test_service.due_for_child(child_id, limit=5)]
    assert first == second
    assert first  # something was actually due

    with session_scope() as session:
        rows = retention_repo.due_for_child(
            session, child_id=__import__("uuid").UUID(child_id), now=datetime.now(timezone.utc)
        )
        assert [str(row.id) for row in rows][: len(first)] == first
        # Oldest debt first, and the order is a function of the rows alone.
        assert rows == sorted(rows, key=retention_rules.order_key)


# --------------------------------------------------------------------------
# The question is a different one about the same concept
# --------------------------------------------------------------------------


def test_the_retention_question_is_not_the_taught_question():
    """"Which letter does Apple start with?" is answered by "...does Ant...?"

    Same concept, different question. A topic that authored only one question
    can only ask that one, and it is priced as recall rather than transfer.
    """
    from app.playground import questions

    topic_id, pool = _a_topic_with_two_questions()
    assert topic_id, "the shipped syllabus should author two questions somewhere"

    taught = pool[0]
    asked = retention_questions.pick(topic_id, taught_ref=taught.activity_id)
    assert asked is not None
    assert asked.activity_id != taught.activity_id
    assert retention_rules.is_transfer(
        taught_question_ref=taught.activity_id, asked_question_ref=asked.activity_id
    )

    # ...and with nothing recorded about the teaching question, no transfer is
    # claimed: an unproven transfer is not paid for.
    assert not retention_rules.is_transfer(taught_question_ref="", asked_question_ref="x")


def test_a_question_that_wants_a_tap_has_something_to_tap():
    """The same rule the class keeps: options or a spoken answer, never a
    typing box in front of a child who cannot type."""
    from app.playground import questions

    checked = 0
    for topic_id in _every_topic()[:40]:
        asked = retention_questions.pick(topic_id)
        if asked is None:
            continue
        checked += 1
        assert asked.expects in {"tap", "voice"}
        if asked.expects == "tap":
            assert len(asked.options) >= 2
            assert any(contains_answer(option, asked.answer) for option in asked.options)
    assert checked, "no topic in the shipped syllabus produced a retention question"


# --------------------------------------------------------------------------
# The reward belongs to the original teaching action
# --------------------------------------------------------------------------


def test_a_pass_pays_the_original_teaching_episode(client: TestClient):
    teach_a_day(client, "retention-credit@example.com")
    age_episodes(days=3)
    retention_test_service.schedule()

    with session_scope() as session:
        test = session.scalars(select(RetentionTest)).first()
        episode = retention_repo.source_episode(session, test)
        before = (episode.state_key, episode.action, episode.answer_leak_vetoed)
        test_id = str(test.id)
        episode_id = str(episode.id)

    outcome = retention_test_service.settle(test_id, passed=True, asked_question_ref="other_q")
    assert outcome["settled"] is True
    assert outcome["result"] == reward_rules.PASS
    assert outcome["episode_id"] == episode_id
    assert outcome["episodes_paid"] == 1
    # The state and action credited are the *teaching* turn's, not the test's.
    assert (outcome["state_key"], outcome["action"]) == (before[0], before[1])

    with session_scope() as session:
        episode = session.get(PolicyEpisode, __import__("uuid").UUID(episode_id))
        assert episode.reward is not None
        assert episode.reward_resolved_at is not None
        assert episode.probe_kind == policy_repo.TEST_KIND
        assert episode.probe_passed is True
        # The Q-value moved, and the episode says what it was on either side.
        assert episode.q_before is not None and episode.q_after is not None
        row = session.scalar(
            select(PolicyQValue).where(
                PolicyQValue.state_key == episode.state_key,
                PolicyQValue.action == episode.action,
            )
        )
        assert row is not None
        assert row.q_value == pytest.approx(episode.q_after)
        # A passed test is a positive reward, so the action it credits is worth
        # more than it was. The exact arithmetic is pinned in the next test, on
        # an episode with no successor state - the honest place for it, because
        # on an episode that has one the bootstrap term is read from a table
        # this very update has just written to.
        assert episode.q_after > episode.q_before


def test_the_q_update_is_the_documented_one(client: TestClient):
    """Q(s,a) <- Q(s,a) + alpha * (r + gamma * max Q(s',a') - Q(s,a)).

    Checked on an episode with no successor state, so `max Q(s',a')` is zero by
    definition and the identity is the reward alone.
    """
    teach_a_day(client, "retention-formula@example.com")
    age_episodes(days=3)
    retention_test_service.schedule()

    with session_scope() as session:
        test = session.scalars(select(RetentionTest)).first()
        episode = retention_repo.source_episode(session, test)
        episode.next_state_key = None
        state_key, action = episode.state_key, episode.action
        q_before = policy_repo.action_values(session, state_key=state_key).get(action, 0.0)
        test_id = str(test.id)

    outcome = retention_test_service.settle(test_id, passed=True)

    with session_scope() as session:
        q_after = policy_repo.action_values(session, state_key=state_key)[action]
    expected = q_before + policy_repo.LEARNING_RATE * (outcome["reward"] - q_before)
    assert q_after == pytest.approx(expected)
    assert (policy_repo.LEARNING_RATE, policy_repo.DISCOUNT) == (0.15, 0.85)


def test_no_episode_is_written_for_the_test_itself(client: TestClient):
    """Answering a retention test chooses no strategy and trains nothing about
    itself. The reward belongs to the teaching turn two days ago."""
    teach_a_day(client, "retention-no-episode@example.com")
    age_episodes(days=3)
    retention_test_service.schedule()

    with session_scope() as session:
        before = len(list(session.scalars(select(PolicyEpisode)).all()))
        test_id = str(session.scalars(select(RetentionTest)).first().id)

    retention_test_service.settle(test_id, passed=True)

    with session_scope() as session:
        assert len(list(session.scalars(select(PolicyEpisode)).all())) == before


def test_a_settled_test_is_never_settled_twice(client: TestClient):
    teach_a_day(client, "retention-once@example.com")
    age_episodes(days=3)
    retention_test_service.schedule()

    with session_scope() as session:
        test_id = str(session.scalars(select(RetentionTest)).first().id)

    first = retention_test_service.settle(test_id, passed=True)
    with session_scope() as session:
        test = session.get(RetentionTest, __import__("uuid").UUID(test_id))
        episode = retention_repo.source_episode(session, test)
        paid_reward, paid_q = episode.reward, episode.q_after

    second = retention_test_service.settle(test_id, passed=False)
    assert first["settled"] is True
    assert second["settled"] is False

    with session_scope() as session:
        test = session.get(RetentionTest, __import__("uuid").UUID(test_id))
        episode = retention_repo.source_episode(session, test)
        assert test.status == retention_rules.SETTLED
        assert test.result == reward_rules.PASS
        # Neither the reward nor the Q-value moved a second time.
        assert episode.reward == paid_reward
        assert episode.q_after == paid_q


def test_an_episode_already_paid_is_not_paid_again(client: TestClient):
    """The older opportunistic probe and the scheduled test both go through
    `pay_episode`, which is where "once" is enforced."""
    teach_a_day(client, "retention-double@example.com")
    age_episodes(days=3)
    retention_test_service.schedule()

    with session_scope() as session:
        test = session.scalars(select(RetentionTest)).first()
        episode = retention_repo.source_episode(session, test)
        test_id, episode_id = str(test.id), str(episode.id)
        # Pay it by hand, as the probe path would.
        assert policy_repo.pay_episode(session, episode, reward=1.0, probe_kind="day2") is True
        paid_q = episode.q_after

    outcome = retention_test_service.settle(test_id, passed=True)
    assert outcome["settled"] is True
    # The test records its own result for the audit trail and moves nothing.
    assert outcome["episodes_paid"] == 0

    with session_scope() as session:
        episode = session.get(PolicyEpisode, __import__("uuid").UUID(episode_id))
        assert episode.reward == 1.0
        assert episode.probe_kind == "day2"
        assert episode.q_after == paid_q


# --------------------------------------------------------------------------
# What a result is worth
# --------------------------------------------------------------------------


def test_the_reward_weights_are_the_configured_ones():
    assert reward_rules.for_retention(passed=True).value == pytest.approx(1.0)
    assert reward_rules.for_retention(passed=True, transfer=True).value == pytest.approx(1.35)
    assert reward_rules.for_retention(passed=False).value == pytest.approx(-0.5)
    # A leak costs more than a passed test pays, so giving the answer away
    # cannot come out ahead even when the child then remembers it.
    assert reward_rules.for_retention(
        passed=True, transfer=True, answer_leak_vetoed=True
    ).value == pytest.approx(-0.15)
    assert reward_rules.for_retention(passed=False, answer_leak_vetoed=True).value == pytest.approx(
        -2.0
    )


def test_the_weights_are_configurable(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("REWARD_RETENTION_PASS", "2.5")
    monkeypatch.setenv("PENALTY_RETENTION_FAIL", "0.1")
    get_settings.cache_clear()
    try:
        assert reward_rules.for_retention(passed=True).value == pytest.approx(2.5)
        assert reward_rules.for_retention(passed=False).value == pytest.approx(-0.1)
    finally:
        get_settings.cache_clear()


# --------------------------------------------------------------------------
# The class asks them, and the curriculum is untouched by them
# --------------------------------------------------------------------------


def test_the_class_opens_with_the_due_check_in(client: TestClient):
    child_id = teach_a_day(client, "retention-class@example.com")
    age_episodes(days=3)
    retention_test_service.schedule()
    next_morning()

    due = retention_test_service.due_for_child(child_id)
    assert due, "something should have been due"

    opened = client.post(f"/playground/teacher/{child_id}/open").json()
    assert opened["is_retention_test"] is True
    assert opened["step"] == "retention"
    assert opened["retention_test_id"] == due[0].test_id
    assert opened["question"] == due[0].question
    # A check-in is not one of the stage's five questions.
    assert opened["questions_asked"] == 0

    # A reload finds the same check-in, not a new one.
    again = client.get(f"/playground/teacher/sessions/{opened['session_id']}").json()
    assert again["retention_test_id"] == opened["retention_test_id"]

    answered = client.post(
        f"/playground/teacher/sessions/{opened['session_id']}/answer",
        json={"answer": due[0].answer},
    ).json()
    assert answered["is_correct"] is True

    with session_scope() as session:
        test = session.get(RetentionTest, __import__("uuid").UUID(due[0].test_id))
        assert test.status == retention_rules.SETTLED
        assert test.result == reward_rules.PASS
        assert test.question_ref == due[0].question_ref


def test_a_check_in_never_touches_the_curriculum(client: TestClient):
    """No attempt row, no stage tally, no plan cursor, no star. A retention test
    feeds the policy and nothing else."""
    child_id = teach_a_day(client, "retention-safe@example.com")
    age_episodes(days=3)
    retention_test_service.schedule()
    next_morning()

    plan_before = client.get(f"/plans/{child_id}/today").json()
    with session_scope() as session:
        attempts_before = len(list(session.scalars(select(Attempt)).all()))

    due = retention_test_service.due_for_child(child_id)
    opened = client.post(f"/playground/teacher/{child_id}/open").json()
    assert opened["is_retention_test"] is True

    # Answer every check-in wrongly - the worst case for the curriculum.
    turn = opened
    for _ in range(len(due)):
        turn = client.post(
            f"/playground/teacher/sessions/{opened['session_id']}/answer",
            json={"answer": "definitely not the answer"},
        ).json()

    with session_scope() as session:
        attempts_after = len(list(session.scalars(select(Attempt)).all()))
        row = session.scalar(
            select(PlaygroundSession).where(
                PlaygroundSession.session_id == opened["session_id"]
            )
        )
        # Nothing was written to the attempt log, so mastery and the weak-skill
        # list have not moved.
        assert attempts_after == attempts_before
        # ...and the stage's own tally is untouched.
        assert (row.topic_answered, row.topic_correct, row.questions_asked) == (0, 0, 0)

    plan_after = client.get(f"/plans/{child_id}/today").json()
    assert plan_after["current_topic_id"] == plan_before["current_topic_id"]
    assert plan_after["completed"] == plan_before["completed"]
    assert turn["stars_earned"] == 0
    assert turn["topic_completed"] is False
    assert turn["next_topic_unlocked"] is False

    # The round is through, so the class is teaching today's first stage.
    assert turn["is_retention_test"] is False
    assert turn["step"] in {"explain", "say_it", "draw", "match", "quiz"}


def test_the_schedule_shows_what_is_due(client: TestClient):
    child_id = teach_a_day(client, "retention-schedule@example.com")
    age_episodes(days=3)
    retention_test_service.schedule()

    plan = client.get(f"/plans/{child_id}/today").json()
    assert plan["retention_tests"], "the schedule should carry the due check-ins"
    first = plan["retention_tests"][0]
    assert {"test_id", "concept_id", "topic_id", "title", "due_at"} <= set(first)
    # Retention tests ride beside the curriculum items, never inside them.
    assert all(item["topic_id"] != first["test_id"] for item in plan["items"])


def test_the_operator_can_see_what_is_owed(client: TestClient):
    teach_a_day(client, "retention-operator@example.com")
    age_episodes(days=3)
    retention_test_service.schedule()

    body = client.get("/policy/retention").json()
    assert body["delay_days"] == 2
    assert body["pending"] > 0
    assert body["weights"]["retention_pass"] == pytest.approx(1.0)


# --------------------------------------------------------------------------
# One complete scenario, in the order the feature happens
# --------------------------------------------------------------------------


def test_day_one_teaches_and_day_three_pays(client: TestClient):
    """Day 1: taught. Day 3: tested on a different question, and the Q-value of
    the Day 1 teaching action moves."""
    child_id = teach_a_day(client, "retention-end-to-end@example.com")

    with session_scope() as session:
        assert session.scalars(select(PolicyEpisode)).first() is not None

    age_episodes(days=3)
    assert planner_runner.sweep()["retention_tests"] > 0
    next_morning()

    due = retention_test_service.due_for_child(child_id)
    assert due

    opened = client.post(f"/playground/teacher/{child_id}/open").json()
    while opened.get("is_retention_test"):
        test_id = opened["retention_test_id"]
        answer = next(one.answer for one in due if one.test_id == test_id)
        opened = client.post(
            f"/playground/teacher/sessions/{opened['session_id']}/answer",
            json={"answer": answer},
        ).json()

    with session_scope() as session:
        settled = [
            test
            for test in session.scalars(select(RetentionTest)).all()
            if test.status == retention_rules.SETTLED
        ]
        assert settled, "the sitting should have settled the check-ins it asked"

        for test in settled:
            assert test.settled_at is not None
            assert test.result == reward_rules.PASS
            assert test.reward is not None and test.reward > 0
            assert test.episodes_paid == 1

            # The reward landed on the Day 1 teaching turn - its state, its
            # action - and the Q-table now holds what that update produced.
            episode = retention_repo.source_episode(session, test)
            assert episode.reward == pytest.approx(test.reward)
            assert episode.probe_kind == policy_repo.TEST_KIND
            assert episode.q_after > episode.q_before
            values = policy_repo.action_values(session, state_key=episode.state_key)
            assert values[episode.action] == pytest.approx(episode.q_after)

        # ...and nothing was written as an episode of the test's own asking.
        assert all(episode.action for episode in session.scalars(select(PolicyEpisode)).all())
