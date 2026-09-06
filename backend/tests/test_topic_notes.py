"""Revision notes: the author's words, the same every time, and no asking.

The Adventure map may now hand a child the notes for a level they have met, so
they can go back over it and it does not fade. These pin the four things that
keep that from quietly becoming a second classroom:

* **deterministic** - no model, no similarity search, so the same level reads
  the same on two different afternoons. A child revising from notes that drift
  is not revising;
* **teaching lines only** - the prompt of a card that has an answer is the
  *asking*, and a page of askings is a test paper. Only hints and the prompts of
  cards with nothing to answer survive;
* **honest when empty** - a level whose author has written nothing comes back
  saying so rather than with something invented to fill the space;
* **it marks nothing** - reading your notes writes no attempt, no probe and no
  episode, and moves no star.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Attempt, PolicyEpisode, RetentionProbe
from app.db.session import session_scope
from app.main import app
from app.playground import notes
from app.services import curriculum_service


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def every_topic() -> list[str]:
    return [
        topic.topic_id
        for summary in curriculum_service.list_classes()
        for subject in curriculum_service.get_class(summary.class_id).subjects
        for topic in subject.topics
    ]


# --------------------------------------------------------------------------
# The same notes, every time
# --------------------------------------------------------------------------


def test_notes_are_deterministic():
    """Twice in a row, and it is the same page. No model, no shuffle, no search."""
    topic_id = "lkg_maths_shapes"
    first, second = notes.for_topic(topic_id), notes.for_topic(topic_id)
    assert first == second
    assert first.has_notes
    assert first.speech == " ".join(first.lines)[: notes.MAX_SPEECH_CHARS].strip()


def test_the_whole_syllabus_produces_notes_without_raising():
    """A level the author has not filled in is a normal state, not an error -
    and it must never be the thing that breaks the map."""
    written = 0
    for topic_id in every_topic():
        made = notes.for_topic(topic_id)
        assert made.topic_id == topic_id
        assert len(made.lines) <= notes.MAX_LINES
        assert len(made.speech) <= notes.MAX_SPEECH_CHARS
        assert made.has_notes == bool(made.lines)
        written += 1 if made.has_notes else 0
    assert written, "the shipped syllabus should have notes somewhere"


def test_a_topic_the_manifest_does_not_have_says_so_kindly():
    made = notes.for_topic("no_such_topic_anywhere")
    assert made.has_notes is False
    assert made.lines == ()
    assert made.speech == ""


# --------------------------------------------------------------------------
# Teaching lines, never the asking
# --------------------------------------------------------------------------


def test_a_question_prompt_never_becomes_a_note():
    """"Tap the circle." is the asking. Its hint is the teaching, and only the
    hint is kept."""
    for topic_id in every_topic():
        made = notes.for_topic(topic_id)
        if not made.has_notes:
            continue
        for activity in curriculum_service.get_activities(topic_id):
            if not (activity.correct_answer or "").strip():
                continue
            prompt = (activity.prompt or "").strip()
            if not prompt:
                continue
            assert all(prompt not in line for line in made.lines), (
                f"{topic_id} put the question {prompt!r} in its notes"
            )


def test_a_contextless_hint_is_given_its_subject():
    """"Round, with no corners." is a riddle on its own. Notes have no question
    above them, so the thing being taught is named in front of it."""
    made = notes.for_topic("lkg_maths_shapes")
    assert "Circle: round, with no corners." in made.lines
    # ...and a hint that already names the thing is left exactly as written.
    assert "A square is equal on every side." in made.lines


def test_a_letter_or_a_number_is_not_used_as_a_label():
    """"F: sing the alphabet song from D." reads as nonsense. A single letter or
    a bare number names a card's answer, not a thing to define."""
    assert notes._named("Sing the alphabet song from D.", "F") == "Sing the alphabet song from D."
    assert notes._named("Touch them and count.", "2") == "Touch them and count."
    # A real name still labels.
    assert notes._named("Round, with no corners.", "circle") == "Circle: round, with no corners."


def test_an_example_is_never_the_lesson_itself():
    """The same rule the class keeps: a level teaching the letter A already
    draws a big A, so naming it again beside itself is not an example."""
    for topic_id in every_topic():
        made = notes.for_topic(topic_id)
        for token in made.example_items:
            assert not token.lower().startswith(("letter", "number", "shape", "colour", "color"))


# --------------------------------------------------------------------------
# The endpoint, and what it must not touch
# --------------------------------------------------------------------------


def test_the_endpoint_serves_the_notes(client: TestClient):
    body = client.get("/curriculum/topics/lkg_maths_shapes/notes").json()
    assert body["has_notes"] is True
    assert body["topic_id"] == "lkg_maths_shapes"
    assert body["lines"]
    assert body["speech"]
    assert {"example_items", "visual_kind", "visual_value", "title"} <= set(body)


def test_reading_the_notes_marks_nothing(client: TestClient):
    """It is revision, not a performance. Nothing here may reach the attempt
    log, a retention probe, the learned policy or a star."""
    with session_scope() as session:
        before = (
            len(list(session.scalars(select(Attempt)).all())),
            len(list(session.scalars(select(RetentionProbe)).all())),
            len(list(session.scalars(select(PolicyEpisode)).all())),
        )

    for topic_id in every_topic()[:8]:
        assert client.get(f"/curriculum/topics/{topic_id}/notes").status_code == 200

    with session_scope() as session:
        after = (
            len(list(session.scalars(select(Attempt)).all())),
            len(list(session.scalars(select(RetentionProbe)).all())),
            len(list(session.scalars(select(PolicyEpisode)).all())),
        )
    assert after == before
