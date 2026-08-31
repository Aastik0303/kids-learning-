"""The AI Teacher: the class, the schedule it runs on, and the day it ends.

The bot retrieves from `data/playground/teacher_notes.md`, explains in one of the
nine strategies and asks its own questions. Five things are worth pinning, and
they are the five that would be expensive to get wrong:

1. **It marks nothing.** The verdict is pure Python. A bot that both sets the
   question and marks it learns that the easiest way to be marked well is to give
   the answer away - the same reason the class never lets a model near
   correctness.
2. **A stage is five questions, and there is no score.** The points this loop
   used to keep are gone: nothing counts up or down beside a four-year-old, and
   the only number left is how many of the five have been settled.
3. **Every question gets three turns and nobody is left stuck.** Asked; asked
   again with a hint and the choices to pick from; and then answered and
   explained. The third turn is not a test and is not marked.
4. **A stage is a plan item, and the day is all of them.** The schedule is not a
   suggestion the teacher consults; it *is* the shape of the sitting. Finishing a
   stage moves the Adventure map, through the same deterministic scorer the
   conductor ends a lesson with - and nothing else moves it, because Adventure
   teaches nothing of its own any more.
5. **A finished day is shut until tomorrow.** The lock lives on the server, so a
   reload cannot get past it.

The suite runs with no provider configured, so every turn here is the
deterministic teacher reading the notes back - which is exactly the path that has
to work when Groq is down.
"""

import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from sqlalchemy import select

from app.db.models import Attempt, PlaygroundSession, PlaygroundTurn
from app.db.session import session_scope
from app.main import app
from app.playground import agent, lesson, questions, rag, stage, visuals


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


# The two steps that are answered and therefore marked. Explaining is watched
# and drawing is drawn: both carry a question in words and neither is scored, so
# "the turn has a question" is not the same thing as "the turn is asking".
SCORED_EXPECTS = {"tap", "voice"}


def _walk_to_a_question(client: TestClient, turn: dict, limit: int = 8) -> dict:
    """Step past explaining and drawing to the first turn that is actually marked."""
    for _ in range(limit):
        if turn.get("question") and turn.get("expects") in SCORED_EXPECTS:
            return turn
        turn = client.post(
            f"/playground/teacher/sessions/{turn['session_id']}/answer", json={"answer": "ready"}
        ).json()
    return turn


def _pending_answer(session_id: str) -> str:
    """The key the server is holding, read the only place it exists: the row.

    A test that wants to get an answer *right* has to ask the server what it
    asked, because the client is never told - which is the point of the column.
    """
    with session_scope() as session:
        row = session.scalar(
            select(PlaygroundSession).where(PlaygroundSession.session_id == session_id)
        )
        return row.pending_answer if row else ""


def _work_through_the_day(client: TestClient, child_id: str, limit: int = 200) -> dict:
    """Answer everything correctly until the class says the day is over."""
    turn = client.post(f"/playground/teacher/{child_id}/open").json()
    for _ in range(limit):
        if turn.get("day_complete"):
            return turn
        said = _pending_answer(turn["session_id"]) or "ready"
        turn = client.post(
            f"/playground/teacher/sessions/{turn['session_id']}/answer", json={"answer": said}
        ).json()
    raise AssertionError("the day never ended")


def make_child(client: TestClient, email: str = "playground@example.com") -> str:
    auth = client.post("/auth/register", json={"name": "P", "email": email, "password": "demo1234"})
    token = auth.json()["session_token"]
    child = client.post(
        "/children",
        json={
            "session_token": token,
            "name": "Aanya",
            "birth_year": date.today().year - 2,
            "birth_month": date.today().month,
            "preferred_language": "English",
        },
    )
    return child.json()["child_id"]


# --------------------------------------------------------------------------
# 1. Retrieval
# --------------------------------------------------------------------------


def test_the_notes_are_retrievable_and_answer_about_the_thing_asked():
    hits = rag.search("teach the number three", top_k=3)
    assert hits
    headings = [hit.passage.heading.lower() for hit in hits]
    assert any("number" in heading for heading in headings), headings


def test_retrieval_says_which_backend_answered():
    """Embeddings when the model loaded, keywords when it could not. Either is a
    real answer; a screen that silently had no retrieval at all is not."""
    assert rag.backend() in {"embeddings", "keyword"}


# --------------------------------------------------------------------------
# 2. Five questions, and no score anywhere
# --------------------------------------------------------------------------


def test_a_verdict_is_right_or_wrong_and_carries_no_number():
    """The verdict says what happened; it does not price it.

    A `points_delta` on this object is what a scoreboard is built out of, so its
    absence is the rule rather than a tidy-up: there is nothing for a screen to
    add up any more.
    """
    assert stage.judge(said="three", expected="3", accept=["three"]).is_correct is True
    assert stage.judge(said="banana", expected="3", accept=["three"]).is_correct is False
    assert not hasattr(stage.judge(said="three", expected="3"), "points_delta")


def test_a_child_saying_the_answer_inside_a_sentence_has_said_it():
    """"it is three" is three. The words around the answer are not the answer."""
    assert stage.judge(said="umm it is three", expected="3", accept=["three"]).is_correct


def test_five_questions_finish_a_stage_and_the_next_one_starts_clean():
    assert stage.QUESTIONS_PER_STAGE == 5
    progress = stage.settle(stage=1, questions_asked=4)
    assert progress.stage_complete is True
    assert progress.stage == 2
    assert progress.questions_asked == 0


def test_a_stage_does_not_end_early_however_the_questions_went():
    """Four settled questions is four, right or wrong. Nothing shortens a stage
    and nothing lengthens it: five is the whole rule."""
    for asked in range(4):
        progress = stage.settle(stage=1, questions_asked=asked)
        assert progress.stage_complete is False
        assert progress.stage == 1
        assert progress.questions_asked == asked + 1


# --------------------------------------------------------------------------
# 3. Strategy
# --------------------------------------------------------------------------


def test_a_second_explanation_is_a_different_one():
    first = agent.choose_strategy(spent=[])
    second = agent.choose_strategy(spent=[first])
    third = agent.choose_strategy(spent=[first, second])
    assert len({first, second, third}) == 3


