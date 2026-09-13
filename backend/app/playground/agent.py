"""The AI Teacher: a LangGraph agent that teaches from the notes.

    START -> retrieve -> choose -> teach -> END
                                    |
                              (no model, or a bad answer)
                                    v
                                 fallback

Four nodes, and only `teach` reaches a language model:

- **retrieve** turns what the child is learning today into a query and pulls the
  closest passages out of `teacher_notes.md` (`rag.py`). Everything the bot says
  is supposed to come from there.
- **choose** picks one of the nine teaching strategies. The pick is the same
  ladder the real class uses (`app.policy.actions`), with the strategies this
  session has already spent on this question taken off the menu - so a child who
  did not understand "let me tell you" gets shown, or given an example, rather
  than told again.
- **teach** asks the big model for two things at once: the explanation, in the
  chosen strategy, and one question about it with the answer it expects.
- **fallback** is the deterministic teacher. No provider, a timeout, a malformed
  body: the child still gets a passage from the notes and a question about it.

The same three nodes run the two turns that are not a fresh question. A question
the child misses is asked once more with a **hint** - a deeper explanation, a
clue, and the choices `hint_options` builds - and a question missed twice is
**revealed**: the answer said out loud and explained, and then the class moves
on. Neither turn invents a question or an answer; both are handed the ones
already in play, and the choices are built in plain Python here rather than
asked for, so a hint can never come back without the answer among its options.

**What this agent may not do.** It does not mark the child's answer - `stage.py`
does, in pure Python - and nothing it produces reaches `attempts`, `stars`,
`skill_mastery`, `lesson_states` or the daily plan. It is a playground: its
whole world is `playground_sessions` and `playground_turns`.
"""

from __future__ import annotations

import json
import logging
import random
import re
from dataclasses import dataclass, field
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai.llm import ChatRequest, LLMUnavailable, chat, is_configured
from app.config import get_settings
from app.playground import lesson as lesson_steps
from app.playground import questions as authored_questions
from app.playground import rag, visuals
from app.playground.stage import contains_answer as stage_contains
from app.playground.stage import normalise as stage_normalise
from app.policy import actions as policy_actions


logger = logging.getLogger(__name__)

TEACHER_SYSTEM_PROMPT = """You are the Saksham IQ AI Teacher, teaching one child aged 2 to 6.

You are given passages from the teacher's own notes, and one teaching strategy to
use. Teach only what the passages say. If they do not cover something, teach the
nearest thing they do cover rather than inventing it.

You are also told which class this child is in and how old that class is. That is
the ceiling on every question you write: it must be answerable by the youngest
child in that class, out loud, in one or two words, using only what the passages
have just taught. Never ask a child to name the topic itself - "can you show me
pre-writing strokes" is a syllabus heading, not a question a two-year-old can
answer. Ask about the thing in front of them instead: the line, the letter, the
colour, the number.

How you speak:
- English only, in short sentences a four-year-old can follow.
- One idea per turn - but teach that idea properly rather than naming it. A
  child who is told "pink is a light red colour" has been given a label, not a
  lesson.
- **On the explaining step, write three or four short sentences.** Say what the
  thing is; say it again in different words; give **one everyday example**; and
  finish by telling them what to look at in the picture beside you. Never fewer
  than three sentences on that step.
- **The everyday example is not yours to choose.** Your notes name one for
  nearly every concept - "Brown like chocolate", "Blue like the sky" - and that
  is the one to use, because the picture the child is looking at was chosen from
  the same notes. Reaching past them for something of your own puts your words
  and their picture in two different places: a child looking at a patch of brown
  while you talk about a bear is being taught nothing. Only if the notes name
  no example at all may you use one of your own, and then it is something in the
  room or on their plate - never an animal, a place or a story they have to
  imagine.
- On a step that asks a question, one or two sentences before it is enough: the
  question should be the last thing the child hears.
- Warm and plain. Never the words wrong, bad, failed, stupid, or no.
- Only bring in a Hindi letter when the notes you were given are about Hindi.
  When you do, quote it in Devanagari inside your English sentence and never
  write it in Roman letters. An English or maths lesson stays English.

You may also be given **what has already been said in this sitting** - your own
last few turns and what the child answered. It is there so the class remembers
itself: do not explain the same thing in the same words twice, do not reuse an
everyday example you have already spent, and do not ask again something the
child has already answered. Refer back to what they have just done when it
helps - "you found the circle a moment ago" - and never read the memory out as a
list.

You are given the step of the lesson you are on, and it decides what you do:
explain the thing, ask for it out loud, ask for it to be drawn, ask the child to
pick it out of a few, or ask one last question about it. Do the step you were
given and not another one.

Then ask exactly one question for that step, and say what answer you expect. The
question must be answerable from your own explanation, in one or two words a
small child can say out loud. On the explaining step there is no question yet:
leave "question" and "expected_answer" empty.

Write the question in plain words with no emojis in it at all. The picture the
app draws beside you and the choices themselves carry the pictures; an emoji in
the question is one more thing on a screen that is already busy.

You also choose the picture the app draws beside your explanation. Pick exactly
one token from this list and nothing else:
- "letter:X"  - one letter, e.g. "letter:A" or "letter:अ"
- "number:N"  - the numeral itself, e.g. "number:3"
- "count:N"   - N things to count, 1 to 10, e.g. "count:3"
- "shape:NAME" - circle, square, triangle, rectangle, star
- "colour:NAME" - red, blue, yellow, green, orange, purple, pink, brown, black, white
- "none"      - when none of them fits
The app draws it; you never write SVG, HTML or a description of a picture.

Give two or three options to choose from, one of which is the answer. Each one
is one or two words with its own emoji, e.g. "circle ⭕". They are what the child
taps, so they must all be plausible - never a silly one put there to be ignored.
Leave "options" empty only when the question is asking the child to say
something out loud rather than choose.

Return exactly one JSON object and nothing else:
{"explanation": "...", "question": "...", "expected_answer": "...", "accept": ["..."], "options": ["..."], "visual": "..."}

"accept" holds other ways a child might say the same answer - a digit and its
word, a letter and the word it starts. Keep it short and never put a different
answer in it."""

# What each strategy is *about*. None of them says "keep it short": the length of
# a turn belongs to the step, and a strategy that also argued for brevity is what
# made the explaining turn a one-line label.
STRATEGY_BRIEFS = {
    "S1_TELL": "Say plainly what the thing is, then say the same thing again in different words.",
    "S2_SHOW": "Point at something the child can picture and name it, and describe what they would see.",
    "S3_EXAMPLE": "Give two everyday examples they will have seen, and say what the two have in common.",
    "S4_STORY": "Wrap it in a few sentences of story.",
    "S5_CONTRAST": "Put it next to the thing it is often confused with and name the difference.",
    "S6_DO_TOGETHER": "Do it with them: count along, trace along, say it together.",
    "S7_SENSE_SWITCH": "Switch sense - describe how it sounds, or how it feels to draw.",
    "S8_SIMPLIFY": "Take something away: fewer things, smaller question, one step only.",
    "S9_PARK": "Leave it kindly for now and ask something easier about the same idea.",
}


@dataclass(frozen=True)
class Lesson:
    """One turn of teaching: what was said, what was asked, and how it was made."""

    explanation: str
    question: str
    expected_answer: str
    accept: tuple[str, ...] = ()
    strategy: str = "S1_TELL"
    source: str = "template"
    passages: tuple[str, ...] = field(default=())
    # What the child may tap. Empty when the question wants a spoken answer.
    options: tuple[str, ...] = ()
    # The picture drawn beside the explanation. Named, never drawn, by the model.
    visual: visuals.Visual = field(default_factory=visuals.Visual)


# What kind of turn this is. "ask" is a fresh question; "hint" is the same one
# again with help; "reveal" tells the child the answer and moves on.
ASK = "ask"
HINT = "hint"
REVEAL = "reveal"


