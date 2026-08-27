"""How a two-year-old is taught something they have never met.

Play Group and Nursery get five teaching strategies, and until now all five came
out of the guide sounding the same: "Tap A." A child who has never seen the
letter A does not need to be told to tap it. They need to *meet* it - see it,
hear the noise it makes, find it in something they already love, draw it with a
finger, and say it out loud with someone.

That is what this module builds, and it builds it out of content that is already
authored. A letter topic in `playgroup.json` carries the whole method in its own
activities: "This is A - down, down, and a little belt", "A says 'aa'", "aa...
apple!", the stroke hint, the word to match. Those lines are written by a
curriculum author; here they are *re-read* so the guide can say the right one at
the right moment, in the strategy the policy chose, however far into the topic
the child has walked.

Nothing here invents curriculum, and no model is consulted. A hallucinated
letter sound is worse than a plain instruction, so the fallbacks are plain.

Early mode only. Standard mode keeps the guide's own wording, which can be
longer and more verbal than a pre-verbal child can use.
"""

import random
import re
from dataclasses import dataclass

from app.schemas.curriculum import Topic
from app.schemas.learning import Activity


# Fourteen words is the early-mode ceiling and it is not a style choice: a
# sentence longer than this stops being heard by a two-year-old.
MAX_WORDS = 14

# Skill id suffixes the authored letter and number topics use. They are how the
# beats find the sound, the word and the stroke without guessing.
SOUND_SUFFIXES = ("_sound", "_phonic", "_says")
WORD_SUFFIXES = ("_word", "_picture", "_match_picture")
WRITE_SUFFIXES = ("_write", "_trace")


@dataclass(frozen=True)
class ConceptCard:
    """Everything the guide knows about the one thing being taught right now."""

    symbol: str = ""
    sound: str = ""
    word: str = ""
    stroke: str = ""
    # The authored teaching line, kept verbatim when there is nothing better to
    # say: an author's sentence beats a generated one every time.
    told: str = ""

    @property
    def has_depth(self) -> bool:
        """Whether there is more here than a name to repeat."""
        return bool(self.sound or self.word or self.stroke)


def _clean(value: str | None) -> str:
    """"letter_A" -> "A", "colour_red" -> "red", "number_3" -> "3"."""
    if not value:
        return ""
    text = value.strip()
    for prefix in ("letter_", "number_", "colour_", "color_", "shape_", "count_"):
        if text.lower().startswith(prefix):
            text = text[len(prefix) :]
    text = text.replace("_", " ").strip()
    # "red swatch", "circle outline", "letter card" - the authored name of the
    # picture, not the name of the thing. A child is taught red, not red swatch.
    for suffix in (" swatch", " outline", " card", " picture", " image"):
        if text.lower().endswith(suffix):
            text = text[: -len(suffix)].strip()
    return text


def _quoted(text: str) -> str:
    """The bit inside quotes: "A says 'aa'." -> "aa"."""
    match = re.search(r"['\"‘’“”]([^'\"‘’“”]{1,12})['\"‘’“”]", text or "")
    return match.group(1).strip() if match else ""


def _first_word_after(text: str, marker: str) -> str:
    """"A is for apple." -> "apple". "अ से अनार।" -> "अनार"."""
    index = (text or "").find(marker)
    if index < 0:
        return ""
    tail = re.sub(r"[^A-Za-zऀ-ॿ ]", " ", text[index + len(marker) :])
    parts = [part for part in tail.split() if part]
    return parts[0] if parts else ""


# Little words a "for" match can land on: "Look for the red one" is not the
# word a letter is for.
STOPWORDS = {"the", "a", "an", "it", "this", "that", "you", "me", "us", "one", "your"}

DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def _with_article(thing: str) -> str:
    return f"{'an' if thing[:1].lower() in 'aeiou' else 'a'} {thing}"


def _name_it(thing: str) -> str:
    """"red" -> "This is red." / "square" -> "This is a square." """
    if not thing:
        return ""
    if thing.lower() in COLOUR_WORDS or not thing.isascii():
        return f"This is {thing}."
    return f"This is {_with_article(thing)}."


def _names_its_answer(activity: Activity) -> bool:
    """Whether the question already says its own answer out loud.

    "Tap the yellow one" does; "which one starts with A?" does not, and the
    difference decides whether the intro may name the concept.
    """
    answer = (activity.correct_answer or "").strip().lower()
    return bool(answer) and answer in (activity.prompt or "").lower()


