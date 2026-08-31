"""Transcribing a child's voice on the server, for when the browser could not.

The browser does the listening first, and usually that is the end of it: the Web
Speech API is instant, free, and already running on the machine the child is
sitting at. It has one bad failure, and it is the one that matters most here.

**It gives up on a quiet child.** Chrome's recogniser decides for itself when
speech has started, and a three-year-old saying "अ" under their breath does not
clear that bar. What comes back is `no-speech` - not "I heard something I could
not read", but silence - and the class has no way to tell that apart from a
child who said nothing at all.

So the class listens twice. Our own level meter, which is far more sensitive
than the recogniser, says whether there was a voice; when there was one and the
browser still heard nothing, the recorded clip comes here. Whisper is very good
at exactly the audio Chrome throws away: quiet, short, accented, a small child.

Groq hosts `whisper-large-v3-turbo` and this project already has a Groq key for
the teacher, so this needs no model download, no GPU and no second key. With no
key configured the endpoint says so plainly and the class carries on with what
the browser gave it - a missed answer, which is what happens today anyway.
"""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

# Turbo rather than the full model: a clip is a second or two of one child
# saying one letter, and the extra accuracy of the large model is not worth the
# wait in front of a four-year-old.
MODEL = "whisper-large-v3-turbo"

# A spoken answer is a second or two - a few tens of kilobytes. This is a long
# way above that and still nowhere near something worth loading into memory.
MAX_AUDIO_BYTES = 2 * 1024 * 1024

# The whole point is to be quick enough that a child does not notice the second
# attempt. Past this it is not worth having.
TIMEOUT_SECONDS = 8.0


# Kept open between clips for the same reason the model client is: the TLS
# handshake cost more than the transcription itself.
_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS,
            limits=httpx.Limits(max_keepalive_connections=2, keepalive_expiry=300.0),
        )
    return _client


class SttError(RuntimeError):
    """The clip could not be transcribed. The message is for a grown-up."""


def is_configured() -> bool:
    return bool(get_settings().groq_api_key)


async def transcribe(audio: bytes, *, filename: str = "answer.webm", language: str = "") -> str:
    """What was said in this clip, or `""` if it held nothing.

    `language` is a BCP-47 tag from the client ("hi-IN"); only its first part is
    sent, because that is what the API takes. Pinning it matters on a clip this
    short - language detection on one spoken letter is close to a coin toss, and
    a Hindi level asking for "अ" wants the Hindi model whatever the child's
    profile says.
    """
    if not audio:
        return ""
    if len(audio) > MAX_AUDIO_BYTES:
        raise SttError("That recording is too long to transcribe.")

    settings = get_settings()
    if not settings.groq_api_key:
        raise SttError("Server transcription is not configured; set GROQ_API_KEY.")

    data = {"model": MODEL, "response_format": "json", "temperature": "0"}
    if language:
        data["language"] = language.split("-")[0]

    try:
        response = await _http().post(
            TRANSCRIPTION_URL,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            data=data,
            files={"file": (filename, audio, "application/octet-stream")},
        )
        response.raise_for_status()
        body = response.json()
    except httpx.HTTPError as error:
        # Never fatal to a lesson: the caller reports an empty transcript and the
        # class treats it the way it treats any answer it did not catch.
        logger.warning("Server transcription failed: %s", error)
        raise SttError("The transcription service could not be reached.") from error
    except ValueError as error:
        raise SttError("The transcription service sent something unreadable.") from error

    return str(body.get("text", "")).strip()
