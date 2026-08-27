import logging
from collections import OrderedDict

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services import edge_voice_service
from app.services.answer_resolution_service import AnswerResolutionContext, AnswerResolutionResult, resolve_answer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/speech", tags=["speech"])

# Lines the guide says over and over - the greeting, "Let us look at this one",
# every praise in the pool - cost a round trip each time they are asked for, and
# that second is spent with a child watching a still screen. The same words in
# the same voice always produce the same audio, so they are kept. Free with Edge
# as well as paid with ElevenLabs: the cost that matters here is the wait.
#
# Keyed by the words *and* the voice settings, so changing the voice in `.env`
# cannot serve the old one back - and the provider is part of the key, so the two
# voices never serve each other's audio. Bounded, and oldest-out: a lesson says a
# few dozen distinct lines and this only has to cover the ones that repeat.
_VOICE_CACHE: OrderedDict[tuple[str, str, str, str], tuple[bytes, str]] = OrderedDict()
VOICE_CACHE_LIMIT = 256


class SpeechNormalizeRequest(BaseModel):
    transcript: str = ""
    confidence: float
    answer_type: str = ""
    activity_id: str | None = None
    correct_answer: str | None = None
    accepted_answers: list[str] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)
    # The recogniser's runners-up, best first. Optional, and only consulted
    # when the first guess resolves to nothing.
    alternatives: list[str] = Field(default_factory=list, max_length=5)


class SpeechSynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    # Which voice to use. Empty means "whatever the server is configured for",
    # which is the free Edge voice unless an ElevenLabs key is set. The client
    # may ask for one explicitly so a grown-up can compare them without the
    # server being restarted; it can never ask for one that is not configured.
    provider: str = Field(default="", pattern="^(edge|elevenlabs)?$")


@router.post("/normalize", response_model=AnswerResolutionResult)
def normalize(payload: SpeechNormalizeRequest) -> AnswerResolutionResult:
    return resolve_answer(
        AnswerResolutionContext(
            transcript=payload.transcript,
            confidence=max(0.0, min(1.0, payload.confidence)),
            answer_type=payload.answer_type,
            correct_answer=payload.correct_answer,
            accepted_answers=payload.accepted_answers,
            options=payload.options,
            alternatives=payload.alternatives,
        )
    )


@router.post("/synthesize")
async def synthesize(payload: SpeechSynthesisRequest) -> Response:
    """The guide's words, spoken.

    Two providers, and the free one is the default:

    * **edge** - Microsoft Edge's neural voices through `edge-tts`. No key, no
      cost, and one voice reads English and Devanagari in the same sentence,
      which is exactly how this app narrates Hindi.
    * **elevenlabs** - better still, and paid. Used when its key is configured,
      or when the client asks for it by name.

    This used to answer 503 with no ElevenLabs key, which sent every install
    without one back to whatever robotic voice the browser happened to ship. It
    no longer can: a machine with nothing configured gets a real voice.
    """
    settings = get_settings()
    text = payload.text.strip()
    wanted = payload.provider or ("elevenlabs" if settings.elevenlabs_api_key else "edge")

    if wanted == "elevenlabs" and not settings.elevenlabs_api_key:
        # Asked for by name but not configured. The free voice is a better answer
        # than an error, and the header says which one actually spoke.
        wanted = "edge"

    if wanted == "edge":
        return await _speak_with_edge(text)
    return await _speak_with_elevenlabs(text, settings)


async def _speak_with_edge(text: str) -> Response:
    settings = get_settings()
    cache_key = (text, "edge", settings.edge_tts_voice, settings.edge_tts_rate)
    cached = _VOICE_CACHE.get(cache_key)
    if cached is not None:
        _VOICE_CACHE.move_to_end(cache_key)
        return _audio_response(*cached, provider="edge")

    try:
        audio = await edge_voice_service.synthesize(text)
    except edge_voice_service.EdgeVoiceError as error:
        # The client falls back to the browser's own voice on this, so the guide
        # gets quieter rather than silent.
        raise HTTPException(
            status_code=502,
            detail={"code": "VOICE_GENERATION_FAILED", "message": str(error)},
        ) from error

    _remember(cache_key, audio, "audio/mpeg")
    return _audio_response(audio, "audio/mpeg", provider="edge")


async def _speak_with_elevenlabs(text: str, settings) -> Response:
    cache_key = (
        text,
        settings.elevenlabs_voice_id,
        settings.elevenlabs_selected_model,
        settings.elevenlabs_output_format,
    )
    cached = _VOICE_CACHE.get(cache_key)
    if cached is not None:
        _VOICE_CACHE.move_to_end(cache_key)
        return _audio_response(*cached, provider="elevenlabs")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
    params = {"output_format": settings.elevenlabs_output_format}
    if settings.elevenlabs_optimize_streaming_latency:
        params["optimize_streaming_latency"] = settings.elevenlabs_optimize_streaming_latency

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            upstream = await client.post(
                url,
                params=params,
                headers={"xi-api-key": settings.elevenlabs_api_key, "Content-Type": "application/json"},
                json={
                    "text": text,
                    "model_id": settings.elevenlabs_selected_model,
                    "voice_settings": {"stability": 0.55, "similarity_boost": 0.8, "use_speaker_boost": True},
                },
            )
            upstream.raise_for_status()
    except httpx.HTTPError as exc:
        # The paid voice failed, and the free one is right there. A child should
        # not lose the lesson's voice over somebody's billing.
        logger.warning("ElevenLabs failed, falling back to the Edge voice: %s", exc)
        return await _speak_with_edge(text)

    media_type = upstream.headers.get("content-type", "audio/mpeg")
    _remember(cache_key, upstream.content, media_type)
    return _audio_response(upstream.content, media_type, provider="elevenlabs")


def _remember(key: tuple, audio: bytes, media_type: str) -> None:
    """Keep the clip, and drop the oldest when the shelf is full."""
    _VOICE_CACHE[key] = (audio, media_type)
    _VOICE_CACHE.move_to_end(key)
    while len(_VOICE_CACHE) > VOICE_CACHE_LIMIT:
        _VOICE_CACHE.popitem(last=False)


def _audio_response(audio: bytes, media_type: str, *, provider: str = "") -> Response:
    return Response(
        content=audio,
        media_type=media_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            # Which voice actually spoke. The client does not need it, but a
            # grown-up wondering why the guide sounds different can read it in
            # the network tab instead of guessing.
            "X-Voice-Provider": provider,
        },
    )