def _is_english(text: str) -> bool:
    """English narration, emoji and all - but no Devanagari sentence.

    Every line the app says is English with the taught letter or word quoted
    inside it. A Hindi topic teaches Hindi; it is not *spoken* in Hindi. Emoji
    are not a script and are welcome.
    """
    return bool(text) and not DEVANAGARI.search(text)


def card_for(topic: Topic, activity: Activity | None, activities: list[Activity]) -> ConceptCard:
    """Read the topic's own activities for what this concept actually is.

    The child may be on the last question of a letter level, where the authored
    prompt is "Which letter does it start with?" - the sound and the word live
    three activities back, and that is exactly what a struggling child needs
    said again. So the card is built from the whole topic, not from the one
    activity in front of them.
    """
    symbol = ""
    sound = ""
    word = ""
    stroke = ""
    told = ""

    for item in activities:
        skill = (item.skill_id or "").lower()
        text = f"{item.prompt} {item.hint}".strip()

        if not symbol:
            symbol = _clean(item.visual_items[0] if item.visual_items else "") or _clean(item.correct_answer)
        if not sound and skill.endswith(SOUND_SUFFIXES):
            sound = _quoted(text)
        if not word:
            # "A is for apple", and the Hindi topics' "अ से अनार". The taught
            # word is kept in the script it was authored in: a Devanagari word
            # is never handed back transliterated into Roman letters.
            found = _first_word_after(text, " for ") or _first_word_after(text, " से ")
            if found and found.lower() not in STOPWORDS:
                word = found
            elif skill.endswith(WORD_SUFFIXES):
                word = _clean(item.correct_answer)
        if not stroke and (item.trace_target or skill.endswith(WRITE_SUFFIXES)):
            stroke = (item.hint or "").strip()
        # The authored teaching sentence, but only when it is English. Every
        # narration in this app is English with the taught letter or word quoted
        # inside it - a Hindi topic teaches Hindi, it is not *spoken* in Hindi -
        # so a Devanagari prompt is left to the activity screen and the guide
        # builds its own English frame around the symbol instead.
        if not told and not item.correct_answer and _is_english(item.prompt or ""):
            told = (item.prompt or "").strip()

    if activity is not None:
        answer = _clean(activity.correct_answer)
        # The activity in front of the child wins on the name of the thing: a
        # match question about "apple" is not a question about the letter card
        # that opened the level. Casing is the exception - the answer key for a
        # letter may be "a" where the level teaches "A", and a child meeting a
        # letter for the first time should be shown the shape they were taught.
        if answer and symbol and answer.lower() == symbol.lower():
            pass
        elif answer:
            symbol = answer
        symbol = symbol or _clean(topic.title)

    return ConceptCard(symbol=symbol, sound=sound, word=word, stroke=stroke, told=told)


def spoken_form(concept: str, *, prompt: str = "", hint: str = "") -> str:
    """How a concept should be *said*, when its answer key is a roman token.

    Hindi levels name their pictures with asset tokens - "anar", "aam", "imli" -
    because that is what a filename would be. That is fine on disk and wrong in
    the guide's mouth: it made the app say "Tap anar", a Hindi word spelled in
    Roman letters, which is precisely what this project does not do. The taught
    word is quoted in Devanagari inside an English sentence, or it is not said.

    The Devanagari is not guessed or transliterated - it is read back out of the
    activity's own authored prompt, "अ से अनार। अनार कौन सा है?", which is
    where the author already wrote it. When the prompt does not carry it, the
    concept is returned untouched: saying the token is bad, and inventing a
    spelling for a word the curriculum never wrote would be worse.
    """
    text = (concept or "").strip()
    if not text or not text.isascii():
        return text

    authored = f"{prompt or ''} {hint or ''}"
    if not DEVANAGARI.search(authored):
        return text

    # The danda and double danda sit inside the Devanagari block, so the
    # character filter in `_first_word_after` keeps them and the word comes
    # back as "अनार।" - a full stop read aloud in the middle of a sentence.
    word = _first_word_after(authored, " से ").strip("।॥ ")
    return word or text


def _same_item(left: str | None, right: str | None) -> bool:
    """Whether two skill ids are about the same taught thing.

    `hindi_906` and `hindi_906_word` are; `hindi_905` and `hindi_906` are not.
    The boundary is checked on an underscore so `letter_A` never matches
    `letter_AB`.
    """
    first, second = (left or "").strip(), (right or "").strip()
    if not first or not second:
        return False
    if first == second:
        return True
    longer, shorter = (first, second) if len(first) > len(second) else (second, first)
    return longer.startswith(f"{shorter}_")


