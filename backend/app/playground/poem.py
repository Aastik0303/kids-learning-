"""The poem the class says instead of a lesson, every fifth day.

A day is one level from every subject (`plan_service._candidates`), and on a
poem day one of those levels steps aside and a poem takes its place. The day
does not get longer and it does not get shorter: a Nursery child's six stages
are still six, and one of them is a poem. The level that stepped aside is not
lost - it is still that subject's first weak or unfinished topic, so it is back
in tomorrow's plan on its own.

**Why a poem at all.** Five days of being asked things is a lot for a child of
three. A poem is the one stage in the schedule where nothing can be got wrong:
there is no question, no option to tap, no microphone waiting, nothing marked
and nothing at stake. It is the class saying something *to* the child rather
than asking something of them, and it is why the poem is put at the end of the
day (`app/ai/planner/graph.py`) - the sitting finishes on the part that cannot
go badly.

**What a poem is not.** It is not a level. Its `topic_id` is deliberately not in
the manifest, so every rule that reads the manifest already does the right thing
with it without being told about poems at all: `_award_level` finds no topic and
returns nothing, so no star is paid, nothing is unlocked and no certificate is
re-checked; nothing is written to `attempts`; no policy episode is committed and
no retention probe is scheduled, because a poem teaches no skill that could be
tested two days later. The one thing it *does* do is move the plan cursor, which
it must - a stage of the day that never finishes is a day that never finishes.

**No model, ever.** These are written out here in full, by a person, and the
class reads them exactly as they are. There is no generation and no retrieval:
a poem a child hears on the tenth of the month must be the same poem, word for
word, that they hear when it comes round again, because saying it along with the
teacher the second time is the entire point of a nursery rhyme.

**The picture follows the words.** Every verse names its own asset token by hand,
out of `visuals.THINGS`, and a verse that names nothing shows nothing rather
than a near-miss - the same rule `visualIcon` keeps for अनार. That is also why
the poems about a phone and about a thinking machine are written round things
the app can actually draw: a clock, a book, a car, a cat. Nothing in here is
allowed to invent a picture to fill the board.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.playground import visuals


# How often a poem comes round, in days. Every fifth day one subject's level
# steps aside for it.
EVERY_DAYS = 5

# The prefix that tells a poem's topic id from a level's, everywhere. Nothing
# else in the manifest starts with it, which is what lets `is_poem` be a string
# test rather than a lookup - and a lookup is exactly what must not be needed,
# because the point of a poem id is that the manifest does not have one.
TOPIC_PREFIX = "poem_"


@dataclass(frozen=True)
class Part:
    """One turn of a poem: what is said, what is on the card, what is drawn.

    `line` is the handful of words printed large - the one thing on this screen
    a grown-up reads along from, and a shape a child begins to recognise before
    they can read it. `speech` is the whole verse, said out loud. `picture` is an
    asset token or nothing at all.
    """

    line: str
    speech: str
    picture: str = ""

    @property
    def visual(self) -> visuals.Visual:
        """The picture for this verse, as the board's own vocabulary.

        Built here rather than parsed: `visuals.parse` refuses `thing:` on
        purpose, because the only thing that may name an everyday object is a
        person, and these were named by one. The client is still the second
        gate - a token it has no strokes for draws nothing.
        """
        token = (self.picture or "").strip()
        if not token:
            return visuals.Visual()
        if token in visuals.THINGS:
            return visuals.Visual(kind="thing", value=token)
        return visuals.parse(token)


@dataclass(frozen=True)
class Poem:
    """One poem, and the stage the class makes out of it."""

    poem_id: str
    title: str
    parts: tuple[Part, ...]

    @property
    def topic_id(self) -> str:
        return f"{TOPIC_PREFIX}{self.poem_id}"


# The poems, in the order they come round. A person wrote every line of this.
#
# The subjects are the ones the user asked for - the thinking machine, the phone
# in a grown-up's hand, the apple - and then the ordinary things a nursery rhyme
# has always been about. They are written for two to six: short lines, one idea
# each, a rhyme a child can hear coming, and nothing in them a small child has
# not already seen for themselves.
POEMS: tuple[Poem, ...] = (
    Poem(
        poem_id="ai",
        title="The Machine That Thinks",
        parts=(
            Part(
                line="A machine that thinks!",
                speech=(
                    "Today there is no question to answer. Today we say a poem "
                    "together, and this one is about a machine that thinks. "
                    "Listen with me."
                ),
            ),
            Part(
                line="It knows the time.",
                speech=(
                    "There is a clever little machine, "
                    "it never has to guess. "
                    "You ask it what the time is now, "
                    "and it will answer yes."
                ),
                picture="clock",
            ),
            Part(
                line="It reads a book.",
                speech=(
                    "It reads a story from a book, "
                    "in someone else's voice. "
                    "It knows a hundred hundred tales "
                    "and lets you take your choice."
                ),
                picture="book",
            ),
            Part(
                line="It helps a car.",
                speech=(
                    "It helps a car to find the road "
                    "and tells it where to go. "
                    "It learned it all from you and me - "
                    "it did not always know."
                ),
                picture="car",
            ),
            Part(
                line="Say it with me!",
                speech=(
                    "A clever little machine that thinks, that reads, that finds "
                    "the way. Say it with me one more time, and then off we go."
                ),
            ),
        ),
    ),
    Poem(
        poem_id="mobile",
        title="The Little Talking Box",
        parts=(
            Part(
                line="A talking box!",
                speech=(
                    "No question today - today we say a poem together. This one "
                    "is about the little talking box that lives in a grown-up's "
                    "hand. Listen with me."
                ),
            ),
            Part(
                line="Nani says hello.",
                speech=(
                    "A little box that sings and rings "
                    "and lives inside a hand. "
                    "Nani says hello inside it "
                    "from another land."
                ),
                # Nothing, on purpose. This verse names a box, a hand and a
                # grandmother, and the app can draw none of them; a drum stood
                # here, which is the near-miss the whole rule forbids.
                picture="",
            ),
            Part(
                line="A cat to look at.",
                speech=(
                    "It keeps a picture of a cat, "
                    "a birthday and a tree. "
                    "You tap it once and there they are, "
                    "for everyone to see."
                ),
                picture="cat",
            ),
            Part(
                line="Now put it down.",
                speech=(
                    "But when the sun is going down "
                    "we put the small box by, "
                    "and run outside to find a bird "
                    "and wave it goodbye."
                ),
                picture="bird",
            ),
            Part(
                line="Say it with me!",
                speech=(
                    "It sings, it rings, it shows a cat - and then we put it "
                    "down. Say it with me one more time, and then off we go."
                ),
            ),
        ),
    ),
    Poem(
        poem_id="apple",
        title="One Red Apple",
        parts=(
            Part(
                line="One red apple.",
                speech=(
                    "No question today - today we say a poem together, and this "
                    "one is about an apple. Listen with me."
                ),
                picture="apple",
            ),
            Part(
                line="Up in the tree.",
                speech=(
                    "One red apple in a tree, "
                    "as high as high can be. "
                    "The wind came by and gave a push - "
                    "it fell right down to me."
                ),
                picture="tree",
            ),
            Part(
                line="Wash it in water.",
                speech=(
                    "I washed it in the water "
                    "until it shone like glass, "
                    "and sat down with it in my hand "
                    "upon the cool green grass."
                ),
                # The apple - "it" in every line of this verse. A leaf stood
                # here for the grass, which is a different thing drawn beside
                # the one the verse is about.
                picture="apple",
            ),
            Part(
                line="Crunch!",
                speech=(
                    "I took one bite - it went crunch! - "
                    "so sweet and white inside. "
                    "And in the middle, small and brown, "
                    "the little seeds all hide."
                ),
                picture="apple",
            ),
            Part(
                line="Say it with me!",
                speech=(
                    "One red apple, up in the tree, washed in the water, and "
                    "crunch! Say it with me one more time, and then off we go."
                ),
            ),
        ),
    ),
    Poem(
        poem_id="rain",
        title="Rain On The Roof",
        parts=(
            Part(
                line="Rain today!",
                speech=(
                    "No question today - today we say a poem together, and this "
                    "one is about the rain. Listen with me."
                ),
                picture="rain",
            ),
            Part(
                line="Pitter, patter.",
                speech=(
                    "Pitter patter on the roof, "
                    "pitter patter down. "
                    "The rain has come to wash the leaves "
                    "and wash the dusty town."
                ),
                picture="cloud",
            ),
            Part(
                line="Under the umbrella.",
                speech=(
                    "I hold my big umbrella up "
                    "and hear it drum and drum, "
                    "and every puddle on the path "
                    "says splash when I have come."
                ),
                picture="umbrella",
            ),
            Part(
                line="Then the sun!",
                speech=(
                    "And when the rain has said enough "
                    "and every cloud has gone, "
                    "the sun comes out to dry the world "
                    "and puts its warm coat on."
                ),
                picture="sun",
            ),
            Part(
                line="Say it with me!",
                speech=(
                    "Pitter patter on the roof, splash in every puddle, and then "
                    "the sun. Say it with me one more time, and then off we go."
                ),
            ),
        ),
    ),
    Poem(
        poem_id="moon",
        title="Goodnight, Moon",
        parts=(
            Part(
                line="Goodnight!",
                speech=(
                    "No question today - today we say a poem together, and this "
                    "one is for the night time. Listen with me."
                ),
                picture="moon",
            ),
            Part(
                line="The moon comes up.",
                speech=(
                    "When all the day is packed away "
                    "and put back on the shelf, "
                    "the moon climbs up above the roof "
                    "and lights it by itself."
                ),
                picture="moon",
            ),
            Part(
                line="The cat curls up.",
                speech=(
                    "The cat curls up beside the door, "
                    "the bird is in the tree, "
                    "and everybody in the house "
                    "is quiet - even me."
                ),
                picture="cat",
            ),
            Part(
                line="Sleep well.",
                speech=(
                    "So goodnight moon, and goodnight cat, "
                    "and goodnight little light. "
                    "The sun will come and wake us up. "
                    "Sleep well, and sleep all night."
                ),
                picture="sun",
            ),
            Part(
                line="Say it with me!",
                speech=(
                    "Goodnight moon, goodnight cat, goodnight little light. Say "
                    "it with me one more time, and then off we go."
                ),
            ),
        ),
    ),
)

_BY_TOPIC = {poem.topic_id: poem for poem in POEMS}


def is_poem(topic_id: str) -> bool:
    """Whether this item of the day is a poem rather than a level.

    A string test on purpose. The whole design of a poem's topic id is that the
    manifest does not hold it, so anything that had to look it up to find out
    would be asking the one place that cannot answer.
    """
    return str(topic_id or "").startswith(TOPIC_PREFIX)


def get(topic_id: str) -> Poem | None:
    """The poem with this id, or nothing.

    Nothing is a real answer and every caller handles it: a plan frozen before a
    poem was renamed still holds the old id, and a stage that cannot find its
    poem is finished rather than left in front of the child.
    """
    return _BY_TOPIC.get(str(topic_id or ""))


def is_poem_day(plan_date: date) -> bool:
    """Whether today is one of the days a poem replaces a level.

    Counted off the calendar rather than off anything the child has done, and
    deterministic for the same reason the planner is: two reads of the same day
    have to agree, and a frozen plan has to be explicable a week later. Every
    child meets a poem on the same days, which is also the answer a parent is
    least surprised by.
    """
    return plan_date.toordinal() % EVERY_DAYS == 0


def _poem_number(plan_date: date) -> int:
    """Which poem day this is, counting from the start of the calendar."""
    return plan_date.toordinal() // EVERY_DAYS


def for_day(plan_date: date) -> Poem | None:
    """The poem this day gets, or nothing when it is not a poem day.

    They come round in order and then start again, so a child meets each of them
    before meeting any of them twice - and meeting one twice is the point, not a
    failure: the second time is the time they can say it along with you.
    """
    if not is_poem_day(plan_date) or not POEMS:
        return None
    return POEMS[_poem_number(plan_date) % len(POEMS)]


def replaced_index(plan_date: date, count: int) -> int:
    """Which of the day's levels steps aside for the poem.

    It walks, so it is not the same subject's turn to be missed every time. The
    user asked for the poem to replace *any* subject rather than a fixed one,
    and a fixed one would mean a child who meets a poem every fifth day meets
    General Awareness four days in five for ever.
    """
    if count <= 0:
        return -1
    return _poem_number(plan_date) % count


def title_of(topic_id: str) -> str:
    """The poem's own title, for a plan item that has no manifest entry."""
    found = get(topic_id)
    return found.title if found is not None else ""


__all__ = [
    "EVERY_DAYS",
    "POEMS",
    "TOPIC_PREFIX",
    "Part",
    "Poem",
    "for_day",
    "get",
    "is_poem",
    "is_poem_day",
    "replaced_index",
    "title_of",
]