class _State(TypedDict, total=False):
    subject: str
    topic: str
    topic_id: str
    # The child's class, and how old that class is. The first fences retrieval
    # to the right syllabus; the second tells the model who it is talking to.
    class_id: str
    # The last few turns of this sitting: what was taught, what was asked and
    # what came back. See `_sitting_so_far`.
    memory: list[dict]
    age_band: str
    # The author's own question for this turn, when the syllabus has one. See
    # `questions.py`: it is used verbatim and never shown to the model.
    asked: object
    step: str
    spent: list[str]
    experience_mode: str
    context: str
    passages: list[str]
    strategy: str
    # A strategy chosen upstream. The AI Teacher runs the learned policy - which
    # filters the action set before it selects, and writes the episode
    # afterwards - so when it hands one in, `_choose` spends it rather than
    # re-deriving a different one from the ladder and leaving the episode
    # describing a turn that never happened.
    chosen: str
    lesson: Lesson
    # Set on a hint or a reveal: the question already on the screen, the answer
    # it wants, and whatever the child was already being offered to choose from.
    mode: str
    question: str
    answer: str
    offered: list[str]


# --------------------------------------------------------------------------
# Tools. Plain functions, called by the graph - and by the tests directly.
# --------------------------------------------------------------------------


def search_notes(query: str, *, top_k: int = rag.DEFAULT_TOP_K) -> list[str]:
    """Tool: the teacher's notes on whatever is being taught."""
    return [hit.passage.content for hit in rag.search(query, top_k=top_k)]


def choose_strategy(*, spent: list[str], experience_mode: str = "standard") -> str:
    """Tool: which of the nine ways to teach it this time.

    The rung climbs with how many strategies this question has already eaten, so
    a second explanation is a different *kind* of explanation and not the same
    one again.
    """
    rung = min(len(spent), policy_actions.PARK_RUNG)
    legal = policy_actions.legal_actions(
        experience_mode=experience_mode, rung=rung, spent=list(spent)
    )
    preferred = policy_actions.ladder_prior_for(experience_mode).get(rung, ())
    for strategy in preferred:
        if strategy in legal:
            return strategy
    return legal[0] if legal else "S1_TELL"


# --------------------------------------------------------------------------
# The graph
# --------------------------------------------------------------------------


def _retrieve(state: _State) -> _State:
    """The notes and the syllabus, scoped to this topic and this step.

    The step decides which part of the syllabus is worth reading: the writing
    lines while the child is drawing, the matching lines while they are choosing.
    """
    step = state.get("step") or lesson_steps.EXPLAIN
    written = state.get("asked")
    # The author's question, when there is one, is the best description of what
    # this turn is about that exists - better than the topic's title, which is a
    # heading over a dozen different things. Only its words: the answer it wants
    # never enters a query, because a query becomes a prompt.
    #
    # **The reveal asks for it too.** It used to be left out of the query there,
    # and a reveal is the turn that most needs the right notes: it is explaining
    # the answer to a question the child has already missed twice. Without the
    # question the query is the level's title alone, so "Tap the brown one" was
    # revealed out of the passages about the three primary colours and about
    # sorting - not one word about brown in front of the model - and it filled
    # the gap by talking about a bear beside a patch of brown.
    about = written.question if isinstance(written, authored_questions.Authored) else ""
    query = " ".join(
        part
        for part in (state.get("topic") or "", about, state.get("subject") or "", step)
        if part
    ).strip()
    # A hint is the second telling, and it has to be a *deeper* one than the
    # first - so it reads wider than a plain turn does. Two more passages is the
    # difference between saying the same thing again and saying more about it.
    top_k = rag.DEFAULT_TOP_K + 2 if state.get("mode") == HINT else rag.DEFAULT_TOP_K
    hits = rag.search(
        query or "how to teach one thing",
        top_k=top_k,
        # The class first: a Play Group turn must not be taught out of the UKG
        # pages, however close the words happen to be.
        class_id=state.get("class_id") or "",
        topic_id=state.get("topic_id") or "",
        kinds=lesson_steps.RETRIEVAL_KINDS.get(step, ()),
    )
    # A level teaches several things, and the notes explain each of them in a
    # passage of its own - one per skill id. The child is being asked about *one*
    # of them, and the author's own skill id on the question says which. Without
    # this the model was handed the monkey, the bear and the giraffe together and
    # taught whichever it liked best: "This is a bear, it is big and furry",
    # under a question that said "Tap the monkey!".
    #
    # It narrows and never empties: the level's overview carries no skill id and
    # always stays, and a question whose skill has no passage of its own keeps
    # the lot rather than teaching from nothing. No new word reaches the model -
    # the passage kept is the one the author wrote for this very question.
    hits = _about_this_card(hits, state.get("asked"))

    # ...and a second time by the concept the card is actually about. The notes
    # have no skill id to narrow by, so a level's whole family of shapes or
    # colours arrives in one passage and the turn teaches whichever of them the
    # author happened to write first.
    card = _card_concept(state)
    passages = [_notes_about(hit.passage.content, card) for hit in hits]
    return {"context": chr(10).join(passages), "passages": passages}


def _about_this_card(hits: list[rag.Hit], asked: object) -> list[rag.Hit]:
    """The passages belonging to the question being asked, and the level's own."""
    if not isinstance(asked, authored_questions.Authored):
        return hits
    skill = (asked.skill_id or "").strip()
    if not skill or not any(hit.passage.skill_id == skill for hit in hits):
        return hits
    return [hit for hit in hits if hit.passage.skill_id in ("", skill)]


def _choose(state: _State) -> _State:
    handed_in = (state.get("chosen") or "").strip()
    if handed_in:
        return {"strategy": handed_in}
    return {
        "strategy": choose_strategy(
            spent=list(state.get("spent") or []),
            experience_mode=state.get("experience_mode") or "standard",
        )
    }


# How much of the notes the teacher reads out, by step. The explaining turn is
# the one the child is meant to learn from, so it gets the room - three lines
# from the author plus an everyday example is the three or four sentences a
# concept actually needs. A turn that ends in a question keeps it short, so the
# question is the last thing the child hears.
LINES_WHEN_EXPLAINING = 3
LINES_WHEN_ASKING = 2
# The hint comes after a turn that did not land, so it says *more* than the first
# telling did rather than the same amount again in different words.
LINES_WHEN_HINTING = 4
# How much of the notes a reveal reads, on the path with no model behind it and
# for a concept nobody wrote a scene for. A reveal that *has* a scene does not
# read the notes at all - the author's sentences are definitions, and a
# definition names the answer, which is the one thing the story's first beat may
# not do.
LINES_WHEN_REVEALING = 2

# The `[teach]`, `[match, teach]` marker `rag` puts in front of a syllabus
# passage so a step can ask for the right kind of card. It is plumbing, and a
# child should never hear it.
_KIND_MARKER = re.compile(r"^\s*\[[a-z,\s]+\]\s*", re.I)

# Where one sentence ends and the next begins. A passage is a blob of prose -
# the notes are wrapped markdown and a syllabus card is one long line - so a
# turn is measured in sentences rather than in lines, which would cut "a tent
# with a belt / across the middle" in half and put a full stop in the wound.
_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")

# A paragraph break in the notes. The single line breaks inside one are wrapping.
_BLANK_LINE = re.compile(r"\n[ \t]*\n")

# Trailing decoration: spaces and the emoji the notes' author writes at the end
# of a cheerful line. Whether a sentence is finished is decided behind them.
_TRAILING_DECOR = re.compile(r"[^\w.?!।]+$")