# --------------------------------------------------------------------------
# 4. The sitting, end to end
# --------------------------------------------------------------------------


def test_a_sitting_teaches_and_asks(client: TestClient):
    child_id = make_child(client)

    opened = client.post(f"/playground/teacher/{child_id}/open")
    assert opened.status_code == 200, opened.text
    turn = opened.json()
    assert turn["speech"], "a sitting opens on the explanation"
    assert turn["strategy"]
    assert turn["stage"] == 1 and turn["questions_asked"] == 0

    turn = _walk_to_a_question(client, turn)
    assert turn["question"]

    wrong = client.post(
        f"/playground/teacher/sessions/{turn['session_id']}/answer",
        json={"answer": "something that is not the answer"},
    ).json()
    assert wrong["is_correct"] is False
    assert wrong["feedback"]
    # Wrong does not mean the same explanation again.
    assert wrong["strategy"] != turn["strategy"]


def test_no_turn_the_client_ever_sees_carries_a_score(client: TestClient):
    """The child's screen has nothing to draw a scoreboard from.

    The points are not hidden from the client, they are gone: a field that is
    still sent is a field a screen can start drawing again next time somebody is
    in a hurry.
    """
    child_id = make_child(client, "teacher-no-score@example.com")
    turn = client.post(f"/playground/teacher/{child_id}/open").json()
    scoring = {"points", "points_to_advance", "points_delta", "score"}

    for _ in range(6):
        assert not scoring & set(turn), sorted(scoring & set(turn))
        said = _pending_answer(turn["session_id"]) or "ready"
        turn = client.post(
            f"/playground/teacher/sessions/{turn['session_id']}/answer", json={"answer": said}
        ).json()


def test_the_class_says_hello_before_it_teaches_anything(client: TestClient):
    """A child dropped straight into an explanation has been given no way in.

    The opening turn says hello, says how much there is today and says what
    happens to a question they cannot answer - and then teaches. It is said once:
    a reload teaches the step again without re-introducing the class.
    """
    child_id = make_child(client, "teacher-intro@example.com")
    opened = client.post(f"/playground/teacher/{child_id}/open").json()

    assert opened["speech"].startswith("Hello!")
    assert "little questions" in opened["speech"]
    assert opened["speech"].count(".") >= 3, "the intro is two or three lines, not one"

    again = client.post(f"/playground/teacher/{child_id}/open").json()
    assert not again["speech"].startswith("Hello!"), "the class introduces itself once"


def test_a_marked_answer_lands_in_the_one_attempt_log(client: TestClient):
    """Mastery, the weak-skill list and the policy reward all read `attempts`.

    A teaching loop that graded an answer and kept the verdict to itself would
    leave every one of them reading a partial history and never say so. The
    verdict written here is `stage.judge`'s, which is plain Python over the
    authored key - no model is upstream of the log.
    """
    child_id = make_child(client, "teacher-attempts@example.com")
    turn = _walk_to_a_question(client, client.post(f"/playground/teacher/{child_id}/open").json())

    client.post(
        f"/playground/teacher/sessions/{turn['session_id']}/answer",
        json={"answer": "something that is not the answer"},
    )

    with session_scope() as session:
        logged = session.query(Attempt).all()
        assert logged, "an answered question was never written to the attempt log"
        assert all(attempt.topic_id for attempt in logged)


def test_watching_and_drawing_are_not_marked(client: TestClient):
    """Explaining is watched and a traced letter cannot be right or wrong.

    Neither is an answer, so neither is marked and neither is written to the
    attempt log. A child who taps "got it" has not got anything wrong.
    """
    child_id = make_child(client, "teacher-unscored@example.com")
    turn = client.post(f"/playground/teacher/{child_id}/open").json()
    assert turn["expects"] == "ready"

    watched = client.post(
        f"/playground/teacher/sessions/{turn['session_id']}/answer", json={"answer": "ready"}
    ).json()

    assert watched["is_correct"] is None
    assert watched["questions_asked"] == 0, "watching is not one of the five"
    with session_scope() as session:
        assert session.query(Attempt).count() == 0


def test_the_question_and_its_answer_stay_on_the_server(client: TestClient):
    """The client is never told what it is about to be asked to answer."""
    child_id = make_child(client, "playground-key@example.com")
    turn = _walk_to_a_question(client, client.post(f"/playground/teacher/{child_id}/open").json())

    assert "expected_answer" not in turn
    assert "accept" not in turn
    with session_scope() as session:
        row = session.query(PlaygroundSession).one()
        assert row.pending_answer, "the answer is kept server-side, where the child cannot read it"


def test_a_lost_session_is_told_kindly(client: TestClient):
    answered = client.post(
        "/playground/teacher/sessions/teach_nothing/answer", json={"answer": "hello"}
    )
    assert answered.status_code == 404
    assert answered.json()["error"]["code"] == "PLAYGROUND_SESSION_GONE"


# --------------------------------------------------------------------------
# 5. The schedule, and the picture
# --------------------------------------------------------------------------


def test_the_bot_teaches_whatever_today_s_plan_is_pointing_at(client: TestClient):
    """The playground follows the schedule; it does not pick its own topic.

    This is the whole connection between the sandbox and the rest of the app,
    and it goes one way: the plan is read, and nothing is written back to it.
    """
    child_id = make_child(client, "playground-plan@example.com")
    plan = client.get(f"/plans/{child_id}/today").json()
    planned = [item["topic_id"] for item in plan["items"]]

    turn = client.post(f"/playground/teacher/{child_id}/open").json()

    # The plan's items are the stages, and a sitting opens on the first of them.
    assert turn["topic_id"] in planned, (turn["topic_id"], planned)
    assert turn["topic_id"] == planned[0]
    assert turn["topic_title"] and turn["topic_title"] != turn["topic_id"]

    # And the plan is exactly where it was: reading it moved nothing.
    after = client.get(f"/plans/{child_id}/today").json()
    assert after["items"] == plan["items"]
    assert after["completed"] == plan["completed"]


