from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.services.answer_normalization_service import normalize_answer

router = APIRouter(prefix="/speech", tags=["speech"])


class SpeechTranscribeResponse(BaseModel):
    transcript: str
    confidence: float
    normalized: str


async def _payload_from_request(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        return await request.json()
    if "multipart/form-data" in content_type:
        try:
            form = await request.form()
        except Exception:
            return {}
        audio = form.get("audio")
        if hasattr(audio, "close"):
            await audio.close()
        return dict(form)
    return {}


@router.post("/transcribe", response_model=SpeechTranscribeResponse)
async def transcribe(request: Request) -> SpeechTranscribeResponse:
    payload = await _payload_from_request(request)
    transcript = str(payload.get("transcript") or payload.get("browser_transcript") or "").strip()
    confidence_value = payload.get("confidence", 0 if not transcript else 0.9)
    try:
        confidence = float(confidence_value)
    except (TypeError, ValueError):
        confidence = 0.0

    return SpeechTranscribeResponse(
        transcript=transcript,
        confidence=max(0.0, min(1.0, confidence)),
        normalized=normalize_answer(transcript, str(payload.get("answer_type") or "")),
    )
