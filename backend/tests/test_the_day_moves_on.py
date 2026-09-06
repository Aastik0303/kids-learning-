"""A level that was taught finishes today's item, whether or not it passed.

This is the test the project did not have on the day the schedule stopped dead.

`daily_plan_items.completed_at` was written only inside
`award_topic_completion`'s `if passed:` branch. A child who scored under the
topic's `passing_score` - which for a three-year-old is most mornings, since the
levels shipped want 80% - therefore left every item of the day NULL. The
consequences compounded quietly, and none of them raised:

* `plan_cursor` still pointed at item one, so `is_day_complete` stayed false;
* `open_session` discards a `day_complete` row and starts a clean sitting, so
  the class reopened **on the same level, the same afternoon**, for ever;
* no level was ever added to `completed_topics`, so the next level was never
  unlocked and the subjects behind it were never scheduled;
* Adventure showed nothing moving, because nothing had.

The rule these pin is the one the cursor's own docstring always described:
**passing is what earns the star and unlocks the next level; being taught
through is what finishes an item of today's work.** They are different
questions, and the day is answered by the second one.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import DailyPlanItem, PlaygroundSession
from app.db.session import session_scope
from app.main import app
from app.playground.stage import contains_answer


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


def play(client: TestClient, session_id: str, *, correctly: bool, turns: int = 260) -> dict:
    """Play a whole sitting, getting everything right or everything wrong.

    The key is read out of the server's own row because the client is never told
    it - which is the point of keeping it there - and "wrong" is a string that
    cannot be any authored answer.
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
            said = (
                next((option for option in options if contains_answer(option, answer)), answer)
                if correctly
                else "hmmmm not that one"
            )
        turn = client.post(
            f"/playground/teacher/sessions/{session_id}/answer", json={"answer": said}
        ).json()
        if turn.get("expects") == "done" or turn.get("day_complete"):
            break
    return turn


def test_a_day_of_failed_levels_still_finishes(client: TestClient):
    """The whole sitting was taught. The day knows it."""
    child_id = make_child(client, "day-moves-fail@example.com")

    before = client.get(f"/plans/{child_id}/today").json()
    assert before["complete"] is False
    assert before["total"] > 1

    opened = client.post(f"/playground/teacher/{child_id}/open").json()
    last = play(client, opened["session_id"], correctly=False)
    assert last["day_complete"] is True

    after = client.get(f"/plans/{child_id}/today").json()
    assert after["complete"] is True
    assert after["current_topic_id"] is None
    assert after["completed"] == after["total"]
    assert all(item["done"] for item in after["items"])

    with session_scope() as session:
        items = list(session.scalars(select(DailyPlanItem)).all())
        assert items and all(item.completed_at is not None for item in items)

    # ...and nothing was awarded for it. The day moved; the levels did not.
    profile = client.get(f"/children/{child_id}").json()
    assert profile["stars"] == 0
    assert all(
        not progress["completed_topics"] for progress in profile["subject_progress"].values()
    )


def test_the_class_does_not_reopen_on_the_level_it_just_taught(client: TestClient):
    """The stall as a child met it: finish the sitting, and the class starts
    again at level one on the same afternoon."""
    child_id = make_child(client, "day-moves-loop@example.com")

    opened = client.post(f"/playground/teacher/{child_id}/open").json()
    first_topic = opened["topic_id"]
    play(client, opened["session_id"], correctly=False)

    reopened = client.post(f"/playground/teacher/{child_id}/open").json()
    assert reopened["day_complete"] is True
    assert reopened["expects"] == "done"
    # The thing that was actually happening: stage 1, first topic, all over again.
    assert not (reopened["stage"] == 1 and reopened["topic_id"] == first_topic
                and reopened["day_complete"] is False)


def test_a_failed_level_comes_back_tomorrow_as_a_revisit(client: TestClient, next_day):
    """The level is not lost. It did not pass, so it did not unlock anything and
    it is on the weak list - and `_candidates` puts a weak level first."""
    child_id = make_child(client, "day-moves-revisit@example.com")

    opened = client.post(f"/playground/teacher/{child_id}/open").json()
    today = client.get(f"/plans/{child_id}/today").json()
    stuck = today["items"][0]["topic_id"]
    play(client, opened["session_id"], correctly=False)

    next_day()
    tomorrow = client.get(f"/plans/{child_id}/today").json()

    assert tomorrow["plan_date"] != today["plan_date"]
    assert tomorrow["complete"] is False
    assert any(
        item["topic_id"] == stuck and item["reason"] == "revisit" for item in tomorrow["items"]
    )


def test_a_passed_day_still_unlocks_the_next_levels(client: TestClient, next_day):
    """The fix must not have made passing meaningless: a level that passes still
    completes, still pays, and still opens the next one - which is tomorrow's."""
    child_id = make_child(client, "day-moves-pass@example.com")

    today = client.get(f"/plans/{child_id}/today").json()
    planned = {item["topic_id"] for item in today["items"]}

    opened = client.post(f"/playground/teacher/{child_id}/open").json()
    play(client, opened["session_id"], correctly=True)

    profile = client.get(f"/children/{child_id}").json()
    completed = {
        topic
        for progress in profile["subject_progress"].values()
        for topic in progress["completed_topics"]
    }
    unlocked = {
        topic
        for progress in profile["subject_progress"].values()
        for topic in progress["unlocked_topics"]
    }
    assert planned <= completed, "every level of a perfect day should be finished"
    assert unlocked - completed, "finishing a level should have opened the next one"
    assert profile["stars"] > 0

    # Tomorrow's plan is the levels today unlocked - which is the whole point of
    # holding them back until tomorrow.
    next_day()
    tomorrow = client.get(f"/plans/{child_id}/today").json()
    assert tomorrow["items"]
    assert {item["topic_id"] for item in tomorrow["items"]} & (unlocked - completed)
    assert not ({item["topic_id"] for item in tomorrow["items"]} & completed)
