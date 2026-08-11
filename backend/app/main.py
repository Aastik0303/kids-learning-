from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, children, companion, dev, guide, history, learning, practice, progress, speech, toddler
from app.config import get_settings
from app.services.learning_memory_service import initialize_learning_memory_store

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_learning_memory_store()
    yield


app = FastAPI(title="AI Nursery Learning Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    print(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "SERVER_ERROR", "message": "Something went wrong. Let us try again."}},
    )


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "mode": "prototype"}


app.include_router(auth.router)
app.include_router(children.router)
app.include_router(companion.router)
app.include_router(learning.router)
app.include_router(practice.router)
app.include_router(progress.router)
app.include_router(speech.router)
app.include_router(toddler.router)
app.include_router(guide.router)
app.include_router(history.router)
app.include_router(dev.router)