def _item_activities(activity: Activity, activities: list[Activity]) -> list[Activity]:
    """Just the cards about the thing *this* card is about.

    A Hindi level teaches अ and then आ in one topic. Reading the concept from
    the whole topic always finds अ - it is first - so every card in the second
    half was introduced with the first half's letter: "This is अ. अ is for
    अनार." in front of a question about आम. Scoped to the item, each card is
    introduced with its own.

    Falls back to the whole topic when the level does not use skill ids, which
    is the behaviour every English level already had.
    """
    scoped = [item for item in activities if _same_item(item.skill_id, activity.skill_id)]
    return scoped or activities


def _is_spoken(activity: Activity) -> bool:
    """Whether this card is answered out loud rather than with a finger."""
    kind = (getattr(activity, "answer_kind", "") or "").lower()
    return kind == "spoken" or (activity.type or "").lower().startswith("repeat_")


def _words(text: str, limit: int = MAX_WORDS) -> str:
    parts = text.split()
    return text if len(parts) <= limit else " ".join(parts[:limit])


# The play in "khel khel mein". Each strategy has a few shapes so a child who
# needs four turns on one question does not hear one sentence four times. They
# are deliberately concrete: a noise to copy, a thing to look at, a finger to
# move. Nothing here asks a pre-verbal child to reason.
def _tell(card: ConceptCard, rng: random.Random) -> str:
    if card.sound and card.symbol:
        return rng.choice(
            [
                f"This is {card.symbol}. {card.symbol} says {card.sound}.",
                f"Meet {card.symbol}! It says {card.sound}.",
            ]
        )
    if card.word and card.symbol:
        # No authored sound - the Hindi vowels are taught by their word rather
        # than by a spelled-out noise - so the word carries the meeting.
        return f"This is {card.symbol}. {card.symbol} is for {card.word}."
    if card.told:
        return card.told
    return f"This is {card.symbol}." if card.symbol else "Look at this one with me."


def _show(card: ConceptCard, rng: random.Random) -> str:
    if card.word and card.symbol:
        return rng.choice(
            [
                f"Look! {card.symbol} is hiding in {card.word}.",
                f"Watch {card.symbol} light up. {card.word} starts with it!",
            ]
        )
    return f"Look - this one is {card.symbol}." if card.symbol else "Look at the glowing one."


def _do_together(card: ConceptCard, rng: random.Random) -> str:
    if card.sound and card.word:
        return rng.choice(
            [
                f"Together: {card.sound}... {card.word}! Now you.",
                f"Say it with me: {card.sound}... {card.word}!",
            ]
        )
    if card.word and card.symbol:
        return f"Say it with me: {card.symbol}... {card.word}!"
    if card.symbol:
        return f"Let us do it together. Point at {card.symbol} with me."
    return "Let us do this one together."


def _sense_switch(card: ConceptCard, rng: random.Random) -> str:
    if card.stroke and card.symbol:
        return rng.choice(
            [
                f"Draw {card.symbol} in the air! {card.stroke}",
                f"Finger up! Make {card.symbol} with me. {card.stroke}",
            ]
        )
    if card.sound:
        return f"Big voice! Say {card.sound} like a lion. {card.sound}!"
    return "Stand up and wiggle, then look again!"


def _park(card: ConceptCard, rng: random.Random) -> str:
    return rng.choice(
        [
            "That one was tricky. Let us play something else!",
            "Good trying! We will meet this one again.",
        ]
    )


BEATS = {
    "S1_TELL": _tell,
    "S2_SHOW": _show,
    "S6_DO_TOGETHER": _do_together,
    "S7_SENSE_SWITCH": _sense_switch,
    "S9_PARK": _park,
}


# How long a teaching intro may run before a question. Longer than the
# fourteen-word instruction ceiling on purpose: this is the part where the child
# is being *taught*, and a two-year-old who is shown a colour for two sentences
# and then asked about it is being taught. Fourteen words is the ceiling on
# telling them what to do, not on showing them what a thing is.
MAX_INTRO_WORDS = 30

# The handover from "watch me" to "your turn". Model, lead, test - and the child
# hears the turn change rather than guessing it from a new screen.
HANDOVERS = ("Now you try.", "Your turn!", "Now you.")


