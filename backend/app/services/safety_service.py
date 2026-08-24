import re

FALLBACK = "I can help you with numbers, letters, colours, shapes, and stories."
BLOCKED_PATTERNS = [
    # Personal information
    r"\b(address|phone number|school name|password|social security)\b",
    r"\b(credit card|bank account|pin number|passport)\b",
    # Violence and fear
    r"\b(hurt|weapon|kill|blood|scary|nightmare|monster|ghost)\b",
    r"\b(fight|punch|kick|shoot|stab|attack|war|bomb|gun|knife)\b",
    # Self-harm and distress
    r"\b(self harm|suicide|cut myself|hurt myself|die|death)\b",
    # Bullying. "fat" was here and blocked ordinary nursery phonics content —
    # "The fat cat sat on the mat" is a real CVC phonics line and got replaced
    # by FALLBACK on every read. A single word cannot safely detect body-shaming
    # without context it doesn't have here, so it is left out of this prototype
    # filter rather than kept and over-blocking common words.
    r"\b(stupid|idiot|dumb|loser|ugly|hate you|shut up)\b",
    # Medical / inappropriate advice
    r"\bmedicine|diagnosis|doctor advice|prescription|drug\b",
    # Strangers and safety
    r"\b(stranger|come with me|get in the car|secret from parents)\b",
    r"\b(don't tell|hide from|run away from home)\b",
    # Inappropriate content
    r"\b(naked|sex|porn|inappropriate|adult content)\b",
    # URLs and contact
    r"https?://",
    r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
    # Phone numbers (basic pattern)
    r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
]


def safe_text(text: str, max_length: int = 600) -> str:
    # PROTOTYPE: keyword safety filter only; replace with layered moderation before production.
    if len(text) > max_length:
        # An over-long response is a length problem, not a safety problem — it
        # used to be discarded entirely and replaced with FALLBACK, which threw
        # away a perfectly safe message just because a model ran on. Trim at a
        # word boundary instead, and only fall through to FALLBACK if trimming
        # leaves nothing usable.
        trimmed = text[:max_length].rsplit(" ", 1)[0].rstrip(".,!") + "."
        text = trimmed if len(trimmed) > 1 else FALLBACK
    lowered = text.lower()
    if any(re.search(pattern, lowered) for pattern in BLOCKED_PATTERNS):
        return FALLBACK
    return text
