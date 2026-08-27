"""Text to speech, through Microsoft Edge's free voices (`edge-tts`).

No paid API and no key: `edge-tts` speaks to the same endpoint the Edge browser's
read-aloud feature uses. The whole module is one function - `text_to_speech(text)`
- which hands back MP3 bytes for the caller to send to the browser.

The bytes are collected in memory rather than written to a file. A voice reply is
a few tens of kilobytes and lives for exactly one HTTP response, so a temporary
file would only add a name to clean up and a race between two requests.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re

import edge_tts
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# The default female Hindi voice, as specified. It reads English text too - with
# an Indian accent - so it works whichever language the assistant answers in.
# Override with TTS_VOICE in .env; `edge-tts --list-voices` prints the rest.
DEFAULT_VOICE = os.getenv("TTS_VOICE", "hi-IN-SwaraNeural")

# Speaking speed and pitch, in the format edge-tts expects ("+0%", "-10%").
DEFAULT_RATE = os.getenv("TTS_RATE", "+0%")
DEFAULT_PITCH = os.getenv("TTS_PITCH", "+0Hz")

# Edge TTS is a network call. Without a ceiling a hung connection would hold the
# request open until the browser gave up, with nothing said about why.
TIMEOUT_SECONDS = float(os.getenv("TTS_TIMEOUT", "30"))

# Long text is slow to synthesise and slower to listen to. The assistant is asked
# to be brief; this is what happens when it is not.
MAX_CHARACTERS = int(os.getenv("TTS_MAX_CHARS", "1500"))


class TTSError(RuntimeError):
    """Speech could not be generated. The message is user-facing."""


async def text_to_speech(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
) -> bytes:
    """Speak `text` and return the audio as MP3 bytes.

    Raises `TTSError` with a message that is safe to show the user.
    """
    spoken = _prepare(text)
    if not spoken:
        raise TTSError("There is nothing to say.")

    try:
        audio = await asyncio.wait_for(
            _synthesise(spoken, voice=voice, rate=rate, pitch=pitch),
            timeout=TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as error:
        raise TTSError(
            "The voice service took too long to answer. Please try again."
        ) from error
    except TTSError:
        raise
    except Exception as error:
        logger.exception("Edge TTS failed")
        raise TTSError(f"The voice service failed: {error}") from error

    if not audio:
        raise TTSError(
            f"The voice service returned no audio. Check that '{voice}' is a real "
            "voice name - run: edge-tts --list-voices"
        )

    return audio


async def _synthesise(text: str, *, voice: str, rate: str, pitch: str) -> bytes:
    """Stream one utterance out of Edge TTS and join the audio chunks.

    `Communicate.stream()` yields two kinds of chunk - audio, and the word
    boundary markers used for subtitles. Only the audio is kept.
    """
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)

    audio = bytearray()
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio" and chunk.get("data"):
            audio.extend(chunk["data"])

    return bytes(audio)


def _prepare(text: str) -> str:
    """Tidy the text into something worth sending to the voice.

    Whitespace is collapsed because a run of newlines becomes an audible stumble,
    and anything past the ceiling is cut at a sentence end rather than mid-word.
    """
    cleaned = re.sub(r"\s+", " ", (text or "")).strip()
    if len(cleaned) <= MAX_CHARACTERS:
        return cleaned

    clipped = cleaned[:MAX_CHARACTERS]
    # Prefer the last full stop, so the reply ends on a sentence instead of a
    # syllable. If there is none, take the whole clip.
    end = max(clipped.rfind("."), clipped.rfind("?"), clipped.rfind("!"))
    return clipped[: end + 1] if end > 0 else clipped


async def list_voices(prefix: str = "") -> list[dict]:
    """Every voice Edge offers, optionally filtered by locale prefix ("hi-IN").

    Not needed by the app - it is here so `/voices` can answer "what else could
    this sound like?" without anyone having to leave the browser.
    """
    try:
        voices = await asyncio.wait_for(edge_tts.list_voices(), timeout=TIMEOUT_SECONDS)
    except Exception as error:
        logger.exception("Could not list Edge TTS voices")
        raise TTSError(f"Could not list voices: {error}") from error

    return [
        {
            "name": voice.get("ShortName", ""),
            "gender": voice.get("Gender", ""),
            "locale": voice.get("Locale", ""),
        }
        for voice in voices
        if not prefix or str(voice.get("ShortName", "")).startswith(prefix)
    ]


__all__ = ["DEFAULT_VOICE", "TTSError", "list_voices", "text_to_speech"]
