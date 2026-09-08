"""Three games for one level, built out of what a person already wrote for it.

The Adventure map used to hand a level's **notes** back: the author's teaching
lines, printed and read aloud. A grown-up revises by re-reading; a three-year-old
does not, and would not. They play. So a level's page now offers **three games
about that level's own content** - find it, match the pairs, pop the right one -
and the notes are gone from the child's screen.

Everything that kept the notes safe keeps these safe, and for the same reasons:

* **No model, anywhere.** Every question, every choice and every picture token
  here was typed by the person who wrote the syllabus, read through
  `app/playground/questions.py` - the same fenced path the class asks from. The
  same level gives the same three games on every afternoon, which is what makes
  a game worth getting good at.
* **Nothing is marked.** No attempt, no tally, no probe, no policy episode, no
  star, no plan movement. A game is not a performance and losing one costs a
  child nothing. This is the notes rule, and it matters more here, because a
  game *looks* like it should be scored.
* **It plays, it does not open.** No lesson starts from here. The class is
  still the AI Teacher and the schedule still decides when a level is taught;
  this is a level the child has already been given, handed back as something to
  do rather than something to read.
* **The right answer is decided the way the class decides it.**
  `stage.contains_answer` picks which choice is the answer, the same whole-word
  rule that decides which options the class may show and which tap it marks
  right. When those two disagree a child taps the answer in front of them and is
  told they are wrong, which is the one thing a game must never do.

A level that authored too little gets **fewer than three games** rather than an
invented one - the same honesty the notes kept when they said a level had
nothing written down yet.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.playground import questions, stage as stage_rules
from app.services import curriculum_service


logger = logging.getLogger(__name__)

# How many rounds a game may hold. Five is the class's own stage length and it is
# about a minute of play - long enough to be a game, short enough that a child
# who is losing interest reaches the end rather than being rescued from it.
MAX_FIND_ROUNDS = 5
MAX_POP_ROUNDS = 4

# How many different things the matching game may use. Four pairs is eight cards,
# which is the most a four-year-old can hold on one screen without scrolling -
# and a memory game you have to scroll is a memory game you cannot win.
MAX_PAIR_TOKENS = 6
# Two is a real game at this age. A Play Group letter level names exactly two
# pictures - the letter and the thing it starts with - and turning over A and
# then the apple is the whole of what that level teaches. Refusing to deal a
# four-card pack is what left twenty-six of the levels a two-year-old actually
# meets with two games instead of three.
MIN_PAIR_TOKENS = 2

# A pop round needs something to *not* pop. With one bubble there is no choosing.
MIN_POP_OPTIONS = 2

# How many rounds are read out of the level before they are shared out. The
# tapping game takes the first few and the popping game takes the ones after
# them, so a child who plays both is asked about different things - and only
# when the level authored too few does the second game repeat the first.
MAX_ROUNDS_READ = MAX_FIND_ROUNDS + MAX_POP_ROUNDS


@dataclass(frozen=True)
class GameOption:
    """One thing a child can tap.

    `token` is the asset name the author wrote and `label` is what it says on the
    button. The client turns the token into a picture; it draws nothing for a
    token it has no artwork for, which is the rule `visualIcon` keeps for अनार.
    """

    token: str
    label: str


@dataclass(frozen=True)
class GameRound:
    """One asking. `answer` indexes `options` and is never a word match.

    Both the tapping game and the popping game are shaped like this - a question,
    a handful of things, and which of them is right - because they differ in how
    they are *played*, not in what they are about. The client draws them
    differently and neither of them marks anything.
    """

    ask: str
    say: str
    options: tuple[GameOption, ...]
    answer: int


@dataclass(frozen=True)
class LevelGame:
    topic_id: str
    game_id: str
    kind: str
    title: str
    blurb: str
    icon: str
    rounds: tuple[GameRound, ...] = ()
    # The matching game's pack: one token per pair, dealt twice by the client.
    tokens: tuple[str, ...] = ()


@dataclass(frozen=True)
class TopicGames:
    topic_id: str
    title: str
    games: tuple[LevelGame, ...] = field(default_factory=tuple)


def _token_of(label: str) -> str:
    """The asset name behind a choice as it is written on the button.

    An authored option arrives decorated - "standing line ⬇️", "red apple 🍎" -
    because a child reads the picture before the word. The emoji is the author's
    and is kept on the button; the token is what is left of it, which is what the
    client looks a picture up by.
    """
    words = re.sub(r"[^A-Za-z0-9ऀ-ॿ ]+", " ", str(label or ""))
    return re.sub(r"\s+", "_", words.strip()).lower()


def _answer_index(options: tuple[str, ...], answer: str) -> int:
    """Which option *is* the answer, by the class's own rule.

    `stage.contains_answer` and nothing else. A round whose answer is not among
    its options, or is among two of them, is dropped: an unanswerable round is
    worse than a shorter game.
    """
    hits = [index for index, option in enumerate(options) if stage_rules.contains_answer(option, answer)]
    return hits[0] if len(hits) == 1 else -1


def _rounds(topic_id: str, limit: int) -> tuple[GameRound, ...]:
    """The author's choice questions for this level, as rounds of a game."""
    made: list[GameRound] = []
    seen: set[str] = set()
    for authored in questions.for_topic(topic_id):
        if not authored.is_choice or len(made) >= limit:
            continue
        index = _answer_index(authored.options, authored.answer)
        if index < 0:
            continue
        ask = authored.question.strip()
        if not ask or ask in seen:
            continue
        seen.add(ask)
        made.append(
            GameRound(
                ask=ask,
                # What the child hears. The hint comes with it because in a game
                # nobody is being tested - a clue said up front is the whole
                # difference between playing and being examined.
                say=" ".join(part for part in (ask, authored.hint.strip()) if part),
                options=tuple(
                    GameOption(token=_token_of(option), label=option) for option in authored.options
                ),
                answer=index,
            )
        )
    return tuple(made)


