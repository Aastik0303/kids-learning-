"""The authored activity content, exercised against the shipped manifest.

All four classes have real activities. These tests guard the things that
only appear once content exists: the class-level file layout, the activity kinds
that are not tap-a-choice, deliberately removed subjects, and a topic played
from start to finish.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import activity_evaluators, curriculum_service
from app.services.learning_service import LESSON_LENGTH
from app.services.mock_storage import mock_child_profiles


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_curriculum():
    curriculum_service.reload_curriculum()
    yield
    curriculum_service.reload_curriculum()


def make_nursery_child(client: TestClient, email: str):
    auth = client.post("/auth/register", json={"name": "P", "email": email, "password": "demo1234"})
    if auth.status_code != 200:
        auth = client.post("/auth/login", json={"email": email, "password": "demo1234"})
    token = auth.json()["session_token"]
    child = client.post(
        "/children",
        json={
            "session_token": token,
            "name": "Ana",
            "birth_year": date.today().year - 3,
            "birth_month": date.today().month,
            "preferred_language": "English",
        },
    ).json()
    assert child["class_id"] == "nursery"
    return token, child["child_id"]


def play_topic(client: TestClient, child_id: str, topic_id: str) -> None:
    """Play a topic to the end, so the one after it opens."""
    started = client.post(
        "/learning/start", json={"child_id": child_id, "topic_id": topic_id}
    ).json()
    assert "session_id" in started, started
    activity = started["activity"]
    while activity is not None:
        answer = (
            "done"
            if activity["answer_kind"] == "presentational"
            else (activity["correct_answer"] or "spoken")
        )
        response = client.post(
            "/learning/answer", json={"session_id": started["session_id"], "answer": answer}
        ).json()
        activity = response.get("activity")


def make_lkg_child(client: TestClient, email: str):
    auth = client.post("/auth/register", json={"name": "P", "email": email, "password": "demo1234"})
    if auth.status_code != 200:
        auth = client.post("/auth/login", json={"email": email, "password": "demo1234"})
    token = auth.json()["session_token"]
    child = client.post(
        "/children",
        json={
            "session_token": token,
            "name": "Ishan",
            "birth_year": date.today().year - 4,
            "birth_month": date.today().month,
            "preferred_language": "English",
        },
    ).json()
    assert child["class_id"] == "lkg"
    return token, child["child_id"]


def make_play_group_child(client: TestClient, email: str):
    auth = client.post("/auth/register", json={"name": "P", "email": email, "password": "demo1234"})
    if auth.status_code != 200:
        auth = client.post("/auth/login", json={"email": email, "password": "demo1234"})
    token = auth.json()["session_token"]
    child = client.post(
        "/children",
        json={
            "session_token": token,
            "name": "Mira",
            "birth_year": date.today().year - 2,
            "birth_month": date.today().month,
            "preferred_language": "English",
        },
    ).json()
    assert child["class_id"] == "playgroup"
    return token, child["child_id"]


# --------------------------------------------------------------------------
# the content loads
# --------------------------------------------------------------------------


AUTHORED_CLASSES = {"playgroup": 182, "nursery": 503, "lkg": 98, "ukg": 118}

HINDI_SWAR = ["अ", "आ", "इ", "ई", "उ", "ऊ", "ए", "ऐ", "ओ", "औ", "अं", "अः"]
HINDI_VYANJAN = ["क", "ख", "ग", "घ", "ङ"]


@pytest.mark.parametrize("class_id,expected", sorted(AUTHORED_CLASSES.items()))
def test_every_subject_of_an_authored_class_is_playable(client, class_id, expected):
    detail = client.get(f"/curriculum/classes/{class_id}").json()
    for subject in detail["subjects"]:
        assert subject["available"] is True, f"{subject['subject_id']} has no activities"
    assert detail["activity_count"] == expected


def test_play_group_content_uses_the_requested_subjects(client: TestClient):
    """Play Group ships English, Early Mathematics and General Awareness only."""
    detail = client.get("/curriculum/classes/playgroup").json()
    assert [subject["subject_id"] for subject in detail["subjects"]] == [
        "pg_english", "pg_maths", "pg_ga"
    ]
    assert detail["activity_count"] == 182


def test_general_awareness_teaches_three_things_a_level(client: TestClient):
    """Every General Awareness level meets its things one at a time.

    A level introduces each of its three or four items and then asks for that
    same item, and carries extra question variants on top so the adventure and
    Practice do not repeat each other. The teaching cards stay under
    LESSON_LENGTH on purpose: that is what stops a lesson sampling them away and
    asking a two-year-old about something nobody showed them.
    """
    subject = client.get("/curriculum/subjects/pg_ga").json()
    assert len(subject["topics"]) == 14

    for topic in subject["topics"]:
        activities = client.get(f"/curriculum/topics/{topic['topic_id']}/activities").json()
        taught = [a for a in activities if a["answer_kind"] == "presentational"]
        asked = [a for a in activities if a["answer_kind"] != "presentational"]
        assert 3 <= len(taught) < LESSON_LENGTH, topic["topic_id"]
        assert len(asked) >= len(taught), topic["topic_id"]
        # Every item is introduced, and checked after it is introduced.
        introduced = {a["visual_items"][0] for a in taught}
        for card in taught:
            item = card["visual_items"][0]
            after = activities[activities.index(card) + 1:]
            assert any(a["correct_answer"] == item for a in after), (
                f"{topic['topic_id']} teaches {item} but never checks it"
            )

        # Nothing is asked about that this level did not introduce. A question
        # may offer pictures from outside the level — "which one is red, the
        # apple or the banana?" — but the skill it tests is one of the level's.
        for question in asked:
            assert question["correct_answer"] in introduced or any(
                question["skill_id"].endswith(item) for item in introduced
            ), f"{topic['topic_id']} asks {question['activity_id']} about an untaught thing"


def test_every_play_group_topic_has_several_examples_to_practise(client: TestClient):
    """Practice and the adventure share a topic but must not share one question.

    A topic with a single answerable activity would hand a child the identical
    question on both surfaces, so every Play Group topic carries a spread of
    examples of the same skill.
    """
    detail = client.get("/curriculum/classes/playgroup").json()
    for subject in detail["subjects"]:
        for topic in subject["topics"]:
            activities = client.get(f"/curriculum/topics/{topic['topic_id']}/activities").json()
            answerable = [a for a in activities if a["answer_kind"] != "presentational"]
            assert len(answerable) >= 2, topic["topic_id"]


def test_removed_play_group_subjects_are_recorded_not_deleted(client: TestClient):
    """Four subjects were removed from Play Group by product decision: Motor
    Skills first, then Social and Emotional Learning, Creative Learning and Basic
    Life Skills. All four are in the published syllabus, so each is recorded
    rather than deleted and any authored activities stay on disk — restoring one
    is a manifest edit alone. Nothing serves them meanwhile."""
    detail = client.get("/curriculum/classes/playgroup").json()
    removed = ["pg_motor", "pg_social", "pg_creative", "pg_life"]
    assert [s["subject_id"] for s in detail["subjects"]] == ["pg_english", "pg_maths", "pg_ga"]
    assert detail["removed_subject_ids"] == removed
    for subject_id in removed:
        assert client.get(f"/curriculum/subjects/{subject_id}").status_code == 404
    assert client.get("/curriculum/topics/pg_motor_fine_motor_skills").status_code == 404
    assert client.get("/curriculum/topics/pg_social_emotions").status_code == 404


def test_ukg_hindi_is_served_again(client: TestClient):
    """Language (Hindi) was removed from UKG by an earlier product decision and
    restored on request. Its content never left the activity file, so restoring
    the subject was a manifest edit and nothing else."""
    detail = client.get("/curriculum/classes/ukg").json()
    assert "ukg_language" in [s["subject_id"] for s in detail["subjects"]]
    assert detail["removed_subject_ids"] == []
    subject = client.get("/curriculum/subjects/ukg_language").json()
    assert subject["language"] == "hi"
    assert [t["topic_id"] for t in subject["topics"]] == [
        "ukg_lang_swar", "ukg_lang_vyanjan", "ukg_lang_matra"
    ]


def test_lesson_metadata_comes_from_the_authored_file(client: TestClient):
    topic = client.get("/curriculum/topics/nur_maths_shapes").json()
    assert topic["objective"].startswith("Recognise circle")
    assert topic["intro_message"] == "Shapes are everywhere! Let us meet them one by one."
    assert topic["star_reward"] == 5
    assert topic["delivery"] == "digital"


def test_evs_is_split_into_three_real_topics(client: TestClient):
    subject = client.get("/curriculum/subjects/nur_evs").json()
    assert [t["topic_id"] for t in subject["topics"]] == [
        "nur_evs_living",
        "nur_evs_plants",
        "nur_evs_air_water_sun",
    ]
    # All seven published EVS items survive the regrouping.
    assert sum(len(t["subtopics"]) for t in subject["topics"]) == 7


def test_lkg_does_all_of_its_writing_in_art(client: TestClient):
    """Every drawing step LKG has lives in one subject.

    English still teaches the letters — identify them, link an object, say the
    sounds — but the finger-tracing that used to sit inside those topics is in
    Art & Writing, so a child finds writing in the same place every time.
    """
    detail = client.get("/curriculum/classes/lkg").json()
    traced_in: dict[str, set[str]] = {}
    for subject in detail["subjects"]:
        for topic in subject["topics"]:
            for activity in client.get(f"/curriculum/topics/{topic['topic_id']}/activities").json():
                if activity["type"] == "trace":
                    traced_in.setdefault(subject["subject_id"], set()).add(topic["topic_id"])
    assert traced_in == {"lkg_art": {"lkg_art_strokes", "lkg_art_writing"}}


def test_the_move_to_art_kept_every_published_lkg_subtopic(client: TestClient):
    """Art & Writing is a delivery decision, not a syllabus change: the published
    items it holds left English rather than being copied out of it."""
    assert client.get("/curriculum/classes/lkg").json()["subtopic_count"] == 103

    art = client.get("/curriculum/subjects/lkg_art").json()
    moved = [sub for topic in art["topics"] for sub in topic["subtopics"]]
    assert "Standing Line" in moved and "Down Curve" in moved
    assert [sub for sub in moved if sub.startswith("Writing")] == [
        "Writing Capital Letters (A-Z)",
        "Writing Small Letters (a-z)",
    ]

    english = client.get("/curriculum/subjects/lkg_english").json()
    remaining = [sub for topic in english["topics"] for sub in topic["subtopics"]]
    assert "Writing" not in remaining
    assert "Standing Line" not in remaining


def rewind_english_progress(child_id: str, **stored) -> None:
    """Put a child's LKG English progress back to a shape an older release wrote."""
    mock_child_profiles[child_id]["subject_progress"]["lkg_english"].update(stored)


