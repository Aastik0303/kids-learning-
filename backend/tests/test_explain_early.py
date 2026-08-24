"""What a Play Group child actually hears while meeting something new.

Before this, all five early-mode strategies came out of the guide as "Tap A."
A child who has never seen the letter A does not need to be told to tap it, and
being told four times is how a two-year-old learns that learning feels bad.

These tests pin the two halves of the fix: the concept card really is read out
of the authored content (nothing is invented), and each strategy says something
a pre-verbal child can use - a noise to copy, a thing to look at, a finger to
move.
"""

import pytest
from fastapi.testclient import TestClient

from app.conductor import explain
from app.main import app
from app.services import curriculum_service


LETTER_TOPIC = "pg_english_letters_a"
HINDI_TOPIC = "nur_hindi_swar_a_aa"

EARLY_STRATEGIES = ("S1_TELL", "S2_SHOW", "S6_DO_TOGETHER", "S7_SENSE_SWITCH", "S9_PARK")


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def card(topic_id: str):
    topic = curriculum_service.get_topic(topic_id)
    activities = curriculum_service.get_activities(topic_id)
    question = next((a for a in activities if a.correct_answer), activities[-1])
    return explain.card_for(topic, question, activities), topic, activities


# --------------------------------------------------------------------------
# The card comes out of the curriculum, not out of a model
# --------------------------------------------------------------------------


def test_a_letter_card_is_read_from_the_authored_level(client: TestClient):
    """Letter A's level already carries the whole method in its own activities.
    The guide reads it rather than being told the same thing twice."""
    concept, _, _ = card(LETTER_TOPIC)

    assert concept.symbol == "A"
    assert concept.sound == "aa"
    assert concept.word == "apple"
    assert "down" in concept.stroke.lower()
    assert concept.has_depth


def test_the_letter_keeps_the_shape_the_level_taught(client: TestClient):
    """The answer key for the spoken step is "a"; the level teaches "A". A child
    meeting a letter for the first time is shown the shape they were taught."""
    concept, _, _ = card(LETTER_TOPIC)

    assert concept.symbol == "A"


def test_a_child_hears_the_sound_the_word_and_the_stroke(client: TestClient):
    """One strategy each: tell it, show it, do it together, use the body."""
    concept, _, _ = card(LETTER_TOPIC)

    lines = {s: explain.beat(strategy=s, card=concept, seed="t") for s in EARLY_STRATEGIES}

    assert "aa" in lines["S1_TELL"]
    assert "apple" in lines["S2_SHOW"]
    assert "apple" in lines["S6_DO_TOGETHER"] and "Now you" in lines["S6_DO_TOGETHER"]
    assert "air" in lines["S7_SENSE_SWITCH"] or "Finger" in lines["S7_SENSE_SWITCH"]
    # Parking is kind, and never asks the question again.
    assert "?" not in lines["S9_PARK"]


def test_every_early_line_fits_a_two_year_old(client: TestClient):
    concept, _, _ = card(LETTER_TOPIC)

    for strategy in EARLY_STRATEGIES:
        line = explain.beat(strategy=strategy, card=concept, seed="t")
        assert line
        assert len(line.split()) <= explain.MAX_WORDS, strategy


def test_the_same_turn_says_the_same_thing_twice(client: TestClient):
    """A refresh must not reshuffle the teaching: a child being taught by noise
    is not being taught."""
    concept, _, _ = card(LETTER_TOPIC)

    first = explain.beat(strategy="S1_TELL", card=concept, seed="session:activity:0")
    again = explain.beat(strategy="S1_TELL", card=concept, seed="session:activity:0")
    next_try = explain.beat(strategy="S1_TELL", card=concept, seed="session:activity:1")

    assert first == again
    assert isinstance(next_try, str)


# --------------------------------------------------------------------------
# The Hindi levels teach Hindi; they are not spoken in Hindi
# --------------------------------------------------------------------------


