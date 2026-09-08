"""A level that has been passed is not weak any more, so tomorrow is the next one.

The stall as the user met it: letter A was taught, failed once, taught again and
passed - the star was paid, the map unlocked letter B - and the scheduler went
on putting A in front of the child every single morning. Nothing downstream was
broken: `award_topic_completion` completed the topic, unlocked the next and
ticked the plan cursor. The plan for the *next* day was the problem.

`mark_weak` appends a skill to `child["weak_skills"]` and nothing anywhere ever
removed one. `plan_service._candidates` prefers a weak level over new ground -
correctly - so the first level a child ever struggled with became that subject's
permanent answer to "what is today?", and every level behind it was unreachable.
It happened in every subject at once, because every subject has a first level.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app

from test_the_day_moves_on import make_child, play


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_a_level_that_passes_stops_being_weak(client: TestClient, next_day):
    child_id = make_child(client, "weak-clears@example.com")

    # Day one: the whole day goes badly, so every level of it is marked weak.
    opened = client.post(f"/playground/teacher/{child_id}/open").json()
    play(client, opened["session_id"], correctly=False)
    day_one = client.get(f"/plans/{child_id}/today").json()
    struggled = {item["topic_id"] for item in day_one["items"]}

    # Day two: the same levels come back as revisits, and this time they pass.
    next_day()
    day_two = client.get(f"/plans/{child_id}/today").json()
    assert {item["topic_id"] for item in day_two["items"]} == struggled
    assert all(item["reason"] == "revisit" for item in day_two["items"])
    opened = client.post(f"/playground/teacher/{child_id}/open").json()
    play(client, opened["session_id"], correctly=True)

    profile = client.get(f"/children/{child_id}").json()
    assert not profile["weak_skills"], "a level that passed is not weak any more"

    # Day three is the levels day two unlocked, in every subject.
    next_day()
    day_three = client.get(f"/plans/{child_id}/today").json()
    assert not ({item["topic_id"] for item in day_three["items"]} & struggled)


def test_a_completed_level_opens_the_next_one_even_on_an_old_record(client: TestClient):
    """The second half of the same stall, found in the live database.

    Two children had subjects whose only unlocked topic was one they had already
    completed - a record written before the unlock rule, or one whose next
    topic's id was renamed and pruned. `_candidates` looks for the first
    *unlocked* topic that is not completed, finds none, and drops the subject
    out of the day: those subjects had simply stopped being taught, and nothing
    the child did could bring them back. Reconciling on read opens them.
    """
    from app.services import child_service, child_store

    child_id = make_child(client, "unlock-heals@example.com")

    child = child_store.get(child_id)
    subject_id, progress = next(iter(child["subject_progress"].items()))
    first = progress["unlocked_topics"][0]
    progress["completed_topics"] = [first]
    progress["unlocked_topics"] = [first]
    child_store.save(child)
    child_store.reset_cache()

    profile = child_service.get_child(child_id)
    board = profile.subject_progress[subject_id]
    assert len(board.unlocked_topics) > 1, "finishing a level opens the next one"
    assert board.current_topic_id not in board.completed_topics

    plan = client.get(f"/plans/{child_id}/today").json()
    planned = {item["topic_id"] for item in plan["items"]}
    assert planned & set(board.unlocked_topics) - {first}
    assert first not in planned, "a finished level is not what the subject is waiting on"