def test_a_topic_leaving_a_subject_does_not_lock_the_child_out(client: TestClient):
    """Writing moved to Art & Writing after LKG children already existed.

    Their English progress still named the topic that left, and that id is on no
    subject's board any more — so English drew every topic locked with no way in,
    and Practice refused to start, for a child who had done nothing wrong. The
    subject reopens at its first topic instead.
    """
    _, child_id = make_lkg_child(client, "lkgmoved@example.com")
    rewind_english_progress(
        child_id,
        unlocked_topics=["lkg_eng_strokes"],
        current_topic_id="lkg_eng_strokes",
        completed_topics=[],
        scores={},
    )

    healed = client.get(f"/children/{child_id}").json()["subject_progress"]["lkg_english"]
    assert healed["unlocked_topics"] == ["lkg_eng_capitals"]
    assert healed["current_topic_id"] == "lkg_eng_capitals"

    practice = client.post(
        "/practice/start", json={"child_id": child_id, "subject_id": "lkg_english"}
    )
    assert practice.status_code == 200, practice.json()
    assert practice.json()["activities"]


def test_reconciling_progress_keeps_what_the_child_earned(client: TestClient):
    """Only the departed topic is forgotten. Everything still on this subject's
    board keeps its completion and its score."""
    _, child_id = make_lkg_child(client, "lkgkeep@example.com")
    rewind_english_progress(
        child_id,
        unlocked_topics=["lkg_eng_strokes", "lkg_eng_capitals", "lkg_eng_smalls"],
        completed_topics=["lkg_eng_strokes", "lkg_eng_capitals"],
        current_topic_id="lkg_eng_smalls",
        scores={"lkg_eng_strokes": 100, "lkg_eng_capitals": 90},
    )

    healed = client.get(f"/children/{child_id}").json()["subject_progress"]["lkg_english"]
    assert healed["unlocked_topics"] == ["lkg_eng_capitals", "lkg_eng_smalls"]
    assert healed["completed_topics"] == ["lkg_eng_capitals"]
    assert healed["scores"] == {"lkg_eng_capitals": 90}
    # Still part way through Small Letters, exactly where they left off.
    assert healed["current_topic_id"] == "lkg_eng_smalls"


