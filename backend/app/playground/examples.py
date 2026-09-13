"""The pictures a child looks at instead of reading the explanation.

The AI Teacher writes three or four sentences for every teaching turn - what the
thing is, said again in other words, and something the child has seen for
themselves. All of that is for the **ear**: the guide says it out loud. On the
screen it was a wall of prose in front of a two-year-old who cannot read a word
of it, sitting where the one thing they *can* use should be.

So the words stay spoken and the screen shows the example instead: the two or
three everyday things the author themselves named beside this level -
`apple` for the letter A, `ball` for a circle, `tomato` for red - which the
client draws as pictures. Nothing here is written by a model and nothing is
invented: the tokens come out of `visual_items` in the authored activities, and
a level whose author named nothing shows no example rather than a made-up one.
That is the same rule `agent.EVERYDAY_EXAMPLES` keeps for the spoken sentence.

**An example may never be the answer.** These pictures sit beside the question,
so a level teaching red whose question is "tap the red one" must not show an
apple as its example while the apple is the thing to tap. Every candidate is put
through `stage.contains_answer` - the one function that decides both what may be
shown as a choice and what counts as right - against the answer the server is
holding and the choices already on the screen, and anything that matches is
dropped.

**An example belongs to the concept on the card, not to the level.** A shapes
level names a ball beside its circle and nothing at all beside its square, and
this used to fall back to the rest of the level and draw the ball on the square
card - beside the question "tap the square!", whose other choice was the circle.
A round thing next to that question is worse than an empty board twice over: it
is not an example of what is being taught, and it is a picture of the wrong
answer. So the author's own grouping is the boundary. When the card names a
concept, an authored example has to come from an activity that names that same
concept; the rest of the level is only ever read for a card that names no
concept at all, and even then an activity that teaches one of the choices on
screen is skipped whole.

When the author grouped no everyday thing with the concept, the picture falls
back to `_CONCEPT_PICTURES` - the same hand-written everyday example the teacher
is already saying out loud from `agent.EVERYDAY_EXAMPLES`, as asset tokens. That
is not an invented example: it is the sentence the child is hearing, drawn. It
is hand-written and closed, it covers only the shapes and colours the app can
actually draw, and a concept missing from it shows nothing.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

from app.playground import stage as stage_rules
from app.playground import visuals
from app.services import curriculum_service
from app.services import cache


logger = logging.getLogger(__name__)


# How many pictures a child can take in beside a question. Three is the most any
# authored activity names, and more than three is a row to scan rather than an
# example to glance at.
MAX_ITEMS = 3

# Tokens that are the *lesson* rather than an example of it. A card teaching the
# letter A already draws a big A; naming it again beside itself teaches nothing
# and costs the space the example is there to fill.
_KIND_PREFIXES = ("letter", "number", "shape", "colour", "color")

# An asset token that is a picture of nothing in particular. These are drawn as
# marks and swatches by the client, so they say nothing an example needs to say.
_NOT_A_THING = {
    "dot", "dots", "line", "curve", "zigzag", "stroke", "slant", "slanting",
    "swatch", "outline", "group", "tenframe", "shape", "colour", "color",
    "plus", "minus", "equals", "question", "mixed", "same", "different",
    # Shapes the app has no drawing for. They are still the shape lesson's own
    # furniture, and `visuals.from_concept` does not recognise them because it
    # only knows what it can draw.
    "oval", "diamond", "semicircle",
}

# The last word of a token that names a pre-writing mark rather than a thing.
_MARK_WORDS = {"line", "lines", "slant", "stroke", "strokes", "curve", "curves", "zigzag"}

# The everyday things a concept is made of, for the concepts whose author named
# none beside them.
#
# These are the *same* examples `agent.EVERYDAY_EXAMPLES` speaks - a picture of
# what the child is hearing rather than a second, different example - narrowed
# twice over. Every token here is something the client has real artwork for, so
# nothing is named that would come out as a neutral mark; and every token is a
# thing rather than a figure, so a shape's example is never another shape. A
# concept whose everyday things the app cannot draw is absent, and absent means
# no picture: black has a crow in the spoken line and nothing here, because a
# crow drawn in the app's own colours is not black.
# It is read **both ways**. Forwards it is this concept's own examples, and
# backwards - `_picture_of` - it is whose example a picture is, which is what
# keeps a shapes level's box of exemplars from handing the circle's ball to the
# triangle, and what `not_examples` sends the client so the class never
# illustrates a contrast it only mentioned in passing. That second reading is
# why a concept lists everything the app can draw *of* it and not only the one
# thing the spoken line names: a plate and the moon are the circle's whether or
# not this turn's sentence reached for them.
_CONCEPT_PICTURES: dict[str, tuple[str, ...]] = {
    "shape:circle": ("ball", "clock", "plate", "moon", "wheel"),
    "shape:square": ("bread", "box", "window"),
    "shape:triangle": ("ice_cream",),
    "shape:rectangle": ("door", "book", "notebook"),
    "colour:red": ("tomato", "fireengine", "apple"),
    "colour:blue": ("sky", "water"),
    "colour:yellow": ("banana", "sun"),
    "colour:green": ("leaf", "grass", "peas"),
    "colour:orange": ("orangefruit", "carrot"),
    "colour:purple": ("grapes",),
    "colour:pink": ("flower", "watermelon"),
    "colour:brown": ("bread", "tree"),
    "colour:black": ("crow",),
    "colour:white": ("milk", "cloud"),
}


def _picture_of(token: str) -> str:
    """Which concept `_CONCEPT_PICTURES` says this everyday thing is a picture of.

    The table is written the other way round - concept to pictures - and this
    reads it back: `ball` is the circle's, `door` is the rectangle's, `tomato`
    is red's. A word it does not hold belongs to nobody in particular, which is
    the honest answer for `hat` or `samosa`.
    """
    words = _clean(token).replace(" ", "_")
    for concept, pictures in _CONCEPT_PICTURES.items():
        if words in pictures:
            return concept
    return ""


def _belongs_elsewhere(token: str, concept: visuals.Visual) -> bool:
    """Whether this picture is an example of a *different* card of this lesson.

    The ball-on-the-square-card bug again, one level further in. An author who
    writes an activity of shape *exemplars* - a ball, a book, a hat, all in one
    `visual_items` list - has named no concept in that list, so it reads as the
    level's own picture box and every card of the level was offered the lot.
    A shapes level's picture box is not a box of neutral pictures, though: each
    one of them is a picture of one of its other shapes, and a ball beside "Tap
    the triangle!" is the circle's example on the triangle's card.

    `_CONCEPT_PICTURES` is the hand-written answer to which is whose, and it is
    only ever consulted *within one family* - a ball is not the circle's on a
    letters card, where it is simply a ball.
    """
    if not concept.is_shown:
        return False
    owner = _picture_of(token)
    if not owner:
        return False
    kind, _, _value = owner.partition(":")
    return kind == concept.kind and owner != concept.as_token()


def not_examples(concept: visuals.Visual | None) -> list[str]:
    """The everyday words that may never be illustrated beside this card.

    The teacher reaches for a contrast while it explains - "a triangle has three
    corners, a circle has none, round like a ball" - and the class shows the
    example it is saying at the moment it says it
    (`frontend/lib/spokenExamples.ts`). That is right for the card's own
    examples and wrong for the ones it borrowed: a **ball** on the screen while
    the question says "Tap the triangle!" is the circle's picture on the
    triangle's card, which is the fault the user has reported three times now in
    three different places.

    The client cannot know whose picture a word is - it has a table of pictures,
    not of concepts - so the server says. Hand-written, closed, and no model:
    the other members of this concept's own family, out of `_CONCEPT_PICTURES`.
    """
    if concept is None or not concept.is_shown:
        return []
    mine = concept.as_token()
    banned: list[str] = []
    for token, pictures in _CONCEPT_PICTURES.items():
        kind, _, _value = token.partition(":")
        if kind != concept.kind or token == mine:
            continue
        for picture in pictures:
            words = picture.replace("_", " ")
            if words not in banned:
                banned.append(words)
    return banned


def _clean(token: str) -> str:
    """An asset token in one shape: lowercase words joined by single spaces."""
    text = re.sub(r"[^\w\sऀ-ॿ]", " ", str(token or "").lower()).replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def _names_the_concept(token: str, visual: visuals.Visual) -> bool:
    """Whether this token is the very thing this card is teaching.

    `letter_A`, `letter_small_a` and a bare `a` are all the letter A; `circle` is
    the circle the card is already drawing. Compared on the cleaned words so the
    author's underscores and a bare word are the same thing.
    """
    words = _clean(token)
    if not words:
        return True
    value = _clean(visual.value)
    parts = words.split()
    head = parts[0] if parts else ""
    rest = " ".join(part for part in parts[1:] if part != "small")
    if head in _KIND_PREFIXES:
        return not value or rest == value or words == value
    return bool(value) and words == value


def _is_lesson_furniture(token: str) -> bool:
    """Whether this token is a glyph or a figure rather than a thing in the world.

    A card on the letter A must not offer B as its example, and a card on
    circles must not offer the square: those are other cards of the same lesson,
    and they are not something a child has "seen for themselves" the way they
    have seen an apple or a ball. `visuals.from_concept` knows the vocabulary
    the app draws, and the *glyph* half of it - letters, numbers, shapes,
    colours - is the furniture.

    Its other half is not. Since the app learned to draw a cow and an apple,
    `from_concept` recognises those too, and reading "is it recognised?" as "is
    it furniture?" made every everyday thing in the syllabus furniture and left
    every level with no examples at all. An apple is the example; that is the
    whole point of it.
    """
    words = _clean(token)
    if not words:
        return True
    parts = words.split()
    if parts[0] in _KIND_PREFIXES:
        return True
    # "standing_line", "left_slant", "curve_stroke" - the marks a pre-writing
    # level is teaching. They are named as assets like everything else, and they
    # are no more an everyday example than the letter A is.
    if parts[-1] in _MARK_WORDS:
        return True
    return visuals.from_concept(words).kind in _KIND_PREFIXES


def _names_another_concept(group: tuple[str, ...], concept: visuals.Visual) -> bool:
    """Whether this activity teaches a *different* card of the same lesson.

    A shapes level puts `circle` and `ball` in one activity and `square` in the
    next; a letters level puts the letters in one activity and the apple and the
    ball in another. The difference is what this asks about: an activity that
    names a concept of its own belongs to that concept, and an activity that
    names none belongs to the level. Only the first kind is out of bounds, and
    only when the concept it names is not the one on the card.

    A card with no concept of its own has no *other* concept either, so nothing
    is out of bounds for it: the whole level is its picture box, exactly as
    before. Being strict there would empty the strip on every letters level in
    the syllabus, whose author names the letters in one activity and the
    pictures in the next.
    """
    if not concept.is_shown:
        return False
    for token in group:
        if not _is_lesson_furniture(token):
            continue
        if _names_the_concept(token, concept):
            continue
        return True
    return False


@lru_cache(maxsize=256)
def _authored_items(topic_id: str) -> tuple[tuple[str, ...], ...]:
    """The pictures the author named, kept grouped by the activity that named them.

    Grouped rather than flattened because a level covering A and B names both an
    apple and a ball, and the A card should show the apple: the group an
    activity's items form is the author's own answer to which example goes with
    which card.

    Cached alongside `questions.for_topic` and for the same reason: the syllabus
    is read from disk at boot and does not change under a running server.
    """
    if not topic_id:
        return ()
    try:
        activities = curriculum_service.get_activities(topic_id)
    except Exception:  # pragma: no cover - a topic id the manifest no longer has
        logger.warning("No authored activities for topic %s", topic_id)
        return ()

    groups: list[tuple[str, ...]] = []
    for activity in activities:
        items = tuple(
            str(token)
            for token in (activity.visual_items or [])
            if _clean(token) and _clean(token) not in _NOT_A_THING
        )
        if items:
            groups.append(items)
    return tuple(groups)


def for_turn(
    topic_id: str,
    *,
    visual: visuals.Visual | None = None,
    answer: str = "",
    options: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """The example pictures for this turn: the author's own, never the answer.

    Gives back asset tokens - `apple`, `red_ball` - and not words to read. The
    client draws each one and drops any it has no artwork for, so a token nobody
    has drawn yet costs nothing.

    The activities that name this card's own concept are read first, so a level
    covering A and B shows the apple on the A card. The rest of the level is the
    fallback, and a level whose author named nothing shows nothing at all.
    """
    # **The answer decides which concept this card is about, and the picture
    # beside it only decides when the answer names nothing.** "Tap the
    # triangle!" is a triangle card however the picture was worked out - and it
    # was worked out from the level's title and then from whichever concept the
    # retrieved notes led with, which on a level called "Shapes" was the circle
    # on every single card. So the example followed the circle onto the triangle
    # card, and the triangle card showed a ball.
    concept = visuals.from_concept(answer or "")
    if not concept.is_shown:
        concept = visual or visuals.Visual()
    keys = [value for value in (answer or "",) if value]
    offered = [str(one) for one in (options or []) if str(one).strip()]
    groups = _authored_items(topic_id)

    def usable(token: str) -> bool:
        if _names_the_concept(token, concept) or _is_lesson_furniture(token):
            return False
        # A picture of one of this level's *other* concepts. An activity of bare
        # exemplars names no concept, so it reads as the level's picture box -
        # and on a shapes level that box is a ball for the circle, a book for
        # the rectangle and a hat for the triangle, handed whole to every card.
        if _belongs_elsewhere(token, concept):
            return False
        # Never an example of the thing the child is about to be asked for.
        if any(stage_rules.contains_answer(token, key) for key in keys):
            return False
        return not any(stage_rules.contains_answer(one, token) for one in offered)

    def take(source: list[tuple[str, ...]]) -> list[str]:
        kept: list[str] = []
        for group in source:
            for token in group:
                if token in kept or not usable(token):
                    continue
                kept.append(token)
                if len(kept) >= MAX_ITEMS:
                    return kept
        return kept

    this_card = [
        group
        for group in groups
        if concept.is_shown and any(_names_the_concept(token, concept) for token in group)
    ]

    # The author's own, from the activity that teaches this very concept.
    authored = take(this_card)
    if authored:
        return authored

    # Then the rest of the level, minus the activities that are about one of its
    # *other* concepts. That is the whole of the ball-on-the-square-card bug: an
    # author who put `circle` and `ball` in one activity has said the ball is a
    # picture of the circle, so it belongs on the circle's card and nowhere else.
    # An activity that names no concept - the four balls of a counting level, the
    # apple and ball of a letters level - is the level's own picture box and is
    # read as before.
    rest = take([group for group in groups if not _names_another_concept(group, concept)])
    if rest:
        return rest

    # And last, the everyday example the teacher is already saying out loud.
    if concept.is_shown:
        spoken = [
            token for token in _CONCEPT_PICTURES.get(concept.as_token(), ()) if usable(token)
        ]
        return spoken[:MAX_ITEMS]
    return []


def reset() -> None:
    """Drop the cache. Tests use it; nothing in a request does."""
    _authored_items.cache_clear()


cache.register("playground.examples", _authored_items.cache_clear)


__all__ = ["MAX_ITEMS", "for_turn", "not_examples", "reset"]