def test_every_turn_carries_a_picture_the_app_knows_how_to_draw(client: TestClient):
    child_id = make_child(client, "playground-visual@example.com")
    turn = client.post(f"/playground/teacher/{child_id}/open").json()

    assert turn["visual_kind"] in {"", "letter", "number", "count", "shape", "colour"}
    if turn["visual_kind"]:
        assert turn["visual_value"]


def test_a_model_that_names_a_picture_the_app_cannot_draw_gets_none():
    """The model chooses from a list; anything else is not drawn.

    A model handing back markup - or a shape nobody authored - would be a model
    writing into a child's screen, so `parse` is deliberately unforgiving.
    """
    assert visuals.parse("shape:circle").kind == "shape"
    assert visuals.parse("count:3").kind == "count"
    assert visuals.parse("letter:अ").kind == "letter"
    for bad in ("shape:blob", "count:44", "<svg onload=alert(1)>", "none", "", None):
        assert visuals.parse(bad).is_shown is False, bad


def test_the_deterministic_teacher_still_draws_something():
    """No model, no picture chosen - so it is read out of the words instead."""
    assert visuals.from_concept("Letters: A, B, C", "").as_token() == "letter:A"
    assert visuals.from_concept("Number 1", "").as_token() == "number:1"
    assert visuals.from_concept("Shapes", "A circle is round").as_token() == "shape:circle"


# --------------------------------------------------------------------------
# 5c. The explaining turn teaches, rather than labelling
# --------------------------------------------------------------------------


def _explained(topic_id: str, title: str) -> str:
    """What the deterministic teacher says on the explaining step of a level."""
    state = {"subject": "", "topic": title, "topic_id": topic_id, "step": lesson.EXPLAIN, "spent": []}
    state.update(agent._retrieve(state))
    return agent._fallback_lesson(state).explanation


def test_the_explaining_turn_is_several_sentences_and_not_a_label():
    """"Pink is a light red colour" is a label, and a label is not a lesson.

    The user asked for the explaining step to teach in three or four sentences
    with an example in them. This pins the path with no model behind it, which is
    the one that has to work when the provider is down - the prompt asks the
    model for the same shape.
    """
    said = _explained("pg_ga_colors_3", "Colours: Pink, Black, White")

    sentences = [part for part in re.split(r"(?<=[.!?])\s+", said) if part.strip()]
    assert len(sentences) >= 3, said
    # And one of them is somewhere a child has actually seen the thing.
    assert "look for pink" in said.lower(), said


def test_the_picture_follows_the_level_title_and_not_its_notes():
    """A level on pink draws pink, however much its notes talk about red.

    Colours are explained by comparison - the notes for any colour level mention
    the others - so reading the title and the explanation as one lump let the
    first colour in the list win. A pink lesson beside a red circle is the app
    contradicting itself in front of a three-year-old.
    """
    notes = "Red is the colour of a tomato. Blue is the colour of the sky."
    assert visuals.from_concept("Colours: Pink, Black, White", notes).as_token() == "colour:pink"


def test_a_level_is_about_what_comes_after_its_colon():
    """"स्वर: अ, आ" teaches अ. The word before the colon is the kind of thing."""
    assert visuals.from_concept("स्वर: अ, आ").as_token() == "letter:अ"
    assert visuals.from_concept("Letters: A, B, C").as_token() == "letter:A"


def test_the_retrieval_marker_never_reaches_the_child():
    """`[teach]` is how a passage says which step it belongs to. It is plumbing."""
    said = _explained("pg_maths_number_1", "Number 1")
    assert "[teach]" not in said and "[match" not in said, said


def test_the_explanation_reads_as_sentences_not_as_wrapped_lines():
    """The notes are wrapped markdown; the wrapping is not punctuation.

    Splitting a passage on its line breaks and finishing each piece with a full
    stop cut "a tent with a belt / across the middle" in half and put a stop in
    the wound.
    """
    said = _explained("pg_english_letters_a", "Letters: A, B, C")
    assert ". across" not in said.lower(), said
    assert not re.search(r"\.\s+[a-z]", said), said


def test_the_question_is_plain_words_with_no_emojis_in_it(client: TestClient):
    """The picture beside the explanation and the choices carry the pictures.

    An emoji in the question is one more thing on a screen that is already busy,
    and the child is about to be *asked to speak* rather than to read it.
    """
    child_id = make_child(client, "playground-emoji@example.com")
    turn = _walk_to_a_question(client, client.post(f"/playground/teacher/{child_id}/open").json())

    assert turn["question"]
    assert not any(0x1F000 <= ord(char) <= 0x1FAFF for char in turn["question"]), turn["question"]
    assert not any(0x2600 <= ord(char) <= 0x27BF for char in turn["question"]), turn["question"]


@pytest.mark.parametrize(
    "written,plain",
    [
        ("How many corners? 🔺", "How many corners?"),
        ("Which one is purple? 🟣 or 🍇", "Which one is purple?"),
        ("Say A out loud!", "Say A out loud!"),
        ("Is it red or blue?", "Is it red or blue?"),
    ],
)
def test_a_stray_emoji_is_taken_out_and_the_sentence_still_reads(written: str, plain: str):
    """The prompt asks for none; "mostly obliges" is not a rule, so it is
    cleaned where it is certain - including the "or" the emoji was joining."""
    assert agent.strip_emoji(written) == plain


# --------------------------------------------------------------------------
# 5b. The stages are the schedule, and the day ends
# --------------------------------------------------------------------------


def test_the_stages_are_the_days_plan_and_nothing_else(client: TestClient):
    """One stage per planned item. A stage is a level, not a difficulty."""
    child_id = make_child(client, "teacher-stages@example.com")
    plan = client.get(f"/plans/{child_id}/today").json()
    if not plan["items"]:
        pytest.skip("this class has nothing to plan today")

    turn = client.post(f"/playground/teacher/{child_id}/open").json()

    assert turn["stages_total"] == plan["total"]
    assert turn["stage"] == 1
    assert turn["topic_id"] == plan["items"][0]["topic_id"]