def test_physical_topics_declare_how_they_are_delivered(client: TestClient):
    assert client.get("/curriculum/topics/nur_art_gross").json()["delivery"] == "parent_guided"
    assert client.get("/curriculum/topics/nur_art_fine").json()["delivery"] == "hybrid"
    assert client.get("/curriculum/topics/nur_maths_colours").json()["delivery"] == "digital"


# --------------------------------------------------------------------------
# activity kinds
# --------------------------------------------------------------------------


def test_every_activity_declares_how_it_is_answered(client: TestClient):
    kinds = set()
    for class_id in AUTHORED_CLASSES:
        detail = client.get(f"/curriculum/classes/{class_id}").json()
        for subject in detail["subjects"]:
            for topic in subject["topics"]:
                for activity in client.get(f"/curriculum/topics/{topic['topic_id']}/activities").json():
                    assert activity["answer_kind"] in {"choice", "spoken", "presentational"}
                    kinds.add(activity["answer_kind"])
    # The authored content genuinely uses all three.
    assert kinds == {"choice", "spoken", "presentational"}


@pytest.mark.parametrize("class_id", sorted(AUTHORED_CLASSES))
def test_choice_activities_never_exceed_the_mode_cap(client, class_id):
    cap = client.get(f"/curriculum/classes/{class_id}/experience").json()["max_choices_per_screen"]
    detail = client.get(f"/curriculum/classes/{class_id}").json()
    for subject in detail["subjects"]:
        for topic in subject["topics"]:
            for activity in client.get(f"/curriculum/topics/{topic['topic_id']}/activities").json():
                assert len(activity["options"]) <= cap, activity["activity_id"]