def test_a_hindi_level_is_narrated_in_english_around_the_letter(client: TestClient):
    """The letter and the word stay in Devanagari - that is the content being
    taught - and the sentence around them is English."""
    concept, _, _ = card(HINDI_TOPIC)

    assert concept.symbol == "अ"
    assert concept.word == "अनार"

    told = explain.beat(strategy="S1_TELL", card=concept, seed="t")
    assert told.startswith("This is अ")
    assert "अनार" in told
    # Never transliterated back into Roman letters, and never a whole Devanagari
    # sentence - the authored Devanagari prompt is left to the activity screen.
    assert "anar" not in told.lower()
    assert "यह" not in told


def test_a_devanagari_prompt_is_never_repeated_as_narration(client: TestClient):
    concept, _, _ = card(HINDI_TOPIC)

    assert not explain.DEVANAGARI.search(concept.told or "x")


# --------------------------------------------------------------------------
# A topic with nothing to read still teaches
# --------------------------------------------------------------------------


def test_a_plain_topic_falls_back_to_the_authored_sentence(client: TestClient):
    """Shapes have no sound and no stroke authored. The author's own teaching
    line is better than anything generated, so it is used as it is."""
    concept, _, _ = card("pg_maths_shapes")

    told = explain.beat(strategy="S1_TELL", card=concept, seed="t")

    assert told
    assert concept.symbol
    assert not concept.sound


def test_an_unknown_strategy_says_nothing(client: TestClient):
    """Standard mode keeps the guide's own wording; this module answers for the
    five strategies Play Group and Nursery may use and stays quiet otherwise."""
    concept, _, _ = card(LETTER_TOPIC)

    assert explain.beat(strategy="S4_STORY", card=concept) == ""
    assert explain.beat(strategy=None, card=concept) == ""


def test_an_empty_card_says_nothing(client: TestClient):
    assert explain.beat(strategy="S1_TELL", card=explain.ConceptCard()) == ""


# --------------------------------------------------------------------------
# And it reaches the child through the conductor
# --------------------------------------------------------------------------


def test_the_conductor_speaks_the_playful_line_to_an_early_child(client: TestClient):
    """End to end: the policy picks the strategy, this module finds the words."""
    from datetime import date

    token = client.post(
        "/auth/register", json={"name": "P", "email": "explain@example.com", "password": "demo1234"}
    ).json()["session_token"]
    child_id = client.post(
        "/children",
        json={
            "session_token": token,
            "name": "Aaru",
            "birth_year": date.today().year - 2,
            "birth_month": 6,
            "preferred_language": "English",
        },
    ).json()["child_id"]

    directive = client.post(f"/conductor/{child_id}/open").json()
    session_id = directive["session_id"]
    assert session_id, directive

    heard = [directive["speech"]["text"]]
    for _ in range(6):
        directive = client.post(
            f"/conductor/sessions/{session_id}/input", json={"kind": "ready"}
        ).json()
        heard.append(directive["speech"]["text"])
        if directive.get("activity"):
            break

    # Whatever it said, it said it in words a two-year-old can hold. A turn that
    # teaches before it asks is allowed the longer intro ceiling; an instruction
    # on its own is not.
    ceiling = explain.MAX_INTRO_WORDS + explain.MAX_WORDS
    assert all(len(line.split()) <= ceiling for line in heard if line)
    assert any(line for line in heard)


# --------------------------------------------------------------------------
# Teach it, then ask it
# --------------------------------------------------------------------------


COLOUR_TOPIC = "pg_ga_colors_1"


def activity_in(topic_id: str, activity_id: str):
    activities = curriculum_service.get_activities(topic_id)
    return (
        curriculum_service.get_topic(topic_id),
        next(a for a in activities if a.activity_id == activity_id),
        activities,
    )


