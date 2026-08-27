"""The say-it-back beat, and what the class does with what it hears.

Three things are being pinned down here, and they are the three that would be
easy to break later:

1. **The microphone never opens on an answer key.** The beat runs on teaching
   cards only, and a directive that asks the child to speak carries no correct
   answer for them to read off the screen.
2. **An echo is never a score.** Failing to say "A" out loud does not write an
   attempt, does not cost a star, and does not stop the child doing the
   drawing. It re-explains, twice, and then carries on regardless.
3. **What a child actually says is answered as what it is.** "Pata nahi", the
   question read back, and "I want mumma" are three different things and get
   three different responses - none of which is "wrong".
"""

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.conductor import echo, unexpected
from app.conductor import explain
from app.conductor.explain import ConceptCard
from app.conductor.phases import Phase, teaching_sequence
from app.main import app
from app.services import curriculum_service


SUBJECT_ID = "pg_maths"
FIRST_TOPIC = "pg_maths_colours"


@pytest.fixture()
def authored(tmp_path, monkeypatch):
    """One Play Group topic: a teaching card, then a question.

    It teaches a *number*, because that and the alphabet are the only two things
    the microphone is opened for. The topic id is a real one from the manifest;
    what it contains is ours, and a colour level here would - correctly - never
    reach the beat at all.
    """
    activities_dir = tmp_path / "activities"
    activities_dir.mkdir()
    (activities_dir / f"{SUBJECT_ID}.json").write_text(
        json.dumps(
            {
                "subject_id": SUBJECT_ID,
                "topics": {
                    FIRST_TOPIC: [
                        {
                            "activity_id": f"{FIRST_TOPIC}_intro",
                            "type": "introduce_number",
                            "prompt": "This is 3.",
                            "visual_items": ["number_3"],
                            "hint": "Three like three apples.",
                            "skill_id": "number_3",
                        },
                        {
                            "activity_id": f"{FIRST_TOPIC}_1",
                            "type": "identify_number",
                            "prompt": "Tap 3.",
                            "visual_items": ["number_3", "number_4"],
                            "options": ["3", "4"],
                            "correct_answer": "3",
                            "hint": "3 comes after 2.",
                            "skill_id": "number_3_match",
                        },
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(curriculum_service, "ACTIVITIES_DIR", activities_dir)
    curriculum_service.reload_curriculum()
    yield
    monkeypatch.undo()
    curriculum_service.reload_curriculum()


@pytest.fixture()
def client(authored):
    with TestClient(app) as test_client:
        yield test_client


# The topic id has to be one the manifest declares; what it contains is ours.
LETTER_TOPIC = FIRST_TOPIC


def _letter_activities() -> list[dict]:
    """A real letter level's shape: explained over three cards, then drawn,
    then matched. The beat belongs once, between the third card and the
    drawing."""
    return [
        {
            "activity_id": "let_1",
            "type": "introduce_letter",
            "prompt": "This is A.",
            "visual_items": ["letter_A"],
            "skill_id": "letter_A",
        },
        {
            "activity_id": "let_2",
            "type": "introduce_letter",
            "prompt": "A says 'aa'.",
            "skill_id": "letter_A_sound",
        },
        {
            "activity_id": "let_3",
            "type": "introduce_letter",
            "prompt": "A is for apple.",
            "skill_id": "letter_A_word",
        },
        {
            "activity_id": "let_4",
            "type": "trace",
            "prompt": "Draw A with your finger.",
            "trace_target": "A",
            "hint": "Down, down, and a little belt.",
            "skill_id": "letter_A_write",
        },
        {
            "activity_id": "let_5",
            "type": "match",
            "prompt": "Which one is A?",
            "options": ["A", "B"],
            "correct_answer": "A",
            "skill_id": "letter_A_match",
        },
    ]


@pytest.fixture()
def letter_client(tmp_path, monkeypatch):
    activities_dir = tmp_path / "letters"
    activities_dir.mkdir()
    (activities_dir / f"{SUBJECT_ID}.json").write_text(
        json.dumps({"subject_id": SUBJECT_ID, "topics": {LETTER_TOPIC: _letter_activities()}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(curriculum_service, "ACTIVITIES_DIR", activities_dir)
    curriculum_service.reload_curriculum()
    with TestClient(app) as test_client:
        yield test_client
    monkeypatch.undo()
    curriculum_service.reload_curriculum()


def test_the_class_listens_once_when_the_explaining_is_done(letter_client: TestClient):
    """Explain, explain, explain, listen, draw - in that order, once."""
    directive = letter_client.post(f"/conductor/{_child(letter_client)}/open").json()
    session_id = directive["session_id"]

    seen: list[tuple[str, str]] = []
    for _ in range(20):
        seen.append((directive["phase"], (directive.get("activity") or {}).get("activity_id") or ""))
        if directive["phase"] == "say_it":
            directive = _send(
                letter_client, session_id, kind="voice", answer=directive["listen"]["expect"], confidence=0.95
            )
            continue
        if directive["next_input"]["expects"] != "ready":
            break
        directive = _send(letter_client, session_id, kind="ready")

    say_it_after = [activity_id for phase, activity_id in seen if phase == "say_it"]
    drawn = [activity_id for phase, activity_id in seen if activity_id == "let_4"]
    if not say_it_after:
        pytest.skip("today's plan did not open this topic")

    # Once, on the last explaining card - not after the first one, and never on
    # the drawing.
    assert say_it_after == ["let_3"]
    assert "let_4" not in say_it_after
    # And it happened before the child was asked to draw.
    if drawn:
        assert seen.index(("say_it", "let_3")) < seen.index(("i_do", "let_4"))


# --------------------------------------------------------------------------
# 1. Which subjects stop and listen
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "subject_id", ["pg_english", "nur_maths", "lkg_english", "ukg_maths", "nur_hindi", "ukg_language"]
)
def test_the_alphabet_and_number_subjects_stop_and_listen(subject_id: str):
    """English, maths and the two Hindi subjects.

    Hindi is here because a Hindi level teaches an alphabet - the Devanagari
    letter is the thing being learnt, exactly as A is in English.
    """
    assert echo.subject_speaks(subject_id) is True


@pytest.mark.parametrize("subject_id", ["nur_ga", "nur_evs", "nur_art", "ukg_rhymes", ""])
def test_the_other_subjects_keep_the_microphone_shut(subject_id: str):
    assert echo.subject_speaks(subject_id) is False


@pytest.mark.parametrize("thing", ["A", "b", "Z", "3", "10", "अ", "क", "की"])
def test_a_letter_or_a_number_is_asked_for(thing: str):
    """An alphabet letter - in either script - or a number. "की" is two code
    points and still one letter; counting characters would reject it."""
    assert echo.is_letter_or_number(thing) is True


@pytest.mark.parametrize("thing", ["red", "circle", "apple", "अनार", "", "3 apples"])
def test_anything_that_is_not_a_letter_or_a_number_is_not(thing: str):
    """The beat is for an alphabet and for numbers. A colour or a shape is
    taught by looking and pointing, and "rectangle" said into a browser
    recogniser tests the microphone rather than the child. A whole word is not
    asked for either - अनार is offered beside अ, never instead of it."""
    assert echo.is_letter_or_number(thing) is False
    assert echo.target_for(ConceptCard(symbol=thing, word="something")).is_askable is False


def test_the_beat_is_added_after_i_do_and_only_on_a_teaching_card():
    assert teaching_sequence(lesson_flow="pool", needs_answer=False, echo=True) == (
        Phase.I_DO,
        Phase.SAY_IT,
    )
    # A question keeps its own sequence: an open microphone next to an answer
    # key is the one thing this feature must never build.
    assert Phase.SAY_IT not in teaching_sequence(lesson_flow="pool", needs_answer=True, echo=True)
    assert Phase.SAY_IT not in teaching_sequence(lesson_flow="complete", needs_answer=True, echo=True)
    assert teaching_sequence(lesson_flow="pool", needs_answer=False, echo=False) == (Phase.I_DO,)


# --------------------------------------------------------------------------
# 2. What counts as having said it
# --------------------------------------------------------------------------


def _target() -> echo.EchoTarget:
    return echo.target_for(ConceptCard(symbol="A", sound="aa", word="apple"))


def test_the_thing_its_sound_and_its_word_all_count():
    target = _target()
    for said in ("a", "aa", "apple", "A"):
        assert echo.judge(heard=said, confidence=0.9, target=target).landed, said


def test_a_near_miss_from_a_three_year_old_counts():
    # "appul" is a child saying apple. Marking that as not-said would teach them
    # that speaking up is risky.
    assert echo.judge(heard="appul", confidence=0.9, target=_target()).landed


def test_something_else_entirely_does_not_count_but_is_not_wrong():
    verdict = echo.judge(heard="elephant", confidence=0.9, target=_target())
    assert verdict.outcome == "unmatched"
    assert verdict.landed is False


def test_silence_and_noise_are_a_microphone_problem_not_an_answer():
    assert echo.judge(heard="", confidence=0.9, target=_target()).outcome == "no_speech"
    assert echo.judge(heard="a", confidence=0.1, target=_target()).outcome == "no_speech"


def test_a_card_with_nothing_to_say_back_is_never_asked():
    assert echo.target_for(ConceptCard()).is_askable is False


# --------------------------------------------------------------------------
# 2b. Hindi, where the thing being said is Devanagari
# --------------------------------------------------------------------------


def test_a_hindi_letter_can_be_said_back():
    """अ is asked for, and अनार counts as having said it.

    No browser recogniser reliably transcribes an isolated vowel, so the word is
    offered beside the letter and either one counts - which is also how the
    level teaches it: "अ से अनार".
    """
    target = echo.target_for(ConceptCard(symbol="अ", word="अनार"))
    assert target.is_askable
    assert echo.judge(heard="अ", confidence=0.9, target=target).landed
    assert echo.judge(heard="अनार", confidence=0.9, target=target).landed
    # A different letter is still not a match.
    assert not echo.judge(heard="आ", confidence=0.9, target=target).landed


def test_a_hindi_word_keeps_its_matras():
    r"""`\w` deletes Devanagari's combining vowel signs, which turns अनार into a
    different word entirely. Losing them made a correct answer unrecognisable."""
    target = echo.target_for(ConceptCard(symbol="अ", word="अनार"))
    assert "अनार" in target.accepted
    assert "अनर" not in target.accepted


def test_the_guide_asks_for_the_hindi_letter_in_an_english_sentence():
    """Narration is English with the Devanagari quoted inside it - never a whole
    sentence in Hindi, and never the letter transliterated into Roman."""
    asked = echo.ask(echo.target_for(ConceptCard(symbol="अ", word="अनार")))
    assert "अ" in asked
    assert asked.startswith("Now your turn")


def test_a_hindi_utterance_still_survives_being_tokenised():
    """A child may still say something in Hindi on any card, so the classifier
    that decides what an utterance *was* keeps its Devanagari handling."""
    assert unexpected._tokens("अनार क्या है") == [
        "अनार",
        "क्या",
        "है",
    ]


# --------------------------------------------------------------------------
# 3. Unexpected utterances
# --------------------------------------------------------------------------


def test_an_option_on_the_screen_is_always_an_answer():
    # "No" on a yes/no question is a choice. The classifier must hand it back
    # rather than read it as a refusal.
    assert unexpected.classify("no", options=["yes", "no"]).kind == "answer"
    assert unexpected.classify("stop", options=["stop", "go"]).kind == "answer"


@pytest.mark.parametrize("said", ["i dont know", "pata nahi", "nahi pata", "dunno"])
def test_i_dont_know_is_shown_rather_than_asked_again(said: str):
    heard = unexpected.classify(said, options=["a", "b"])
    assert heard.kind == "dont_know"
    assert heard.action == unexpected.TOGETHER
    assert heard.blameless


def test_a_child_who_wants_their_mother_is_allowed_to_stop():
    heard = unexpected.classify("i want mumma", options=["a", "b"])
    assert heard.kind == "distress"
    assert heard.action == unexpected.END_KINDLY


def test_asking_for_it_again_gets_it_again():
    assert unexpected.classify("again", options=["a", "b"]).action == unexpected.REPEAT


def test_reading_the_question_out_loud_is_not_an_answer():
    heard = unexpected.classify(
        "which one is the red one",
        options=["circle", "square"],
        prompt="Which one is the red one?",
    )
    assert heard.kind == "read_the_question"


def test_a_long_story_is_lovely_and_still_not_an_answer():
    heard = unexpected.classify(
        "my dog ran in the garden and then he jumped very high",
        options=["circle", "square"],
    )
    assert heard.kind == "chatter"
    assert heard.blameless


def test_every_kind_is_blameless_and_carries_words_for_the_child():
    for said in ("", "pata nahi", "again", "elephant", "i want mumma", "umm"):
        heard = unexpected.classify(said, options=["circle", "square"])
        assert heard.blameless
        if heard.kind != "answer":
            assert heard.reply.strip()


# --------------------------------------------------------------------------
# 4. The whole beat, through the conductor
# --------------------------------------------------------------------------


def _child(client: TestClient) -> str:
    auth = client.post(
        "/auth/register", json={"name": "P", "email": "sayit@example.com", "password": "demo1234"}
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


def _send(client: TestClient, session_id: str, **payload) -> dict:
    response = client.post(f"/conductor/sessions/{session_id}/input", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _run_to_say_it(client: TestClient) -> dict:
    directive = client.post(f"/conductor/{_child(client)}/open").json()
    for _ in range(12):
        if directive["phase"] == "say_it":
            return directive
        if directive["next_input"]["expects"] != "ready":
            break
        directive = _send(client, directive["session_id"], kind="ready")
    pytest.skip("today's plan opened on a subject that does not listen")


def test_the_class_explains_then_asks_the_child_to_say_it(client: TestClient):
    directive = _run_to_say_it(client)

    assert directive["next_input"]["expects"] == "voice"
    assert directive["listen"]["active"] is True
    assert directive["listen"]["expect"]
    assert directive["speech"]["text"]
    # No "next" button, and no waiting forever either.
    assert directive["auto_advance_in_ms"] is None


def test_the_microphone_is_never_open_next_to_an_answer_key(client: TestClient):
    directive = _run_to_say_it(client)

    assert directive["activity"]["correct_answer"] is None
    assert directive["activity"]["accept"] == []
    expect = directive["listen"]["expect"].lower()
    # What the child is asked to say is the thing that was just explained, and
    # the card it was explained from has no answer to give away.
    assert expect and expect in " ".join(directive["listen"]["contextual_strings"]).lower()


def test_saying_it_moves_the_class_on(client: TestClient):
    directive = _run_to_say_it(client)
    session_id = directive["session_id"]

    after = _send(
        client, session_id, kind="voice", answer=directive["listen"]["expect"], confidence=0.95
    )
    assert after["phase"] != "say_it"
    assert after["close"] is None or after["close"]["reason"] != "end_kindly"


def test_not_saying_it_re_explains_once_and_then_carries_on_anyway(client: TestClient):
    """One ask, whatever comes back.

    The child is asked to say something back once in a sitting. An echo that did
    not land is answered by explaining the thing again in different words - and
    then the class carries on to the next beat rather than reopening the
    microphone, which is the difference between a moment the child answers and a
    checkpoint they have to get past.
    """
    directive = _run_to_say_it(client)
    session_id = directive["session_id"]

    again = _send(client, session_id, kind="voice", answer="elephant", confidence=0.9)
    # Explained again rather than marked wrong, and the question is not scored.
    assert again["phase"] == "i_do"
    assert again["heard_as"] == "off_topic"

    # And it never walks back into the beat: the rest of the sitting is taught
    # and answered, with no second microphone anywhere in it.
    phases = [again["phase"]]
    for _ in range(20):
        if again["next_input"]["expects"] != "ready":
            break
        again = _send(client, session_id, kind="ready")
        phases.append(again["phase"])
    assert "say_it" not in phases
    assert again["listen"]["active"] is False


def test_an_echo_never_costs_a_star(client: TestClient):
    child_id = _child(client)
    directive = client.post(f"/conductor/{child_id}/open").json()
    session_id = directive["session_id"]
    for _ in range(12):
        if directive["phase"] == "say_it":
            break
        if directive["next_input"]["expects"] != "ready":
            pytest.skip("today's plan opened on a subject that does not listen")
        directive = _send(client, session_id, kind="ready")
    else:  # pragma: no cover - the loop finds the beat or skips above
        pytest.skip("today's plan opened on a subject that does not listen")

    before = client.get(f"/children/{child_id}").json()
    _send(client, session_id, kind="voice", answer="elephant", confidence=0.9)
    after = client.get(f"/children/{child_id}").json()

    assert after["stars"] == before["stars"]


def test_a_child_who_asks_to_stop_is_not_argued_with(client: TestClient):
    directive = _run_to_say_it(client)

    closing = _send(
        client, directive["session_id"], kind="voice", answer="i want mumma", confidence=0.9
    )
    assert closing["close"] is not None
    assert closing["close"]["reason"] == "end_kindly"
    assert closing["heard_as"] == "distress"


# --------------------------------------------------------------------------
# 5. The client's whole loop, walked with no client decisions
# --------------------------------------------------------------------------


def test_a_whole_sitting_walks_on_directive_fields_alone(letter_client: TestClient):
    """`useConductorClass` reads five fields and nothing else.

    This walks a sitting the way the app does - speak, then do what
    `next_input.expects` says, then report - and asserts it reaches `close`
    without the caller ever deciding anything: no picking the next activity, no
    checking an answer, no choosing when to open the microphone.
    """
    directive = letter_client.post(f"/conductor/{_child(letter_client)}/open").json()
    session_id = directive["session_id"]

    phases: list[str] = []
    for _ in range(60):
        phases.append(directive["phase"])

        # Every directive must be renderable and answerable from its own fields.
        assert directive["speech"]["text"], f"nothing to say in {directive['phase']}"
        assert directive["session_id"] == session_id

        if directive["close"]:
            break

        expects = directive["next_input"]["expects"]
        if expects == "voice":
            # The microphone opens because `listen.active` says so - the client
            # never works out for itself that it is the child's turn to speak.
            assert directive["listen"]["active"] is True
            directive = _send(
                letter_client,
                session_id,
                kind="voice",
                answer=directive["listen"]["expect"],
                confidence=0.95,
            )
        elif expects == "ready":
            # The guide is talking. The class carries on by itself - this is
            # where the "next" button used to be.
            assert directive["auto_advance_in_ms"] is not None
            directive = _send(letter_client, session_id, kind="ready")
        elif expects == "tap":
            assert directive["auto_advance_in_ms"] is None
            options = directive["scaffold"]["options_shown"] or directive["activity"]["options"]
            assert options, "asked for a tap with nothing to tap"
            directive = _send(letter_client, session_id, kind="tap", answer=options[0])
        else:  # trace
            directive = _send(letter_client, session_id, kind="trace", answer="done")
    else:  # pragma: no cover - a sitting that never ends is the failure
        raise AssertionError(f"the class never closed; phases were {phases}")

    assert directive["close"] is not None
    assert "i_do" in phases


def test_the_answer_key_never_reaches_the_client_at_any_point(letter_client: TestClient):
    """Walked over a whole sitting, not just the first question."""
    directive = letter_client.post(f"/conductor/{_child(letter_client)}/open").json()
    session_id = directive["session_id"]

    for _ in range(60):
        activity = directive.get("activity")
        if activity:
            assert activity["correct_answer"] is None
            assert activity["accept"] == []
        if directive["close"]:
            break

        expects = directive["next_input"]["expects"]
        if expects == "voice":
            directive = _send(
                letter_client, session_id, kind="voice", answer=directive["listen"]["expect"], confidence=0.95
            )
        elif expects == "ready":
            directive = _send(letter_client, session_id, kind="ready")
        elif expects == "tap":
            options = directive["scaffold"]["options_shown"] or directive["activity"]["options"]
            directive = _send(letter_client, session_id, kind="tap", answer=options[0])
        else:
            directive = _send(letter_client, session_id, kind="trace", answer="done")


# --------------------------------------------------------------------------
# 6. The taught word is never spelled in Roman letters
# --------------------------------------------------------------------------


def test_a_hindi_picture_token_is_spoken_in_devanagari():
    """Hindi levels name their pictures with asset tokens - "anar", "aam".

    Speaking the token made the guide say "Tap anar": a Hindi word in Roman
    letters, which is the one thing this project's narration rule forbids. The
    Devanagari is read back out of the author's own prompt.
    """
    assert (
        explain.spoken_form("anar", prompt="अ से अनार। अनार कौन सा है?")
        == "अनार"
    )
    assert explain.spoken_form("aam", prompt="आ से आम। आम कौन सा है?") == "आम"


def test_the_sentence_ending_danda_is_not_read_as_part_of_the_word():
    """। sits inside the Devanagari block, so a naive filter keeps it and the
    guide says a full stop in the middle of its own sentence."""
    assert "।" not in explain.spoken_form("anar", prompt="अ से अनार।")


def test_english_concepts_and_devanagari_answers_pass_through_untouched():
    assert explain.spoken_form("red", prompt="Tap the red one.") == "red"
    assert explain.spoken_form("अ", prompt="अ पर उँगली रखो।") == "अ"
    # No authored Devanagari to read the word out of: the token is returned as
    # it is rather than a spelling being invented for it.
    assert explain.spoken_form("anar", prompt="Which one is it?") == "anar"


# --------------------------------------------------------------------------
# 7. A tap is never asked for when there is nothing to tap
# --------------------------------------------------------------------------


def test_a_spoken_card_keeps_the_microphone_even_after_dropping_to_taps():
    """Found by walking a real Hindi sitting against a running server.

    Two silences on the say-it beat correctly put the microphone away and set
    the sitting to taps. Several activities later the lesson reached
    `repeat_letter` - a card whose whole answer is spoken, and which therefore
    carries no options - and asked the child to tap. There was nothing on the
    screen to tap and no way forward: a dead end, at the end of a lesson the
    child had otherwise finished.
    """
    from app.conductor.phases import Phase
    from app.schemas.learning import Activity
    from app.services.conductor_service import _expected_input

    spoken = Activity(
        activity_id="x", type="repeat_letter", prompt="p", options=[],
        correct_answer="अ", answer_kind="spoken",
    )
    choice = Activity(
        activity_id="y", type="select_letter", prompt="p", options=["अ", "आ"],
        correct_answer="अ", answer_kind="choice",
    )

    # Nothing to tap: the microphone stays, and the idle ladder remains the way
    # out if it genuinely cannot hear them.
    assert _expected_input(spoken, "tap", Phase.YOU_DO) == "voice"
    assert _expected_input(spoken, "voice", Phase.YOU_DO) == "voice"
    # A card with options still honours the switch to taps, as it always did.
    assert _expected_input(choice, "tap", Phase.YOU_DO) == "tap"


# --------------------------------------------------------------------------
# 8. A Hindi level teaches two letters, and each card gets its own
# --------------------------------------------------------------------------


def test_each_item_is_introduced_with_its_own_letter():
    """`nur_hindi_swar_a_aa` teaches अ and then आ inside one topic.

    Reading the concept from the whole topic always found अ - it is first - so
    every card in the second half was introduced with the first half's letter:
    "This is अ. अ is for अनार." said in front of a question about आम. The
    question was right and the teaching in front of it was about something else.
    """
    from app.services import curriculum_service

    topic = curriculum_service.get_topic("nur_hindi_swar_a_aa")
    activities = curriculum_service.get_activities("nur_hindi_swar_a_aa")
    scripts = {item.activity_id: explain.script_for(topic, item, activities) for item in activities}

    for activity_id, line in scripts.items():
        if activity_id.startswith("nur_hin_906"):
            assert "आ" in line, (activity_id, line)
            # The other letter must not be what this card teaches.
            assert "अनार" not in line, (activity_id, line)


def test_a_spoken_card_says_say_and_a_tapped_one_says_tap():
    """The microphone was opening on `repeat_letter` while the guide said
    "Tap अ" - pointing a child at something that was not on the screen."""
    from app.services import curriculum_service

    topic = curriculum_service.get_topic("nur_hindi_swar_a_aa")
    activities = curriculum_service.get_activities("nur_hindi_swar_a_aa")
    by_id = {item.activity_id: item for item in activities}

    spoken = explain.script_for(topic, by_id["nur_hin_905_4"], activities)
    assert "Say" in spoken and "Tap" not in spoken, spoken

    tapped = explain.script_for(topic, by_id["nur_hin_905_2"], activities)
    assert "Tap" in tapped, tapped


def test_a_picture_question_asks_for_its_own_picture():
    """It asked "Tap अ" - the topic's letter - on a card whose answer is अनार."""
    from app.services import curriculum_service

    topic = curriculum_service.get_topic("nur_hindi_swar_a_aa")
    activities = curriculum_service.get_activities("nur_hindi_swar_a_aa")
    by_id = {item.activity_id: item for item in activities}

    line = explain.script_for(topic, by_id["nur_hin_905_3"], activities)
    assert "अनार" in line, line


# --------------------------------------------------------------------------
# 9. The ask has to be something a recogniser can actually catch
# --------------------------------------------------------------------------


def test_the_ask_offers_the_word_beside_the_letter():
    """No browser recogniser reliably transcribes an isolated letter.

    "A" is a third of a second of sound and comes back as silence over and over,
    while the same child saying a whole word is transcribed perfectly - which is
    exactly what was reported. A word gives the recogniser something to catch,
    and the letter, its sound and its word all count as having said it, so the
    child is not being asked for more than before.
    """
    letter = echo.target_for(ConceptCard(symbol="A", sound="aa", word="apple"))
    first = echo.ask(letter)
    assert "A" in first and "apple" in first, first

    second = echo.ask(letter, attempt=1)
    assert "apple" in second and second != first


def test_either_the_letter_or_the_word_counts_as_having_said_it():
    target = echo.target_for(ConceptCard(symbol="A", sound="aa", word="apple"))
    assert echo.judge(heard="A", confidence=0.9, target=target).landed
    assert echo.judge(heard="apple", confidence=0.9, target=target).landed
    # Both are offered to the recogniser as hints, too.
    assert "apple" in target.contextual_strings


def test_a_concept_with_no_word_still_asks_for_the_thing_itself():
    """Numbers and colours are taught without a "X is for Y" word."""
    target = echo.target_for(ConceptCard(symbol="3"))
    assert echo.ask(target) == "Now your turn. Can you say 3?"


def _two_letter_activities() -> list[dict]:
    """A level that teaches two letters, each explained then drawn then matched."""
    cards: list[dict] = []
    for letter, word in (("A", "apple"), ("B", "ball")):
        cards += [
            {
                "activity_id": f"two_{letter}_1",
                "type": "introduce_letter",
                "prompt": f"This is {letter}.",
                "visual_items": [f"letter_{letter}"],
                "skill_id": f"letter_{letter}",
            },
            {
                "activity_id": f"two_{letter}_2",
                "type": "introduce_letter",
                "prompt": f"{letter} is for {word}.",
                "skill_id": f"letter_{letter}_word",
            },
            {
                "activity_id": f"two_{letter}_3",
                "type": "match",
                "prompt": f"Which one is {letter}?",
                "options": [letter, "Z"],
                "correct_answer": letter,
                "skill_id": f"letter_{letter}_match",
            },
        ]
    return cards


@pytest.fixture()
def two_letter_client(tmp_path, monkeypatch):
    activities_dir = tmp_path / "two_letters"
    activities_dir.mkdir()
    (activities_dir / f"{SUBJECT_ID}.json").write_text(
        json.dumps({"subject_id": SUBJECT_ID, "topics": {LETTER_TOPIC: _two_letter_activities()}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(curriculum_service, "ACTIVITIES_DIR", activities_dir)
    curriculum_service.reload_curriculum()
    with TestClient(app) as test_client:
        yield test_client
    monkeypatch.undo()
    curriculum_service.reload_curriculum()


def test_a_sitting_asks_for_a_voice_once_however_many_things_it_teaches(
    two_letter_client: TestClient,
):
    """One microphone per lesson, near the start - not one per thing taught.

    This level explains two letters, so the beat used to happen twice: once when
    A had been explained and again when B had. The child is asked once, at the
    beginning, and the rest of the lesson is taught and answered without the
    microphone coming back.
    """
    session = two_letter_client.post(f"/conductor/{_child(two_letter_client)}/open").json()
    session_id = session["session_id"]

    listened_on: list[str] = []
    seen_cards: list[str] = []
    directive = session
    for _ in range(30):
        seen_cards.append((directive.get("activity") or {}).get("activity_id") or "")
        if directive["phase"] == "say_it":
            listened_on.append((directive.get("activity") or {}).get("activity_id") or "")
            directive = _send(
                two_letter_client,
                session_id,
                kind="voice",
                answer=directive["listen"]["expect"],
                confidence=0.95,
            )
            continue
        expects = directive["next_input"]["expects"]
        if expects == "ready":
            directive = _send(two_letter_client, session_id, kind="ready")
            continue
        if expects == "tap" and directive.get("activity"):
            # Answer the question so the lesson reaches the second letter.
            options = directive["scaffold"]["options_shown"] or directive["activity"]["options"]
            directive = _send(two_letter_client, session_id, kind="tap", answer=options[0])
            continue
        break

    if not listened_on:
        pytest.skip("today's plan did not open this topic")
    # The lesson really did carry on into the second letter - otherwise "asked
    # once" would only mean the walk stopped early.
    assert any(card.startswith("two_B") for card in seen_cards), seen_cards
    assert listened_on == ["two_A_2"], listened_on


def test_the_class_stops_and_waits_while_the_child_draws(letter_client: TestClient):
    """Explain, say it, draw - and the drawing gets its own turn.

    The writing card cannot be graded, so it evaluates as presentational, and
    that used to mean the class showed it for a few seconds and moved on by
    itself. The child never got to draw. It waits now: the beat asks for a
    trace and offers no auto-advance, and finishing it still scores nothing.
    """
    child_id = _child(letter_client)
    directive = letter_client.post(f"/conductor/{child_id}/open").json()
    session_id = directive["session_id"]

    drawing = None
    for _ in range(20):
        if directive["next_input"]["expects"] == "trace":
            drawing = directive
            break
        if directive["phase"] == "say_it":
            directive = _send(
                letter_client, session_id, kind="voice", answer=directive["listen"]["expect"], confidence=0.95
            )
            continue
        if directive["next_input"]["expects"] != "ready":
            break
        directive = _send(letter_client, session_id, kind="ready")

    if drawing is None:
        pytest.skip("today's plan did not open this topic")

    assert drawing["activity"]["activity_id"] == "let_4"
    # Nothing carries the class past this on a timer, and the microphone is shut.
    assert drawing["auto_advance_in_ms"] is None
    assert drawing["listen"]["active"] is False

    stars_before = letter_client.get(f"/progress/{child_id}/rewards").json()["stars"]
    after = _send(letter_client, session_id, kind="trace", answer="A")
    # Drawing it moves the class on, and is not marked: no star for a finger.
    assert after["next_input"]["expects"] != "trace"
    assert letter_client.get(f"/progress/{child_id}/rewards").json()["stars"] == stars_before
    assert not [
        attempt
        for attempt in letter_client.get(f"/history/{child_id}").json()["attempts"]
        if attempt.get("activity_id") == "let_4"
    ]