def _fallback_lesson(state: _State) -> Lesson:
    """The teacher without a model: the notes themselves, and a question from them.

    Always available, and no longer a single line. When the explaining step falls
    to this path the child gets several sentences out of the notes and an
    everyday example after them, because "pink is a light red colour" is a label
    and a label is not a lesson. Sentences come out of the author's own passages
    and the example out of `EVERYDAY_EXAMPLES` below - both written by a person,
    which is what lets this path run when no model can.

    It runs the other two turns as well. A **hint** reads wider, says more, and
    ends in a clue and the choices `hint_options` builds; a **reveal** opens with
    the answer and then says why. Neither may be thinner than the turn that
    failed to land, which is the whole reason this path counts its sentences.
    """
    passages = list(state.get("passages") or [])
    topic = (state.get("topic") or "this").strip()
    first = passages[0] if passages else ""
    step = state.get("step") or lesson_steps.EXPLAIN
    mode = state.get("mode") or ASK
    explaining = step == lesson_steps.EXPLAIN and mode == ASK

    heading = first.splitlines()[0].strip() if first else topic
    # What this card is about, and it is decided *here* - before a sentence of
    # the turn has been picked. It is what says which of the notes' lines belong
    # to this concept (`_on_topic`) and which everyday example fits, as well as
    # what is drawn. The author's answer decides it; the title is asked next, so
    # a lesson on pink is about pink even when the notes it retrieved explain
    # red, and the notes last of all.
    #
    # Reading it off the title alone and correcting it to the answer further
    # down is what put the circle's sentences under "Tap the triangle!": by the
    # time the answer had a say, the words had already been chosen.
    visual = _card_concept(state, visuals.from_concept(topic or heading))

    # The notes, in sentences. A single passage is often one line, so a second
    # one is read from the next passage rather than leaving the turn thin.
    wanted = _lines_wanted(mode=mode, explaining=explaining)
    lines: list[str] = []
    for passage in passages[:3]:
        lines.extend(_sentences(passage))
        if len(_on_topic(lines, visual)) >= wanted:
            break

    lines = _on_topic(lines, visual)
    explanation = " ".join(lines[:wanted]) or f"Let us look at {topic} together."
    if not visual.is_shown:
        visual = visuals.from_concept(topic or heading, explanation)

    answer = (state.get("answer") or "").strip()

    # The everyday example rounds off an explanation and a hint. It is **not**
    # added to a reveal any more: a reveal opens on a scene of its own now
    # (`REAL_LIFE_SCENES`), and `EVERYDAY_EXAMPLES` is allowed to name the thing
    # - "A samosa is a triangle" - which is exactly what the story's first beat
    # may not do.
    if explaining or mode == HINT:
        example = _everyday_example(visual)
        if example:
            explanation = f"{explanation} {example}"

    if mode == REVEAL:
        # The same three beats as the model's, hand-written: somewhere the child
        # has been, then the picture beside them, then the name for it.
        #
        # The scene replaces the notes rather than joining them, because the
        # author's sentences are *definitions* - "A triangle has three straight
        # sides" - and a definition names the answer, which is the one thing the
        # first beat may not do. A concept nobody wrote a scene for keeps the
        # notes, in the order it always had them, with the answer moved to the
        # end where it now belongs.
        scene = _real_life_scene(visual)
        beats = (scene or explanation, _look_at_the_board(visual), _answer_sentence(answer))
        return Lesson(
            explanation=" ".join(part for part in (*beats, MOVING_ON) if part),
            question="",
            expected_answer="",
            accept=(),
            strategy=state.get("strategy") or "S1_TELL",
            source="template",
            passages=tuple(passages),
            visual=visual,
        )

    if mode == HINT:
        options = _hint_choices(state, answer, visual)
        clue = _fallback_clue(visual, bool(options))
        return Lesson(
            explanation=" ".join(part for part in (explanation, clue) if part),
            # The question does not change on a hint: it is still on the screen
            # and it is still the one being answered.
            question=(state.get("question") or "").strip(),
            expected_answer=answer,
            accept=(),
            strategy=state.get("strategy") or "S1_TELL",
            source="template",
            passages=tuple(passages),
            options=options,
            visual=visual,
        )

    # The author's own question first. A person wrote it for children of this
    # class, with its own choices and their emoji, which is a better question
    # than anything that can be built out of a topic's title.
    written = authored_for(state)
    if written is not None:
        # The card is about what its question asks for, not about whichever
        # concept the retrieved notes led with.
        asking = visuals.for_card(written.answer, visual)
        return Lesson(
            explanation=explanation,
            question=written.question,
            expected_answer=written.answer,
            accept=written.accept,
            strategy=state.get("strategy") or "S1_TELL",
            source="syllabus",
            passages=tuple(passages),
            options=ensure_options(
                answer=written.answer,
                options=written.options,
                topic_id=state.get("topic_id") or "",
                visual=asking,
            ),
            visual=asking,
        )

    # The topic's own title, never the passage heading: that ends in the
    # author's skill id, and "Can you draw letter_b_write?" is not a question.
    question, expected = _fallback_question(step, topic, visual)
    question = _drawing_question(state.get("topic_id") or "", step, question)
    options: tuple[str, ...] = ()
    if expected and lesson_steps.EXPECTS.get(step) == "tap":
        options = ensure_options(
            answer=expected,
            options=(),
            topic_id=state.get("topic_id") or "",
            visual=visual,
        )
    return Lesson(
        explanation=explanation,
        question=question,
        expected_answer=expected,
        accept=(),
        strategy=state.get("strategy") or "S1_TELL",
        source="template",
        passages=tuple(passages),
        options=options,
        visual=visual,
    )


def _lines_wanted(*, mode: str, explaining: bool) -> int:
    """How many sentences of the notes this turn reads out.

    A hint gets the most of all. It is the turn after the one that did not work,
    so saying the same amount again in the same words is the one thing it must
    not do.
    """
    if mode == HINT:
        return LINES_WHEN_HINTING
    if mode == REVEAL:
        return LINES_WHEN_REVEALING
    return LINES_WHEN_EXPLAINING if explaining else LINES_WHEN_ASKING


def _answer_sentence(answer: str) -> str:
    """How the reveal **ends**. Warm, and never about the child getting it wrong.

    It used to be how the reveal opened - "The answer is triangle. Let me show
    you why." - and a child handed the answer in the first second has no reason
    left to listen to the why. It is the last beat of the story now, so it is
    written as an arrival rather than an announcement.
    """
    text = (answer or "").strip()
    if not text:
        return "That is the one."
    return f"So this one is called {text}."


# The real moment a reveal opens on, per concept, and it names no answer.
#
# Hand-written, closed, and only the things the app can draw - the same rule
# `EVERYDAY_EXAMPLES` and `examples._CONCEPT_PICTURES` keep, for the same reason:
# a scene invented on the spot for a concept nobody wrote one for is worse than
# no scene, and a concept missing from here simply falls back to the author's
# own notes. The difference from `EVERYDAY_EXAMPLES` is what it may *say*: that
# one is allowed to name the thing ("A samosa is a triangle"), and this one is
# not, because it comes before the answer rather than after it.
REAL_LIFE_SCENES = {
    "shape:circle": (
        "Think of the wheel on your toy car, going round and round. Or a hot "
        "chapati on your plate at dinner. If you put your finger on the edge and "
        "walk it all the way round, you never once have to stop and turn."
    ),
    "shape:square": (
        "Think of a slice of bread just before Mummy puts it in the toaster. Or "
        "the window in your kitchen. Walk your finger along one edge and stop - "
        "then along the next edge, and it is exactly as long as the first one."
    ),
    "shape:triangle": (
        "Think of a samosa on your plate, or a slice of pizza. Now think of the "
        "roof on top of a little house you have drawn. Each one is wide at the "
        "bottom and comes up to one point at the very top."
    ),
    "shape:rectangle": (
        "Think of the door you walked through this morning. Or a book lying on "
        "the table. Two of its sides are long and two of them are short, so it is "
        "taller than it is wide - or wider than it is tall."
    ),
    "shape:star": (
        "Think of the sky at night, right up above your house, with the little "
        "lights that twinkle in it. Or the sticker your teacher puts on your book "
        "when you have done something well."
    ),
    "colour:red": (
        "Think of a tomato in the kitchen, and a fire engine going past with its "
        "bell ringing, and an apple that is ready to eat. They are all wearing "
        "the same coat."
    ),
    "colour:blue": (
        "Think of the sky on a day with no clouds in it at all. And think of the "
        "deep sea, far out where the big fish live. Both of them are wearing the "
        "same coat."
    ),
    "colour:yellow": (
        "Think of a banana you have peeled, and the sun you draw in the corner of "
        "your picture, and a lemon in the kitchen. All three are wearing the same "
        "bright coat."
    ),
    "colour:green": (
        "Think of the leaves on a tree outside, and the grass you run on, and the "
        "peas on your plate that you push around with your spoon."
    ),
    "colour:orange": (
        "Think of a carrot, and the fruit that has the very same name as its own "
        "colour, and a marigold at a puja. They are all wearing one coat."
    ),
    "colour:purple": (
        "Think of a bunch of grapes, and a brinjal in the vegetable basket. They "
        "are darker than pink and they are not quite blue."
    ),
    "colour:pink": (
        "Think of a rose in somebody's garden, and a piece of bubblegum, and the "
        "middle of a watermelon when it is cut open."
    ),
    "colour:brown": (
        "Think of a chapati that has been on the fire a little while, and the "
        "trunk of a big tree, and a bar of chocolate."
    ),
    "colour:black": (
        "Think of the sky very late at night, and a crow sitting on a wall, and "
        "the tyre of a car."
    ),
    "colour:white": (
        "Think of a glass of milk, and a piece of cotton wool, and a cloud on a "
        "nice day."
    ),
}


