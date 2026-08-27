"""The FastAPI app: four endpoints and the page that uses them.

    GET  /health   is everything wired up?
    POST /chat     text in, the assistant's reply out
    POST /tts      text in, spoken MP3 out
    POST /stt      audio in, text out (for when Whisper takes over from the browser)
    GET  /         the frontend itself

The app also *serves* the frontend, from `../frontend`. That is not decoration:
opening `index.html` straight off the disk makes the page's origin `file://`, and
a `fetch` from there to `127.0.0.1:8000` is a cross-origin request that the
browser blocks. Serving both from one origin means the demo works the moment the
server starts, with nothing to configure.

Every endpoint answers a failure with a sentence a person can act on. The browser
shows whatever `detail` says, so "Groq rejected the API key" reaches the screen
instead of "500 Internal Server Error".
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import ai, stt, tts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(
    title="AI Voice Agent",
    description="Browser microphone -> Groq -> Edge TTS -> spoken reply.",
    version="1.0.0",
)

# The frontend is served from this same origin, so CORS is not needed for the
# demo. It is open here so you can also run the page from Live Server, a phone on
# the LAN, or a separate frontend dev server while you are building.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# What goes in and what comes out
# --------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """`min_length` is the invalid-input guard: an empty message is a 422 with a
    readable explanation, before any of our code runs."""

    message: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    response: str


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    # Optional overrides, so the page can offer a different voice without the
    # server needing a restart. Empty means "use the configured default".
    voice: str = Field(default="", max_length=64)


class STTResponse(BaseModel):
    transcript: str
    engine: str


# --------------------------------------------------------------------------
# The endpoints
# --------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    """Is this thing on?

    Deliberately does not call Groq or Edge - a health check that costs money and
    a network round trip is one nobody dares to poll. It reports what is
    *configured*, which is what is actually worth knowing before you speak.
    """
    return {
        "status": "ok",
        "groq_key_configured": ai.has_api_key(),
        "model": ai.MODEL,
        "tts_voice": tts.DEFAULT_VOICE,
        "stt_engine": stt.ENGINE_NAME,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    """What the user said, in; what the assistant says back, out."""
    try:
        reply = await ai.get_ai_response(payload.message)
    except ai.AIError as error:
        # 502: this server is fine, the thing it depends on is not.
        raise HTTPException(status_code=502, detail=str(error)) from error

    return ChatResponse(response=reply)


@app.post("/tts")
async def speak(payload: TTSRequest) -> Response:
    """Text in, an MP3 out.

    Returned as bytes rather than a file on disk: the audio is small, it is
    wanted exactly once, and a temp file would need cleaning up and would race
    two requests against each other.
    """
    try:
        audio = await tts.text_to_speech(
            payload.text, voice=payload.voice.strip() or tts.DEFAULT_VOICE
        )
    except tts.TTSError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": 'inline; filename="reply.mp3"',
            "Cache-Control": "no-store",
        },
    )


@app.post("/stt", response_model=STTResponse)
async def transcribe(file: UploadFile = File(...)) -> STTResponse:
    """Audio in, text out - the seam where Whisper replaces the browser.

    With the default `STT_ENGINE=browser` this answers 501 and says so: the
    browser is doing the transcribing and there is nothing here to do. Set
    `STT_ENGINE=whisper` and the same endpoint starts working, with no change
    anywhere else in the project.
    """
    try:
        audio = await file.read()
    except Exception as error:
        raise HTTPException(status_code=400, detail="Could not read the upload.") from error

    try:
        text = await stt.transcribe(audio, filename=file.filename or "audio.webm")
    except stt.STTError as error:
        # 501 for "this engine does not do that", 400 for "that audio was no good".
        status = 501 if stt.ENGINE_NAME == "browser" else 400
        raise HTTPException(status_code=status, detail=str(error)) from error

    return STTResponse(transcript=text, engine=stt.ENGINE_NAME)


@app.get("/voices")
async def voices(prefix: str = "") -> list[dict]:
    """Every Edge voice, so you can pick a different one without leaving the app.

    `/voices?prefix=hi-IN` lists the Hindi ones.
    """
    try:
        return await tts.list_voices(prefix)
    except tts.TTSError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.exception_handler(Exception)
async def unhandled(request, error: Exception) -> JSONResponse:
    """Anything nobody thought of, said politely and logged in full.

    Without this the browser gets an empty 500 and the user gets a page that
    silently does nothing.
    """
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on the server. Please try again."},
    )


# --------------------------------------------------------------------------
# The page
# --------------------------------------------------------------------------

# Mounted last, so /chat, /tts and the rest are matched before the catch-all.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:  # pragma: no cover - only if the frontend folder was moved or deleted

    @app.get("/")
    async def missing_frontend() -> FileResponse:
        raise HTTPException(
            status_code=404,
            detail=f"The frontend folder was not found at {FRONTEND_DIR}.",
        )


# --------------------------------------------------------------------------
# Running it directly
# --------------------------------------------------------------------------

if __name__ == "__main__":
    # `python -m backend.main` starts the server on the configured port without
    # anyone having to remember a flag. `uvicorn backend.main:app --reload` still
    # works and is the better one while you are editing - it just needs
    # `--port 8009` on the command line, because uvicorn's own default is 8000.
    import os

    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8009")),
        reload=os.getenv("RELOAD", "1") == "1",
    )
