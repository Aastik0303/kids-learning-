"""Rate limiting: how much one caller may ask for, and how fast.

Not every endpoint here costs the same. A curriculum read is a dictionary
lookup; a teaching turn calls a language model; `/speech/say` synthesises audio.
So the limit is per **route class** rather than one number for the whole API,
and the expensive classes are the tight ones - an unthrottled `/speech` is
somebody else's bill.

**Two buckets are checked on every request**, and the second is why the first
can be generous:

* **the caller's own bucket** - keyed by their bearer token when they are
  signed in, and by their IP address when they are not. Keying signed-in
  traffic by token matters here specifically: a great many of these families are
  on Indian mobile networks behind carrier-grade NAT, where thousands of
  unrelated people share one public address. A per-IP-only limiter would have
  them taking each other's class offline.
* **a per-IP ceiling**, much higher, which nobody using the app normally will
  ever reach. It exists because the token half of the rule above is
  self-declared: anyone can invent a new bearer string and get a fresh bucket,
  and this is the thing that stops that being unlimited.

The algorithm is a token bucket: a steady refill at `requests / per_seconds`,
and a capacity that allows a short burst. A fixed window would let a client
spend a whole minute's allowance in the last second of one window and again in
the first second of the next; and a burst is exactly what a real class does -
a page loads its plan, its child, its curriculum and its first turn at once, and
then goes quiet while a three-year-old thinks.

**It fails open.** A bug or an exhaustion in here must never be what takes the
class down, so the middleware catches everything and lets the request through.
The state is in this process, so two workers allow roughly twice these numbers;
that is a deliberate trade against needing Redis to answer a request at all.
"""

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from hashlib import blake2b

from app.config import Settings


@dataclass(frozen=True)
class Limit:
    """A refill rate and a burst, in one place so it can be read aloud."""

    requests: int
    per_seconds: float
    burst: int

    @property
    def refill_per_second(self) -> float:
        return self.requests / self.per_seconds if self.per_seconds > 0 else float("inf")

    def retry_after(self, tokens: float) -> int:
        """Whole seconds until one more request would be allowed."""
        needed = max(0.0, 1.0 - tokens)
        rate = self.refill_per_second
        if rate <= 0:  # pragma: no cover - a zero-rate limit is a closed door
            return int(self.per_seconds)
        return max(1, int(needed / rate + 0.999))


# The route classes, most specific prefix first. A path that matches none of
# them is "read", which is the generous one.
#
# `/health` is deliberately absent: it is what the platform polls to decide
# whether this instance is alive, and rate-limiting it is how a busy server gets
# restarted for being busy.
EXEMPT_PREFIXES = ("/health",)


def bucket_for(path: str) -> str:
    """Which class of limit this path falls under."""
    if path.startswith("/auth/"):
        return "auth"
    if path.startswith("/speech/"):
        return "speech"
    if path.startswith(("/playground/", "/agent/", "/conductor/", "/learning/", "/practice/")):
        return "ai"
    return "read"


def limits_from(settings: Settings) -> dict[str, Limit]:
    """The configured limits, so none of these numbers needs a deploy to change.

    The defaults are set against what the app itself does rather than against a
    round number:

    * **auth** - signing in is a handful of requests. It is low because it is
      the surface worth attacking, and because the per-account lockout in
      `auth_service` counts password guesses separately and per account.
    * **ai** - a teaching turn, and the retries and re-reads around it. A child's
      turn takes seconds, so this is many times what a real class can use.
    * **speech** - every one of these spends CPU synthesising audio.
    * **read** - plans, curriculum, progress. Cheap, cached, and asked for in
      bursts as a page loads.
    """
    return {
        "auth": Limit(settings.rate_limit_auth_per_minute, 60.0, settings.rate_limit_auth_per_minute),
        "ai": Limit(settings.rate_limit_ai_per_minute, 60.0, settings.rate_limit_ai_per_minute),
        "speech": Limit(settings.rate_limit_speech_per_minute, 60.0, settings.rate_limit_speech_per_minute),
        "read": Limit(settings.rate_limit_read_per_minute, 60.0, settings.rate_limit_read_per_minute),
        # The ceiling. Per IP, whatever the route and whoever is signed in.
        "ip": Limit(settings.rate_limit_ip_per_minute, 60.0, settings.rate_limit_ip_per_minute),
    }


@dataclass
class Decision:
    allowed: bool
    limit: Limit
    remaining: int
    retry_after: int = 0
    bucket: str = ""


class RateLimiter:
    """The buckets, and the arithmetic on them.

    Bounded on purpose. One entry per caller per route class is small, but the
    key includes something a stranger chooses, so an unbounded map here is a way
    to exhaust the instance's memory rather than its request budget. Least
    recently used is dropped, which - because a dropped bucket comes back full -
    is a deliberate and documented softness: filling the map faster than the
    limits allow is itself the thing the IP ceiling caps.
    """

    def __init__(self, *, maxsize: int = 20_000):
        self.maxsize = maxsize
        self._buckets: OrderedDict[tuple[str, str], tuple[float, float]] = OrderedDict()
        self._lock = threading.Lock()

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()

    def check(self, *, key: str, bucket: str, limit: Limit, now: float | None = None) -> Decision:
        """Spend one token, or refuse. Never raises."""
        now = time.monotonic() if now is None else now
        slot = (bucket, key)

        with self._lock:
            tokens, last_seen = self._buckets.get(slot, (float(limit.burst), now))
            # Refill for the time since this caller was last seen, capped at the
            # burst so a caller who was away for a week does not come back with
            # a week's worth of requests in hand.
            tokens = min(float(limit.burst), tokens + max(0.0, now - last_seen) * limit.refill_per_second)

            if tokens < 1.0:
                self._buckets[slot] = (tokens, now)
                self._buckets.move_to_end(slot)
                return Decision(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    retry_after=limit.retry_after(tokens),
                    bucket=bucket,
                )

            tokens -= 1.0
            self._buckets[slot] = (tokens, now)
            self._buckets.move_to_end(slot)
            while len(self._buckets) > self.maxsize:
                self._buckets.popitem(last=False)

            return Decision(allowed=True, limit=limit, remaining=int(tokens), bucket=bucket)

    def __len__(self) -> int:
        with self._lock:
            return len(self._buckets)


def client_ip(headers, client_host: str | None, *, trust_forwarded: bool) -> str:
    """The caller's address, as far as it can be known.

    Behind Render, Vercel or any other proxy the socket's peer is the proxy, so
    without `X-Forwarded-For` every request in the world shares one bucket. With
    it, the header is written by the client and can say anything - so it is
    honoured only when `RATE_LIMIT_TRUST_FORWARDED_FOR` says this deployment is
    actually behind a proxy that overwrites it. Both failure modes are real;
    which one applies is a property of the deployment and not something that can
    be guessed from inside a request.
    """
    if trust_forwarded:
        forwarded = headers.get("x-forwarded-for") or ""
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:64]
    return (client_host or "unknown")[:64]


def caller_key(headers, ip: str) -> str:
    """Who this request is counted against.

    The bearer token when there is one, hashed - the buckets are keyed by it and
    keys end up in memory and in nothing else, but a session token is a
    credential and a credential does not belong in a dictionary key that some
    future logging change might print. The address otherwise.
    """
    bearer = headers.get("authorization") or headers.get("x-demo-session") or ""
    if bearer.lower().startswith("bearer "):
        bearer = bearer[7:]
    bearer = bearer.strip()
    if bearer:
        return "t:" + blake2b(bearer.encode("utf-8", "ignore"), digest_size=12).hexdigest()
    return "ip:" + ip