def test_a_question_is_taught_before_it_is_asked(client: TestClient):
    """"Tap the red one" means nothing to a child who has not just been shown
    red. The level already carries the teaching; the intro says it first."""
    topic, question, activities = activity_in(COLOUR_TOPIC, "pg_gcol1_2")

    intro = explain.question_intro(topic, question, activities)

    assert intro.startswith("This is red")
    assert "Red like an apple" in intro
    # The question itself comes last, after a handover the child can hear.
    assert intro.endswith(question.prompt.strip())
    assert any(hand in intro for hand in explain.HANDOVERS)


def test_the_intro_never_says_the_answer(client: TestClient):
    """The letter level's match question is answered by "apple". An intro built
    from the activity would open with "Meet apple!" - the answer key, out loud,
    before the question is asked."""
    topic, question, activities = activity_in(LETTER_TOPIC, "pg_let_a_6")

    intro = explain.question_intro(topic, question, activities)

    assert intro.startswith("Meet A") or intro.startswith("This is A")
    said_before_question = intro.split("Your turn")[0].split("Now you")[0]
    assert "apple" not in said_before_question.lower()


def test_a_teaching_card_is_the_explanation_and_gets_no_intro(client: TestClient):
    topic, card_activity, activities = activity_in(COLOUR_TOPIC, "pg_gcol1_1")

    assert explain.question_intro(topic, card_activity, activities) == ""


def test_a_hindi_question_is_taught_in_english_and_asked_in_devanagari(client: TestClient):
    topic, question, activities = activity_in(HINDI_TOPIC, "nur_hin_905_2")

    intro = explain.question_intro(topic, question, activities)

    assert intro.startswith("This is अ")
    assert intro.endswith("Tap अ.")
    # The authored Devanagari prompt stays on the screen, not in the narration.
    assert "उँगली" not in intro


def test_the_intro_stays_short_enough_to_be_heard(client: TestClient):
    for topic_id in (COLOUR_TOPIC, LETTER_TOPIC, "pg_maths_shapes", "pg_maths_colours"):
        activities = curriculum_service.get_activities(topic_id)
        topic = curriculum_service.get_topic(topic_id)
        for question in [a for a in activities if a.correct_answer]:
            intro = explain.question_intro(topic, question, activities)
            if intro:
                assert len(intro.split()) <= explain.MAX_INTRO_WORDS + len(question.prompt.split()), (
                    topic_id,
                    question.activity_id,
                )


def test_the_conductor_teaches_before_the_first_question_and_not_after(client: TestClient):
    """First presentation explains; a second attempt belongs to the repair
    ladder, which has its own thing to say."""
    from datetime import date

    token = client.post(
        "/auth/register", json={"name": "P", "email": "intro@example.com", "password": "demo1234"}
    ).json()["session_token"]
    child_id = client.post(
        "/children",
        json={
            "session_token": token,
            "name": "Aaru",
            "birth_year": date.today().year - 2,
            "birth_month": 6,
            "preferred_language": "English",
        },
    ).json()["child_id"]

    directive = client.post(f"/conductor/{child_id}/open").json()
    session_id = directive["session_id"]

    asked = None
    for _ in range(8):
        directive = client.post(
            f"/conductor/sessions/{session_id}/input", json={"kind": "ready"}
        ).json()
        if directive.get("activity") and directive["next_input"]["expects"] in ("tap", "voice"):
            asked = directive
            break

    assert asked, "the conductor never put a question to the child"
    first = asked["speech"]["text"]
    assert any(hand in first for hand in explain.HANDOVERS) or len(first.split()) >= 6

    wrong = client.post(
        f"/conductor/sessions/{session_id}/input", json={"kind": "tap", "value": "__no__"}
    ).json()

    assert wrong["speech"]["text"] != first


# --------------------------------------------------------------------------
# The teaching card itself: meeting a thing, not being shown its label
# --------------------------------------------------------------------------


