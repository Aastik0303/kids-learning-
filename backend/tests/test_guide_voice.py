"""The guide's voice: one voice, free, and never silent.

`/speech/synthesize` used to have two providers - Microsoft Edge's free neural
voices and a paid ElevenLabs one that took over whenever a key happened to be
present in `.env`. It has one now. A key left in somebody's environment was
enough to change the voice of the whole site without anybody choosing it, so the
guide sounded like a different person depending on whose machine was serving it,
and a child heard a different teacher.

Four things are pinned here:

1. **Edge speaks, whatever is configured and whatever is asked for.** A request
   naming the old paid provider still gets Edge, and says so in
   `X-Voice-Provider`.
2. **A failure is reported rather than hidden**, because the web client falls
   back to the browser's own voice on it - an empty 200 would be silence.
3. **The repeated lines are only synthesised once.**
4. **A line with Devanagari quoted inside English goes out whole**, which is the
   reason this voice was chosen.

The network is never touched: `edge_voice_service.synthesize` is replaced,
because what is being tested is the *routing*, not Microsoft's servers.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.api import speech as speech_api
from app.main import app
from app.services import edge_voice_service


EDGE_AUDIO = b"\xff\xf3edge-audio" + b"\x00" * 64


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def empty_voice_cache():
    """Each test starts with nothing remembered, or the second one reads the
    first one's clip back and proves nothing."""
    speech_api._VOICE_CACHE.clear()
    yield
    speech_api._VOICE_CACHE.clear()


@pytest.fixture()
def fake_edge(monkeypatch):
    """Edge, without Microsoft. Records what it was asked to say."""
    said = []

    async def _synthesize(text, *, voice="", rate="", pitch=""):
        said.append(text)
        return EDGE_AUDIO

    monkeypatch.setattr(edge_voice_service, "synthesize", _synthesize)
    return said


# --------------------------------------------------------------------------
# 1. There is one voice
# --------------------------------------------------------------------------


def test_the_free_neural_voice_speaks(client: TestClient, fake_edge):
    response = client.post("/speech/synthesize", json={"text": "Hello little one."})

    assert response.status_code == 200
    assert response.headers["x-voice-provider"] == "edge"
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == EDGE_AUDIO
    assert fake_edge == ["Hello little one."]


@pytest.mark.parametrize("asked_for", ["edge", "elevenlabs", "browser", ""])
def test_no_request_can_change_the_voice(client: TestClient, fake_edge, asked_for):
    """`provider` is accepted and ignored.

    Accepted rather than refused because older clients and the mobile app still
    send it, and a 422 on the voice endpoint would leave a child in silence over
    a field nobody reads. Ignored because there is only one voice to pick.
    """
    response = client.post(
        "/speech/synthesize", json={"text": "Say it with me.", "provider": asked_for}
    )

    assert response.status_code == 200
    assert response.headers["x-voice-provider"] == "edge"
    assert response.content == EDGE_AUDIO


# --------------------------------------------------------------------------
# 2. Nothing leaves a child in silence
# --------------------------------------------------------------------------


def test_edge_failing_is_reported_rather_than_hidden(client: TestClient, monkeypatch):
    """The web client falls back to the browser's own voice on this, so it has to
    be a failure it can see - not an empty 200."""

    async def _explode(text, *, voice="", rate="", pitch=""):
        raise edge_voice_service.EdgeVoiceError("Edge is down")

    monkeypatch.setattr(edge_voice_service, "synthesize", _explode)

    response = client.post("/speech/synthesize", json={"text": "Hello."})

    assert response.status_code == 502
    # This app reshapes HTTPException into {"error": {...}} - see app.main's
    # handler - so the code is there rather than under FastAPI's "detail".
    assert response.json()["error"]["code"] == "VOICE_GENERATION_FAILED"


# --------------------------------------------------------------------------
# 3. The cache, and the input
# --------------------------------------------------------------------------


def test_the_same_line_is_only_synthesised_once(client: TestClient, fake_edge):
    """The guide says "Let us look at this one" all day. Saying it costs a round
    trip with a child watching a still screen."""
    for _ in range(3):
        assert client.post("/speech/synthesize", json={"text": "Let us look."}).status_code == 200

    assert fake_edge == ["Let us look."], "the line was synthesised more than once"


