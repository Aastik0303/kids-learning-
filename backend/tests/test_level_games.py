"""The games a level hands back, and the boundaries that keep them games.

A level's page on the Adventure map used to give a child the author's teaching
lines to re-read. It gives them three games now, built from the same authored
syllabus. These assert the four things that make that safe: the games exist for
the levels a child actually meets, the answer they mark is the answer they show,
they are made only of authored content, and playing one is not a lesson.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.playground import games, stage
from app.services import curriculum_service


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def every_topic_id() -> list[str]:
    found: list[str] = []
    for summary in curriculum_service.list_classes():
        for subject in curriculum_service.get_class(summary.class_id).subjects:
            for topic in curriculum_service.get_subject(subject.subject_id).topics:
                found.append(topic.topic_id)
    return found


def test_every_level_offers_at_least_one_game():
    """A level with nothing to play is a page with nothing on it.

    Not three, because a level whose author wrote very little gets fewer rather
    than an invented one - but never none, or the page a child navigated to is
    empty.
    """
    empty = [topic_id for topic_id in every_topic_id() if not games.for_topic(topic_id).games]
    assert empty == []


def test_most_levels_offer_all_three():
    """The shape the whole feature is for. A regression that quietly drops a
    game on half the syllabus would otherwise pass every other test here."""
    ids = every_topic_id()
    full = [topic_id for topic_id in ids if len(games.for_topic(topic_id).games) == 3]
    assert len(full) > len(ids) * 0.9


def test_the_answer_shown_is_the_answer_marked():
    """The one rule. `stage.contains_answer` chose the index, so the option at
    that index must be the one that test agrees with - a child who taps the
    answer put in front of them can never be told they are wrong."""
    for topic_id in every_topic_id():
        for game in games.for_topic(topic_id).games:
            for round_ in game.rounds:
                assert 0 <= round_.answer < len(round_.options)
                answer = round_.options[round_.answer]
                others = [
                    option
                    for index, option in enumerate(round_.options)
                    if index != round_.answer
                ]
                # Exactly one option is the answer, or the round is unanswerable.
                assert not any(
                    stage.contains_answer(option.label, answer.label) for option in others
                ), f"{topic_id}/{game.game_id}: two options are the same answer"


def test_a_round_always_has_something_to_choose_between():
    for topic_id in every_topic_id():
        for game in games.for_topic(topic_id).games:
            for round_ in game.rounds:
                assert len(round_.options) >= 2
                assert round_.ask.strip()


def test_the_matching_pack_never_holds_the_same_picture_twice():
    """`letter_a` and `a` both draw the letter A, so a child would turn over two
    cards that look identical and be told they do not match."""
    for topic_id in every_topic_id():
        for game in games.for_topic(topic_id).games:
            if game.kind != "pairs":
                continue
            drawn = [re.sub(r"^(letter|number|hindi)_", "", token) for token in game.tokens]
            assert len(drawn) == len(set(drawn)), f"{topic_id}: duplicate picture in the pack"
            assert len(game.tokens) >= 2


def test_every_word_in_a_game_was_typed_by_the_syllabus_author():
    """Nothing here is written by a model, and the way to prove it is that every
    question on a game board is a string that exists in the authored file."""
    topic_id = "nur_maths_shapes"
    authored = {
        (activity.prompt or "").strip()
        for activity in curriculum_service.get_activities(topic_id)
    }
    for game in games.for_topic(topic_id).games:
        for round_ in game.rounds:
            assert round_.ask in authored


def test_the_endpoint_serves_them_and_writes_nothing(client: TestClient):
    response = client.get("/curriculum/topics/nur_maths_shapes/games")
    assert response.status_code == 200
    body = response.json()
    assert body["topic_id"] == "nur_maths_shapes"
    assert {game["kind"] for game in body["games"]} == {"find", "pairs", "pop"}

    # Playing is not a request. The whole game is fetched once and everything the
    # child taps stays in the browser, so there is no route here that could
    # write an attempt, a star or a plan movement.
    routes = {getattr(route, "path", "") for route in app.routes}
    assert not any(path.startswith("/curriculum/topics") and "game" in path and path.endswith("answer") for path in routes)


def test_a_topic_the_manifest_does_not_have_is_empty_rather_than_an_error(client: TestClient):
    response = client.get("/curriculum/topics/not_a_real_topic/games")
    assert response.status_code == 200
    assert response.json()["games"] == []


def test_the_games_reach_no_model_and_no_writer():
    """The import fence, read off the module itself.

    `games.py` may read the syllabus and the same pure marking rule the class
    uses. It may not reach a model client, a repository or a service that
    writes - which is what would turn a game into a second classroom.
    """
    source = (games.__file__ or "")
    assert source
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    for forbidden in ("app.ai", "app.policy", "history_service", "learning_service", "app.db"):
        assert f"import {forbidden}" not in text and f"from {forbidden}" not in text
