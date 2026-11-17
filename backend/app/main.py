import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
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
    playground,
    policy,
    practice,
    progress,
    speech,
)
from app.api.middleware import (
    ContentCacheMiddleware,
    RateLimitMiddleware,
    ServerTimingMiddleware,
)
from app.config import get_settings
from app.playground import rag
from app.conductor.skill_graph import load_skill_graph
from app.db.bootstrap import ensure_schema, pending_migrations, schema_ready
from app.services import cache, planner_runner
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
    # A database that is merely *behind* is the worse failure, because nothing
    # crashes: the tables all exist, so the check above is happy, and only the
    # column the new code selects is missing. That is how the whole schedule
    # disappeared once - every read of today's plan raised, `plan_service` caught
    # it so that infrastructure could not lock a child out, and the schedule
    # strip, the day's gate and the AI Teacher's stages all quietly degraded with
    # no error anywhere. Say it at boot, loudly, with the fix in the line.
    behind = pending_migrations()
    if behind:
        logger.error(
            "Database is %d migration(s) behind (%s). Today's plan cannot be read, "
            "so the schedule will not show and the class will not follow it. "
            "Run: cd backend && alembic upgrade head",
            len(behind),
            ", ".join(behind),
        )
    initialize_learning_memory_store()
    # The Planner Agent runs itself from here: today's plan is frozen before the
    # child opens the app, not built by their first request. Off when
    # `PLANNER_AUTO_RUN=0`, which is what the test suite sets.
    planner_task = planner_runner.start()
    # The AI Teacher's retrieval index, built off the request path. It is a
    # playground, so a failure here is logged and forgotten - the tab still
    # works, it just pays the build on its first turn.
    threading.Thread(target=rag.warm, name="playground-rag-warm", daemon=True).start()
    try:
        yield
    finally:
        if planner_task is not None:
            planner_task.cancel()


app = FastAPI(title="AI Nursery Learning Platform", version="0.1.0", lifespan=lifespan)

# Middleware runs outermost-first in the order it is *last* added, so this
# block reads bottom-to-top: CORS sees the request first, then the rate limiter,
# then compression, then the content cache, then timing closest to the route.
#
# The order is not cosmetic. The rate limiter has to sit inside CORS or a
# refused cross-origin request arrives at the browser without the headers that
# let it read the refusal, and a 429 then shows up in the console as a CORS
# error - which is a bug report about the wrong thing entirely. And
# `ContentCacheMiddleware` has to sit *inside* GZip so it hashes the real body
# rather than whichever compression the caller happened to accept, or two
# browsers get two ETags for one answer.
app.add_middleware(ServerTimingMiddleware)
app.add_middleware(ContentCacheMiddleware)
# 500 bytes: below that a compressed body is not reliably smaller, and the CPU
# is real. The curriculum, a plan and a class detail are all far above it.
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # So a browser can read how much of its allowance is left, and how long a
    # 429 wants it to wait, instead of only seeing that something failed.
    expose_headers=[
        "ETag",
        "Retry-After",
        "Server-Timing",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Bucket",
    ],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Through logging and with the traceback: a bare `print` of the message is
    # all a production 500 used to leave behind, which is not enough to find it.
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "SERVER_ERROR", "message": "Something went wrong. Let us try again."}},
    )


@app.get("/health")
async def health() -> dict:
    """Whether this process can actually serve a class.

    `pending_migrations` is here and not only in the boot log because a server
    that has been up for a week has scrolled its boot log away, and "the
    scheduling is gone" is a question someone asks days later.
    """
    behind = pending_migrations()
    return {
        "ok": True,
        "schema_ready": schema_ready(),
        "pending_migrations": behind,
        "schema_current": not behind,
        # Hit rates for the in-process content caches. Counts only - there is
        # nothing here about any child, and it is what makes "is the cache
        # actually being used" answerable without attaching a profiler to a
        # running server.
        "caches": cache.stats(),
    }


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
app.include_router(playground.router)
app.include_router(policy.router)
# Development only, and not merely refused there: a route that answers 403 in
# production is still a route, still in the schema and still one misread setting
# away from unlocking a child's whole curriculum. Outside development it is not
# mounted at all.
if settings.env.lower() == "development":
    app.include_router(dev.router)