def _pictures(topic_id: str) -> tuple[str, ...]:
    """Every picture this level names, in the order the author wrote them.

    The matching pack. Letters, numbers, shapes and colours are all welcome here
    - unlike the class's example strip, which excludes them because there they
    would be an "example" of themselves. In a memory game the letter A *is* the
    thing being matched, which is exactly the point.
    """
    tokens: list[str] = []

    # Two tokens that *draw the same picture* cannot both be in a matching pack:
    # `letter_a` and `a` are both the letter A on the card, so a child turns over
    # two cards that look identical and is told they do not match. The client is
    # what resolves a token to a picture, so this is the same collapsing done
    # server-side - a prefix the resolver drops is dropped here too.
    seen: set[str] = set()

    def add(raw: str) -> None:
        token = _token_of(questions.label(raw))
        if not token:
            return
        drawn = re.sub(r"^(letter|number|hindi)_", "", token)
        if drawn in seen:
            return
        seen.add(drawn)
        tokens.append(token)

    for authored in questions.for_topic(topic_id):
        for item in authored.visual_items:
            add(item)
        add(authored.answer)

    if len(tokens) < MIN_PAIR_TOKENS:
        # Some levels are all tracing and author no question at all, so the loop
        # above finds nothing to match. Their activities still name pictures.
        try:
            for activity in curriculum_service.get_activities(topic_id):
                for item in activity.visual_items or ():
                    add(item)
        except Exception:  # pragma: no cover - a topic id the manifest no longer has
            logger.warning("No authored activities to build a game from for %s", topic_id)

    return tuple(tokens[:MAX_PAIR_TOKENS])


def _find_game(topic_id: str, rounds: tuple[GameRound, ...]) -> LevelGame | None:
    if not rounds:
        return None
    return LevelGame(
        topic_id=topic_id,
        game_id="find",
        kind="find",
        title="Find it!",
        blurb="Listen, then tap the right one.",
        icon="👀",
        rounds=rounds[:MAX_FIND_ROUNDS],
    )


def _pairs_game(topic_id: str, tokens: tuple[str, ...]) -> LevelGame | None:
    if len(tokens) < MIN_PAIR_TOKENS:
        return None
    return LevelGame(
        topic_id=topic_id,
        game_id="pairs",
        kind="pairs",
        title="Find the pairs",
        blurb="Turn two cards over and see if they match.",
        icon="🃏",
        tokens=tokens,
    )


def _pop_game(topic_id: str, rounds: tuple[GameRound, ...]) -> LevelGame | None:
    """The same authored rounds, floating.

    Only rounds with something to leave alone: a bubble field where every bubble
    is right is a field a child cannot get wrong, which is not a game.
    """
    usable = tuple(one for one in rounds if len(one.options) >= MIN_POP_OPTIONS)
    if not usable:
        return None
    return LevelGame(
        topic_id=topic_id,
        game_id="pop",
        kind="pop",
        title="Pop it!",
        blurb="Pop the bubbles with the right one inside.",
        icon="🫧",
        rounds=usable[:MAX_POP_ROUNDS],
    )


def for_topic(topic_id: str) -> TopicGames:
    """The three games this level can offer, and only the ones it really can.

    Read-only in every sense: nothing here writes a row, and playing what it
    returns writes nothing either.
    """
    try:
        topic = curriculum_service.get_topic(topic_id)
        title = topic.title
    except Exception:  # pragma: no cover - a topic id the manifest no longer has
        logger.warning("No such topic to build games for: %s", topic_id)
        return TopicGames(topic_id=topic_id, title="")

    rounds = _rounds(topic_id, MAX_ROUNDS_READ)
    tokens = _pictures(topic_id)
    # The popping game gets what the tapping game did not use, and falls back to
    # the whole list when the level did not author enough to go round.
    spare = rounds[MAX_FIND_ROUNDS:] or rounds
    built = (
        _find_game(topic_id, rounds),
        _pairs_game(topic_id, tokens),
        _pop_game(topic_id, spare),
    )
    return TopicGames(
        topic_id=topic_id,
        title=title,
        games=tuple(game for game in built if game is not None),
    )