@pytest.mark.parametrize("class_id", sorted(AUTHORED_CLASSES))
def test_every_authored_answer_is_accepted_by_its_own_evaluator(client, class_id):
    """The answer key must actually pass. This is not a tautology: the answer
    goes through speech normalization on the way in, and a type missing from the
    letter or number tables there has its answer stripped as a filler word — a
    child tapping the right button is then told they are wrong, forever.
    """
    detail = client.get(f"/curriculum/classes/{class_id}").json()
    for subject in detail["subjects"]:
        for topic in subject["topics"]:
            for activity in client.get(f"/curriculum/topics/{topic['topic_id']}/activities").json():
                if activity["answer_kind"] == "presentational" or activity["open_ended"]:
                    continue
                is_correct, _ = activity_evaluators.evaluate(
                    activity_evaluators.EvaluationInput(
                        activity_type=activity["type"],
                        correct_answer=activity["correct_answer"] or "",
                        options=activity["options"],
                        answer=activity["correct_answer"] or "",
                        accepted_answers=tuple(activity["accept"]),
                    )
                )
                assert is_correct, f"{activity['activity_id']} ({activity['type']}) rejects its own answer"


def test_parent_activities_carry_a_note_for_the_grown_up(client: TestClient):
    activities = client.get("/curriculum/topics/nur_art_fine/activities").json()
    parent_cards = [a for a in activities if a["type"] == "parent_activity"]
    assert parent_cards
    for card in parent_cards:
        assert card["answer_kind"] == "presentational"
        assert card["parent_note"]


def test_trace_activities_carry_a_target_and_a_threshold(client: TestClient):
    activities = client.get("/curriculum/topics/nur_eng_strokes/activities").json()
    traces = [a for a in activities if a["type"] == "trace"]
    assert traces
    for trace in traces:
        assert trace["trace_target"]
        assert 0 < trace["min_accuracy"] <= 1


# --------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------


def evaluate(activity_type, correct, options, answer, **kwargs):
    return activity_evaluators.evaluate(
        activity_evaluators.EvaluationInput(
            activity_type=activity_type,
            correct_answer=correct,
            options=options,
            answer=answer,
            **kwargs,
        )
    )[0]


def test_presentational_activities_complete_by_taking_part():
    assert evaluate("introduce", "", [], "done") is True
    assert evaluate("trace", "", [], "done") is True
    assert evaluate("parent_activity", "", [], "done") is True


def test_spoken_activities_accept_the_authored_spellings():
    # "Say the sound: aa" accepts a, aa, ay, ah.
    assert evaluate("voice_repeat", "a", [], "ah", accepted_answers=("a", "aa", "ay", "ah")) is True
    assert evaluate("voice_repeat", "a", [], "", accepted_answers=("a", "aa")) is False


def test_open_ended_speech_accepts_any_real_attempt():
    assert evaluate("voice_repeat", "", [], "My name is Ana", open_ended=True) is True
    assert evaluate("voice_repeat", "", [], "   ", open_ended=True) is False


def test_multi_answer_match_compares_as_a_set():
    """"Put the red things together" has two right answers out of three."""
    options = ["apple", "tomato", "banana"]
    assert evaluate("match", "apple,tomato", options, "tomato,apple") is True
    assert evaluate("match", "apple,tomato", options, "apple") is False
    assert evaluate("match", "apple,tomato", options, "apple,banana") is False


def test_three_option_counting_still_scores_exactly():
    assert evaluate("count_objects", "3", ["2", "3", "4"], "3") is True
    assert evaluate("count_objects", "3", ["2", "3", "4"], "three") is True
    assert evaluate("count_objects", "3", ["2", "3", "4"], "4") is False


# --------------------------------------------------------------------------
# a real lesson, played through
# --------------------------------------------------------------------------


