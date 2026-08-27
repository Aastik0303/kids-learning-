"""The AI brain: one function that turns what the user said into what to say back.

Everything that touches Groq lives here. The rest of the app calls
`get_ai_response(user_text)` and never imports the SDK, so swapping the provider
later is a change to this file alone.

Two things are deliberate:

* **The reply is written to be spoken.** The system prompt asks for no markdown,
  and `_clean_for_speech` strips it anyway - a model obeys a prompt most of the
  time, and "most of the time" is not good enough when the failure mode is a
  voice reading "asterisk asterisk" out loud.
* **The key is never hardcoded.** It is read from the environment, and a missing
  one is a clear message rather than a stack trace from inside the SDK.
"""

from __future__ import annotations

import logging
import os
import re

from dotenv import load_dotenv
from groq import AsyncGroq

# Load backend/.env if it is there. Real environment variables always win, which
# is what lets a deployment set the key without a file on disk.
load_dotenv()

logger = logging.getLogger(__name__)


# The personality, exactly as specified. Written for speech, not for a screen.
SYSTEM_PROMPT = (
    "You are a friendly female AI voice assistant.\n"
    "Speak naturally and conversationally.\n"
    "Keep answers short and easy to understand.\n"
    "Do not use unnecessary markdown, bullet points, emojis, or special "
    "characters because your response will be converted to speech.\n"
    "If the user asks a question, answer directly.\n"
    "If the user asks for an explanation, explain it simply.\n"
    "Always respond in a polite and helpful manner."
)

# Which Groq model answers. Overridable from .env so trying a different one is a
# config change rather than a code change.
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Short on purpose: this is going to be read out loud, and nobody wants to listen
# to four hundred words. It is a ceiling, not a target.
MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "300"))

TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.6"))

# The placeholder that ships in .env.example. Treated as "not set", so a user who
# copied the file but forgot to paste their key gets the helpful message rather
# than a 401 from Groq.
_PLACEHOLDER_KEY = "your_groq_api_key_here"


class AIError(RuntimeError):
    """Something went wrong on the way to an answer. The message is user-facing."""


# One client for the process. Built on first use rather than at import, so the
# app can start (and `/health` can answer) with no key configured.
_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    """The Groq client, or a clear explanation of what is missing."""
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or api_key == _PLACEHOLDER_KEY:
        raise AIError(
            "GROQ_API_KEY is not set. Copy backend/.env.example to backend/.env "
            "and put your key in it, then restart the server."
        )

    _client = AsyncGroq(api_key=api_key)
    return _client


def has_api_key() -> bool:
    """Whether a key is configured. Used by /health, which never calls Groq."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    return bool(api_key) and api_key != _PLACEHOLDER_KEY


async def get_ai_response(user_text: str) -> str:
    """What the assistant says back to `user_text`.

    Async because it is awaited inside a FastAPI request: a blocking HTTP call
    here would stall every other request in the process while it waited.

    Raises `AIError` with a message that is safe to show the user.
    """
    text = (user_text or "").strip()
    if not text:
        raise AIError("I did not catch that. Please try speaking again.")

    try:
        completion = await _get_client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
    except AIError:
        # Already a friendly message - a missing key, for instance.
        raise
    except Exception as error:  # the SDK raises several types; all mean "no answer"
        logger.exception("Groq request failed")
        raise AIError(_friendly_groq_error(error)) from error

    reply = ""
    if completion.choices:
        reply = (completion.choices[0].message.content or "").strip()

    if not reply:
        raise AIError("The AI did not say anything. Please try again.")

    return _clean_for_speech(reply)


def _friendly_groq_error(error: Exception) -> str:
    """Turn an SDK exception into a sentence a person can act on.

    Matched on the class name rather than by importing every error type, because
    the SDK's exception module has moved between versions and a broken import
    here would hide the real problem behind an ImportError.
    """
    name = type(error).__name__

    if "Authentication" in name or "PermissionDenied" in name:
        return "Groq rejected the API key. Check GROQ_API_KEY in backend/.env."
    if "RateLimit" in name:
        return "Groq is rate limiting right now. Please wait a moment and try again."
    if "NotFound" in name:
        return (
            f"Groq does not have a model called '{MODEL}'. "
            "Set GROQ_MODEL in backend/.env to one your account can use."
        )
    if "Connection" in name or "Timeout" in name:
        return "Could not reach Groq. Check your internet connection and try again."

    return f"The AI service failed: {error}"


# Markdown the model was asked not to write, and the emoji ranges that read as
# nothing at all when spoken.
_MARKDOWN = re.compile(r"[*_`#>|]+")
_BULLETS = re.compile(r"^\s*[-•‣]\s+", re.MULTILINE)
_EMOJI = re.compile(
    "["
    "\U0001f000-\U0001faff"
    "☀-➿"
    "⬀-⯿"
    "︀-️"
    "]+"
)


def _clean_for_speech(text: str) -> str:
    """Strip what a voice cannot read.

    The prompt already asks for none of this. This is the belt to that pair of
    braces: a stray "**" costs nothing to remove here and sounds like a fault in
    the app when it reaches the speaker.
    """
    cleaned = _MARKDOWN.sub("", text)
    cleaned = _BULLETS.sub("", cleaned)
    cleaned = _EMOJI.sub("", cleaned)
    # Collapse the blank lines bullet removal leaves behind, and any run of
    # spaces, into single separators.
    cleaned = re.sub(r"\n{2,}", "\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


__all__ = ["AIError", "MODEL", "SYSTEM_PROMPT", "get_ai_response", "has_api_key"]
