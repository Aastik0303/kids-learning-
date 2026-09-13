"""In-process caching, and the rules about what may go in it.

Most of what this API answers is the same thing over and over: the curriculum
manifest, the questions a person authored for a level, the three games built out
of them, a topic's title. None of it changes while the server is running - it is
read from disk at boot - and re-deriving it inside a child's turn is latency
paid for nothing.

**What may be cached here, and what may not.** This is the important part, and
it is not a performance question.

* **Authored content may be cached.** The manifest, the syllabus, teaching
  notes, a level's games. These are files, they change on deploy, and every
  cache built from them is registered below so one call drops all of them.
* **A child's truth may not.** Attempts, mastery, stars, unlocked topics,
  completed levels, today's plan cursor. Those are written inside the request
  that earned them and read back by the next one, and a cache in front of them
  is a class that celebrates a star twice or refuses a level the child has just
  finished. `child_store`'s identity map is as far as that goes, and it is an
  identity map rather than a cache: it holds the *same object* the writers
  mutate, so there is nothing to go stale.
* **A session may not.** Whether an `auth_sessions` row is still open is asked
  on every request on purpose - a cached "yes" is a sign-out that did not sign
  anybody out, and a password reset that left the other device signed in.

Two workers hold two copies of everything here, which is fine for content that
only changes on deploy and is exactly why nothing else belongs in it.
"""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


# A value that is legitimately `None` must not read as a miss, so misses are
# reported by identity against this rather than by `is None`.
_MISS = object()


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expiries: int = 0

    @property
    def hit_rate(self) -> float:
        asked = self.hits + self.misses
        return round(self.hits / asked, 4) if asked else 0.0

    def as_dict(self, *, size: int) -> dict:
        return {
            "size": size,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expiries": self.expiries,
            "hit_rate": self.hit_rate,
        }


class TTLCache:
    """A bounded cache with an optional lifetime, safe across threads.

    Three things it does that a bare dict does not:

    * **it is bounded.** An unbounded dict keyed by anything a request can
      influence - a child id, a topic id from a URL - is a slow memory leak, and
      on a small instance that ends as an out-of-memory kill rather than as a
      slow endpoint. Least-recently-used is evicted at `maxsize`.
    * **it can expire.** `ttl_seconds=None` means "until the process restarts or
      somebody clears it", which is right for a file read at boot. A number is
      right for anything derived from a row.
    * **it computes a missing value once.** Without that, the first request
      after a restart - or after a clear - is answered by every worker thread at
      the same time, each doing the same expensive read. A per-key lock is taken
      for the computation while the cache itself stays open to other keys.
    """

    def __init__(self, name: str, *, maxsize: int = 512, ttl_seconds: float | None = None):
        self.name = name
        self.maxsize = max(1, maxsize)
        self.ttl_seconds = ttl_seconds
        self.stats = CacheStats()
        self._entries: OrderedDict[Any, tuple[Any, float | None]] = OrderedDict()
        self._lock = threading.Lock()
        # One lock per key being computed, so a slow miss on one key does not
        # hold up a hit on another.
        self._computing: dict[Any, threading.Lock] = {}

    # -- reading -----------------------------------------------------------

    def get(self, key: Any, default: Any = None) -> Any:
        found = self._peek(key)
        if found is _MISS:
            self.stats.misses += 1
            return default
        self.stats.hits += 1
        return found

    def _peek(self, key: Any) -> Any:
        """The live value, or `_MISS`. Does not count a hit or a miss."""
        with self._lock:
            entry = self._entries.get(key, _MISS)
            if entry is _MISS:
                return _MISS
            value, expires_at = entry
            if expires_at is not None and expires_at <= time.monotonic():
                del self._entries[key]
                self.stats.expiries += 1
                return _MISS
            self._entries.move_to_end(key)
            return value

    def get_or_compute(self, key: Any, factory: Callable[[], Any]) -> Any:
        """The cached value, computing it exactly once if it is not there.

        An exception from `factory` is **not** cached. A failed read of a file
        or a row is a moment, and remembering it would turn one bad second into
        a bad hour.
        """
        found = self._peek(key)
        if found is not _MISS:
            self.stats.hits += 1
            return found

        with self._lock:
            key_lock = self._computing.setdefault(key, threading.Lock())

        with key_lock:
            # Whoever else was waiting on this lock may have filled it in.
            found = self._peek(key)
            if found is not _MISS:
                self.stats.hits += 1
                return found

            self.stats.misses += 1
            value = factory()
            self.set(key, value)

        with self._lock:
            # Dropped rather than kept: one lock object per key ever computed is
            # the same leak the cache itself is bounded against.
            self._computing.pop(key, None)
        return value

    # -- writing -----------------------------------------------------------

    def set(self, key: Any, value: Any) -> None:
        expires_at = None if self.ttl_seconds is None else time.monotonic() + self.ttl_seconds
        with self._lock:
            self._entries[key] = (value, expires_at)
            self._entries.move_to_end(key)
            while len(self._entries) > self.maxsize:
                self._entries.popitem(last=False)
                self.stats.evictions += 1

    def invalidate(self, key: Any) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._computing.clear()

    # -- looking at it -----------------------------------------------------

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def as_dict(self) -> dict:
        return self.stats.as_dict(size=len(self))


# --------------------------------------------------------------------------
# The registry
# --------------------------------------------------------------------------
#
# Every cache derived from authored content registers how to clear itself, so
# `reload_curriculum()` empties all of them together. Without this the test
# suite - which swaps the manifest on disk and re-reads it - would go on being
# answered from a cache built out of the previous one, and the failure would
# show up as an unrelated assertion in a much later test.


@dataclass
class _Registry:
    clearables: dict[str, Callable[[], None]] = field(default_factory=dict)
    caches: dict[str, TTLCache] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


_registry = _Registry()


def register(name: str, clear: Callable[[], None], *, cache: TTLCache | None = None) -> None:
    """Say how to empty one cache built out of authored content.

    `clear` is anything that empties it - a `TTLCache.clear`, or an
    `lru_cache`'s own `cache_clear`, which is why this takes a callable rather
    than only a cache object.
    """
    with _registry.lock:
        _registry.clearables[name] = clear
        if cache is not None:
            _registry.caches[name] = cache


def content_cache(name: str, *, maxsize: int = 512, ttl_seconds: float | None = None) -> TTLCache:
    """A registered cache for content that only changes on deploy."""
    cache = TTLCache(name, maxsize=maxsize, ttl_seconds=ttl_seconds)
    register(name, cache.clear, cache=cache)
    return cache


def clear_content_caches() -> None:
    """Empty every registered cache. Called when the curriculum is re-read."""
    with _registry.lock:
        clearables = list(_registry.clearables.values())
    for clear in clearables:
        clear()


def stats() -> dict[str, dict]:
    """Hit rates, for `/health`. Counts only - nothing about any child."""
    with _registry.lock:
        caches = dict(_registry.caches)
    return {name: cache.as_dict() for name, cache in sorted(caches.items())}


@contextmanager
def suspended() -> Iterator[None]:
    """Empty every content cache, and empty it again on the way out.

    For a test that rewrites the curriculum on disk: whatever it cached while
    the manifest was swapped must not outlive it.
    """
    clear_content_caches()
    try:
        yield
    finally:
        clear_content_caches()
