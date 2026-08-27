"""The guide's voice: free by default, paid when it is paid for, never silent.

`/speech/synthesize` used to answer 503 unless an ElevenLabs key was configured,
and every install without one fell back to whatever robotic voice the browser
happened to ship. It cannot any more: Microsoft Edge's neural voices are free and
need no key, so a machine with nothing configured still gets a real voice.

Three things are pinned here, and all three are about a child not losing the
lesson's voice over somebody's configuration:

1. **No key is not an error.** With no ElevenLabs key the endpoint speaks with
   Edge and says so in `X-Voice-Provider`.
2. **The paid voice failing falls through to the free one**, rather than 502-ing
   a child into silence.
3. **The two voices never serve each other's audio.** The cache is keyed by
   provider as well as by the words.

The network is never touched: `edge_voice_service.synthesize` is replaced, because
what is being tested is the *routing*, not Microsoft's servers.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import speech as speech_api
from app.config import get_settings
from app.main import app
from app.services import edge_voice_service


# Two obviously different clips, so a test that gets the wrong one fails loudly
# rather than passing on a coincidence.
EDGE_AUDIO = b"\xff\xf3edge-audio" + b"\x00" * 64
ELEVEN_AUDIO = b"\xff\xf3eleven-audio" + b"\x00" * 64


async def _eleven_ok(self, url, **kwargs):
    """A successful ElevenLabs reply.

    The request has to be attached: `raise_for_status()` reads it back to build
    its message and raises RuntimeError on a response that never had one.
    """
    return httpx.Response(
        200,
        content=ELEVEN_AUDIO,
        headers={"content-type": "audio/mpeg"},
        request=httpx.Request("POST", url),
    )


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


@pytest.fixture()
def no_elevenlabs_key(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "elevenlabs_api_key", "", raising=False)
    return settings


@pytest.fixture()
def with_elevenlabs_key(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "elevenlabs_api_key", "test-key", raising=False)
    return settings


# --------------------------------------------------------------------------
# 1. A machine with no key still has a voice
# --------------------------------------------------------------------------


def test_no_key_speaks_with_edge_instead_of_refusing(
    client: TestClient, fake_edge, no_elevenlabs_key
):
    """This is the whole point of the change. It used to be a 503."""
    response = client.post("/speech/synthesize", json={"text": "Hello little one."})

    assert response.status_code == 200
    assert response.headers["x-voice-provider"] == "edge"
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == EDGE_AUDIO
    assert fake_edge == ["Hello little one."]


def test_the_paid_voice_is_preferred_when_it_is_paid_for(
    client: TestClient, fake_edge, with_elevenlabs_key, monkeypatch
):
    monkeypatch.setattr(httpx.AsyncClient, "post", _eleven_ok)

    response = client.post("/speech/synthesize", json={"text": "Good morning."})

    assert response.status_code == 200
    assert response.headers["x-voice-provider"] == "elevenlabs"
    assert response.content == ELEVEN_AUDIO
    assert fake_edge == [], "the free voice was not needed"


# --------------------------------------------------------------------------
# 2. Nothing leaves a child in silence
# --------------------------------------------------------------------------


def test_elevenlabs_failing_falls_through_to_the_free_voice(
    client: TestClient, fake_edge, with_elevenlabs_key, monkeypatch
):
    """A billing problem, a rate limit, a dropped connection - none of them is a
    reason for the guide to stop talking."""

    async def _explode(self, url, **kwargs):
        raise httpx.ConnectError("nope")

    monkeypatch.setattr(httpx.AsyncClient, "post", _explode)

    response = client.post("/speech/synthesize", json={"text": "Let us try this one."})

    assert response.status_code == 200
    assert response.headers["x-voice-provider"] == "edge"
    assert response.content == EDGE_AUDIO


def test_asking_for_the_paid_voice_without_a_key_gets_the_free_one(
    client: TestClient, fake_edge, no_elevenlabs_key
):
    """The client cannot see whether a key is configured, so choosing the paid
    voice must not be a way to break the app."""
    response = client.post(
        "/speech/synthesize", json={"text": "Say it with me.", "provider": "elevenlabs"}
    )

    assert response.status_code == 200
    assert response.headers["x-voice-provider"] == "edge"


def test_edge_failing_is_reported_rather_than_hidden(
    client: TestClient, no_elevenlabs_key, monkeypatch
):
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


def test_the_same_line_is_only_synthesised_once(
    client: TestClient, fake_edge, no_elevenlabs_key
):
    """The guide says "Let us look at this one" all day. Saying it costs a round
    trip with a child watching a still screen."""
    for _ in range(3):
        assert client.post("/speech/synthesize", json={"text": "Let us look."}).status_code == 200

    assert fake_edge == ["Let us look."], "the line was synthesised more than once"


def test_the_two_voices_never_serve_each_others_audio(
    client: TestClient, fake_edge, with_elevenlabs_key, monkeypatch
):
    """Same words, different provider, different clip. A cache keyed on the words
    alone would hand the paid voice's audio back for a free-voice request."""

    monkeypatch.setattr(httpx.AsyncClient, "post", _eleven_ok)

    line = {"text": "The very same words."}
    paid = client.post("/speech/synthesize", json={**line, "provider": "elevenlabs"})
    free = client.post("/speech/synthesize", json={**line, "provider": "edge"})

    assert paid.content == ELEVEN_AUDIO
    assert free.content == EDGE_AUDIO


def test_an_unknown_provider_is_refused(client: TestClient):
    assert client.post("/speech/synthesize", json={"text": "hi", "provider": "hal9000"}).status_code == 422


def test_empty_text_is_refused(client: TestClient):
    assert client.post("/speech/synthesize", json={"text": ""}).status_code == 422


# --------------------------------------------------------------------------
# 4. One voice, both scripts
# --------------------------------------------------------------------------


def test_a_line_with_hindi_quoted_inside_english_goes_out_whole(
    client: TestClient, fake_edge, no_elevenlabs_key
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