def _real_life_scene(visual: visuals.Visual) -> str:
    """The scene a reveal opens on, or nothing.

    Nothing is a real answer, the same way it is for an everyday example: the
    turn falls back to the author's own notes rather than to something made up.
    """
    return REAL_LIFE_SCENES.get(visual.as_token(), "")


# What the middle beat says, by what is on the board. Short - its whole job is
# to move the child's eyes from the story to the picture that is being drawn
# beside them while it is being drawn.
_BOARD_BEATS = {
    "shape": "Now look at the picture beside me while I draw it, and trace it with your finger.",
    "colour": "Now look at the picture beside me. That is the colour, all the way through.",
    "letter": "Now look at the picture beside me. That is it, written big.",
    "number": "Now look at the picture beside me. That is the one I mean.",
    "count": "Now look at the picture beside me and count them with me, one at a time.",
    "thing": "Now look at the picture beside me while I draw it.",
}


def _look_at_the_board(visual: visuals.Visual) -> str:
    """The beat between the story and the answer: what to look at, and nothing else."""
    if not visual.is_shown:
        return ""
    return _BOARD_BEATS.get(visual.kind, "")


def _closed_with_the_answer(explanation: str, answer: str) -> bool:
    """Whether the last sentence of this reveal already names the answer.

    The model is told to finish on it, and when it has there is nothing to add:
    saying it twice at the end of a story is the one place repetition sounds
    like a mistake. When it has not - and it does not, once in five - the closing
    sentence is appended, because a reveal that never says the answer is the one
    failure this turn exists to prevent.
    """
    text = (explanation or "").strip()
    if not text or not (answer or "").strip():
        return False
    tail = [part for part in _SENTENCE_END.split(text) if part.strip()][-2:]
    return any(stage_contains(part, answer) for part in tail)


# Said at the end of a reveal, so the child hears that the question is finished
# with rather than waiting to be asked it a third time.
MOVING_ON = "Now let us try the next one together."


def _fallback_clue(visual: visuals.Visual, has_options: bool) -> str:
    """The one sentence at the end of a hint that points at the answer.

    It points; it does not say. What actually narrows the field is the choices
    beside it - which is what giving the hint *through* the options means - so
    this sentence's whole job is to send the child's eyes to the right places.
    """
    where = " Then pick the one you think it is." if has_options else ""
    if not visual.is_shown:
        # No picture to point at. Pointing at one anyway would send a child
        # looking for something that is not on their screen.
        return f"Here is a clue: think about what we just looked at together.{where}"
    if visual.kind == "colour":
        return f"Here is a clue: it is the colour in the picture beside me.{where}"
    if visual.kind == "shape":
        return f"Here is a clue: it is the shape in the picture beside me.{where}"
    if visual.kind in {"letter", "number", "count"}:
        return f"Here is a clue: look at the picture beside me - that is the one.{where}"
    return f"Here is a clue: look carefully at the picture beside me.{where}"


# Letters a wrong choice can be built from when the concept is a letter. Two
# alphabets, because a Hindi level's choices have to be Devanagari - a child
# asked to pick a Devanagari letter out of "A, B" has not been asked anything.
_ENGLISH_LETTERS = tuple(chr(code) for code in range(ord("A"), ord("Z") + 1))
_DEVANAGARI_LETTERS = tuple(
    "अ आ इ ई उ ऊ ए ऐ ओ औ "
    "क ख ग घ च छ ज झ ट ठ "
    "ड ढ ण त थ द ध न प फ "
    "ब भ म य र ल व श ष स ह".split()
)

# How many things a hint puts in front of a child. Three is enough to still be a
# question and few enough to be a help; two is what a longer list narrows to.
HINT_CHOICES = 3
NARROWED_CHOICES = 2


def hint_options(
    *, answer: str, offered: list[str] | tuple[str, ...] = (), visual: visuals.Visual | None = None
) -> tuple[str, ...]:
    """The choices a hint puts on the screen. Built here, in plain Python.

    This *is* the hint: a list of two or three things one of which is right is a
    far better clue to a four-year-old than any sentence. It is built rather than
    asked for so that the answer is always among the choices - a hint whose
    options do not contain the answer is a question with no right answer in it.

    Two shapes, in order:

    * **the child was already choosing** - the list is narrowed to the answer and
      one other, keeping the author's own words and emoji. Fewer doors is the
      help;
    * **the child was answering out loud** - three choices are built out of the
      family the concept belongs to: other colours for a colour, other shapes for
      a shape, neighbouring numbers for a number, other letters of the same
      script for a letter. A concept with no family gets no options, and the hint
      is words alone rather than a made-up choice.
    """
    wanted = stage_normalise(answer)
    if not wanted:
        return ()

    existing = [str(value).strip() for value in offered if str(value).strip()]
    right = next((value for value in existing if stage_contains(value, answer)), "")
    if right:
        if len(existing) <= NARROWED_CHOICES:
            return tuple(existing)
        others = [value for value in existing if value != right]
        keep = _shuffled(others, answer)[: NARROWED_CHOICES - 1]
        return tuple(_shuffled([right, *keep], answer))

    pool = _family(answer, visual)
    if not pool:
        return ()
    distractors = [value for value in pool if stage_normalise(value) != wanted]
    keep = _shuffled(distractors, answer)[: HINT_CHOICES - 1]
    if not keep:
        return ()
    return tuple(_shuffled([answer.strip(), *keep], answer))


def _family(answer: str, visual: visuals.Visual | None) -> tuple[str, ...]:
    """The other things of the same kind, to choose wrongly between.

    A wrong choice has to be *plausible*, which here means the same kind of
    thing: green beside red, 4 beside 3, B beside A. A silly one put there to be
    ignored is not a choice, and a child learns nothing from picking around it.
    """
    text = answer.strip()
    lowered = text.lower()

    if lowered in visuals.COLOURS:
        return visuals.COLOURS
    if lowered in visuals.SHAPES:
        return visuals.SHAPES
    if text.isdigit():
        number = int(text)
        return tuple(
            str(value) for value in (number - 2, number - 1, number + 1, number + 2) if value >= 0
        )
    if len(text) == 1 and text.upper() in _ENGLISH_LETTERS:
        return _ENGLISH_LETTERS
    if any("ऀ" <= char <= "ॿ" for char in text):
        return _DEVANAGARI_LETTERS

    kind = visual.kind if visual else ""
    if kind == "colour":
        return visuals.COLOURS
    if kind == "shape":
        return visuals.SHAPES
    return ()