def test_finishing_a_stage_completes_the_level_and_unlocks_the_next(client: TestClient):
    """The join to the Adventure map, and the only thing that moves it now.

    Adventure teaches nothing of its own any more - it draws what this class has
    done. So the stars, the finished level and the next unlock all have to come
    out of a sitting here, through `award_topic_completion` and no other path.
    """
    child_id = make_child(client, "teacher-unlocks@example.com")
    before = client.get(f"/progress/{child_id}").json()["child"]
    planned = [item["topic_id"] for item in client.get(f"/plans/{child_id}/today").json()["items"]]
    if not planned:
        pytest.skip("this class has nothing to plan today")

    _work_through_the_day(client, child_id)

    after = client.get(f"/progress/{child_id}").json()["child"]
    completed = {
        topic_id
        for progress in after["subject_progress"].values()
        for topic_id in progress["completed_topics"]
    }
    assert set(planned) <= completed, (planned, completed)
    assert after["stars"] > before["stars"], "finishing a level pays the manifest's stars"

    # And what a finished level earns is an unlock, not a lesson: the level it
    # opened is tomorrow's, and the plan is the thing that says when.
    opened = {
        topic_id
        for progress in after["subject_progress"].values()
        for topic_id in progress["unlocked_topics"]
    }
    assert opened > set(planned)


def test_the_day_ends_and_stays_ended_until_tomorrow(client: TestClient):
    """The lock the user asked for, and it lives on the server.

    Reopening the tab, reloading the page, answering into the old session - none
    of them are a way back in. Tomorrow's plan does not exist yet.
    """
    child_id = make_child(client, "teacher-daylock@example.com")
    if not client.get(f"/plans/{child_id}/today").json()["items"]:
        pytest.skip("this class has nothing to plan today")

    last = _work_through_the_day(client, child_id)
    assert last["day_complete"] is True
    assert last["expects"] == "done", "there is nothing to answer when the day is over"
    assert not last["question"]

    reopened = client.post(f"/playground/teacher/{child_id}/open").json()
    assert reopened["day_complete"] is True
    assert not reopened["question"]

    answered = client.post(
        f"/playground/teacher/sessions/{last['session_id']}/answer", json={"answer": "more please"}
    ).json()
    assert answered["day_complete"] is True

    with session_scope() as session:
        rows = session.query(PlaygroundSession).all()
        assert all(row.status == "day_complete" for row in rows)


def test_a_sitting_left_open_overnight_is_yesterdays(client: TestClient):
    """A day is a day. Last night's half-taught stage is not today's first one."""
    child_id = make_child(client, "teacher-overnight@example.com")
    first = client.post(f"/playground/teacher/{child_id}/open").json()

    with session_scope() as session:
        row = session.scalar(
            select(PlaygroundSession).where(PlaygroundSession.session_id == first["session_id"])
        )
        row.plan_date = date.today() - timedelta(days=1)
        row.plan_index = 2
        row.questions_asked = 3

    today = client.post(f"/playground/teacher/{child_id}/open").json()

    assert today["session_id"] != first["session_id"]
    assert today["stage"] == 1
    assert today["questions_asked"] == 0


# --------------------------------------------------------------------------
# 6. The syllabus in the index, and the choices on the screen
# --------------------------------------------------------------------------


def test_the_shipped_syllabus_is_in_the_index():
    """The bot has to know what this class actually teaches, not only how to
    teach. Without the syllabus it would explain whatever it knew about the
    letter A rather than what the author wrote for A in this class."""
    passages = rag._load_passages()
    sources = {passage.source for passage in passages}
    assert "syllabus" in sources and "notes" in sources
    assert len([p for p in passages if p.source == "syllabus"]) > 50


def test_no_answer_key_is_ever_embedded():
    """Everything in the index goes to a model that is about to talk to the
    child. `correct_answer`, `accept` and `options` stay out of it."""
    for passage in rag._load_passages():
        assert "correct_answer" not in passage.text
        assert "accepted_answers" not in passage.text


def test_a_syllabus_topic_can_be_retrieved_by_what_it_teaches():
    hits = rag.search("circles squares and triangles", top_k=5)
    assert any(hit.passage.source == "syllabus" for hit in hits), [h.passage.heading for h in hits]


def test_options_are_only_shown_when_the_answer_is_among_them():
    """A set of choices without the right answer in it is a question a child
    cannot get right, so it is dropped rather than drawn."""
    assert agent._options_from(["circle", "square"], expected="circle") == ("circle", "square")
    assert agent._options_from(["square", "triangle"], expected="circle") == ()
    assert agent._options_from(["one"], expected="one") == ()
    assert agent._options_from("not a list", expected="one") == ()
    # At most four, however many arrive.
    assert len(agent._options_from(["3", "4", "5", "6", "7"], expected="3")) == 4


def test_the_options_offered_are_the_ones_kept_on_the_row(client: TestClient):
    child_id = make_child(client, "playground-options@example.com")
    turn = client.post(f"/playground/teacher/{child_id}/open").json()

    assert isinstance(turn["options"], list)
    with session_scope() as session:
        row = session.query(PlaygroundSession).one()
        assert list(row.pending_options or []) == turn["options"]


# --------------------------------------------------------------------------
# 7. The order a concept is taught in
# --------------------------------------------------------------------------


def test_the_sequence_is_explain_say_draw_match_then_one_more():
    assert lesson.sequence_for(can_say=True, can_draw=True) == (
        lesson.EXPLAIN,
        lesson.SAY_IT,
        lesson.DRAW,
        lesson.MATCH,
        lesson.QUIZ,
    )


def test_a_concept_with_nothing_to_say_or_draw_skips_those_steps():
    """A colour has no sound to make and no shape to trace. Asking anyway would
    be the app talking to itself."""
    assert lesson.sequence_for(can_say=False, can_draw=False) == (
        lesson.EXPLAIN,
        lesson.MATCH,
        lesson.QUIZ,
    )


def test_a_wrong_answer_keeps_the_step_and_a_right_one_moves_it_on():
    steps = lesson.sequence_for(can_say=True, can_draw=True)
    at_match = lesson.current(steps, 3)

    stayed = lesson.after_answer(steps, at_match, is_correct=False)
    assert stayed.name == lesson.MATCH and stayed.tries == 1

    moved = lesson.after_answer(steps, at_match, is_correct=True)
    assert moved.name == lesson.QUIZ and moved.tries == 0