def test_a_child_can_play_shapes_from_start_to_finish(client: TestClient):
    _, child_id = make_nursery_child(client, "shapes@example.com")
    started = client.post(
        "/learning/start", json={"child_id": child_id, "topic_id": "nur_maths_shapes"}
    ).json()
    assert started["experience_mode"] == "early"
    # A lesson is a sample of the topic, so it is short enough to finish in one sitting.
    assert started["activity_total"] == LESSON_LENGTH

    session_id = started["session_id"]
    activity = started["activity"]
    response = started

    for _ in range(started["activity_total"]):
        assert activity is not None, "ran out of activities before the topic completed"
        # Answer the way the UI would for each kind.
        if activity["answer_kind"] == "choice":
            answer = activity["correct_answer"]
        elif activity["answer_kind"] == "spoken":
            answer = activity["correct_answer"] or "spoken"
        else:
            answer = "done"
        response = client.post(
            "/learning/answer", json={"session_id": session_id, "answer": answer}
        ).json()
        assert response["is_correct"] is True, activity["activity_id"]
        activity = response.get("activity")

    assert response["complete"] is True
    assert response["topic_completed"] is True
    assert response["current_score"] == 100
    assert response["next_topic_id"] == "nur_maths_colours"
    assert response["next_topic_unlocked"] is True


def test_the_next_topic_really_opens_after_completion(client: TestClient):
    _, child_id = make_nursery_child(client, "unlocked@example.com")
    # Colours is locked until Shapes is done.
    blocked = client.post("/learning/start", json={"child_id": child_id, "topic_id": "nur_maths_colours"})
    assert blocked.status_code == 403

    started = client.post(
        "/learning/start", json={"child_id": child_id, "topic_id": "nur_maths_shapes"}
    ).json()
    activity = started["activity"]
    while activity is not None:
        answer = (
            activity["correct_answer"]
            if activity["answer_kind"] == "choice"
            else (activity["correct_answer"] or "done")
        )
        response = client.post(
            "/learning/answer", json={"session_id": started["session_id"], "answer": answer}
        ).json()
        activity = response.get("activity")

    opened = client.post("/learning/start", json={"child_id": child_id, "topic_id": "nur_maths_colours"})
    assert opened.status_code == 200


def test_practice_draws_only_answerable_activities(client: TestClient):
    _, child_id = make_nursery_child(client, "nurpractice@example.com")
    session = client.post(
        "/practice/start", json={"child_id": child_id, "subject_id": "nur_maths"}
    ).json()
    assert session["activities"]
    for activity in session["activities"]:
        # A watch-and-listen card is not something to practise.
        assert activity["answer_kind"] != "presentational"


def test_play_group_meets_the_alphabet_one_letter_at_a_time(client: TestClient):
    """A to Z in order, three letters per lesson, each one shown before it is asked.

    A two-year-old cannot be handed six letters sampled at random. Every letter
    gets its own "this is B, B is for ball" card, and that card is never sampled
    away — being asked to find a letter nobody introduced is the failure this
    guards against.
    """
    subject = client.get("/curriculum/subjects/pg_english").json()
    letter_topics = [t for t in subject["topics"] if t["topic_id"].startswith("pg_english_letters_")]
    assert len(letter_topics) == 9

    taught = ""
    for topic in letter_topics:
        activities = client.get(f"/curriculum/topics/{topic['topic_id']}/activities").json()
        introductions = [a for a in activities if a["type"] == "introduce_letter"]
        # Every letter is introduced, and introducing comes before asking.
        assert activities[: len(introductions)] == introductions
        assert len(introductions) <= LESSON_LENGTH, topic["topic_id"]
        for card in introductions:
            taught += card["prompt"].split()[2].rstrip(".")
        # Each letter of the group is also checked.
        for letter in {a["correct_answer"] for a in activities if a["correct_answer"]}:
            assert letter.lower() in topic["topic_id"]

    assert taught == "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def test_nursery_meets_every_letter_as_one_big_and_small_pair(client: TestClient):
    """A to Z in order, two letters per level, big and small taught together.

    Nursery's published syllabus lists capitals and small letters as two units
    months apart. A three-year-old does not experience "A" and "a" as two
    things, so the level teaches Aa on one card: the introduction always names
    the pair, and the same level asks the child to match the small letter back
    to its capital.
    """
    subject = client.get("/curriculum/subjects/nur_english").json()
    letter_topics = [t for t in subject["topics"] if t["topic_id"].startswith("nur_eng_letters_")]
    assert len(letter_topics) == 13

    taught = ""
    for topic in letter_topics:
        activities = client.get(f"/curriculum/topics/{topic['topic_id']}/activities").json()
        introductions = [a for a in activities if a["type"] == "introduce_letter"]
        assert len(introductions) == 2, topic["topic_id"]
        for card in introductions:
            pair = card["prompt"].split()[2].rstrip(".")
            # "This is Aa." — the capital and its small letter, on one card.
            assert len(pair) == 2 and pair[0].isupper() and pair[1] == pair[0].lower(), pair
            assert f"letter_small_{pair[1]}" in card["visual_items"], pair
            taught += pair[0]
        # Both forms are practised: find the capital, then match the small one.
        assert {a["type"] for a in activities} >= {"select_letter", "match", "repeat_letter", "trace"}
        for letter in {a["correct_answer"] for a in activities if a["correct_answer"]}:
            assert len(letter) == 1

    assert taught == "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def test_a_nursery_letter_level_is_played_in_full(client: TestClient):
    """Meet Aa, find the big A, match the small a, say the sound, write both.

    The level is a method, not a pool, so it carries `complete` and every step
    is played. Sampling it would drop one of the steps for one of the letters,
    which is not a shorter lesson but a broken method.
    """
    _, child_id = make_nursery_child(client, "nurletters@example.com")
    topic = client.get("/curriculum/topics/nur_eng_letters_ab").json()
    assert topic["lesson_flow"] == "complete"
    # Letters open after the pre-writing strokes, which come first in English.
    play_topic(client, child_id, "nur_eng_strokes")

    started = client.post(
        "/learning/start", json={"child_id": child_id, "topic_id": "nur_eng_letters_ab"}
    ).json()
    # Six steps per letter: a-j write their small letter too, as the syllabus asks.
    assert started["activity_total"] == 12

    played, activity, response = [], started["activity"], started
    while activity is not None:
        played.append((activity["type"], activity["correct_answer"] or activity["trace_target"]))
        answer = "done" if activity["answer_kind"] == "presentational" else activity["correct_answer"]
        response = client.post(
            "/learning/answer", json={"session_id": started["session_id"], "answer": answer}
        ).json()
        activity = response.get("activity")

    assert played == [
        ("introduce_letter", None), ("select_letter", "A"), ("match", "A"),
        ("repeat_letter", "a"), ("trace", "A"), ("trace", "small_a"),
        ("introduce_letter", None), ("select_letter", "B"), ("match", "B"),
        ("repeat_letter", "b"), ("trace", "B"), ("trace", "small_b"),
    ]
    assert response["complete"] is True and response["topic_completed"] is True
    assert response["next_topic_id"] == "nur_eng_letters_cd"
    assert response["next_topic_unlocked"] is True