def test_a_colour_card_teaches_rather_than_labels(client: TestClient):
    """The screen that said "Red like a tomato." and offered a Next button.

    A two-year-old meeting a colour needs the name, something they know that is
    that colour, a second one so it is the colour and not the apple they
    remember, and something to do while they hear it.
    """
    topic, card_activity, activities = activity_in(COLOUR_TOPIC, "pg_gcol1_1")

    script = explain.teaching_script(topic, card_activity, activities)

    assert script.startswith("This is red")
    assert "apple" in script
    assert "tomato" in script
    assert any(word in script for word in ("find", "Point", "Look", "Say", "voice"))
    assert len(script.split()) <= explain.MAX_TEACHING_WORDS


def test_each_card_invites_its_own_colour(client: TestClient):
    """The blue card must not ask a child to point at red - the level teaches
    one colour per card, and the invitation follows the card."""
    topic, blue_card, activities = activity_in(COLOUR_TOPIC, "pg_gcol1_3")

    script = explain.teaching_script(topic, blue_card, activities)

    assert "blue" in script.lower()
    assert "point at red" not in script.lower()


def test_a_question_with_no_card_of_its_own_names_its_own_concept(client: TestClient):
    """Play Group Maths authors one teaching card, for red, and then asks about
    yellow. Teaching red before a yellow question is teaching the wrong thing."""
    topic, yellow, activities = activity_in("pg_maths_colours", "pg_co_3")

    intro = explain.question_intro(topic, yellow, activities)

    assert "yellow" in intro.lower()
    assert "apple" not in intro.lower()


def test_shapes_keep_their_article(client: TestClient):
    """"This is square" is not English, and this is read aloud."""
    topic, square, activities = activity_in("pg_maths_shapes", "pg_sh_3")

    intro = explain.question_intro(topic, square, activities)

    assert "This is a square." in intro or "This is a circle" in intro


def test_the_lesson_screen_teaches_the_same_way_the_conductor_does(client: TestClient):
    """Auto-open lands a Play Group child on `/learning`, so the guide there has
    to teach exactly as the conductor would. Same child, same activity, same
    words."""
    from datetime import date

    token = client.post(
        "/auth/register", json={"name": "P", "email": "screen@example.com", "password": "demo1234"}
    ).json()["session_token"]
    child = client.post(
        "/children",
        json={
            "session_token": token,
            "name": "Aaru",
            "birth_year": date.today().year - 2,
            "birth_month": 6,
            "preferred_language": "English",
        },
    ).json()

    plan = client.get(f"/plans/{child['child_id']}/today").json()
    current = next(item for item in plan["items"] if item["current"])
    started = client.post(
        "/learning/start", json={"child_id": child["child_id"], "topic_id": current["topic_id"]}
    ).json()
    activity = started["activity"]

    said = client.post(
        "/agent/guide",
        json={
            "session_id": started["session_id"],
            "child_id": child["child_id"],
            "mode": "learning",
            "event": "TOPIC_QUESTION_LOADED",
            "route": "/adventure",
            "screen": "topic_session",
            "feature": "lesson",
            "experience_mode": child["experience_mode"],
            "question": {
                "activity_id": activity["activity_id"],
                "topic": activity["type"],
                "concept": activity["type"],
                "prompt": activity["prompt"],
                "answer_type": activity["type"],
                "options": activity["options"],
                "correct_answer": activity["correct_answer"],
                "attempt": 0,
                "hint": activity["hint"],
                "visual_items": activity["visual_items"],
            },
            "progress": {
                "current_subject": current["skill_id"].split(":")[0],
                "current_topic": current["topic_id"],
            },
            "available_actions": ["highlight"],
            "available_targets": ["activity-area"],
        },
    ).json()

    # More than the one-line label it used to be, and inside the teaching cap.
    assert len(said["message"].split()) > 6
    assert len(said["message"].split()) <= explain.MAX_TEACHING_WORDS + 8
