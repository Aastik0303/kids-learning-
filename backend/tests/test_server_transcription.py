"""The second pair of ears: `/speech/transcribe`.

The browser listens first and usually that is the end of it. This endpoint
exists for the one thing Chrome's recogniser is bad at - a child too quiet for
it, which it reports as silence rather than as something it could not read. The
web client records the same audio beside the recogniser and sends the clip here
only when its own level meter says a voice was there and the recogniser gave it
nothing.

What is pinned here is the shape of that fallback, not Whisper: the transcriber
is replaced in every test, because what matters is that a clip goes in, a
transcript comes out, and that nothing about it can end a lesson.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import stt_service


CLIP = b"\x1a\x45\xdf\xa3fake-webm-audio" + b"\x00" * 256


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def fake_transcriber(monkeypatch):
    """Whisper, without Groq. Records what it was given."""
    seen = {}

    async def _transcribe(audio, *, filename="answer.webm", language=""):
        seen["bytes"] = len(audio)
        seen["filename"] = filename
        seen["language"] = language
        # Padded on purpose: Whisper puts a leading space on almost everything.
        return " A " if audio else ""

    monkeypatch.setattr(stt_service, "transcribe", _transcribe)
    return seen


def test_a_clip_comes_back_as_words(client: TestClient, fake_transcriber):
    response = client.post(
        "/speech/transcribe?language=hi-IN",
        content=CLIP,
        headers={"Content-Type": "audio/webm"},
    )

    assert response.status_code == 200
    # Trimmed, because a transcript is compared against an answer downstream and
    # " A " is not "A".
    assert response.json()["transcript"] == "A"
    assert fake_transcriber["bytes"] == len(CLIP)
    assert fake_transcriber["language"] == "hi-IN"


def test_the_container_is_taken_from_the_content_type(client: TestClient, fake_transcriber):
    """Whisper reads the format from the file name it is given, and browsers do
    not all record `webm` - Safari hands back `mp4`."""
    client.post("/speech/transcribe", content=CLIP, headers={"Content-Type": "audio/mp4"})

    assert fake_transcriber["filename"].endswith(".mp4")


def test_an_empty_clip_is_an_answer_not_an_error(client: TestClient, fake_transcriber):
    """The clip really did hold nothing. That is what a child who said nothing
    sounds like, and it is not a failure - the class treats it the way it treats
    any answer it did not catch."""
    response = client.post("/speech/transcribe", content=b"", headers={"Content-Type": "audio/webm"})

    assert response.status_code == 200
    assert response.json()["transcript"] == ""


def test_no_transcriber_configured_says_so_rather_than_pretending(
    client: TestClient, monkeypatch
):
    """A 503 the client can recognise. It falls back to reporting what the
    browser heard, which is exactly what happened before this endpoint existed -
    so an install with no key loses nothing, it just does not gain this."""

    async def _unconfigured(audio, *, filename="answer.webm", language=""):
        raise stt_service.SttError("Server transcription is not configured.")

    monkeypatch.setattr(stt_service, "transcribe", _unconfigured)

    response = client.post("/speech/transcribe", content=CLIP, headers={"Content-Type": "audio/webm"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "TRANSCRIPTION_UNAVAILABLE"


def test_a_recording_that_is_too_long_is_refused(client: TestClient, fake_transcriber):
    """An answer is a second or two. Anything near this is not a child speaking,
    and it is refused before it is read rather than after."""
    too_much = b"\x00" * (stt_service.MAX_AUDIO_BYTES + 1)

    response = client.post(
        "/speech/transcribe", content=too_much, headers={"Content-Type": "audio/webm"}
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "AUDIO_TOO_LONG"
    assert "bytes" not in fake_transcriber, "the clip was read before it was refused"


def test_the_transcriber_never_decides_whether_an_answer_was_right(client: TestClient):
    """The boundary this project is built on, restated where it is easiest to
    break: this endpoint returns *what was said* and nothing else. No score, no
    verdict, no answer key in the request. `stage.judge` and the evaluators are
    still the only things that mark anything.
    """
    fields = set(client.app.openapi()["components"]["schemas"]["SpeechTranscriptionResult"]["properties"])

    assert fields == {"transcript", "engine"}
