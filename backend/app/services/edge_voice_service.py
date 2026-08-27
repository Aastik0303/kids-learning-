"""The guide's voice, spoken by Microsoft Edge's free neural voices.

This is the voice agent's TTS, brought into the class. It replaces two things
that were never good enough for a child's screen:

* **the browser's own `speechSynthesis`** - which is whatever robotic voice the
  machine happens to ship, differs on every device, and on Windows usually reads
  Devanagari as silence;
* **ElevenLabs** - which is excellent and costs money per sentence, so it was
  gated behind a key most installs do not have, and the class fell back to the
  robot.

`edge-tts` is free, needs no key, and one voice reads **both scripts**. That last
part matters more here than anywhere else: the guide narrates in English with
Hindi quoted inside it - "This is कमल. Can you say कमल?" - and `hi-IN-SwaraNeural`
says that whole sentence properly in one breath. The web client used to have to
cut the line into runs by script and hand each run to a different voice; with
this it does not.

**No model is involved.** This turns text into audio and does nothing else. What
the guide says is decided upstream, by the conductor and the AI Teacher, and is
already through `safety_service.safe_text` by the time it arrives here.
"""

from __future__ import annotations

import asyncio
import logging
import re

import edge_tts

from app.config import get_settings

logger = logging.getLogger(__name__)


class EdgeVoiceError(RuntimeError):
    """Speech could not be generated."""


# Edge is a network call. Without a ceiling a hung connection holds a child in
# front of a still screen until the browser gives up.
TIMEOUT_SECONDS = 15.0


async def synthesize(text: str, *, voice: str = "", rate: str = "", pitch: str = "") -> bytes:
    """Speak `text` and return MP3 bytes.

    Raises `EdgeVoiceError`. The caller decides what a failure means - on the web
    client it means falling back to the browser's own voice, so a broken network
    makes the guide sound worse rather than making it mute.
    """
    settings = get_settings()
    spoken = _prepare(text)
    if not spoken:
        raise EdgeVoiceError("There is nothing to say.")

    chosen = voice or settings.edge_tts_voice

    try:
        audio = await asyncio.wait_for(
            _stream(
                spoken,
                voice=chosen,
                rate=rate or settings.edge_tts_rate,
                pitch=pitch or settings.edge_tts_pitch,
            ),
            timeout=TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as error:
        raise EdgeVoiceError("The voice took too long to answer.") from error
    except Exception as error:
        logger.warning("Edge TTS failed: %s", error)
        raise EdgeVoiceError(f"The voice service failed: {error}") from error

    if not audio:
        raise EdgeVoiceError(f"The voice service returned no audio for '{chosen}'.")
    return audio


async def _stream(text: str, *, voice: str, rate: str, pitch: str) -> bytes:
    """Collect one utterance. `stream()` also yields word-boundary markers; only
    the audio chunks are kept."""
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    audio = bytearray()
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio" and chunk.get("data"):
            audio.extend(chunk["data"])
    return bytes(audio)


def _prepare(text: str) -> str:
    """Whitespace collapsed, because a run of newlines becomes an audible stumble."""
    return re.sub(r"\s+", " ", (text or "")).strip()


__all__ = ["EdgeVoiceError", "synthesize"]
