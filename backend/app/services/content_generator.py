import random
from typing import Protocol

from app.services.safety_service import safe_text


TUTOR_INTRO_TEMPLATES = [
    "Today we are learning {topic}. Ready, {name}? Let us try one little question.",
    "Here comes {topic}. Here we go, {name}! Let us try together.",
    "It is time for {topic}. Are you ready, {name}? Let us find out!",
    "Let us explore {topic}, {name}! One step at a time.",
    "{topic} is going to be fun, {name}! Let us begin.",
]

HINT_TEMPLATES = [
    "Good try! {hint}",
    "Almost! {hint}",
    "Almost! {hint}",
    "Let us look again. {hint}",
    "Think about it this way: {hint}",
]

STREAK_MESSAGES = [
    "You are on a roll! Keep going.",
    "Great listening! Keep going.",
    "Look at you go! Another one right.",
    "Nice streak! Keep going.",
]

# Every lesson is narrated in English, the Hindi-language subjects included:
# there, Hindi is the content being taught, quoted inside an English sentence,
# not the language the tutor speaks in. These pools used to have Devanagari
# twins keyed on the subject's declared language; `language` survives as an
# argument so callers do not all have to change, and every value maps here.
TEMPLATES: dict[str, dict[str, list[str]]] = {
    "en": {"intro": TUTOR_INTRO_TEMPLATES, "hint": HINT_TEMPLATES, "streak": STREAK_MESSAGES},
}


def _pool(language: str, kind: str) -> list[str]:
    return TEMPLATES.get(language, TEMPLATES["en"])[kind]


class ContentGenerator(Protocol):
    def tutor_intro(self, child_name: str, topic_title: str, language: str = "en") -> str:
        ...

    def hint(self, base_hint: str, language: str = "en") -> str:
        ...

    def streak_encouragement(self, language: str = "en") -> str:
        ...


class TemplateContentGenerator:
    """The lesson's own copy: an intro, a hint wrapper, a streak line.

    None of it is worth a model call. The intro is the child's name and the
    topic title - both of which the server already holds - and the hint is an
    authored hint with a warm opening in front of it. Sending those to a
    provider buys latency and one more place a bad answer could reach a child,
    and buys nothing back.
    """

    def tutor_intro(self, child_name: str, topic_title: str, language: str = "en") -> str:
        template = random.choice(_pool(language, "intro"))
        return safe_text(template.format(topic=topic_title, name=child_name))

    def hint(self, base_hint: str, language: str = "en") -> str:
        template = random.choice(_pool(language, "hint"))
        return safe_text(template.format(hint=base_hint))

    def streak_encouragement(self, language: str = "en") -> str:
        return safe_text(random.choice(_pool(language, "streak")))


def get_content_generator(provider: str = "none") -> ContentGenerator:
    """The lesson's copy generator. There is only one, whatever the provider is.

    There used to be a second class here - `LLMContentGenerator` - returned
    whenever a provider was configured. It was an empty subclass of this one, so
    "the LLM content generator" produced the same templates while reading as
    though a model were writing them.

    It is gone rather than implemented, and that is the design rather than a
    shortcut. Model-written child-facing wording has exactly one path in this
    codebase - the guide, reached through the conductor - and that path is where
    the safety filter, the answer-leak check, the early-mode word cap and the
    strategy validation live. A second, weaker path to the same child's ears is
    not something to add for a greeting.

    `provider` is still accepted so callers need not care, and is deliberately
    ignored.
    """
    return TemplateContentGenerator()
