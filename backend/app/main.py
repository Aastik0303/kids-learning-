import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    auth,
    children,
    companion,
    conductor,
    curriculum,
    dev,
    guide,
    history,
    learning,
    plans,
    practice,
    progress,
    speech,
)
from app.config import get_settings
from app.conductor.skill_graph import load_skill_graph
from app.db.bootstrap import ensure_schema, schema_ready
from app.services import planner_runner
from app.services.curriculum_service import load_curriculum
from app.services.learning_memory_service import initialize_learning_memory_store

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Fail fast: a malformed curriculum stops the server here, with the offending
    # file and field named, rather than surfacing as a broken screen for a child.
    load_curriculum()
    # The prerequisite graph is authored content, so it fails at boot with the
    # offending skill named rather than sending a child backwards mid-lesson.
    load_skill_graph()
    # A local SQLite file is created from the models; PostgreSQL is Alembic's,
    # and two things creating tables in production is how a migration ends up
    # half applied. Say so at boot rather than failing inside the first write.
    ensure_schema()
    if not schema_ready():
        logger.warning("Database schema is missing. Run: cd backend && alembic upgrade head")
    initialize_learning_memory_store()
    # The Planner Agent runs itself from here: today's plan is frozen before the
    # child opens the app, not built by their first request. Off when
    # `PLANNER_AUTO_RUN=0`, which is what the test suite sets.
    planner_task = planner_runner.start()
    try:
        yield
    finally:
        if planner_task is not None:
            planner_task.cancel()


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
    return {"ok": True, "schema_ready": schema_ready()}


app.include_router(auth.router)
app.include_router(children.router)
app.include_router(companion.router)
app.include_router(curriculum.router)
app.include_router(conductor.router)
app.include_router(learning.router)
app.include_router(plans.router)
app.include_router(practice.router)
app.include_router(progress.router)
app.include_router(speech.router)
app.include_router(guide.router)
app.include_router(history.router)
app.include_router(dev.router)
