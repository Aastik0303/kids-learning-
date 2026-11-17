"""Every fifth day, one subject's level steps aside and a poem takes its place.

The user asked for it in one sentence: a poem every five days, replacing any one
subject, and the day staying the length it was - "agr schedule me 5 sub hai to
poem ke baad 5 rhe". These tests pin all three of those, and the fourth thing
that matters most: a poem is **not a level**, so nothing about it may reach a
star, an unlock, the attempt log or the learned policy.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Attempt, PolicyEpisode
from app.db.session import session_scope
from app.main import app
from app.playground import poem


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def make_child(client: TestClient, email: str = "poem@example.com", years: int = 4) -> str:
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


# --------------------------------------------------------------------------
# When a poem comes, and what it costs the day
# --------------------------------------------------------------------------


def test_a_poem_comes_round_every_fifth_day():
    """One day in five, counted off the calendar so two reads always agree."""
    start = date(2026, 1, 1)
    days = [start + timedelta(days=offset) for offset in range(20)]
    poem_days = [day for day in days if poem.is_poem_day(day)]

    assert len(poem_days) == 4, "twenty days is four poem days"
    gaps = {
        (later - earlier).days for earlier, later in zip(poem_days, poem_days[1:])
    }
    assert gaps == {poem.EVERY_DAYS}


def test_the_poems_come_round_in_order_and_then_begin_again():
    """A child meets each poem before meeting any of them twice.

    Meeting one twice is the point rather than a failure: the second time is the
    time they can say it along with the teacher.
    """
    start = date(2026, 1, 1)
    seen = []
    day = start
    while len(seen) < len(poem.POEMS) + 2:
        if poem.is_poem_day(day):
            seen.append(poem.for_day(day).poem_id)
        day += timedelta(days=1)

    first_round = seen[: len(poem.POEMS)]
    assert len(set(first_round)) == len(poem.POEMS), "each one before any repeat"
    assert seen[len(poem.POEMS)] == first_round[0], "then it begins again"


def test_a_poem_replaces_a_subject_and_the_day_stays_the_same_length(
    client: TestClient, next_day
):
    """The whole of what was asked for, in one test.

    A poem does not lengthen the day and does not shorten it. The class teaches
    one stage per planned item, so an item added is a longer sitting for a
    three-year-old and an item removed is a subject with nothing in its place.
    """
    child_id = make_child(client)

    next_day.ordinary()
    ordinary = client.get(f"/plans/{child_id}/today").json()["items"]
    assert not any(item["reason"] == "poem" for item in ordinary)

    next_day.on_a_poem_day()
    poem_day = client.get(f"/plans/{child_id}/today").json()["items"]

    assert len(poem_day) == len(ordinary), "the day is the length it was"
    poems = [item for item in poem_day if item["reason"] == "poem"]
    assert len(poems) == 1, "exactly one, and it replaced a level rather than joining it"
    assert poem.is_poem(poems[0]["topic_id"])
    # The title a parent reads on the schedule strip, not the raw id: a poem is
    # deliberately not in the manifest, so the ordinary lookup cannot find it.
    assert poems[0]["title"] == poem.get(poems[0]["topic_id"]).title


def test_the_level_that_stepped_aside_is_back_the_next_day(client: TestClient, next_day):
    """Nothing is lost to a poem. The level was that subject's first weak or
    unfinished topic and it still is tomorrow, so it returns on its own."""
    child_id = make_child(client, "poem-returns@example.com")

    next_day.ordinary()
    before = {item["topic_id"] for item in client.get(f"/plans/{child_id}/today").json()["items"]}

    next_day.on_a_poem_day()
    on_the_day = {
        item["topic_id"] for item in client.get(f"/plans/{child_id}/today").json()["items"]
    }
    missing = before - on_the_day
    assert len(missing) == 1, "exactly one level stepped aside"

    next_day.ordinary()
    after = {item["topic_id"] for item in client.get(f"/plans/{child_id}/today").json()["items"]}
    assert missing <= after, "and it is back the next morning"


def test_the_poem_is_the_last_stage_of_the_day(client: TestClient, next_day):
    """A poem is the one stage where nothing can go wrong, so the sitting ends
    on it - "finish on a win", more surely than any level manages."""
    child_id = make_child(client, "poem-last@example.com")

    next_day.on_a_poem_day()
    items = client.get(f"/plans/{child_id}/today").json()["items"]

    assert len(items) > 1
    assert items[-1]["reason"] == "poem"


# --------------------------------------------------------------------------
# What the class does with one
# --------------------------------------------------------------------------


def _open_on_the_poem(client: TestClient, child_id: str) -> dict:
    """Play the day through until the class reaches its poem stage."""
    turn = client.post(f"/playground/teacher/{child_id}/open").json()
    for _ in range(400):
        if turn.get("is_poem"):
            return turn
        if turn.get("day_complete"):
            raise AssertionError("the day finished without ever reaching the poem")
        answer = "ready"
        if turn.get("options"):
            answer = turn["options"][0]
        turn = client.post(
            f"/playground/teacher/sessions/{turn['session_id']}/answer",
            json={"answer": answer},
        ).json()
    raise AssertionError("never reached the poem")


def test_the_class_says_the_poem_one_verse_at_a_time(client: TestClient, next_day):
    """A poem stage is said, not taught: a line on the card, a verse out loud,
    a picture when the verse names one, and nothing to answer."""
    child_id = make_child(client, "poem-class@example.com")
    next_day.on_a_poem_day()

    turn = _open_on_the_poem(client, child_id)
    said = poem.get(turn["topic_id"])

    assert turn["step"] == "poem"
    assert turn["expects"] == "ready", "there is nothing here to get wrong"
    assert not turn["options"]
    assert turn["strategy"] == "", "no strategy was spent on a poem"
    assert turn["questions_per_stage"] == len(said.parts)

    heard = [turn["speech"]]
    for _ in range(len(said.parts) - 1):
        turn = client.post(
            f"/playground/teacher/sessions/{turn['session_id']}/answer",
            json={"answer": "ready"},
        ).json()
        heard.append(turn["speech"])

    assert heard == [part.speech for part in said.parts], "in order, word for word"


def test_asking_something_in_the_middle_of_a_poem_keeps_the_verse(client: TestClient, next_day):
    """The child's own question is answered and the same verse comes back. It
    used to come back as an ordinary lesson turn, with the verse gone from the
    card and `is_poem` false."""
    child_id = make_child(client, "poem-ask@example.com")
    next_day.on_a_poem_day()

    turn = _open_on_the_poem(client, child_id)
    asked = client.post(
        f"/playground/teacher/sessions/{turn['session_id']}/ask",
        json={"question": "why is the moon round?"},
    ).json()

    assert asked["is_poem"] is True
    assert asked["step"] == "poem"
    assert asked["question"] == turn["question"], "the same verse is still on the card"
    assert asked["questions_asked"] == turn["questions_asked"], "asking moves nothing"

    reread = client.get(f"/playground/teacher/sessions/{turn['session_id']}").json()
    assert reread["is_poem"] is True
    assert reread["question"] == turn["question"]


def test_a_poem_pays_no_star_and_writes_no_attempt(client: TestClient, next_day):
    """A poem is not a level, and its topic id is deliberately not in the
    manifest so that every rule which reads the manifest already does the right
    thing with it. This is that promise, checked from the database."""
    child_id = make_child(client, "poem-pays@example.com")
    next_day.on_a_poem_day()

    turn = _open_on_the_poem(client, child_id)
    said = poem.get(turn["topic_id"])

    with session_scope() as session:
        before = len(session.scalars(select(Attempt)).all())
        episodes_before = len(session.scalars(select(PolicyEpisode)).all())

    for _ in range(len(said.parts)):
        turn = client.post(
            f"/playground/teacher/sessions/{turn['session_id']}/answer",
            json={"answer": "ready"},
        ).json()
        assert turn.get("stars_earned", 0) == 0
        assert turn.get("topic_completed") is not True
        assert turn.get("next_topic_unlocked") is not True

    with session_scope() as session:
        attempts = session.scalars(select(Attempt)).all()
        episodes = session.scalars(select(PolicyEpisode)).all()

    assert len(attempts) == before, "nothing about a poem is an attempt"
    assert len(episodes) == episodes_before, "and nothing about it is a teaching episode"


def test_the_poem_finishes_the_day_rather_than_stalling_it(client: TestClient, next_day):
    """A poem is a stage of the schedule, so it has to be able to end.

    It moves the plan cursor and nothing else. A stage that never finishes is a
    day that never finishes, and the class would reopen on it for ever.
    """
    child_id = make_child(client, "poem-finishes@example.com")
    next_day.on_a_poem_day()

    turn = _open_on_the_poem(client, child_id)
    said = poem.get(turn["topic_id"])
    for _ in range(len(said.parts)):
        turn = client.post(
            f"/playground/teacher/sessions/{turn['session_id']}/answer",
            json={"answer": "ready"},
        ).json()

    assert turn["day_complete"] is True, "the poem is the last stage, so this ends the day"
    plan = client.get(f"/plans/{child_id}/today").json()
    assert plan["complete"] is True


# --------------------------------------------------------------------------
# The class that cannot say one
# --------------------------------------------------------------------------


def test_the_conductor_steps_over_the_poem_rather_than_breaking_on_it(
    client: TestClient, next_day
):
    """The mobile app's loop has no way to say a poem, and must not 404 on one.

    This is what it did. `/conductor/{child}/open` teaches whatever today's plan
    is pointing at, and it looks the topic up in the manifest - which is the one
    place a poem is deliberately not. So on a poem morning, once the day's
    levels were done and the cursor came to rest on the poem, every open
    answered `MISSING_CURRICULUM`; and because nothing in that loop can finish a
    poem, the cursor stayed there and the day could not end either.
    """
    child_id = make_child(client, "poem-conductor@example.com")
    next_day.on_a_poem_day()
    _open_on_the_poem(client, child_id)

    plan = client.get(f"/plans/{child_id}/today").json()
    assert poem.is_poem(plan["current_topic_id"]), "the day should be resting on its poem"

    directive = client.post(f"/conductor/{child_id}/open")

    assert directive.status_code == 200, directive.text
    body = directive.json()
    # Everything this loop can teach is behind the poem, so the day is over for
    # it - warmly, and in words a child hears rather than an error.
    assert body["phase"] == "close"
    assert body["close"]["reason"] == "day_complete"
    assert "tomorrow" in body["speech"]["text"].lower()


def test_the_poem_is_still_there_for_the_class_that_can_say_it(
    client: TestClient, next_day
):
    """Stepping over a poem is not finishing it. The web class still says it."""
    child_id = make_child(client, "poem-still-there@example.com")
    next_day.on_a_poem_day()
    _open_on_the_poem(client, child_id)
    client.post(f"/conductor/{child_id}/open")

    plan = client.get(f"/plans/{child_id}/today").json()
    poem_item = next(item for item in plan["items"] if poem.is_poem(item["topic_id"]))

    assert poem_item["done"] is False
    assert plan["complete"] is False
    # And it is named by its title rather than by `poem_moon`, on the strip a
    # grown-up reads.
    assert poem_item["title"] == poem.title_of(poem_item["topic_id"])
    assert client.post(f"/playground/teacher/{child_id}/open").json().get("is_poem") is True


# --------------------------------------------------------------------------
# The poems themselves
# --------------------------------------------------------------------------


def test_every_poem_is_written_out_in_full_and_draws_only_what_exists():
    """No model wrote any of this, and no verse names a picture the app cannot
    draw - the same rule `visualIcon` keeps for अनार: nothing, rather than a
    near-miss."""
    from app.playground import visuals

    assert poem.POEMS, "the feature is the poems"
    for one in poem.POEMS:
        assert one.title.strip()
        assert len(one.parts) >= 3, one.poem_id
        for part in one.parts:
            assert part.line.strip(), one.poem_id
            assert part.speech.strip(), one.poem_id
            if part.picture:
                assert part.picture in visuals.THINGS, f"{one.poem_id}: {part.picture}"
                assert part.visual.is_shown


def test_the_user_asked_for_these_subjects():
    """AI, the phone, and the apple were named directly."""
    asked = {"ai", "mobile", "apple"}
    assert asked <= {one.poem_id for one in poem.POEMS}