def question_intro(
    topic: Topic,
    activity: Activity | None,
    activities: list[Activity],
) -> str:
    """Teach the thing, then ask about it. Two or three lines, in that order.

    A question asked cold is a question a two-year-old cannot answer: "tap the
    red one" means nothing to a child who has not just been shown red. The level
    almost always contains the teaching already - an `introduce` card carrying
    the same `skill_id` as the question, with the anchor an author wrote for it
    ("This is red. Red like an apple.") - so the intro is that card's own words,
    then the handover, then the question.

    Returns "" for a teaching card (which is the explanation) and for a repeat
    attempt (where the repair ladder, not this, decides what to say).
    """
    if activity is None or not activity.correct_answer:
        return ""

    # The teaching card for *this* item. Matched on a skill-id prefix, not on
    # equality: a level authors the card as `hindi_906` and the question about
    # its picture as `hindi_906_word`, so exact matching found nothing and the
    # intro fell back to the whole topic - which opens with the *previous*
    # letter. That is how a card asking for आम came to be introduced with
    # "This is अ. अ is for अनार": the right question, taught with the wrong item.
    taught = [
        item
        for item in activities
        if item.skill_id
        and _same_item(item.skill_id, activity.skill_id)
        and not item.correct_answer
        and item.activity_id != activity.activity_id
    ]
    # Longest match first, so `hindi_906_word` prefers a card authored for
    # `hindi_906_word` over the broader `hindi_906` one when both exist.
    taught.sort(key=lambda item: len(item.skill_id or ""), reverse=True)

    lines: list[str] = []
    if taught and _is_english(taught[0].prompt):
        lines.append(taught[0].prompt.strip())
    elif _names_its_answer(activity):
        # No teaching card for this skill - "Tap the yellow one" in a level whose
        # only authored card is red. The concept is named from the question
        # itself, which is safe precisely because the question already says it
        # out loud; teaching red here would be teaching the wrong thing.
        answer = _clean(activity.correct_answer)
        lines.append(_name_it(answer))
    else:
        # A match question, whose answer the prompt does not name. Only the
        # topic's own concept may be spoken here - naming the answer would hand
        # it over before the question is asked.
        # `activity=None` on purpose: the intro introduces the *concept*, not
        # the answer in front of the child. Built from the activity, a match
        # question whose answer is "apple" would open with "Meet apple!" - which
        # is the answer key, said out loud, before the question is even asked.
        told = _tell(
            card_for(topic, None, _item_activities(activity, activities)),
            random.Random(activity.activity_id),
        )
        if told:
            lines.append(told)

    anchor = (taught[0].hint if taught else "") or ""
    if lines and anchor and _is_english(anchor) and len(" ".join(lines).split()) <= 12:
        lines.append(anchor.strip())

    handover = random.Random(activity.activity_id).choice(HANDOVERS)
    if _is_english(activity.prompt):
        question = activity.prompt.strip()
    else:
        # A Devanagari prompt stays on the screen; what is *said* is English
        # with the taught word quoted in it.
        #
        # Two things this has to get right. The word is the one *this* question
        # is about - a picture-match card asking for अनार was saying "Tap अ",
        # the topic's letter, because it fell back to the topic card. And a card
        # the child answers by *speaking* must not say "Tap": `repeat_letter`
        # opens the microphone and then told them to tap something that was not
        # on the screen.
        asked = spoken_form(_clean(activity.correct_answer), prompt=activity.prompt, hint=activity.hint)
        symbol = asked or card_for(topic, None, _item_activities(activity, activities)).symbol
        verb = "Say" if _is_spoken(activity) else "Tap"
        question = f"{verb} {symbol}." if symbol else ""

    if not question:
        return ""
    if not lines:
        return ""

    script = " ".join([*lines, handover, question])
    if len(script.split()) > MAX_INTRO_WORDS and len(lines) > 1:
        # Drop the second anchor before anything else: the question and the
        # first teaching line are what the turn is for.
        script = " ".join([lines[0], handover, question])
    return script


# A teaching card is not an instruction, so it gets more room than one: this is
# the moment the child meets the thing at all.
MAX_TEACHING_WORDS = 34

# What the child does while they are being told. Model, lead, test - these are
# the "lead" half, and none of them claims a fact the curriculum did not author.
SAY_INVITES = ("Say {thing} with me!", "Big voice - say {thing}!", "Say {thing} twice with me!")
FIND_INVITES = ("Can you find {thing} near you?", "Point at {thing} with me!", "Look around for {thing}!")

# "find a circle" reads; "find circle" does not. Colours take no article.

