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
from app.playground import rag, visuals
from app.playground.stage import normalise as stage_normalise
from app.policy import actions as policy_actions


logger = logging.getLogger(__name__)

TEACHER_SYSTEM_PROMPT = """You are the Saksham IQ AI Teacher, teaching one child aged 2 to 6.

You are given passages from the teacher's own notes, and one teaching strategy to
use. Teach only what the passages say. If they do not cover something, teach the
nearest thing they do cover rather than inventing it.

How you speak:
- English only, in short sentences a four-year-old can follow.
- One idea per turn - but teach that idea properly rather than naming it. A
  child who is told "pink is a light red colour" has been given a label, not a
  lesson.
- **On the explaining step, write three or four short sentences.** Say what the
  thing is; say it again in different words; give **one everyday example the
  child has seen for themselves** - something in the room, on their plate, on
  the way to the shop; and finish by telling them what to look at in the
  picture beside you. Never fewer than three sentences on that step.
- On a step that asks a question, one or two sentences before it is enough: the
  question should be the last thing the child hears.
- Warm and plain. Never the words wrong, bad, failed, stupid, or no.
- Only bring in a Hindi letter when the notes you were given are about Hindi.
  When you do, quote it in Devanagari inside your English sentence and never
  write it in Roman letters. An English or maths lesson stays English.

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
    step: str
    spent: list[str]
    experience_mode: str
    context: str
    passages: list[str]
    strategy: str
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
    query = " ".join(
        part for part in (state.get("topic") or "", state.get("subject") or "", step) if part
    ).strip()
    # A hint is the second telling, and it has to be a *deeper* one than the
    # first - so it reads wider than a plain turn does. Two more passages is the
    # difference between saying the same thing again and saying more about it.
    top_k = rag.DEFAULT_TOP_K + 2 if state.get("mode") == HINT else rag.DEFAULT_TOP_K
    hits = rag.search(
        query or "how to teach one thing",
        top_k=top_k,
        topic_id=state.get("topic_id") or "",
        kinds=lesson_steps.RETRIEVAL_KINDS.get(step, ()),
    )
    passages = [hit.passage.content for hit in hits]
    return {"context": chr(10).join(passages), "passages": passages}


def _choose(state: _State) -> _State:
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
# The reveal opens with the answer itself, so what follows is only the why - two
# sentences and an example, and then the class moves on.
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
    # No model to choose a picture, so it is read out of the words instead - and
    # it is also what says which sentences belong to this concept and which
    # everyday example fits. The title is asked before the notes, so a lesson on
    # pink is about pink even when the notes it retrieved explain red.
    visual = visuals.from_concept(topic or heading)

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

    if explaining or mode in (HINT, REVEAL):
        example = _everyday_example(visual)
        if example:
            explanation = f"{explanation} {example}"

    answer = (state.get("answer") or "").strip()

    if mode == REVEAL:
        # The answer first, because it is the thing the child has been waiting
        # for, and the explaining after it rather than in front of it.
        return Lesson(
            explanation=" ".join(
                part for part in (_answer_sentence(answer), explanation, MOVING_ON) if part
            ),
            question="",
            expected_answer="",
            accept=(),
            strategy=state.get("strategy") or "S1_TELL",
            source="template",
            passages=tuple(passages),
            visual=visual,
        )

    if mode == HINT:
        options = hint_options(
            answer=answer, offered=list(state.get("offered") or []), visual=visual
        )
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

    # The topic's own title, never the passage heading: that ends in the
    # author's skill id, and "Can you draw letter_b_write?" is not a question.
    question, expected = _fallback_question(step, topic)
    return Lesson(
        explanation=explanation,
        question=question,
        expected_answer=expected,
        accept=(),
        strategy=state.get("strategy") or "S1_TELL",
        source="template",
        passages=tuple(passages),
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
    """How the reveal opens. Warm, and never about the child getting it wrong."""
    text = (answer or "").strip()
    if not text:
        return "Let me show you this one."
    return f"The answer is {text}. Let me show you why."


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
    right = next((value for value in existing if wanted in stage_normalise(value)), "")
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


def _fallback_question(step: str, topic_title: str) -> tuple[str, str]:
    """What the deterministic teacher asks on each step. No model, still a lesson."""
    name = (topic_title or "this").strip().lower()
    if step == lesson_steps.EXPLAIN:
        return "", ""
    if step == lesson_steps.SAY_IT:
        return f"Now your turn - can you say {name}?", name
    if step == lesson_steps.DRAW:
        return f"Can you draw {name} with your finger?", "done"
    return f"Can you show me {name}?", name


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
            f"Step of the lesson: {step} - {_brief_for(state)}",
            f"Teaching strategy to use: {strategy} - {STRATEGY_BRIEFS.get(strategy, '')}",
            *_help_context(state),
        ],
        temperature=0.5,
        # Room for the answer *after* the model has thought. At 500 the big
        # model's reasoning ate the whole budget and Groq rejected the empty
        # body; "low" effort keeps the turn under two seconds as well. The
        # explaining turn is three or four sentences now, so the budget went up
        # with it - a truncated body is a turn taught from the notes instead.
        max_tokens=1200,
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
    # The explaining step is not a question, so the model is not held to one.
    teaching_only = step == lesson_steps.EXPLAIN
    if not teaching_only and (not question or not expected):
        return {"lesson": _fallback_lesson(state)}
    if teaching_only:
        question, expected = "", ""

    raw_accept = decoded.get("accept") or []
    accept = tuple(str(value).strip() for value in raw_accept if str(value).strip())[:6]
    options = _options_from(decoded.get("options"), expected=expected)

    return {
        "lesson": Lesson(
            explanation=explanation,
            question=question,
            expected_answer=expected,
            accept=accept,
            strategy=strategy,
            source="llm",
            passages=tuple(passages),
            options=options,
            visual=visual,
        )
    }


def _brief_for(state: _State) -> str:
    """What the model is being asked to do this turn, in one line."""
    mode = state.get("mode") or ASK
    if mode == HINT:
        return lesson_steps.HINT_BRIEF
    if mode == REVEAL:
        return lesson_steps.REVEAL_BRIEF
    return lesson_steps.BRIEFS.get(state.get("step") or lesson_steps.EXPLAIN, "")


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
    if (state.get("mode") or ASK) == REVEAL:
        return Lesson(
            explanation=" ".join(
                part for part in (_answer_sentence(answer), explanation, MOVING_ON) if part
            ),
            question="",
            expected_answer="",
            accept=(),
            strategy=strategy,
            source="llm",
            passages=tuple(passages),
            visual=visual,
        )

    options = hint_options(
        answer=answer, offered=list(state.get("offered") or []), visual=visual
    )
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

    wanted = stage_normalise(expected)
    if not any(wanted and wanted in stage_normalise(option) for option in seen):
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
    step: str = lesson_steps.EXPLAIN,
    mode: str = ASK,
    question: str = "",
    answer: str = "",
    offered: list[str] | tuple[str, ...] = (),
) -> Lesson:
    """Run one turn of the agent and get back what to say and what to ask.

    `mode` is which of the three turns a question gets. `ASK` writes a new
    question. `HINT` and `REVEAL` are about the question already on the screen,
    so they are handed it - along with its answer and whatever the child was
    already being offered - and they never write a new one.
    """
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = _graph()
    result = _COMPILED.invoke(
        {
            "subject": subject,
            "topic": topic,
            "topic_id": topic_id,
            "step": step,
            "spent": list(spent),
            "experience_mode": experience_mode,
            "mode": mode,
            "question": question,
            "answer": answer,
            "offered": list(offered),
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


def answer_question(*, topic: str, topic_id: str, question: str) -> tuple[str, str]:
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
                f"The child asked: {asked}",
            ],
            temperature=0.4,
            max_tokens=700,
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