def test_an_unknown_provider_is_refused(client: TestClient):
    """Ignoring the field is not the same as accepting nonsense in it."""
    assert client.post("/speech/synthesize", json={"text": "hi", "provider": "hal9000"}).status_code == 422


def test_empty_text_is_refused(client: TestClient):
    assert client.post("/speech/synthesize", json={"text": ""}).status_code == 422


# --------------------------------------------------------------------------
# 4. One voice, both scripts
# --------------------------------------------------------------------------


def test_a_line_with_hindi_quoted_inside_english_goes_out_whole(
    client: TestClient, fake_edge
):
    """This is why the Edge voice is worth having.

    The guide narrates in English with the taught word quoted in Devanagari, and
    `hi-IN-SwaraNeural` reads that whole sentence in one breath. The web client
    used to have to cut such a line into runs by script and hand each run to a
    different browser voice; here it is one request with one answer.
    """
    line = "This is कमल. Can you say कमल?"

    response = client.post("/speech/synthesize", json={"text": line})

    assert response.status_code == 200
    assert fake_edge == [line], "the sentence was split before it reached the voice"


# --------------------------------------------------------------------------
# 5. A stumble is not a failure
# --------------------------------------------------------------------------
#
# Microsoft's free endpoint refuses a handshake or drops a connection now and
# then. That reached a child as the device's own robot for the rest of the line
# - and on Windows the robot reads Devanagari as nothing at all - so a transient
# failure is asked again here rather than being handed to the fallback.


@pytest.fixture(autouse=True)
def no_backoff_waiting(monkeypatch):
    """The retry waits are real seconds. Nothing here is testing the clock."""

    async def _no_wait(_seconds):
        return None

    monkeypatch.setattr(edge_voice_service.asyncio, "sleep", _no_wait)


def _stream_that(*outcomes):
    """A fake `_stream` that produces one outcome per call.

    An outcome is either bytes to return or an exception to raise.
    """
    calls = []

    async def _stream(text, *, voice, rate, pitch):
        outcome = outcomes[min(len(calls), len(outcomes) - 1)]
        calls.append(text)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    return _stream, calls


def test_a_dropped_connection_is_asked_again_rather_than_given_up_on(monkeypatch):
    stream, calls = _stream_that(ConnectionResetError("reset"), EDGE_AUDIO)
    monkeypatch.setattr(edge_voice_service, "_stream", stream)

    audio = asyncio.run(edge_voice_service.synthesize("This is कमल."))

    assert audio == EDGE_AUDIO
    assert len(calls) == 2, "the failed attempt was not retried"


def test_a_stream_that_carries_no_audio_is_asked_again(monkeypatch):
    """What a refused handshake usually looks like from here: a clean stream
    with nothing in it."""
    stream, calls = _stream_that(b"", EDGE_AUDIO)
    monkeypatch.setattr(edge_voice_service, "_stream", stream)

    assert asyncio.run(edge_voice_service.synthesize("Hello.")) == EDGE_AUDIO
    assert len(calls) == 2


def test_a_voice_that_stays_down_still_fails_so_the_client_can_fall_back(monkeypatch):
    """Retrying forever would be worse than the robot. After the last attempt
    the caller is told, and the web client speaks with the device's own voice."""
    stream, calls = _stream_that(ConnectionResetError("reset"))
    monkeypatch.setattr(edge_voice_service, "_stream", stream)

    with pytest.raises(edge_voice_service.EdgeVoiceError):
        asyncio.run(edge_voice_service.synthesize("Hello."))

    assert len(calls) == edge_voice_service.ATTEMPTS


def test_the_endpoint_serves_a_recovered_clip_as_a_normal_answer(
    client: TestClient, monkeypatch
):
    """The stumble never reaches the child: /speech/synthesize is a 200."""
    stream, _ = _stream_that(ConnectionResetError("reset"), EDGE_AUDIO)
    monkeypatch.setattr(edge_voice_service, "_stream", stream)

    response = client.post("/speech/synthesize", json={"text": "Hello."})

    assert response.status_code == 200
    assert response.content == EDGE_AUDIO