def authored_for(state: _State) -> authored_questions.Authored | None:
    """The syllabus's own question for this turn, or None.

    Only for the steps that ask the child to choose something. Saying a letter
    out loud and drawing it are not questions the author wrote alternatives for,
    and the reveal and the hint are about a question that already exists.
    """
    asked = state.get("asked")
    if not isinstance(asked, authored_questions.Authored):
        return None
    if (state.get("mode") or ASK) != ASK:
        return None
    if (state.get("step") or lesson_steps.EXPLAIN) not in (lesson_steps.MATCH, lesson_steps.QUIZ):
        return None
    return asked


def ensure_options(
    *,
    answer: str,
    options: tuple[str, ...] | list[str],
    topic_id: str = "",
    visual: visuals.Visual | None = None,
) -> tuple[str, ...]:
    """Choices for a question that needs them, whatever it took to get some.

    A tap question with no choices on it is a typing box in front of a
    two-year-old, which is not a question at all - it is the turn quietly
    failing. So an empty list is repaired rather than accepted, in the order that
    keeps the most of the author in it:

    1. what the caller already had, if it holds the answer;
    2. the author's own choices for this answer, out of the class's syllabus;
    3. the family the concept belongs to - other colours for a colour, other
       letters of the same script for a letter - built by `hint_options`.

    Still nothing means the concept has no family and the syllabus never offered
    it as a choice; the caller shows the question without buttons rather than
    inventing plausible-looking nonsense for a child to pick between.
    """
    existing = tuple(str(value).strip() for value in options if str(value).strip())
    if len(existing) >= 2 and any(stage_contains(option, answer) for option in existing):
        return existing

    from_author = authored_questions.options_for(topic_id, answer)
    if len(from_author) >= 2:
        return from_author

    return hint_options(answer=answer, visual=visual)


def _shuffled(values: list[str], seed: str) -> list[str]:
    """The same order every time for the same answer.

    A reload has to show the same choices in the same places: a child who looks
    away and back at a different screen has been asked a different question.
    Seeding on the answer is what makes that free.
    """
    out = list(values)
    random.Random(f"hint:{seed}").shuffle(out)
    return out


# One everyday example per thing the app can draw, written out rather than
# generated. A child of three learns a colour from the tomato and the fire
# engine, not from the sentence "pink is a light red colour" - and the
# deterministic teacher has no model to think of the tomato for it.
#
# Only the closed vocabularies are here: every colour and shape the app draws.
# Letters are left out on purpose - "A is for apple" is the author's to write,
# and it is already in the notes for the letters that have it.
EVERYDAY_EXAMPLES = {
    "colour:red": "Look for red on a tomato, on a fire engine and on a ripe apple.",
    "colour:blue": "Look for blue in the sky on a clear day, and in the sea.",
    "colour:yellow": "Look for yellow on a banana, on a lemon and on the sun you draw.",
    "colour:green": "Look for green on leaves, on grass and on peas.",
    "colour:orange": "Look for orange on an orange, on a carrot and on a marigold.",
    "colour:purple": "Look for purple on grapes, on a brinjal and on some flowers.",
    "colour:pink": "Look for pink on a rose, on bubblegum and on the inside of a watermelon.",
    "colour:brown": "Look for brown on a chapati, on a tree trunk and on a chocolate.",
    "colour:black": "Look for black on the night sky, on a crow and on a car tyre.",
    "colour:white": "Look for white on milk, on cotton wool and on a cloud.",
    "shape:circle": "A wheel is a circle, and so is a chapati and the full moon.",
    "shape:square": "A window can be a square, and so can a slice of bread.",
    "shape:triangle": "A samosa is a triangle, and so is the roof on a drawing of a house.",
    "shape:rectangle": "A door is a rectangle, and so is a book and a bar of chocolate.",
    "shape:star": "A star is what twinkles in the sky at night.",
}


def _sentences(passage: str) -> list[str]:
    """A passage read the way a person would say it: in sentences.

    The heading goes - it ends in the author's skill id - and so does the
    retrieval marker. What is left is joined back into one piece of prose and
    then cut at its own full stops, because the line breaks in it are wrapping
    and mean nothing. A sentence the author left without a full stop is given
    one, so three of them read as three sentences rather than one long breath.
    """
    body = " ".join(
        _KIND_MARKER.sub("", line).strip()
        for line in passage.splitlines()[1:]
        if line.strip()
    )
    body = " ".join(body.split())
    if not body:
        return []

    out: list[str] = []
    for part in _SENTENCE_END.split(body):
        text = part.strip()
        if not text:
            continue
        core = _TRAILING_DECOR.sub("", text)
        if core and not core.endswith((".", "?", "!", "।")):
            text = f"{text}."
        out.append(text)
    return out


def _card_answer(state: _State) -> str:
    """The answer this card is about, whichever of its turns this is.

    A hint and a reveal are handed the answer already in play. An asking turn
    has the author's own question in `asked` - and so does the explaining step,
    which does not ask it but is written to lead into it (`_leading_question`),
    so the explaining turn is about the same thing the question after it is.
    """
    if (state.get("mode") or ASK) in (HINT, REVEAL):
        return (state.get("answer") or "").strip()
    written = state.get("asked")
    if isinstance(written, authored_questions.Authored):
        return (written.answer or "").strip()
    return ""


def _card_concept(state: _State, drawn: visuals.Visual | None = None) -> visuals.Visual:
    """What this card is about, worked out before a word of it is chosen.

    The answer a person wrote is what says so; the title, the notes and the
    model's own token only get a say when that answer names nothing the app can
    draw. It is `visuals.for_card`'s rule, asked early enough to decide which
    sentences the turn is built out of rather than only which picture sits
    beside them.
    """
    return visuals.for_card(_card_answer(state), drawn)


def _notes_about(content: str, visual: visuals.Visual) -> str:
    """One retrieved passage with the paragraphs about a *different* shape or colour gone.

    `_about_this_card` narrows by the author's skill id, and the teaching notes
    carry none: "## Shapes" is one passage explaining the circle, the square,
    the triangle and the rectangle, and the circle is the paragraph it opens
    with. A hint on the triangle may not name its own answer, so the circle was
    the most available concrete thing on the page and the turn taught that
    instead - the child got a lesson on the circle under "Tap the triangle!".

    A **paragraph** is the unit, not a line and not a sentence. The notes are
    wrapped markdown, so dropping lines cuts "A square has four sides... A
    window," off "a biscuit, a slice of bread." and leaves the crumbs; and a
    paragraph's examples - "A wheel, a plate, the sun" - name no shape at all,
    so dropping single sentences leaves the circle's examples sitting under the
    triangle. What a paragraph names is what it is about, and the whole of it
    goes or the whole of it stays.

    Two things this may not do. It only ever *removes* words - nothing new
    reaches the model, and the answer still never enters a query. And a passage
    with no paragraph about this concept is left **whole**: the notes simply do
    not cover it, and teaching from a neighbour beats teaching from nothing,
    which is the rule `_about_this_card` already keeps.
    """
    if visual.kind not in {"colour", "shape"}:
        return content
    heading, newline, body = content.partition(chr(10))
    if not newline:
        return content

    family = visuals.COLOURS if visual.kind == "colour" else visuals.SHAPES
    others = [name for name in family if name != visual.value]

    kept: list[str] = []
    mine = False
    dropped = False
    for block in _BLANK_LINE.split(body):
        prose = " ".join(block.split())
        if not prose:
            continue
        if re.search(rf"\b{visual.value}s?\b", prose, re.I):
            kept.append(prose)
            mine = True
        elif any(re.search(rf"\b{name}s?\b", prose, re.I) for name in others):
            dropped = True
        else:
            kept.append(prose)

    if not mine or not dropped:
        return content
    return f"{heading}{newline}" + (chr(10) * 2).join(kept)


def _on_topic(lines: list[str], visual: visuals.Visual) -> list[str]:
    """Drop the sentences that are about a *different* colour or shape.

    Retrieval hands back the topic's neighbours as well as the topic, and a
    colours passage explains every colour it knows. Saying "red is the colour of
    a tomato" beside a pink circle is worse than saying less: the picture and the
    words have to be about the same thing.
    """
    if visual.kind not in {"colour", "shape"}:
        return lines
    family = visuals.COLOURS if visual.kind == "colour" else visuals.SHAPES
    others = [name for name in family if name != visual.value]

    kept: list[str] = []
    for line in lines:
        if re.search(rf"\b{visual.value}s?\b", line, re.I):
            kept.append(line)
        elif not any(re.search(rf"\b{name}s?\b", line, re.I) for name in others):
            kept.append(line)
    # Everything mentioned something else. Better the author's words about the
    # family than nothing at all.
    return kept or lines


