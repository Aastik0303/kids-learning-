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

# A Hindi lesson is narrated in Hindi. The subject declares its language in the
# manifest and it arrives here; nothing looks at a subject id.
HINDI_TUTOR_INTRO_TEMPLATES = [
    "आज हम {topic} सीखेंगे। तैयार हो, {name}? चलो शुरू करें!",
    "अब आया {topic}। चलो {name}, साथ में करते हैं।",
    "{topic} का समय है! तैयार हो, {name}?",
    "चलो {name}, {topic} सीखते हैं। एक-एक करके।",
    "{topic} बहुत मज़ेदार है, {name}! शुरू करें?",
]

HINDI_HINT_TEMPLATES = [
    "अच्छी कोशिश! {hint}",
    "लगभग सही! {hint}",
    "एक बार और देखो। {hint}",
    "ऐसे सोचो: {hint}",
]

HINDI_STREAK_MESSAGES = [
    "वाह! ऐसे ही करते रहो।",
    "बहुत बढ़िया सुना! आगे बढ़ो।",
    "क्या बात है! एक और सही।",
    "शाबाश! चलते रहो।",
]

TEMPLATES: dict[str, dict[str, list[str]]] = {
    "en": {"intro": TUTOR_INTRO_TEMPLATES, "hint": HINT_TEMPLATES, "streak": STREAK_MESSAGES},
    "hi": {
        "intro": HINDI_TUTOR_INTRO_TEMPLATES,
        "hint": HINDI_HINT_TEMPLATES,
        "streak": HINDI_STREAK_MESSAGES,
    },
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


class MockContentGenerator:
    def tutor_intro(self, child_name: str, topic_title: str, language: str = "en") -> str:
        template = random.choice(_pool(language, "intro"))
        return safe_text(template.format(topic=topic_title, name=child_name))

    def hint(self, base_hint: str, language: str = "en") -> str:
        template = random.choice(_pool(language, "hint"))
        return safe_text(template.format(hint=base_hint))

    def streak_encouragement(self, language: str = "en") -> str:
        return safe_text(random.choice(_pool(language, "streak")))


class LLMContentGenerator(MockContentGenerator):
    # PROTOTYPE: live providers are intentionally not called unless this adapter is replaced.
    pass


def get_content_generator(provider: str = "none") -> ContentGenerator:
    return MockContentGenerator() if provider == "none" else LLMContentGenerator()
