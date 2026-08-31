"""The day's plan is the day's work.

Unlocking and scheduling used to be the same thing: finish a level, the next one
unlocks, and a child could run through a whole subject in one sitting. They are
separate now. Finishing a level still unlocks the next one - that is what the
lesson earns - but *when* it is played is the plan's to decide, and the plan
holds one level per subject per day.

That is the rule these tests pin, from both ends: what the schedule opens, and
what it holds back until tomorrow.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import child_service, child_store, curriculum_service, plan_service


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def make_child(client: TestClient, email: str = "schedule@example.com", years: int = 3) -> str:
    token = client.post(
        "/auth/register", json={"name": "Parent", "email": email, "password": "demo1234"}
    ).json()["session_token"]
    return client.post(
        "/children",
        json={
            "session_token": token,
            "name": "Aaru",
            "birth_year": date.today().year - years,
            "birth_month": 6,
            "preferred_language": "English",
        },
    ).json()["child_id"]


def plan_of(client: TestClient, child_id: str) -> dict:
    return client.get(f"/plans/{child_id}/today").json()


def play(client: TestClient, child_id: str, topic_id: str) -> dict:
    """Play one topic to the end, answering everything correctly."""
    started = client.post("/learning/start", json={"child_id": child_id, "topic_id": topic_id}).json()
    assert "session_id" in started, started
    activity, response = started["activity"], started
    while activity is not None:
        answer = "done" if activity["answer_kind"] == "presentational" else activity["correct_answer"]
        response = client.post(
            "/learning/answer", json={"session_id": started["session_id"], "answer": answer}
        ).json()
        activity = response.get("activity")
    return response


# --------------------------------------------------------------------------
# What the day opens, and what it holds back
# --------------------------------------------------------------------------


def test_a_planned_topic_opens(client: TestClient):
    child_id = make_child(client)
    planned = plan_of(client, child_id)["items"][0]["topic_id"]

    started = client.post("/learning/start", json={"child_id": child_id, "topic_id": planned})

    assert started.status_code == 200


def test_the_level_a_lesson_unlocks_waits_for_its_day(client: TestClient, next_day):
    """The whole point of a schedule, in one test."""
    child_id = make_child(client)
    first = plan_of(client, child_id)["items"][0]["topic_id"]

    finished = play(client, child_id, first)
    unlocked = finished["next_topic_id"]
    assert finished["next_topic_unlocked"] is True

    same_day = client.post("/learning/start", json={"child_id": child_id, "topic_id": unlocked})
    assert same_day.status_code == 403
    assert same_day.json()["error"]["code"] == "NOT_TODAYS_PLAN"
    # Kind, and never a punishment: no "locked", no "no".
    message = same_day.json()["error"]["message"].lower()
    assert "tomorrow" in message
    assert "lock" not in message

    next_day.until_planned(client, child_id, unlocked)
    assert client.post("/learning/start", json={"child_id": child_id, "topic_id": unlocked}).status_code == 200


def test_a_finished_level_can_be_played_again_any_day(client: TestClient):
    """Going back over something already done is not racing ahead, and a
    favourite lesson being refused would be a strange thing to explain."""
    child_id = make_child(client)
    first = plan_of(client, child_id)["items"][0]["topic_id"]
    play(client, child_id, first)

    again = client.post("/learning/start", json={"child_id": child_id, "topic_id": first})

    assert again.status_code == 200


def test_the_day_reports_itself_finished(client: TestClient):
    child_id = make_child(client)
    for item in plan_of(client, child_id)["items"]:
        play(client, child_id, item["topic_id"])

    plan = plan_of(client, child_id)

    assert plan["complete"] is True
    assert plan["current_topic_id"] is None
    assert plan["completed"] == plan["total"]


def test_a_finished_day_closes_the_class_instead_of_opening_the_next_level(client: TestClient):
    """The conductor must not fall through to "the next unlocked topic" once the
    day is done - that would walk straight past the schedule it just followed."""
    child_id = make_child(client)
    for item in plan_of(client, child_id)["items"]:
        play(client, child_id, item["topic_id"])

    directive = client.post(f"/conductor/{child_id}/open").json()

    assert directive["phase"] == "close"
    assert directive["close"]["reason"] == "day_complete"
    assert "tomorrow" in directive["speech"]["text"].lower()


def test_a_new_day_brings_new_work(client: TestClient, next_day):
    child_id = make_child(client)
    today = plan_of(client, child_id)
    for item in today["items"]:
        play(client, child_id, item["topic_id"])

    next_day()
    tomorrow = plan_of(client, child_id)

    assert tomorrow["plan_date"] != today["plan_date"]
    assert tomorrow["complete"] is False
    assert [item["topic_id"] for item in tomorrow["items"]] != [item["topic_id"] for item in today["items"]]


# --------------------------------------------------------------------------
# The plan itself
# --------------------------------------------------------------------------


def test_a_day_holds_one_level_per_subject(client: TestClient):
    """Two levels of one subject in a day would let a child finish the first and
    walk into the second, which is the thing the day exists to hold back."""
    child_id = make_child(client)

    items = plan_of(client, child_id)["items"]

    subjects = [item["skill_id"].split(":")[0] for item in items]
    assert len(subjects) == len(set(subjects))


def test_two_shaky_levels_in_one_subject_still_cost_the_day_one_slot(client: TestClient):
    """A subject gets one turn a day however many of its levels are shaky.

    This is the case that broke it. Weak topics used to be collected across the
    whole class and put in front of the fresh ones, so a child with two wobbly
    English levels got a day of English, English, Maths - and General Awareness
    never came up at all. The class runs one stage per planned item, so that day
    is a class that spends two of its three stages on the same subject.
    """
    child_id = make_child(client, "schedule-weak@example.com")
    child = child_store.get(child_id)

    subject_id = client.get(f"/curriculum/children/{child_id}/class").json()["subjects"][0][
        "subject_id"
    ]
    unlocked = child["subject_progress"][subject_id]["unlocked_topics"]
    # Two levels of one subject, both marked weak, both unlocked.
    for topic_id in unlocked[:1]:
        child["weak_skills"].append(f"{subject_id}:{topic_id}")
    subject = curriculum_service.get_subject(subject_id)
    for topic in subject.topics[:3]:
        if topic.available and topic.topic_id not in unlocked:
            unlocked.append(topic.topic_id)
            child["weak_skills"].append(f"{subject_id}:{topic.topic_id}")
    child_store.save(child)

    items = plan_of(client, child_id)["items"]

    subjects = [item["skill_id"].split(":")[0] for item in items]
    assert len(subjects) == len(set(subjects)), subjects
    assert subjects.count(subject_id) <= 1


def test_every_subject_is_in_every_day(client: TestClient):
    """A day is one level from each of the child's subjects, and all of them.

    It used to be three, with the subjects rotating by the day number so that
    none was starved. That is what the rotation was *for*, and it meant a
    Nursery child met Hindi every other day and EVS every third - a subject
    could go most of a week without being taught while its levels sat unlocked
    on the Adventure map. The cap is gone and so is the rotation.
    """
    child_id = make_child(client)
    subjects = client.get(f"/curriculum/children/{child_id}/class").json()["subjects"]
    teachable = {subject["subject_id"] for subject in subjects if subject.get("topics")}

    planned = {
        item["skill_id"].split(":")[0] for item in plan_of(client, child_id)["items"]
    }

    assert teachable, "the shipped class has no subjects"
    assert planned == teachable, sorted(teachable - planned)


def test_the_day_is_the_same_shape_tomorrow(client: TestClient, next_day):
    """No rotation means no surprise: the subjects are the same every morning."""
    child_id = make_child(client)

    today = {item["skill_id"].split(":")[0] for item in plan_of(client, child_id)["items"]}
    next_day()
    tomorrow = {item["skill_id"].split(":")[0] for item in plan_of(client, child_id)["items"]}

    assert today == tomorrow


def test_a_child_with_nothing_planned_is_never_locked_out(client: TestClient, monkeypatch):
    """The gate opens when there is no plan to read. A database that cannot
    answer must not cost a child their lesson."""
    child_id = make_child(client)
    child = child_service.get_child(child_id)
    planned = plan_of(client, child_id)["items"][0]["topic_id"]

    monkeypatch.setattr(plan_service, "todays_plan", lambda *args, **kwargs: None)

    gate = plan_service.may_open(child, planned)
    assert gate.allowed is True
    assert gate.reason == "no_plan"
    assert client.post("/learning/start", json={"child_id": child_id, "topic_id": planned}).status_code == 200


def test_the_plan_does_not_change_when_it_is_read_twice(client: TestClient):
    child_id = make_child(client)

    first = plan_of(client, child_id)
    second = plan_of(client, child_id)

    assert [item["topic_id"] for item in first["items"]] == [item["topic_id"] for item in second["items"]]
    assert first["plan_date"] == second["plan_date"]


def test_the_gate_speaks_differently_once_the_day_is_done(client: TestClient):
    child_id = make_child(client)
    items = plan_of(client, child_id)["items"]
    for item in items:
        play(client, child_id, item["topic_id"])

    child = child_service.get_child(child_id)
    gate = plan_service.may_open(child, "nur_maths_count_123")

    assert gate.allowed is False
    assert gate.message == plan_service.DAY_DONE_MESSAGE


def test_yesterdays_plan_is_kept(client: TestClient, next_day):
    """A plan is a record of the day, not a scratchpad: the parent digest reads
    the week back."""
    child_id = make_child(client)
    plan_of(client, child_id)
    next_day()
    plan_of(client, child_id)

    history = client.get(f"/plans/{child_id}/history?days=7").json()

    assert len(history["plans"]) == 2
    assert history["plans"][0]["plan_date"] != history["plans"][1]["plan_date"]


# --------------------------------------------------------------------------
# Auto-open: who the app opens itself for
# --------------------------------------------------------------------------


def test_the_day_opens_itself_for_the_youngest_children(client: TestClient):
    """A two-year-old cannot open their own lesson, and every tap between them
    and it is a place the day ends early."""
    child_id = make_child(client, "early@example.com", years=2)

    plan = plan_of(client, child_id)

    assert plan["autopilot"] is True
    assert plan["current_topic_id"]


def test_an_older_child_still_chooses(client: TestClient):
    """From LKG the child can navigate, and taking that away would be worse than
    the taps."""
    child_id = make_child(client, "older@example.com", years=5)

    assert plan_of(client, child_id)["autopilot"] is False


def test_a_finished_day_does_not_open_anything(client: TestClient):
    child_id = make_child(client, "donefortoday@example.com", years=2)
    for item in plan_of(client, child_id)["items"]:
        play(client, child_id, item["topic_id"])

    plan = plan_of(client, child_id)

    assert plan["complete"] is True
    assert plan["autopilot"] is False


def test_a_day_of_revisits_is_not_born_finished(client: TestClient, next_day):
    """A level the child has already passed, planned again because it went badly.

    This is the case that locked children out. The plan's cursor used to be read
    off the child's lifetime `completed_topics`, and a `revisit` item is in that
    list from the moment it is frozen - that is what makes it a revisit. So the
    whole day arrived ticked: no current topic, `is_day_complete` true, and the
    AI Teacher wrote `day_complete` and refused to open a class that had taught
    nothing. The plan carries its own cursor now.
    """
    child_id = make_child(client, "schedule-revisit@example.com")

    plan = plan_of(client, child_id)
    played = plan["items"][0]
    play(client, child_id, played["topic_id"])

    # It passed, so it is completed - and then it went shaky, so tomorrow plans
    # it again as a revisit.
    child = child_store.get(child_id)
    child["weak_skills"].append(played["skill_id"])
    child_store.save(child)

    # The subjects take turns, so "tomorrow" is really "the day the rotation
    # comes back round to this subject".
    next_day()
    tomorrow = next_day.until_planned(client, child_id, played["topic_id"])
    revisits = [item for item in tomorrow["items"] if item["topic_id"] == played["topic_id"]]
    assert revisits, tomorrow["items"]
    assert revisits[0]["reason"] == "revisit"
    assert revisits[0]["done"] is False
    assert tomorrow["current_topic_id"] is not None

    profile = child_service.get_child(child_id)
    assert plan_service.is_day_complete(profile) is False


def test_playing_a_revisit_ticks_it_off_the_day(client: TestClient, next_day):
    """And it does finish, once the child has actually played it again."""
    child_id = make_child(client, "schedule-revisit-done@example.com")

    played = plan_of(client, child_id)["items"][0]
    play(client, child_id, played["topic_id"])
    child = child_store.get(child_id)
    child["weak_skills"].append(played["skill_id"])
    child_store.save(child)

    next_day()
    next_day.until_planned(client, child_id, played["topic_id"])
    play(client, child_id, played["topic_id"])

    after = plan_of(client, child_id)
    done = [item for item in after["items"] if item["topic_id"] == played["topic_id"]]
    assert done and done[0]["done"] is True
    assert after["current_topic_id"] != played["topic_id"]
