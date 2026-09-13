"""What every request passes through on its way in and out.

Three things, and each of them is about the time a small child spends looking at
a screen that has not finished loading:

* **rate limiting**, so one caller cannot make the class slow for everybody
  else - and so nobody can run up a model bill or a synthesis bill on this
  account;
* **conditional responses** (`ETag` / `If-None-Match`) on the read-only
  curriculum routes, so a returning browser is answered with an empty 304
  instead of the whole syllabus again;
* **timing**, as a `Server-Timing` header, so "the class feels slow" can be
  answered with a number from the browser's own network panel rather than a
  guess.

Compression is Starlette's own `GZipMiddleware` and is added in `app/main.py`.
"""

import logging
import time
from hashlib import blake2b

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.config import get_settings
from app.services import rate_limit
from app.services.rate_limit import EXEMPT_PREFIXES, RateLimiter


logger = logging.getLogger(__name__)

# One limiter for the process. Buckets live in it and nowhere else.
limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Refuse a caller who is asking too fast, kindly and with a `Retry-After`.

    It **fails open**: anything unexpected in here is logged and the request is
    served. A limiter that breaks should cost a log line, never a child's
    lesson.
    """

    async def dispatch(self, request, call_next):
        try:
            decision = self._check(request)
        except Exception:  # pragma: no cover - the fail-open path
            logger.exception("Rate limiter failed; allowing the request through")
            decision = None

        if decision is not None and not decision.allowed:
            # The app's own error envelope, so a client that already knows how
            # to read an error reads this one too. The message is worded for
            # whoever is holding the device, which may be a parent.
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "TOO_MANY_REQUESTS",
                        "message": "That is a lot of asking all at once. Please wait a moment and try again.",
                    }
                },
            )
            self._annotate(response, decision)
            response.headers["Retry-After"] = str(decision.retry_after)
            return response

        response = await call_next(request)
        if decision is not None:
            self._annotate(response, decision)
        return response

    @staticmethod
    def _annotate(response: Response, decision) -> None:
        response.headers["X-RateLimit-Limit"] = str(decision.limit.requests)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        response.headers["X-RateLimit-Bucket"] = decision.bucket

    def _check(self, request):
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return None

        path = request.url.path
        if path.startswith(EXEMPT_PREFIXES):
            return None
        # A browser asks permission before a cross-origin POST and does not send
        # credentials with it. Counting preflights would spend a caller's
        # allowance on requests they did not make.
        if request.method == "OPTIONS":
            return None

        limits = rate_limit.limits_from(settings)
        ip = rate_limit.client_ip(
            request.headers,
            request.client.host if request.client else None,
            trust_forwarded=settings.rate_limit_trust_forwarded_for,
        )

        # The ceiling first. It is the one a caller cannot get out of by
        # inventing a new token, so it is the one worth spending first.
        ceiling = limiter.check(key=f"ip:{ip}", bucket="ip", limit=limits["ip"])
        if not ceiling.allowed:
            return ceiling

        bucket = rate_limit.bucket_for(path)
        return limiter.check(
            key=rate_limit.caller_key(request.headers, ip), bucket=bucket, limit=limits[bucket]
        )


class ContentCacheMiddleware(BaseHTTPMiddleware):
    """`ETag` and `Cache-Control` for the routes that answer authored content.

    The curriculum, a level's games, a topic's notes: files read at boot, the
    same for every child, and changing only when this service is deployed. The
    server already answers them from memory - what this saves is the *network*,
    which on a phone is most of what "slow" means.

    Only ever applied to a **GET** that succeeded, and only on the prefixes
    listed here. Nothing about a child is in any of them: a plan, a progress
    record or a session must be re-read every time, and one path added to this
    tuple carelessly would be a class showing yesterday's stars.

    `must-revalidate` rather than a long `max-age`: the browser may reuse what
    it has for a minute, and after that it asks again and is usually answered
    with 304 and no body at all. A deploy that changes the syllabus is therefore
    visible within the minute rather than whenever a cache happened to expire.
    """

    CACHEABLE_PREFIXES = ("/curriculum",)

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        if request.method not in ("GET", "HEAD"):
            return response
        if not request.url.path.startswith(self.CACHEABLE_PREFIXES):
            return response
        if response.status_code != 200:
            return response

        # The body has to be in hand to be hashed, and at this layer it is a
        # stream rather than bytes - so it is read into memory and handed on as
        # a plain response. That is only safe because of the prefix check
        # above: these are small JSON answers read from memory. Buffering an
        # arbitrary response here would be buffering an audio clip.
        body = b"".join([chunk async for chunk in response.body_iterator])
        response = Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

        etag = '"' + blake2b(body, digest_size=16).hexdigest() + '"'
        max_age = get_settings().content_cache_max_age_seconds
        headers = {
            "ETag": etag,
            "Cache-Control": f"public, max-age={max_age}, must-revalidate",
        }

        if request.headers.get("if-none-match") == etag:
            # Same bytes as last time. 304 carries no body by definition, which
            # is the whole point of it.
            return Response(status_code=304, headers=headers)

        response.headers.update(headers)
        return response


class ServerTimingMiddleware(BaseHTTPMiddleware):
    """How long this took, on the response, in the browser's own units.

    `Server-Timing` shows up in the network panel beside the request, so the
    time inside this service can be told apart from the time on the wire without
    anybody adding logging to find out.
    """

    async def dispatch(self, request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["Server-Timing"] = f'app;dur={elapsed_ms:.1f}'
        return response