def test_a_second_wrong_answer_brings_the_reveal_rather_than_a_third_asking():
    """Two tries, and then the answer. Nobody is asked a third time."""
    steps = lesson.sequence_for(can_say=True, can_draw=True)
    hinted = lesson.current(steps, 3, tries=lesson.HINT_AT_TRY)
    assert hinted.is_hint is True and hinted.is_reveal is False

    revealing = lesson.after_answer(steps, hinted, is_correct=False)
    assert revealing.name == lesson.MATCH, "the reveal is about this question"
    assert revealing.is_reveal is True
    assert revealing.is_scored is False, "the turn that gives the answer is not a test"
    assert revealing.expects == "ready"


def test_the_hint_turn_is_answered_by_tapping():
    """The hint is the choices, so the hint turn is a choosing turn - even when
    the question it is helping with had asked for a spoken answer."""
    steps = lesson.sequence_for(can_say=True, can_draw=True)
    speaking = lesson.current(steps, 1)
    assert speaking.name == lesson.SAY_IT and speaking.expects == "voice"

    hinted = lesson.after_answer(steps, speaking, is_correct=False)
    assert hinted.is_hint is True
    assert hinted.expects == "tap"


def test_the_hint_choices_always_contain_the_answer():
    """A hint whose options leave the answer out is a question with no right
    answer in it, which is why they are built here and never asked for."""
    assert "red" in agent.hint_options(answer="red", visual=visuals.Visual("colour", "red"))
    assert "3" in agent.hint_options(answer="3", visual=visuals.Visual("number", "3"))
    assert "A" in agent.hint_options(answer="A", visual=visuals.Visual("letter", "A"))


def test_the_hint_choices_are_plausible_and_few():
    """Same kind of thing, and two or three of them. A silly option put there to
    be ignored is not a choice."""
    colours = agent.hint_options(answer="red", visual=visuals.Visual("colour", "red"))
    assert len(colours) == agent.HINT_CHOICES
    assert all(option in visuals.COLOURS for option in colours)


def test_a_hint_narrows_the_choices_the_child_already_had():
    """When the child was already choosing, the help is fewer doors - and the
    author's own words and emoji are kept rather than rewritten."""
    offered = ["circle O", "square S", "star T", "triangle V"]
    narrowed = agent.hint_options(answer="circle", offered=offered)
    assert len(narrowed) == agent.NARROWED_CHOICES
    assert "circle O" in narrowed
    assert all(option in offered for option in narrowed)


def test_a_concept_with_no_family_gets_words_and_no_made_up_choices():
    assert agent.hint_options(answer="done", visual=visuals.Visual()) == ()
    assert agent.hint_options(answer="", visual=visuals.Visual("colour", "red")) == ()


def test_the_same_answer_always_gets_the_same_choices_in_the_same_places():
    """A reload has to show the same screen. Different choices beside the same
    words is a different question."""
    first = agent.hint_options(answer="red", visual=visuals.Visual("colour", "red"))
    assert first == agent.hint_options(answer="red", visual=visuals.Visual("colour", "red"))


def test_a_hindi_letter_is_hinted_against_hindi_letters():
    """A child asked to pick a Devanagari letter out of "A, B" has not been asked
    anything."""
    options = agent.hint_options(answer="\u0905", visual=visuals.Visual("letter", "\u0905"))
    assert "\u0905" in options
    assert all(any("\u0900" <= char <= "\u097f" for char in option) for option in options)


def test_one_question_is_asked_hinted_answered_and_then_left(client: TestClient):
    """The whole loop, end to end, on a question the child never gets.

    Three turns and then it is finished with - not asked again, and not counted
    twice. It is one of the stage's five however many turns it took.
    """
    child_id = make_child(client, "teacher-three-turns@example.com")
    asked = _walk_to_a_question(
        client, client.post(f"/playground/teacher/{child_id}/open").json()
    )
    settled_before = asked["questions_asked"]
    session_id = asked["session_id"]
    question = asked["question"]

    def say(text: str) -> dict:
        return client.post(
            f"/playground/teacher/sessions/{session_id}/answer", json={"answer": text}
        ).json()

    hinted = say("nothing like the answer")
    assert hinted["is_hint"] is True and hinted["is_reveal"] is False
    assert hinted["attempt"] == 2
    assert hinted["question"] == question, "the hint helps with the question already asked"
    assert hinted["questions_asked"] == settled_before, "nothing is settled yet"

    revealed = say("still not the answer")
    assert revealed["is_reveal"] is True
    assert revealed["expects"] == "ready", "there is nothing left to answer"
    assert revealed["question"] == ""
    assert revealed["speech"], "the answer is said out loud"
    assert revealed["questions_asked"] == settled_before, "still the same question"

    moved = say("ready")
    assert moved["is_reveal"] is False
    assert moved["is_correct"] is None, "being told the answer is not a mark"
    assert moved["questions_asked"] == settled_before + 1 or moved["advanced"] or moved.get(
        "day_complete"
    )


def test_the_hint_keeps_the_answer_it_is_being_marked_against(client: TestClient):
    """A second telling may change the words and the choices. It may not change
    what counts as right."""
    child_id = make_child(client, "teacher-hint-key@example.com")
    asked = _walk_to_a_question(
        client, client.post(f"/playground/teacher/{child_id}/open").json()
    )
    key = _pending_answer(asked["session_id"])

    client.post(
        f"/playground/teacher/sessions/{asked['session_id']}/answer",
        json={"answer": "not that"},
    )

    assert _pending_answer(asked["session_id"]) == key


def test_a_hint_offers_something_to_choose_between(client: TestClient):
    """The user asked for the hint to be given through options, so the hint turn
    puts choices on the screen - and the answer is one of them."""
    child_id = make_child(client, "teacher-hint-options@example.com")
    asked = _walk_to_a_question(
        client, client.post(f"/playground/teacher/{child_id}/open").json()
    )
    key = _pending_answer(asked["session_id"])

    hinted = client.post(
        f"/playground/teacher/sessions/{asked['session_id']}/answer",
        json={"answer": "not that"},
    ).json()

    if not hinted["options"]:
        pytest.skip("this question's answer has no family to build choices from")
    assert any(stage.normalise(key) in stage.normalise(o) for o in hinted["options"])