def _everyday_example(visual: visuals.Visual) -> str:
    """The one sentence that turns a label into a lesson, or nothing.

    Nothing is a real answer: a made-up example is worse than none, and the
    passages the notes gave are already the author's own words.
    """
    token = visual.as_token()
    if token in EVERYDAY_EXAMPLES:
        return EVERYDAY_EXAMPLES[token]
    if visual.kind == "number" and visual.value.isdigit() and 1 <= int(visual.value) <= 10:
        count = int(visual.value)
        if count == 1:
            return "Find one thing around you right now - one nose, or one spoon on the table."
        return f"Find {count} things around you right now - {count} fingers, or {count} spoons on the table."
    return ""


def _decode(request: ChatRequest) -> dict | None:
    """The model's JSON, with one retry that does not use JSON mode.

    Groq validates JSON mode itself and answers 400 `json_validate_failed` when
    the model's own output does not parse - which the big model does now and
    then, usually by wrapping the object in a code fence. Asking again in plain
    text and taking the first object out of it rescues that turn; anything else
    falls through to the notes.
    """
    try:
        return json.loads(chat(request))
    except (LLMUnavailable, json.JSONDecodeError, TypeError) as error:
        logger.info("AI Teacher: first attempt did not decode (%s)", error)

    try:
        text = chat(
            ChatRequest(
                system=request.system,
                user=[*request.user, "Return the JSON object only. No code fence, no commentary."],
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                json_object=False,
                model=request.model,
                timeout=request.timeout,
            )
        )
    except LLMUnavailable as error:
        logger.info("AI Teacher fell back to the notes: %s", error)
        return None

    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        decoded = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


_EMOJI_RANGES = (
    (0x1F000, 0x1FAFF),  # pictographs, faces, symbols
    (0x2600, 0x27BF),  # misc symbols and dingbats
    (0xFE00, 0xFE0F),  # variation selectors
    (0x1F1E6, 0x1F1FF),  # flags
    (0x2B00, 0x2BFF),  # arrows and geometric shapes
    (0x20E3, 0x20E3),  # the keycap that makes 3️⃣
)


def strip_emoji(text: str) -> str:
    """The question in plain words.

    The prompt asks for no emojis and the model mostly obliges, but "mostly" is
    not a rule - so the question is cleaned here, where it is certain. The
    choices keep theirs: those are pictures a pre-reader taps, not decoration.
    """
    kept = [
        char
        for char in (text or "")
        if not any(low <= ord(char) <= high for low, high in _EMOJI_RANGES)
    ]
    cleaned = " ".join("".join(kept).split()).strip()
    # "Which one is purple? 🟣 or 🍇" leaves a dangling "or" behind it, and the
    # emoji it was joining is gone - so the word goes with it.
    cleaned = re.sub(r"[\s,]*\b(?:or|and)\b[\s,]*([?.!]*)$", r"\1", cleaned, flags=re.I).strip()
    # A space a removed emoji left standing in front of its punctuation.
    return re.sub(r"\s+([?.!,])", r"\1", cleaned).strip()


def _fallback_question(
    step: str, topic_title: str, visual: visuals.Visual | None = None
) -> tuple[str, str]:
    """What the deterministic teacher asks on each step. No model, still a lesson.

    **It asks about the thing, not about the topic.** A level is called
    "Pre-Writing Strokes" and "can you show me pre-writing strokes?" is that
    heading with a question mark on it - a syllabus category, which a
    two-year-old cannot show anybody. When the turn has a picture beside it the
    question is about what is in the picture, which is the thing the child has
    just been taught and the only thing on their screen. The title is the last
    resort, for a concept with no picture at all.
    """
    named = _thing_named(topic_title, visual)
    if step == lesson_steps.EXPLAIN:
        return "", ""
    if step == lesson_steps.SAY_IT:
        return f"Now your turn - can you say {named}?", named
    if step == lesson_steps.DRAW:
        return f"Can you draw {named} with your finger?", "done"
    return f"Which one is {named}?", named


def _drawing_question(topic_id: str, step: str, fallback: str) -> str:
    """The author's words for the tracing card, when they wrote any.

    "Scribble anywhere you like!" is what a person wrote on the same card the
    canvas is about to draw; "can you draw pre-writing strokes with your finger?"
    is what the topic's title becomes when nobody has.
    """
    if step != lesson_steps.DRAW:
        return fallback
    return authored_questions.drawing_prompt(topic_id) or fallback


def _thing_named(topic_title: str, visual: visuals.Visual | None) -> str:
    """What this turn is actually about, in the words a child would use."""
    if visual is not None and visual.is_shown:
        if visual.kind == "letter":
            return visual.value
        if visual.kind in {"number", "count"}:
            return visual.value
        if visual.kind == "colour":
            return f"the colour {visual.value}"
        if visual.kind == "shape":
            return f"the {visual.value}"
    # No picture. What comes after a colon in a level's title is the thing it
    # teaches - "Colours: Pink, Black, White" - and the whole title otherwise.
    named = topic_title.split(":", 1)[1] if ":" in topic_title else topic_title
    return (named or "this").strip().lower()