def test_nursery_writes_small_letters_only_up_to_j(client: TestClient):
    """The syllabus introduces writing for small letters a-j only. Later levels
    still meet and match their small letters; they just do not write them."""
    subject = client.get("/curriculum/subjects/nur_english").json()
    written = set()
    for topic in [t for t in subject["topics"] if t["topic_id"].startswith("nur_eng_letters_")]:
        for activity in client.get(f"/curriculum/topics/{topic['topic_id']}/activities").json():
            target = activity["trace_target"] or ""
            if target.startswith("small_"):
                written.add(target.removeprefix("small_"))
    assert written == set("abcdefghij")


def test_nursery_counts_one_to_ten_one_number_at_a_time(client: TestClient):
    subject = client.get("/curriculum/subjects/nur_maths").json()
    number_topics = [t for t in subject["topics"] if t["topic_id"].startswith("nur_maths_count_")]
    assert [t["topic_id"] for t in number_topics] == [
        "nur_maths_count_123",
        "nur_maths_count_45",
        "nur_maths_count_678",
        "nur_maths_count_910",
    ]

    counted = []
    for topic in number_topics:
        assert topic["lesson_flow"] == "complete"
        activities = client.get(f"/curriculum/topics/{topic['topic_id']}/activities").json()
        for index, card in enumerate(activities):
            if card["type"] != "introduce_number":
                continue
            counted.append(int(card["visual_items"][0]))
            # Meet it, count it, say it, write it — in that order, every time.
            assert [a["type"] for a in activities[index: index + 4]] == [
                "introduce_number", "count_objects", "repeat_number", "trace"
            ]
    assert counted == list(range(1, 11))


def test_nursery_hindi_is_taught_the_same_way_as_english(client: TestClient):
    """Swar अ to अः then व्यंजन क to ङ, two letters per level, each one shown
    before it is asked — the same shape as the English levels."""
    subject = client.get("/curriculum/subjects/nur_hindi").json()
    levels = [t for t in subject["topics"] if t["topic_id"] != "nur_hindi_maukhik"]
    assert len(levels) == 9

    taught = []
    for topic in levels:
        assert topic["lesson_flow"] == "complete", topic["topic_id"]
        activities = client.get(f"/curriculum/topics/{topic['topic_id']}/activities").json()
        # Four steps per letter: meet it, find it, find its picture, say it.
        for start in range(0, len(activities), 4):
            steps = [a["type"] for a in activities[start: start + 4]]
            assert steps == [
                "introduce_letter", "select_letter", "multiple_choice", "repeat_letter"
            ], topic["topic_id"]
            letter = activities[start]["visual_items"][0]
            taught.append(letter)
            # The letter is asked about only after its own introduction card.
            for activity in activities[start + 1: start + 4]:
                assert activity["visual_items"][0] == letter

    assert taught == HINDI_SWAR + HINDI_VYANJAN