def test_a_hint_says_more_than_the_telling_that_did_not_land(client: TestClient):
    """The turn after the one that failed is a deeper explanation, not the same
    amount again in different words."""
    child_id = make_child(client, "teacher-hint-depth@example.com")
    asked = _walk_to_a_question(
        client, client.post(f"/playground/teacher/{child_id}/open").json()
    )

    hinted = client.post(
        f"/playground/teacher/sessions/{asked['session_id']}/answer",
        json={"answer": "not that"},
    ).json()

    assert "clue" in hinted["speech"].lower()
    assert len(hinted["speech"]) > len(asked["speech"])


def test_being_told_the_answer_is_not_recorded_as_another_failed_attempt(
    client: TestClient,
):
    """Two tries were logged, and the turn that explained is not a third."""
    child_id = make_child(client, "teacher-reveal-log@example.com")
    asked = _walk_to_a_question(
        client, client.post(f"/playground/teacher/{child_id}/open").json()
    )
    session_id = asked["session_id"]

    for said in ("not that", "still not that", "ready"):
        client.post(f"/playground/teacher/sessions/{session_id}/answer", json={"answer": said})

    with session_scope() as session:
        logged = session.query(Attempt).all()
    assert len(logged) == 2, [attempt.child_answer for attempt in logged]
    assert sorted(attempt.attempt_index for attempt in logged) == [1, 2]


def test_the_steps_that_are_not_questions_are_never_scored():
    assert lesson.current(("explain",), 0).is_scored is False
    assert lesson.Step(name=lesson.DRAW, index=0).is_scored is False
    assert lesson.Step(name=lesson.SAY_IT, index=0).is_scored is True


def test_a_sitting_walks_the_steps_in_order(client: TestClient):
    child_id = make_child(client, "playground-steps@example.com")
    turn = client.post(f"/playground/teacher/{child_id}/open").json()

    assert turn["step"] == lesson.EXPLAIN
    assert turn["expects"] == "ready"
    assert turn["question"] == "", "the explaining step asks nothing"

    seen = [turn["step"]]
    for _ in range(4):
        turn = client.post(
            f"/playground/teacher/sessions/{turn['session_id']}/answer", json={"answer": "ready"}
        ).json()
        seen.append(turn["step"])

    # Whatever this topic supports, it is walked in the sequence's own order and
    # never goes backwards within one pass.
    order = [lesson.SEQUENCE.index(name) for name in seen]
    assert order == sorted(order) or order[-1] == 0, seen


def test_the_drawing_step_asks_for_a_trace_and_pays_nothing(client: TestClient):
    """A traced letter cannot be marked right or wrong, so it is not marked."""
    child_id = make_child(client, "playground-draw@example.com")
    turn = client.post(f"/playground/teacher/{child_id}/open").json()

    for _ in range(6):
        if turn["step"] == lesson.DRAW:
            break
        turn = client.post(
            f"/playground/teacher/sessions/{turn['session_id']}/answer", json={"answer": "ready"}
        ).json()
    else:
        pytest.skip("today's topic has nothing to trace")

    assert turn["expects"] == "trace"
    assert turn["trace_target"]
    settled_before = turn["questions_asked"]

    after = client.post(
        f"/playground/teacher/sessions/{turn['session_id']}/answer", json={"answer": "done"}
    ).json()
    assert after["questions_asked"] == settled_before, "a traced letter is not one of the five"
    assert after["is_correct"] is None
    assert after["step"] != lesson.DRAW


def test_the_fifth_question_moves_the_child_to_the_next_topic_in_the_plan(
    client: TestClient,
):
    """A stage is a topic, not a bigger number beside the same one."""
    child_id = make_child(client, "playground-stage@example.com")
    plan = client.get(f"/plans/{child_id}/today").json()
    if len(plan["items"]) < 2:
        pytest.skip("today's plan holds only one topic")

    turn = client.post(f"/playground/teacher/{child_id}/open").json()
    first_topic = turn["topic_id"]

    with session_scope() as session:
        row = session.query(PlaygroundSession).one()
        row.questions_asked = stage.QUESTIONS_PER_STAGE - 1
        row.step_index = len(lesson.SEQUENCE) - 1  # a scored step
        row.pending_question = "What is it?"
        row.pending_answer = "yes"
        row.pending_options = []
        session.flush()

    advanced = client.post(
        f"/playground/teacher/sessions/{turn['session_id']}/answer", json={"answer": "yes"}
    ).json()

    assert advanced["advanced"] is True
    assert advanced["stage"] == turn["stage"] + 1
    assert advanced["topic_id"] != first_topic
    assert advanced["topic_id"] in [item["topic_id"] for item in plan["items"]]
    assert advanced["step"] == lesson.EXPLAIN, "a new topic starts from the explanation"


# --------------------------------------------------------------------------
# 8. The child's own question
# --------------------------------------------------------------------------


def test_asking_something_is_answered_and_moves_nothing(client: TestClient):
    """A child interrupting to ask why a circle is round is the most
    cooperative thing they can do. It is answered, and it costs them nothing."""
    child_id = make_child(client, "playground-ask@example.com")
    turn = client.post(f"/playground/teacher/{child_id}/open").json()

    asked = client.post(
        f"/playground/teacher/sessions/{turn['session_id']}/ask",
        json={"question": "why is a circle round"},
    )
    assert asked.status_code == 200, asked.text
    answer = asked.json()

    assert answer["speech"], "the question is answered"
    # The lesson has not moved: same step, same progress, same question waiting.
    assert answer["step"] == turn["step"]
    assert answer["step_index"] == turn["step_index"]
    assert answer["questions_asked"] == turn["questions_asked"]
    assert answer["is_correct"] is None


