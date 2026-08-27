"""Speech to text, behind one interface so the engine can be swapped.

Version one does the listening **in the browser**, with the Web Speech API. That
is the free option that needs no install, no model download and no GPU, and it is
why this file is small: with `STT_ENGINE=browser` the transcript has already been
made by the time the server hears about it.

The interface exists anyway, because the point is to be able to change your mind.
Set `STT_ENGINE=whisper` in `.env`, install `faster-whisper`, and the very same
`/stt` endpoint starts transcribing uploaded audio locally - no other file in the
project changes.

    STT_ENGINE=browser   (default) the browser transcribes; /stt explains itself
    STT_ENGINE=whisper   local faster-whisper transcribes uploaded audio
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Protocol

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


ENGINE_NAME = os.getenv("STT_ENGINE", "browser").strip().lower()

# Which Whisper size to load when the whisper engine is chosen. "base" is the
# sweet spot on a laptop CPU: noticeably better than "tiny", still faster than
# real time. "small" and "medium" are better and slower.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

# Leave empty to let Whisper detect the language, or pin it ("en", "hi") when you
# know - detection costs a little time and occasionally guesses wrong on a short
# clip.
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "").strip()

# Audio bigger than this is refused rather than loaded into memory. A spoken
# question is a few hundred kilobytes; ten megabytes is somebody uploading a
# podcast.
MAX_AUDIO_BYTES = int(os.getenv("STT_MAX_BYTES", str(10 * 1024 * 1024)))


class STTError(RuntimeError):
    """Audio could not be transcribed. The message is user-facing."""


class SpeechToText(Protocol):
    """What every engine has to be able to do.

    One method, `transcribe`, taking the raw bytes of an audio file and giving
    back what was said. Anything that satisfies this can be dropped in.
    """

    name: str

    async def transcribe(self, audio: bytes, filename: str = "audio.webm") -> str:
        ...


class BrowserSTT:
    """The default: the browser already did it.

    There is nothing for the server to transcribe, so this engine says so rather
    than pretending. It exists to keep `/stt` a real endpoint with a real answer
    in the version where the browser is doing the listening.
    """

    name = "browser"

    async def transcribe(self, audio: bytes, filename: str = "audio.webm") -> str:
        raise STTError(
            "This server is set to STT_ENGINE=browser, so speech is transcribed "
            "in the browser with the Web Speech API and /stt has nothing to do. "
            "To transcribe audio here instead, install faster-whisper and set "
            "STT_ENGINE=whisper in backend/.env."
        )


class WhisperSTT:
    """Local Whisper, through `faster-whisper`. No API and no key.

    The model is loaded once, on the first request rather than at import, so a
    server configured for Whisper still starts in a second and only pays the
    load cost if somebody actually speaks. Transcription itself is CPU-bound, so
    it runs in a worker thread and does not block the event loop.
    """

    name = "whisper"

    def __init__(self) -> None:
        self._model = None
        self._lock = asyncio.Lock()

    async def _get_model(self):
        if self._model is not None:
            return self._model

        async with self._lock:
            if self._model is not None:  # another request loaded it while we waited
                return self._model
            try:
                from faster_whisper import WhisperModel
            except ImportError as error:
                raise STTError(
                    "STT_ENGINE=whisper needs faster-whisper. Install it with: "
                    "pip install faster-whisper"
                ) from error

            logger.info("Loading Whisper model %r (first use only)", WHISPER_MODEL)
            self._model = await asyncio.to_thread(
                WhisperModel, WHISPER_MODEL, device="cpu", compute_type="int8"
            )
            return self._model

    async def transcribe(self, audio: bytes, filename: str = "audio.webm") -> str:
        model = await self._get_model()

        # faster-whisper reads a path or a file-like object; a BytesIO keeps the
        # upload off the disk entirely.
        import io

        def _run() -> str:
            segments, _info = model.transcribe(
                io.BytesIO(audio),
                language=WHISPER_LANGUAGE or None,
                vad_filter=True,  # drop the silence around the words
            )
            return " ".join(segment.text.strip() for segment in segments).strip()

        try:
            return await asyncio.to_thread(_run)
        except STTError:
            raise
        except Exception as error:
            logger.exception("Whisper transcription failed")
            raise STTError(f"Could not transcribe the audio: {error}") from error


_ENGINES: dict[str, type] = {
    "browser": BrowserSTT,
    "whisper": WhisperSTT,
}

_engine: SpeechToText | None = None


def get_engine() -> SpeechToText:
    """The configured engine, built once."""
    global _engine
    if _engine is None:
        engine_class = _ENGINES.get(ENGINE_NAME)
        if engine_class is None:
            logger.warning(
                "Unknown STT_ENGINE %r; falling back to 'browser'. Choices: %s",
                ENGINE_NAME,
                ", ".join(sorted(_ENGINES)),
            )
            engine_class = BrowserSTT
        _engine = engine_class()
    return _engine


async def transcribe(audio: bytes, filename: str = "audio.webm") -> str:
    """Transcribe one audio file with whichever engine is configured."""
    if not audio:
        raise STTError("The audio file was empty.")
    if len(audio) > MAX_AUDIO_BYTES:
        raise STTError(
            f"That audio is too large ({len(audio) // 1024} KB). "
            f"The limit is {MAX_AUDIO_BYTES // 1024} KB."
        )

    text = await get_engine().transcribe(audio, filename=filename)
    text = (text or "").strip()
    if not text:
        raise STTError("No speech was found in that audio. Please try again.")
    return text


__all__ = [
    "ENGINE_NAME",
    "BrowserSTT",
    "STTError",
    "SpeechToText",
    "WhisperSTT",
    "get_engine",
    "transcribe",
]