def test_nursery_hindi_never_asks_a_child_to_write(client: TestClient):
    """"Is saal Hindi likhna nahi hai" — the syllabus is speaking and listening
    only this year, so the writing step that English has must not exist here."""
    subject = client.get("/curriculum/subjects/nur_hindi").json()
    for topic in subject["topics"]:
        for activity in client.get(f"/curriculum/topics/{topic['topic_id']}/activities").json():
            assert activity["type"] != "trace", activity["activity_id"]
            assert not activity["trace_target"], activity["activity_id"]


def test_a_nursery_hindi_level_is_played_in_full(client: TestClient):
    _, child_id = make_nursery_child(client, "nurhindi@example.com")
    started = client.post(
        "/learning/start", json={"child_id": child_id, "topic_id": "nur_hindi_swar_a_aa"}
    ).json()
    assert started["activity_total"] == 8

    played, activity, response = [], started["activity"], started
    while activity is not None:
        played.append((activity["type"], activity["correct_answer"]))
        answer = "done" if activity["answer_kind"] == "presentational" else activity["correct_answer"]
        response = client.post(
            "/learning/answer", json={"session_id": started["session_id"], "answer": answer}
        ).json()
        activity = response.get("activity")

    assert played == [
        ("introduce_letter", None), ("select_letter", "अ"), ("multiple_choice", "anar"),
        ("repeat_letter", "अ"),
        ("introduce_letter", None), ("select_letter", "आ"), ("multiple_choice", "aam"),
        ("repeat_letter", "आ"),
    ]
    assert response["complete"] is True and response["topic_completed"] is True
    assert response["next_topic_id"] == "nur_hindi_swar_i_ii"
    assert response["next_topic_unlocked"] is True


def test_hindi_letters_are_accepted_when_said_in_either_script(client: TestClient):
    """A child's speech may come back as "अ" or as "a". Both are the same answer."""
    activities = client.get("/curriculum/topics/nur_hindi_swar_a_aa/activities").json()
    spoken = [a for a in activities if a["answer_kind"] == "spoken"]
    assert spoken
    for activity in spoken:
        assert any(part.isascii() for part in activity["accept"]), activity["activity_id"]
        for said in [activity["correct_answer"], *activity["accept"]]:
            is_correct, _ = activity_evaluators.evaluate(
                activity_evaluators.EvaluationInput(
                    activity_type=activity["type"],
                    correct_answer=activity["correct_answer"],
                    options=activity["options"],
                    answer=said,
                    accepted_answers=tuple(activity["accept"]),
                )
            )
            assert is_correct, f"{activity['activity_id']} rejects '{said}'"


def test_play_group_counts_one_to_ten_in_order(client: TestClient):
    subject = client.get("/curriculum/subjects/pg_maths").json()
    number_topics = [t for t in subject["topics"] if t["topic_id"].startswith("pg_maths_number_")]
    assert [t["topic_id"] for t in number_topics] == [
        "pg_maths_number_123",
        "pg_maths_number_456",
        "pg_maths_number_789",
        "pg_maths_number_10",
    ]

    counted = []
    for topic in number_topics:
        activities = client.get(f"/curriculum/topics/{topic['topic_id']}/activities").json()
        introductions = [a for a in activities if a["type"] == "introduce_number"]
        assert activities[: len(introductions)] == introductions
        counted += [int(card["visual_items"][0]) for card in introductions]
    assert counted == list(range(1, 11))


def test_a_letter_level_teaches_finds_says_and_writes_every_letter(client: TestClient):
    """Four steps per letter, and the level passes only at the end of them.

    Meet the letter, find it, say it out loud, write it with a finger. A level
    of three letters is twelve steps and is played in full — sampling it would
    drop one of the four steps of the method for some letter.
    """
    _, child_id = make_play_group_child(client, "pgletters@example.com")
    topic = client.get("/curriculum/topics/pg_english_letters_abc").json()
    assert topic["lesson_flow"] == "complete"

    started = client.post(
        "/learning/start", json={"child_id": child_id, "topic_id": "pg_english_letters_abc"}
    ).json()
    assert started["activity_total"] == 12

    played, activity, response = [], started["activity"], started
    while activity is not None:
        played.append((activity["type"], activity["correct_answer"] or activity["trace_target"]))
        answer = "done" if activity["answer_kind"] == "presentational" else activity["correct_answer"]
        response = client.post(
            "/learning/answer", json={"session_id": started["session_id"], "answer": answer}
        ).json()
        activity = response.get("activity")

    assert played == [
        ("introduce_letter", None), ("introduce_letter", None), ("introduce_letter", None),
        ("select_letter", "a"), ("select_letter", "b"), ("select_letter", "c"),
        ("repeat_letter", "a"), ("repeat_letter", "b"), ("repeat_letter", "c"),
        ("trace", "A"), ("trace", "B"), ("trace", "C"),
    ]
    assert response["complete"] is True and response["topic_completed"] is True
    assert response["next_topic_id"] == "pg_english_letters_def"
    assert response["next_topic_unlocked"] is True

    # And the level it unlocked really opens.
    opened = client.post(
        "/learning/start", json={"child_id": child_id, "topic_id": "pg_english_letters_def"}
    )
    assert opened.status_code == 200


