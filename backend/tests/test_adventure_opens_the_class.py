"""Opening a level from the Adventure map runs the conductor, not a second loop.

Adventure used to drive `/learning` from the page itself: it started a session,
submitted answers and decided when the microphone opened. That was the second
copy of the class, and the say-it-back beat only ever existed in the conductor -
so a letter explained on the Adventure map went straight to a question and the
child was never asked to say it out loud.

`/conductor/{child}/open` now takes a topic. These tests pin what that may and
may not do: it names the topic, it runs the whole conducted loop including the
listening beat, and it does not become a way past the day's plan.
"""

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import curriculum_service, plan_service


SUBJECT_ID = "pg_maths"
TOPIC_ID = "pg_maths_colours"


def _letter_level() -> list[dict]:
    """A letter level: explained over three cards, then drawn, then matched."""
    return [
        {
            "activity_id": "adv_1",
            "type": "introduce_letter",
            "prompt": "This is A.",
            "visual_items": ["letter_A"],
            "skill_id": "letter_A",
        },
        {
            "activity_id": "adv_2",
            "type": "introduce_letter",
            "prompt": "A says 'aa'.",
            "skill_id": "letter_A_sound",
        },
        {
            "activity_id": "adv_3",
            "type": "introduce_letter",
            "prompt": "A is for apple.",
            "skill_id": "letter_A_word",
        },
        {
            "activity_id": "adv_4",
            "type": "trace",
            "prompt": "Draw A with your finger.",
            "trace_target": "A",
            "skill_id": "letter_A_write",
        },
        {
            "activity_id": "adv_5",
            "type": "match",
            "prompt": "Which one is A?",
            "options": ["A", "B"],
            "correct_answer": "A",
            "skill_id": "letter_A_match",
        },
    ]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    activities_dir = tmp_path / "activities"
    activities_dir.mkdir()
    (activities_dir / f"{SUBJECT_ID}.json").write_text(
        json.dumps({"subject_id": SUBJECT_ID, "topics": {TOPIC_ID: _letter_level()}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(curriculum_service, "ACTIVITIES_DIR", activities_dir)
    curriculum_service.reload_curriculum()
    with TestClient(app) as test_client:
        yield test_client
    monkeypatch.undo()
    curriculum_service.reload_curriculum()


def _child(client: TestClient) -> str:
    auth = client.post(
        "/auth/register", json={"name": "P", "email": "adventure@example.com", "password": "demo1234"}
    )
    response = client.post(
        "/children",
        json={
            "session_token": auth.json()["session_token"],
            "name": "Aanya",
            "birth_year": date.today().year - 2,
            "birth_month": date.today().month,
            "preferred_language": "English",
        },
    )
    return response.json()["child_id"]


def _open(client: TestClient, child_id: str, topic_id: str | None = None):
    body = {"topic_id": topic_id} if topic_id else {}
    return client.post(f"/conductor/{child_id}/open", json=body)


def test_a_level_named_by_adventure_is_the_one_conducted(client: TestClient):
    child_id = _child(client)
    directive = _open(client, child_id, TOPIC_ID)

    assert directive.status_code == 200, directive.text
    assert directive.json()["session_id"].startswith("class_")


def test_the_map_gets_the_listening_beat_the_lesson_page_never_had(client: TestClient):
    """Explain, explain, explain, then stop and open the microphone."""
    child_id = _child(client)
    directive = _open(client, child_id, TOPIC_ID).json()

    for _ in range(12):
        if directive["phase"] == "say_it":
            break
        assert directive["next_input"]["expects"] == "ready", directive["phase"]
        directive = client.post(
            f"/conductor/sessions/{directive['session_id']}/input", json={"kind": "ready"}
        ).json()
    else:  # pragma: no cover - the loop returns long before this
        pytest.fail("the class never stopped to listen")

    assert directive["phase"] == "say_it"
    assert directive["next_input"]["expects"] == "voice"
    assert directive["listen"]["active"] is True
    # The microphone is open on a teaching card, so there is no answer key beside it.
    assert directive["activity"]["correct_answer"] is None


def test_naming_a_topic_is_not_a_way_past_the_days_plan(client: TestClient, monkeypatch):
    """The gate is the same one `/learning` enforces, worded for a child."""
    child_id = _child(client)
    monkeypatch.setattr(
        plan_service,
        "may_open",
        lambda *args, **kwargs: plan_service.DayGate(
            allowed=False, reason="not_today", message="We saved that one for tomorrow!"
        ),
    )

    refused = _open(client, child_id, TOPIC_ID)

    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "NOT_TODAYS_PLAN"
    assert refused.json()["error"]["message"] == "We saved that one for tomorrow!"


def test_opening_with_no_topic_still_follows_the_plan(client: TestClient):
    """The child's own class is untouched: it picks the topic, as it always did."""
    child_id = _child(client)
    assert _open(client, child_id).status_code == 200


def test_what_the_child_says_changes_how_it_is_explained_next(client: TestClient):
    """The reason the microphone is here at all.

    An echo that does not land is not a wrong answer and is never scored - it is
    evidence that *this* explanation did not work. The class answers it by
    climbing a rung and asking the teaching policy again, and the policy will
    not spend a strategy this child has already had on this card. So the second
    explanation is a different one, chosen by the learned policy rather than by
    the child getting something wrong.
    """
    child_id = _child(client)
    directive = _open(client, child_id, TOPIC_ID).json()

    explaining = []
    for _ in range(12):
        if directive["phase"] == "say_it":
            break
        if directive["phase"] == "i_do":
            explaining.append(directive.get("teaching_strategy"))
        directive = client.post(
            f"/conductor/sessions/{directive['session_id']}/input", json={"kind": "ready"}
        ).json()

    assert directive["phase"] == "say_it"
    first_strategy = explaining[-1] if explaining else None

    # Something entirely unrelated came back. Not wrong - just not this.
    again = client.post(
        f"/conductor/sessions/{directive['session_id']}/input",
        json={"kind": "voice", "answer": "banana", "confidence": 0.9},
    ).json()

    assert again["phase"] == "i_do", "an echo that did not land re-explains"
    if first_strategy and again.get("teaching_strategy"):
        assert again["teaching_strategy"] != first_strategy

    # And it cost nothing: no star moved for saying the wrong thing out loud.
    stars = client.get(f"/progress/{child_id}/rewards").json()["stars"]
    assert stars == 0
