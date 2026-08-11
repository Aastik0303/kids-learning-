import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.answer_resolution_service import AnswerResolutionContext, AnswerResolutionResult, resolve_answer

router = APIRouter(prefix="/speech", tags=["speech"])


class SpeechNormalizeRequest(BaseModel):
    transcript: str = ""
    confidence: float
    answer_type: str = ""
    activity_id: str | None = None
    correct_answer: str | None = None
    accepted_answers: list[str] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)


class SpeechSynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=600)


@router.post("/normalize", response_model=AnswerResolutionResult)
async def normalize(payload: SpeechNormalizeRequest) -> AnswerResolutionResult:
    return resolve_answer(
        AnswerResolutionContext(
            transcript=payload.transcript,
            confidence=max(0.0, min(1.0, payload.confidence)),
            answer_type=payload.answer_type,
            correct_answer=payload.correct_answer,
            accepted_answers=payload.accepted_answers,
            options=payload.options,
        )
    )


@router.post("/synthesize")
async def synthesize(payload: SpeechSynthesisRequest) -> Response:
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise HTTPException(
            status_code=503,
            detail={"code": "VOICE_NOT_CONFIGURED", "message": "ElevenLabs voice is not configured."},
        )

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
                    "text": payload.text.strip(),
                    "model_id": settings.elevenlabs_selected_model,
                    "voice_settings": {"stability": 0.55, "similarity_boost": 0.8, "use_speaker_boost": True},
                },
            )
            upstream.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "VOICE_GENERATION_FAILED", "message": "The learning voice is unavailable right now."},
        ) from exc

    return Response(
        content=upstream.content,
        media_type=upstream.headers.get("content-type", "audio/mpeg"),
        headers={"Cache-Control": "private, max-age=3600"},
    )