def _teach(state: _State) -> _State:
    passages = list(state.get("passages") or [])
    if not is_configured():
        return {"lesson": _fallback_lesson(state)}

    strategy = state.get("strategy") or "S1_TELL"
    step = state.get("step") or lesson_steps.EXPLAIN
    mode = state.get("mode") or ASK
    request = ChatRequest(
        system=[TEACHER_SYSTEM_PROMPT],
        user=[
            f"Notes:\n{state.get('context') or ''}",
            f"Today the child is learning: {state.get('topic') or 'numbers'}.",
            _who_is_listening(state),
            f"Step of the lesson: {step} - {_brief_for(state)}",
            f"Teaching strategy to use: {strategy} - {STRATEGY_BRIEFS.get(strategy, '')}",
            *_sitting_so_far(state),
            *_leading_question(state),
            *_help_context(state),
        ],
        temperature=0.5,
        # Room for the answer *after* the model has thought, and no more than
        # that, because the ceiling is not free: Groq reserves
        # `max_completion_tokens` against the account's tokens-per-minute budget
        # whether or not they are used. A measured teaching turn is a ~1000
        # token prompt and **113** completion tokens (36 of them reasoning), so
        # reserving 1200 charged ~2200 against an 8000/minute budget - under
        # four turns a minute before every later one sat in a queue, which is
        # what "the AI is slow" looked like from a child's chair. 500 is more
        # than four times what a turn actually writes and halves the reservation.
        #
        # It is not 500 for its own sake: at 500 *without* `reasoning_effort`
        # the big model's thinking ate the whole budget and Groq rejected the
        # empty body. The two settings go together.
        max_tokens=500,
        json_object=True,
        reasoning_effort="low",
        # The playground runs on the big model on purpose: nothing it says
        # reaches a child's real progress, so a better answer is worth the wait.
        model=get_settings().groq_teacher_model,
        # The class allows six seconds because a child is watching a screen. Here
        # the bot is a sandbox the grown-up is trying out, and the big model is
        # worth waiting a little longer for.
        timeout=20.0,
    )

    decoded = _decode(request)
    if decoded is None:
        return {"lesson": _fallback_lesson(state)}

    explanation = str(decoded.get("explanation") or "").strip()
    if not explanation:
        return {"lesson": _fallback_lesson(state)}

    # The model names a picture; `visuals.parse` decides whether that name is one
    # the app actually draws. Anything else falls back to reading the concept out
    # of the words, and then to no picture at all.
    visual = visuals.parse(decoded.get("visual"))
    if not visual.is_shown:
        visual = visuals.from_concept(state.get("topic") or "", explanation)

    # A hint and a reveal are turns *about a question that already exists*. The
    # model writes the words and nothing else: it does not get to change the
    # question, the answer, or - on a hint - which choices are on the screen,
    # because all three are what the child is in the middle of.
    if mode in (HINT, REVEAL):
        return {"lesson": _help_lesson(state, explanation, visual, strategy, passages)}

    question = strip_emoji(str(decoded.get("question") or ""))
    expected = str(decoded.get("expected_answer") or "").strip()
    # The explaining step is not a question, and neither is a step whose question
    # the author already wrote - on both the model was asked for words alone, so
    # coming back without a question is the right answer rather than a broken one.
    teaching_only = step == lesson_steps.EXPLAIN
    written_ahead = authored_for(state) is not None
    if not teaching_only and not written_ahead and (not question or not expected):
        return {"lesson": _fallback_lesson(state)}
    if teaching_only:
        question, expected = "", ""

    raw_accept = decoded.get("accept") or []
    accept = tuple(str(value).strip() for value in raw_accept if str(value).strip())[:6]
    options = _options_from(decoded.get("options"), expected=expected)

    # The author's question wins on a step where the child chooses. The model
    # has just written the explanation around this concept, which is what it is
    # for; the question itself was written by a person for children of this age,
    # with its own choices, and that is the whole point of having a syllabus.
    written = authored_for(state)
    if written is not None:
        question, expected, accept = written.question, written.answer, written.accept
        options = written.options
        source = "syllabus"
    else:
        source = "llm"

    # Same again: a turn that asks for something draws the thing it is asking
    # about. The explaining step has no answer of its own, and it is not about
    # nothing - it is the turn that leads into the author's next question, and
    # its notes have just been narrowed to that question's concept - so the card
    # falls back to *that* before it falls back to the notes. Otherwise the
    # explanation taught the triangle and the board drew the circle.
    visual = visuals.for_card(expected, _card_concept(state, visual))

    if expected and lesson_steps.EXPECTS.get(step) == "tap":
        options = ensure_options(
            answer=expected,
            options=options,
            topic_id=state.get("topic_id") or "",
            visual=visual,
        )

    question = _drawing_question(state.get("topic_id") or "", step, question)

    return {
        "lesson": Lesson(
            explanation=explanation,
            question=question,
            expected_answer=expected,
            accept=accept,
            strategy=strategy,
            source=source,
            passages=tuple(passages),
            options=options,
            visual=visual,
        )
    }


def _who_is_listening(state: _State) -> str:
    """One line telling the model whose class this is and how old they are.

    Without it the prompt only knows "a child aged 2 to 6", and it wrote for the
    top of that range - which is how a Play Group two-year-old ended up with a
    UKG question.
    """
    band = (state.get("age_band") or "").strip()
    if not band:
        return "This child is in a nursery class. Keep every question tiny."
    return (
        f"This child is in {band}. Every question you write must be answerable by "
        "the youngest child in that class."
    )


def _brief_for(state: _State) -> str:
    """What the model is being asked to do this turn, in one line."""
    mode = state.get("mode") or ASK
    if mode == HINT:
        return lesson_steps.HINT_BRIEF
    if mode == REVEAL:
        return lesson_steps.REVEAL_BRIEF
    return lesson_steps.BRIEFS.get(state.get("step") or lesson_steps.EXPLAIN, "")


def _leading_question(state: _State) -> list[str]:
    """The authored question, told to the model so its explanation leads into it.

    Without this the model explains whatever the retrieved notes are strongest
    on - a turn on pre-writing strokes explained the letter A - and the child
    then gets a question about something else entirely. The *answer* is not sent
    and never is: it is the author's, `stage.judge` marks against it, and a model
    that knows the answer is a model that can hand it over while explaining.
    """
    written = authored_for(state)
    if written is None:
        return []
    return [
        f"After your explanation the child will be asked: {written.question}",
        "Explain what they need to know in order to answer that, and nothing "
        "else. Do not answer it for them, and do not write a question of your "
        "own - leave \"question\" and \"expected_answer\" empty.",
    ]


# How many of the sitting's turns the teacher is reminded of. Four is roughly two
# questions' worth - enough that a hint does not repeat the explanation it is
# helping with, short enough that the memory cannot crowd out the notes the turn
# is actually meant to teach from.
MEMORY_TURNS = 4

# One remembered line is a reminder, not a transcript.
MEMORY_LINE_CHARS = 160


def _trim(text: str, limit: int = MEMORY_LINE_CHARS) -> str:
    words = " ".join(str(text or "").split())
    return words if len(words) <= limit else words[: limit - 1].rstrip() + "…"


def _sitting_so_far(state: _State, *, closing: str = "") -> list[str]:
    """The last few turns of this sitting, in the order they happened.

    Every turn used to be written from nothing: the model was handed the notes,
    the step and the strategy, and no idea that it had already used the same
    everyday example two turns ago or that the child had just got this very
    thing right. That is what made a hint repeat the explanation word for word.

    It is a **reminder, not an instruction**: nothing here decides anything. The
    step, the strategy and the authored question are still what the turn is
    made of, and `stage.judge` still marks in pure Python. The memory only stops
    the class from saying the same thing twice.
    """
    remembered = list(state.get("memory") or ())[-MEMORY_TURNS:]
    lines: list[str] = []
    for turn in remembered:
        said = _trim(turn.get("explanation", ""))
        asked = _trim(turn.get("question", ""))
        answered = _trim(turn.get("child_answer", ""), 60)
        if said:
            lines.append(f"- You said: {said}")
        if asked and not answered:
            lines.append(f"- You asked: {asked}")
        if answered:
            verdict = turn.get("is_correct")
            how = "" if verdict is None else (" and it was right" if verdict else " and it did not land")
            lines.append(f'- The child answered "{answered}"{how}.')
    if not lines:
        return []
    return [
        "What has already been said in this sitting, oldest first:\n" + "\n".join(lines),
        closing
        or (
            "Do not repeat any of it. Teach the next thing in new words, with an "
            "example you have not spent yet."
        ),
    ]


def _help_context(state: _State) -> list[str]:
    """The question and answer already in play, told to the model on a help turn.

    Only on a hint or a reveal. On an ordinary turn the model writes its own
    question, and handing it an answer to a question it has not asked yet is how
    a bot ends up teaching the answer key.
    """
    mode = state.get("mode") or ASK
    if mode not in (HINT, REVEAL):
        return []
    lines = [f"The question already on the screen is: {state.get('question') or ''}"]
    lines.append(f"The answer it is looking for is: {state.get('answer') or ''}")
    if mode == HINT:
        lines.append(
            "Never write that answer in your explanation - the child is about to "
            "choose it for themselves."
        )
    return lines


def _help_lesson(
    state: _State,
    explanation: str,
    visual: visuals.Visual,
    strategy: str,
    passages: list[str],
) -> Lesson:
    """A hint or a reveal, with only the words taken from the model."""
    answer = (state.get("answer") or "").strip()
    # The picture on a helping turn is the picture of the question being helped
    # with. The model chose one while writing the words, and on a level whose
    # title names no concept that choice drifts to whatever it has just been
    # explaining.
    visual = visuals.for_card(answer, visual)
    if (state.get("mode") or ASK) == REVEAL:
        # The story's three beats are the model's to write (`REVEAL_BRIEF`), and
        # the answer is the end of it rather than the start. All this does is
        # make sure the child actually hears it: a reveal that talks around the
        # answer and never says it is the one failure this turn exists to
        # prevent, and one that says it twice at the end is the one place
        # repeating yourself sounds like a mistake.
        closing = "" if _closed_with_the_answer(explanation, answer) else _answer_sentence(answer)
        return Lesson(
            explanation=" ".join(
                part for part in (explanation, closing, MOVING_ON) if part
            ),
            question="",
            expected_answer="",
            accept=(),
            strategy=strategy,
            source="llm",
            passages=tuple(passages),
            visual=visual,
        )

    options = _hint_choices(state, answer, visual)
    return Lesson(
        explanation=explanation,
        question=(state.get("question") or "").strip(),
        expected_answer=answer,
        accept=(),
        strategy=strategy,
        source="llm",
        passages=tuple(passages),
        options=options,
        visual=visual,
    )


