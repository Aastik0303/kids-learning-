import random
from typing import Protocol

from app.schemas.learning import Stage
from app.services.safety_service import safe_text


TUTOR_INTRO_TEMPLATES = [
    "{intro} Ready, {name}? Let us try one little question.",
    "{intro} Here we go, {name}! Let us try together.",
    "{intro} Are you ready, {name}? Let us find out!",
    "{intro} Let us explore, {name}! One step at a time.",
    "{intro} This is going to be fun, {name}! Let us begin.",
]

HINT_TEMPLATES = [
    "Good try! {hint}",
    "Almost! {hint}",
    "Not quite, but you are close! {hint}",
    "Let us look again. {hint}",
    "Think about it this way: {hint}",
]

STREAK_MESSAGES = [
    "You are on a roll! Keep going.",
    "Wow, you are getting so good at this!",
    "Look at you go! Another one right.",
    "You are on fire! Amazing work.",
]


class ContentGenerator(Protocol):
    def tutor_intro(self, child_name: str, stage: Stage) -> str:
        ...

    def hint(self, stage: Stage, base_hint: str) -> str:
        ...

    def streak_encouragement(self) -> str:
        ...


class MockContentGenerator:
    def tutor_intro(self, child_name: str, stage: Stage) -> str:
        template = random.choice(TUTOR_INTRO_TEMPLATES)
        return safe_text(template.format(intro=stage.intro_message, name=child_name))

    def hint(self, stage: Stage, base_hint: str) -> str:
        template = random.choice(HINT_TEMPLATES)
        return safe_text(template.format(hint=base_hint))

    def streak_encouragement(self) -> str:
        return safe_text(random.choice(STREAK_MESSAGES))


class LLMContentGenerator(MockContentGenerator):
    # PROTOTYPE: live providers are intentionally not called unless this adapter is replaced.
    pass


def get_content_generator(provider: str = "none") -> ContentGenerator:
    return MockContentGenerator() if provider == "none" else LLMContentGenerator()