# Colours are named without an article - "this is red" - and everything else
# takes one: "this is a square", "this is a cat".
COLOUR_WORDS = {
    "red", "blue", "yellow", "green", "orange", "purple", "pink",
    "brown", "black", "white", "grey", "gray",
}


def _invites(activity: Activity, topic: Topic) -> tuple[str, ...]:
    """A letter is said; a colour is found. Both are done with the body, and
    neither invitation claims a fact the curriculum did not author."""
    subject = f"{activity.skill_id or ''} {activity.type} {topic.title}".lower()
    if any(word in subject for word in ("letter", "sound", "phonic", "swar", "vyanjan", "hindi")):
        return SAY_INVITES
    return FIND_INVITES


def _anchor(text: str, symbol: str) -> str:
    """The "like a ..." half of an authored teaching line.

    "This is red. 🟥 Red like an apple. 🍎" -> "Red like an apple. 🍎"
    Returns "" when the line carries no anchor, so nothing is invented to fill
    the gap.
    """
    if not text:
        return ""
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    for part in parts:
        if " like " in part.lower():
            return part
    # Some levels put the anchor first: "Red like a tomato. 🍅"
    return parts[0] if parts and " like " in text.lower() else ""


def teaching_script(
    topic: Topic,
    activity: Activity | None,
    activities: list[Activity],
) -> str:
    """The moment a child *meets* a thing, taught rather than labelled.

    The screen for this used to say one line - "Red like a tomato." - and offer
    a Next button. A two-year-old meeting a colour needs more than a label: the
    name, something they know that is that colour, a second one so it is the
    colour and not the apple they remember, and something to do with their body
    while they hear it.

    Every fact comes from the level's own authored card. The only thing added is
    the invitation, which claims nothing.
    """
    if activity is None or activity.correct_answer:
        return ""

    # This card's own concept, not the topic's: a level teaches red, then blue,
    # and the blue card must not invite a child to point at red.
    symbol = _clean(activity.visual_items[0] if activity.visual_items else "") or card_for(
        topic, None, activities
    ).symbol
    prompt = (activity.prompt or "").strip()
    if not _is_english(prompt):
        # A Devanagari teaching card is shown on screen; the narration is built
        # in English around the symbol instead of repeating it.
        prompt = _tell(
            card_for(topic, None, _item_activities(activity, activities)),
            random.Random(activity.activity_id),
        )

    lines = [prompt] if prompt else []

    second = _anchor(activity.hint or "", symbol)
    first = _anchor(activity.prompt or "", symbol)
    if second and _is_english(second) and second.lower() != first.lower():
        # Two anchors, said as a pair, so what is remembered is the colour
        # rather than the apple.
        lines.append(f"{second} Both!" if len(second.split()) <= 5 else second)

    invite = random.Random(activity.activity_id).choice(_invites(activity, topic))
    invites = _invites(activity, topic)
    thing = symbol or "it"
    if symbol and invites is FIND_INVITES:
        thing = symbol if symbol.lower() in COLOUR_WORDS or not symbol.isascii() else _with_article(symbol)
    lines.append(invite.format(thing=thing))

    script = " ".join(line for line in lines if line)
    words = script.split()
    return " ".join(words[:MAX_TEACHING_WORDS]) if len(words) > MAX_TEACHING_WORDS else script


def script_for(
    topic: Topic,
    activity: Activity | None,
    activities: list[Activity],
) -> str:
    """The whole first-presentation script, whichever kind of card this is.

    A teaching card is taught; a question is taught *and then* asked. Either way
    the child hears the thing explained before anything is expected of them.
    """
    if activity is None:
        return ""
    return (
        question_intro(topic, activity, activities)
        if activity.correct_answer
        else teaching_script(topic, activity, activities)
    )


def beat(
    *,
    strategy: str | None,
    card: ConceptCard,
    seed: str = "",
) -> str:
    """One short, playful, concrete line for the strategy the policy chose.

    Returns "" when there is nothing better to say than what the guide already
    had - the caller then keeps the guide's own wording rather than replacing a
    specific sentence with a vaguer one.
    """
    maker = BEATS.get((strategy or "").upper())
    if maker is None:
        return ""
    if not card.symbol and not card.told:
        return ""

    line = maker(card, random.Random(f"{seed}:{strategy}"))
    return _words(line.strip())


__all__ = [
    "ConceptCard",
    "MAX_INTRO_WORDS",
    "MAX_TEACHING_WORDS",
    "MAX_WORDS",
    "beat",
    "card_for",
    "spoken_form",
    "question_intro",
    "script_for",
    "teaching_script",
]