def test_every_writing_step_carries_something_to_trace(client: TestClient):
    """A trace activity with no target would render an empty drawing box."""
    for class_id in AUTHORED_CLASSES:
        detail = client.get(f"/curriculum/classes/{class_id}").json()
        for subject in detail["subjects"]:
            for topic in subject["topics"]:
                for activity in client.get(f"/curriculum/topics/{topic['topic_id']}/activities").json():
                    if activity["type"] != "trace":
                        continue
                    assert activity["trace_target"], activity["activity_id"]
                    assert 0 < activity["min_accuracy"] <= 1, activity["activity_id"]


def test_a_lesson_never_drops_a_teaching_card(client: TestClient):
    """Weather is ten activities against a six-step lesson, so it is sampled —
    but all four of its watch-and-listen cards must survive the trim."""
    _, child_id = make_play_group_child(client, "pgweather@example.com")
    # Weather is the last General Awareness level, so open the class up first.
    client.post(f"/dev/seed/{child_id}")
    topic = "pg_ga_weather"
    authored = client.get(f"/curriculum/topics/{topic}/activities").json()
    teaching = [a["activity_id"] for a in authored if a["answer_kind"] == "presentational"]
    assert len(authored) > LESSON_LENGTH and len(teaching) == 4

    for _ in range(10):
        started = client.post("/learning/start", json={"child_id": child_id, "topic_id": topic}).json()
        played, activity = [], started["activity"]
        while activity is not None:
            played.append(activity["activity_id"])
            answer = "done" if activity["answer_kind"] == "presentational" else activity["correct_answer"]
            response = client.post(
                "/learning/answer", json={"session_id": started["session_id"], "answer": answer}
            ).json()
            activity = response.get("activity")
        assert len(played) == LESSON_LENGTH
        assert set(teaching) <= set(played), "a lesson skipped a teaching card"


def test_a_lesson_is_a_short_varying_sample_of_its_topic(client: TestClient):
    """The first colours level holds nine examples. A two-year-old plays six of
    them, opening on the level's watch-and-listen card, and meets a different
    handful next time."""
    _, child_id = make_play_group_child(client, "pglesson@example.com")
    topic = "pg_ga_colors_1"
    authored = [a["activity_id"] for a in client.get(f"/curriculum/topics/{topic}/activities").json()]
    assert len(authored) > LESSON_LENGTH

    def play_ids() -> list[str]:
        started = client.post("/learning/start", json={"child_id": child_id, "topic_id": topic}).json()
        assert started["activity_total"] == LESSON_LENGTH
        ids, activity = [], started["activity"]
        while activity is not None:
            ids.append(activity["activity_id"])
            answer = "done" if activity["answer_kind"] == "presentational" else activity["correct_answer"]
            response = client.post(
                "/learning/answer", json={"session_id": started["session_id"], "answer": answer}
            ).json()
            activity = response.get("activity")
        return ids

    first = play_ids()
    assert len(first) == LESSON_LENGTH
    assert len(set(first)) == LESSON_LENGTH, "a lesson repeated a question"
    assert first[0] == authored[0], "the lesson did not open on the introduction card"
    # Authored order is kept, so the lesson still reads as a lesson.
    assert first == sorted(first, key=authored.index)

    # Ten replays of a twelve-question topic that never varied would be a bug.
    seen = {tuple(first)} | {tuple(play_ids()) for _ in range(9)}
    assert len(seen) > 1, "every lesson drew the same six questions"


def test_practice_varies_the_example_within_one_topic(client: TestClient):
    """Only the first colours level is unlocked for a new child, so every practice
    question comes from that one level — and they must all be different examples
    of it."""
    _, child_id = make_play_group_child(client, "pgpractice@example.com")
    session = client.post(
        "/practice/start", json={"child_id": child_id, "subject_id": "pg_ga"}
    ).json()
    colours = {a["activity_id"] for a in client.get("/curriculum/topics/pg_ga_colors_1/activities").json()}

    ids = [a["activity_id"] for a in session["activities"]]
    assert len(ids) == 5
    assert len(set(ids)) == 5, "practice repeated a question inside one session"
    assert set(ids) <= colours

    # Seeded from the child's own state, so a reload does not reshuffle.
    again = client.post("/practice/start", json={"child_id": child_id, "subject_id": "pg_ga"}).json()
    assert [a["activity_id"] for a in again["activities"]] == ids