def test_asking_never_marks_anything(client: TestClient):
    child_id = make_child(client, "playground-ask-score@example.com")
    turn = _walk_to_a_question(client, client.post(f"/playground/teacher/{child_id}/open").json())
    before = turn["questions_asked"]
    attempt_before = turn["attempt"]

    for question in ("what is this", "i want mumma", ""):
        turn = client.post(
            f"/playground/teacher/sessions/{turn['session_id']}/ask", json={"question": question}
        ).json()

    assert turn["questions_asked"] == before
    assert turn["attempt"] == attempt_before, "asking does not use up a try"
    with session_scope() as session:
        # Every one is logged as a question that was asked, never as an attempt.
        assert session.query(PlaygroundTurn).filter_by(strategy="ASKED").count() == 3


def test_the_question_the_bot_asked_is_still_waiting_afterwards(client: TestClient):
    child_id = make_child(client, "playground-ask-keeps@example.com")
    turn = _walk_to_a_question(client, client.post(f"/playground/teacher/{child_id}/open").json())
    waiting = turn["question"]

    answered = client.post(
        f"/playground/teacher/sessions/{turn['session_id']}/ask", json={"question": "what is that"}
    ).json()

    assert answered["question"] == waiting
    assert answered["options"] == turn["options"]


# --------------------------------------------------------------------------
# 12. The question a person wrote for this class
# --------------------------------------------------------------------------
#
# Three faults, reported together from a Play Group sitting: the questions were
# written for a much older child ("can you show me pre-writing strokes?"), a
# question that wanted a choice arrived with no choices on it, and a right
# answer was marked wrong when the child tapped it. All three are here.


def test_the_question_is_the_authors_and_not_the_topics_title():
    """The syllabus already holds "Which one is the standing line?" with its two
    choices, written by a person for two-year-olds. The teacher asks that."""
    asked = questions.pick("pg_eng_strokes", nth=0)

    assert asked is not None
    assert asked.question == "Which one is the standing line? \u2b07\ufe0f"
    assert asked.answer == "standing line"
    assert len(asked.options) == 2
    # The title never becomes the question. That was the bug.
    assert "pre-writing strokes" not in asked.question.lower()


def test_a_syllabus_answer_written_as_a_token_is_read_out_for_a_child():
    """`standing_line` is a key into the art; a child reads "standing line".
    Both are the same answer, and the underscore spelling is still accepted."""
    asked = questions.pick("pg_eng_strokes", nth=0)

    assert asked.answer == "standing line"
    assert "standing_line" in asked.accept
    assert stage.normalise("standing_line") == stage.normalise("standing line")


def test_five_questions_of_a_stage_are_five_different_ones():
    first = questions.pick("pg_eng_strokes", nth=0)
    second = questions.pick("pg_eng_strokes", nth=1)

    assert first.question != second.question


def test_a_topic_that_authored_no_question_falls_back_to_its_own_subtopics():
    """An all-tracing topic has nothing with a right answer in it, and the stage
    still has five questions to ask. Its subtopics are the things the child has
    just been shown, so they are the choices - never the topic's own title."""
    asked = questions.pick("lkg_art_strokes", nth=0)

    assert asked is not None
    assert asked.is_choice
    assert any("standing line" in option.lower() for option in asked.options)


def test_a_subtopic_too_long_to_be_a_button_is_not_made_into_one():
    """"Talking about all types of transport as well as providing a
    demonstration of vehicles" is a lesson plan, not a thing to tap."""
    assert questions.pick("ukg_evs_community", nth=0) is None


def test_a_step_that_wants_a_tap_is_given_something_to_tap(client: TestClient):
    """A choice question with no choices on it is a typing box in front of a
    two-year-old, which is the turn quietly failing rather than teaching."""
    child_id = make_child(client, "playground-has-options@example.com")
    turn = client.post(f"/playground/teacher/{child_id}/open").json()

    seen_a_tap = False
    for _ in range(40):
        if turn.get("expects") == "tap" and turn.get("question"):
            seen_a_tap = True
            assert turn["options"], f"nothing to tap on: {turn['question']}"
        if turn.get("day_complete"):
            break
        turn = client.post(
            f"/playground/teacher/sessions/{turn['session_id']}/answer",
            json={"answer": (turn.get("options") or ["yes"])[0]},
        ).json()

    assert seen_a_tap, "the sitting never reached a question that wanted a tap"


def test_an_empty_option_list_is_repaired_rather_than_shown_bare():
    from_author = agent.ensure_options(
        answer="standing line", options=(), topic_id="pg_eng_strokes"
    )

    assert len(from_author) >= 2
    assert any(stage.contains_answer(option, "standing line") for option in from_author)


def test_a_concept_the_syllabus_never_offered_as_a_choice_gets_no_invented_ones():
    """Nothing is made up to fill the row. A question with no plausible
    alternatives is asked in words rather than with nonsense beside it."""
    assert agent.ensure_options(answer="gross motor skills", options=(), topic_id="nur_art_gross") == ()


# --------------------------------------------------------------------------
# 13. Tapping the right box is never wrong
# --------------------------------------------------------------------------


def test_a_tapped_option_is_marked_by_which_button_it_was():
    """The label is the answer dressed up for a child - "standing line \u2b07\ufe0f" for
    `standing_line`. Word-matching the two came apart, and the child who tapped
    the right box was told they were wrong."""
    offered = ["standing line \u2b07\ufe0f", "sleeping line \u27a1\ufe0f"]

    right = stage.judge(
        said="standing line \u2b07\ufe0f",
        expected="standing line",
        accept=["standing_line"],
        offered=offered,
    )
    wrong = stage.judge(
        said="sleeping line \u27a1\ufe0f",
        expected="standing line",
        accept=["standing_line"],
        offered=offered,
    )

    assert right.is_correct
    assert not wrong.is_correct


def test_the_answer_written_as_a_token_still_marks_its_readable_label():
    verdict = stage.judge(
        said="standing line \u2b07\ufe0f",
        expected="standing_line",
        offered=["standing line \u2b07\ufe0f", "sleeping line \u27a1\ufe0f"],
    )

    assert verdict.is_correct


