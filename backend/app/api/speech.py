import logging
from collections import OrderedDict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services import edge_voice_service, stt_service
from app.services.answer_resolution_service import AnswerResolutionContext, AnswerResolutionResult, resolve_answer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/speech", tags=["speech"])

# Lines the guide says over and over - the greeting, "Let us look at this one",
# every praise in the pool - cost a round trip each time they are asked for, and
# that second is spent with a child watching a still screen. The same words in
# the same voice always produce the same audio, so they are kept. The voice is
# free either way; the cost that matters here is the wait.
#
# Keyed by the words *and* the voice settings, so changing the voice in `.env`
# cannot serve the old one back. Bounded, and oldest-out: a lesson says a few
# dozen distinct lines and this only has to cover the ones that repeat.
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
    # Accepted and ignored. There is one voice now - the Edge one - so this
    # field can no longer change what speaks. It is still parsed rather than
    # rejected because older clients (and the mobile app) still send it, and a
    # 422 on the voice endpoint would leave a child in silence over a field
    # nobody reads.
    provider: str = Field(default="", pattern="^(edge|elevenlabs|browser)?$")


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


class SpeechTranscriptionResult(BaseModel):
    transcript: str
    engine: str


@router.post("/transcribe", response_model=SpeechTranscriptionResult)
async def transcribe(request: Request, language: str = "") -> SpeechTranscriptionResult:
    """A second pair of ears, for the clip the browser made nothing of.

    The web client only reaches this when its own recogniser came back empty
    *and* the microphone level said a voice was there - a quiet child, which
    Chrome reports as silence. See `app/services/stt_service.py`.

    The clip is the raw request body rather than a multipart upload: it is one
    unnamed blob straight out of `MediaRecorder`, a form would only wrap it in a
    boundary to unwrap again, and reading it this way keeps `python-multipart`
    off the dependency list.

    An empty transcript is a normal answer here, not an error: it means the clip
    really did hold nothing, and the class treats that the way it treats any
    answer it did not catch. Only a broken or missing transcriber is a failure,
    and it is a 503 so the client can tell the two apart.
    """
    clip = await request.body()
    if len(clip) > stt_service.MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"code": "AUDIO_TOO_LONG", "message": "That recording is too long."},
        )

    filename = "answer.webm"
    content_type = request.headers.get("content-type", "")
    if "ogg" in content_type:
        filename = "answer.ogg"
    elif "mp4" in content_type or "aac" in content_type:
        filename = "answer.mp4"

    try:
        text = await stt_service.transcribe(clip, filename=filename, language=language)
    except stt_service.SttError as error:
        raise HTTPException(
            status_code=503,
            detail={"code": "TRANSCRIPTION_UNAVAILABLE", "message": str(error)},
        ) from error

    # Trimmed here as well as in the service: a transcript is compared against
    # an answer downstream, and " A " is not "A".
    return SpeechTranscriptionResult(transcript=text.strip(), engine=stt_service.MODEL)


@router.post("/synthesize")
async def synthesize(payload: SpeechSynthesisRequest) -> Response:
    """The guide's words, spoken.

    **One voice, everywhere.** Microsoft Edge's neural voices through
    `edge-tts`: no key, no cost, and a single voice that reads English and
    Devanagari in the same sentence, which is exactly how this app narrates
    Hindi. `settings.edge_tts_voice` is the whole of the decision.

    The paid ElevenLabs path is gone rather than merely unpreferred. While it
    existed, a key left in somebody's `.env` was enough to change the voice of
    the entire site without anybody choosing it, and the guide sounded like a
    different person depending on whose machine it was running on. A child
    should hear one teacher.

    `payload.provider` is read and ignored - see `SpeechSynthesisRequest`.
    """
    return await _speak_with_edge(payload.text.strip())


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