def _hint_choices(state: _State, answer: str, visual: visuals.Visual) -> tuple[str, ...]:
    """The choices a hint puts on the screen, and it must have some.

    The hint's whole method is *fewer doors*: a child who missed the question is
    shown the same one again with two things to choose between. A hint that
    arrives with no buttons has given them nothing and left them with the typing
    box they could not use the first time, so an empty narrowing falls through to
    the author's own choices for this answer before it gives up.
    """
    narrowed = hint_options(
        answer=answer, offered=list(state.get("offered") or []), visual=visual
    )
    if narrowed:
        return narrowed
    return ensure_options(
        answer=answer,
        options=(),
        topic_id=state.get("topic_id") or "",
        visual=visual,
    )


def _options_from(raw: object, *, expected: str) -> tuple[str, ...]:
    """The choices to show, checked before a child ever sees them.

    Three rules, and all three are about not putting a broken question in front
    of a four-year-old: they are short, there are at most four, and the answer is
    among them. A set of options that does not contain the answer is a question
    with no right answer in it, so it is thrown away rather than shown.
    """
    if not isinstance(raw, (list, tuple)):
        return ()

    seen: list[str] = []
    for value in raw:
        text = str(value).strip()
        if not text or len(text) > 24:
            continue
        if text.lower() not in {existing.lower() for existing in seen}:
            seen.append(text)

    if len(seen) < 2:
        return ()

    # `contains_answer`, and not a plain substring, because "a" is inside
    # "banana": the loose test used to let a set through whose "right" option was
    # a word that merely happened to contain the answer's letters, and then
    # `stage.judge` - which was never that generous - marked the child wrong for
    # tapping it. One rule for putting an option on the screen and for marking
    # it, or a child gets punished for the gap between two.
    if not any(stage_contains(option, expected) for option in seen):
        return ()
    return tuple(seen[:4])


def _graph():
    builder = StateGraph(_State)
    builder.add_node("retrieve", _retrieve)
    builder.add_node("choose", _choose)
    builder.add_node("teach", _teach)
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "choose")
    builder.add_edge("choose", "teach")
    builder.add_edge("teach", END)
    return builder.compile()


_COMPILED = None


def teach(
    *,
    subject: str,
    topic: str,
    spent: list[str],
    experience_mode: str = "standard",
    topic_id: str = "",
    class_id: str = "",
    age_band: str = "",
    step: str = lesson_steps.EXPLAIN,
    mode: str = ASK,
    question: str = "",
    answer: str = "",
    offered: list[str] | tuple[str, ...] = (),
    asked: authored_questions.Authored | None = None,
    memory: list[dict] | tuple[dict, ...] = (),
    strategy: str = "",
) -> Lesson:
    """Run one turn of the agent and get back what to say and what to ask.

    `mode` is which of the three turns a question gets. `ASK` writes a new
    question. `HINT` and `REVEAL` are about the question already on the screen,
    so they are handed it - along with its answer and whatever the child was
    already being offered - and they never write a new one.

    `memory` is the sitting so far, oldest first, so the class remembers what it
    has already said. It changes nothing about what the turn *is*: it is a
    reminder handed to the model, and no step, verdict or star is downstream of
    it.
    """
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = _graph()
    result = _COMPILED.invoke(
        {
            "subject": subject,
            "topic": topic,
            "topic_id": topic_id,
            "class_id": class_id,
            "age_band": age_band,
            "asked": asked,
            "step": step,
            "spent": list(spent),
            "experience_mode": experience_mode,
            "mode": mode,
            "question": question,
            "answer": answer,
            "offered": list(offered),
            "memory": [dict(turn) for turn in memory],
            "chosen": strategy,
        }
    )
    lesson = result.get("lesson")
    if isinstance(lesson, Lesson):
        return lesson
    return _fallback_lesson(result)  # pragma: no cover - the graph always sets one


ASK_SYSTEM_PROMPT = """You are the Saksham IQ AI Teacher, answering a small child's own question.

You are given passages from the teacher's notes and the syllabus, what the child
is learning right now, and what they asked. Answer only from the passages; if
they do not cover it, say the nearest true thing that they do cover.

Two sentences at most, in English, in words a four-year-old knows. Warm and
plain. Never the words wrong, bad, failed or no. Do not ask a question back -
the lesson has its own question waiting, and yours would be a second one.

If what they said is not really a question - a story, a noise, "I want mumma" -
answer the person rather than the words: one kind sentence, and back to the
thing you were teaching.

Return exactly one JSON object and nothing else: {"answer": "..."}"""


def answer_question(
    *, topic: str, topic_id: str, question: str, memory: list[dict] | tuple[dict, ...] = ()
) -> tuple[str, str]:
    """What the child asked, answered from the notes. Returns (answer, source).

    This is not a turn of the lesson: nothing is marked, no strategy is spent and
    the step does not move. A child who asks something in the middle of being
    taught is doing the most cooperative thing there is, and the app should
    answer them rather than repeat the question they interrupted.
    """
    asked = (question or "").strip()
    if not asked:
        return "", "template"

    hits = rag.search(f"{topic} {asked}".strip(), topic_id=topic_id, top_k=rag.DEFAULT_TOP_K)
    passages = [hit.passage.content for hit in hits]

    if not is_configured():
        # No model: the closest passage in the teacher's own words is a better
        # answer than silence.
        first = passages[0] if passages else ""
        lines = [line.strip() for line in first.splitlines()[1:] if line.strip()]
        return (" ".join(lines[:1]) or f"Good question! Let us look at {topic} together."), "template"

    decoded = _decode(
        ChatRequest(
            system=[ASK_SYSTEM_PROMPT],
            user=[
                "Notes:" + chr(10) + (chr(10) + chr(10)).join(passages),
                f"The child is learning: {topic}.",
                *_sitting_so_far(
                    {"memory": list(memory)},
                    closing=(
                        "That is what the class has just been doing. Answer the "
                        "child's question in a way that fits it, and do not "
                        "repeat an explanation they have already heard."
                    ),
                ),
                f"The child asked: {asked}",
            ],
            temperature=0.4,
            # An answer to a child's own question is a couple of sentences. See
            # the note on the teaching turn: a ceiling is reserved against the
            # per-minute budget even when it is not spent.
            max_tokens=300,
            json_object=True,
            model=get_settings().groq_teacher_model,
            reasoning_effort="low",
            timeout=20.0,
        )
    )
    answer = str((decoded or {}).get("answer") or "").strip()
    if not answer:
        return "Good question! Let us keep looking at this together.", "template"
    return answer, "llm"


def praise() -> str:
    return random.choice(
        ("Yes! That is it.", "Lovely - you got it.", "That is right, well done!")
    )


def encourage() -> str:
    """Said before the hint: the question is still open and help is coming."""
    return random.choice(
        (
            "Good trying! Let us look again.",
            "Nearly! Let us try it another way.",
            "Good try - here is another way to see it.",
        )
    )


def reassure() -> str:
    """Said before the answer is given.

    A child who has missed the same thing twice does not need to be told to try
    harder - they need to be told it is fine and then shown. Nothing here hints
    that they failed at anything, because they have not: this is the turn where
    the teaching happens.
    """
    return random.choice(
        (
            "That one was tricky - let me show you.",
            "This one is a hard one. I will tell you this time.",
            "Good trying! Here is the answer, and why.",
        )
    )


__all__ = [
    "ASK",
    "HINT",
    "MOVING_ON",
    "REVEAL",
    "Lesson",
    "STRATEGY_BRIEFS",
    "answer_question",
    "choose_strategy",
    "encourage",
    "hint_options",
    "reassure",
    "praise",
    "search_notes",
    "strip_emoji",
    "teach",
]