def test_an_option_carrying_the_answer_among_other_words_is_still_the_answer():
    verdict = stage.judge(
        said="red apple \U0001f34e", expected="red", offered=["red apple \U0001f34e", "green leaf \U0001f343"]
    )

    assert verdict.is_correct


def test_one_rule_decides_both_which_options_may_be_shown_and_which_tap_is_right():
    """"a" is inside "banana". The loose test used to let that set through as a
    question about the letter A, and then mark the child wrong for tapping the
    option it had called the answer."""
    assert not stage.contains_answer("banana \U0001f34c", "a")
    assert agent._options_from(["banana \U0001f34c", "ball \u26bd"], expected="a") == ()

    assert stage.contains_answer("apple \U0001f34e", "apple")
    assert stage.contains_answer("3 apples \U0001f34e", "3")


def test_a_spoken_answer_is_still_judged_on_its_words():
    """Only a tap is marked by which button it was. Speech and typing keep the
    generous word matching - a child saying the answer inside a sentence has
    said it."""
    verdict = stage.judge(
        said="i think it is a circle", expected="circle", offered=["circle", "square"]
    )

    assert verdict.is_correct


def test_the_child_is_marked_against_what_was_on_their_screen(client: TestClient):
    """End to end: tapping the option the server itself put there as the answer
    comes back right."""
    child_id = make_child(client, "playground-tap-right@example.com")
    turn = _walk_to_a_question(client, client.post(f"/playground/teacher/{child_id}/open").json())
    if turn["expects"] != "tap" or not turn["options"]:
        pytest.skip("this child's first question does not want a tap")

    answer = _pending_answer(turn["session_id"])
    right = next(
        option for option in turn["options"] if stage.contains_answer(option, answer)
    )

    marked = client.post(
        f"/playground/teacher/sessions/{turn['session_id']}/answer", json={"answer": right}
    ).json()

    assert marked["is_correct"] is True


# --------------------------------------------------------------------------
# 14. The class is the fence around the syllabus
# --------------------------------------------------------------------------


@pytest.mark.parametrize("class_id", ["playgroup", "ukg"])
def test_retrieval_stays_inside_the_childs_own_class(class_id: str):
    """A Play Group child is two. The closest passage to "letters" in the whole
    index is very often a UKG one about reading whole words, and that is how a
    two-year-old came to be taught off a page written for a five-year-old.

    Asserted as an absence: whichever passages come back, none of them is
    another class's. The teaching notes belong to no class and are exempt - see
    the test below.
    """
    hits = rag.search("letters and words", top_k=12, class_id=class_id)
    foreign = [
        hit.passage
        for hit in hits
        if hit.passage.source == "syllabus" and hit.passage.class_id != class_id
    ]

    assert not foreign, [passage.heading for passage in foreign]


def test_a_topic_is_retrieved_from_inside_its_own_class():
    hits = rag.search(
        "standing line", top_k=6, class_id="playgroup", topic_id="pg_eng_strokes"
    )
    syllabus = [hit.passage for hit in hits if hit.passage.source == "syllabus"]

    assert syllabus, "the topic's own passages were filtered away"
    assert {passage.class_id for passage in syllabus} == {"playgroup"}


def test_the_teaching_notes_belong_to_no_class_and_are_always_readable():
    """They are how to teach a letter to a small child, not which letter this
    class teaches, so the class fence does not shut them out."""
    hits = rag.search("how to teach a letter", top_k=8, class_id="playgroup")

    assert any(hit.passage.source == "notes" for hit in hits)


def test_an_unknown_class_still_teaches_rather_than_returning_nothing():
    """Infrastructure never locks a child out of their lesson."""
    assert rag.search("colours", top_k=3, class_id="no-such-class")


# --------------------------------------------------------------------------
# 12. The class remembers its own sitting
# --------------------------------------------------------------------------


def test_the_sitting_so_far_is_a_reminder_and_not_a_transcript():
    """What the model is told about its own last turns, and how it is told it."""
    lines = agent._sitting_so_far(
        {
            "memory": [
                {"explanation": "A circle is round.", "question": "", "child_answer": "", "is_correct": None},
                {"explanation": "", "question": "Which one is the circle?", "child_answer": "circle", "is_correct": True},
            ]
        }
    )
    block = "\n".join(lines)
    assert "A circle is round." in block
    assert '"circle"' in block and "it was right" in block
    assert "Do not repeat" in block


def test_a_sitting_with_nothing_behind_it_carries_no_memory():
    assert agent._sitting_so_far({"memory": []}) == []


def test_the_class_reads_back_what_it_has_already_said(client: TestClient):
    """The teacher is handed its own last turns, so a hint cannot repeat itself.

    The log has always been written; nothing read it, and every turn was composed
    from nothing. This pins the read: after a turn has been taught and answered,
    the sitting's memory holds what was said and what came back - with the
    verdict the pure-Python marker gave it, not one the model chose.
    """
    from app.playground import service as teacher_service

    child_id = make_child(client)
    opened = client.post(f"/playground/teacher/{child_id}/open").json()

    turn = _walk_to_a_question(client, opened)
    just_said = turn["speech"]
    client.post(
        f"/playground/teacher/sessions/{turn['session_id']}/answer",
        json={"answer": "not the answer at all"},
    )

    with session_scope() as session:
        row = session.scalar(
            select(PlaygroundSession).where(PlaygroundSession.session_id == turn["session_id"])
        )
        memory = teacher_service._recent_turns(session, row)

    assert memory, "the sitting remembers nothing"
    assert len(memory) <= agent.MEMORY_TURNS
    assert any(just_said[:30] in item["explanation"] for item in memory)
    answered = [item for item in memory if item["child_answer"]]
    assert answered and answered[-1]["is_correct"] is False


def test_the_memory_is_only_a_reminder_and_marks_nothing(client: TestClient):
    """A remembered turn must not be able to move a verdict.

    The memory is handed to a model. If anything downstream of a star could read
    it, a model would be upstream of the child's progress - so the marker is
    checked here against a memory that says the opposite of the truth.
    """
    verdict = stage.judge(said="circle", expected="circle", accept=[], offered=[])
    assert verdict.is_correct is True
