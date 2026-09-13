"""Caching and rate limiting: what they speed up, and what they must not touch.

The interesting assertions here are the negative ones. A cache that makes a read
fast and a star slow to appear has not made the app faster, it has made it
wrong, and a rate limiter that refuses a child mid-lesson has done the same. So
these tests pin the boundaries as much as the behaviour:

* authored content is cached and a manifest reload empties every cache at once;
* a child's own truth - stars, progress, today's plan - is never cached;
* whether a session is still open is asked every time, so signing out signs out;
* the limiter refuses by route class, refills over time, fails open, and counts
  a signed-in caller by their token rather than by an address they may be
  sharing with a whole mobile network.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.api import middleware
from app.config import get_settings
from app.main import app
from app.services import cache, curriculum_service, plan_service
from app.services.rate_limit import Limit, RateLimiter, bucket_for, caller_key, client_ip


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def fresh_limiter():
    """Every test starts with nobody having spent anything."""
    middleware.limiter.clear()
    yield
    middleware.limiter.clear()


@pytest.fixture()
def no_limit(monkeypatch):
    """For the tests that are about something other than the limiter."""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def register(client: TestClient, email: str = "cache@example.com") -> dict:
    return client.post(
        "/auth/register", json={"name": "Parent", "email": email, "password": "a-real-password"}
    ).json()


def make_child(client: TestClient, auth: dict) -> dict:
    return client.post(
        "/children",
        json={
            "session_token": auth["session_token"],
            "name": "Aria",
            "birth_year": 2021,
            "birth_month": 4,
            "preferred_language": "en",
        },
    ).json()


# --------------------------------------------------------------------------
# The cache itself
# --------------------------------------------------------------------------


def test_a_value_is_computed_once():
    store = cache.TTLCache("test", maxsize=8)
    calls = []

    def factory():
        calls.append(1)
        return "value"

    assert store.get_or_compute("k", factory) == "value"
    assert store.get_or_compute("k", factory) == "value"
    assert len(calls) == 1
    assert store.stats.hits == 1
    assert store.stats.misses == 1


def test_none_is_a_value_and_not_a_miss():
    """A cached `None` that read as a miss would recompute for ever."""
    store = cache.TTLCache("test", maxsize=8)
    calls = []
    store.get_or_compute("k", lambda: calls.append(1))
    store.get_or_compute("k", lambda: calls.append(1))
    assert len(calls) == 1


def test_a_failed_computation_is_not_cached():
    """One bad second must not become a bad hour."""
    store = cache.TTLCache("test", maxsize=8)

    with pytest.raises(RuntimeError):
        store.get_or_compute("k", lambda: (_ for _ in ()).throw(RuntimeError("no")))

    assert store.get_or_compute("k", lambda: "second time") == "second time"


def test_the_cache_is_bounded():
    """An unbounded cache keyed by anything a request chooses is a memory leak."""
    store = cache.TTLCache("test", maxsize=3)
    for index in range(10):
        store.set(index, index)

    assert len(store) == 3
    assert store.stats.evictions == 7
    # Least recently used went first.
    assert store.get(0) is None
    assert store.get(9) == 9


def test_an_entry_expires():
    store = cache.TTLCache("test", maxsize=8, ttl_seconds=0.05)
    store.set("k", "value")
    assert store.get("k") == "value"
    time.sleep(0.08)
    assert store.get("k") is None
    assert store.stats.expiries == 1


def test_reloading_the_curriculum_empties_every_content_cache(client):
    """The one that makes the rest of the suite trustworthy.

    A test that swaps the manifest on disk must not then be answered out of a
    cache built from the manifest before it.
    """
    client.get("/curriculum")
    plan_service.topic_title("nur_english_t1")

    assert any(entry["size"] for entry in cache.stats().values())

    curriculum_service.reload_curriculum()
    assert all(entry["size"] == 0 for entry in cache.stats().values())


def test_every_content_cache_is_registered():
    """Registration is what makes the clear above complete.

    A cache added later and not registered would not be emptied by a reload, and
    that failure shows up as an unrelated assertion in a much later test.
    """
    registered = set(cache.stats()) | set(cache._registry.clearables)
    for expected in (
        "curriculum.overview",
        "plan.topic_title",
        "playground.games",
        "playground.notes",
        "playground.questions",
        "playground.examples",
        "conductor.skill_graph",
    ):
        assert expected in registered


# --------------------------------------------------------------------------
# What must never be cached
# --------------------------------------------------------------------------


def test_a_childs_progress_is_never_served_stale(client, no_limit):
    """Stars are truth. A cache in front of them is a star that appears late -
    or twice."""
    auth = register(client, "progress-cache@example.com")
    child = make_child(client, auth)
    child_id = child["child_id"]

    before = client.get(f"/progress/{child_id}").json()["child"]["stars"]
    assert before == 0

    # Move the ledger the way the class does, then read it straight back.
    from app.services import child_store

    record = child_store.get(child_id)
    record["stars"] = 7
    child_store.save(record)

    after = client.get(f"/progress/{child_id}").json()["child"]["stars"]
    assert after == 7


def test_signing_out_signs_out_immediately(client, no_limit):
    """Whether the session row is still open is asked on every request.

    Caching that answer - even for a few seconds - is a sign-out that did not
    sign anybody out, and a password reset that left the other device in.
    """
    auth = register(client, "signout-cache@example.com")
    headers = {"Authorization": f"Bearer {auth['session_token']}"}

    assert client.get("/children", headers=headers).status_code == 200
    client.post("/auth/logout", json={"session_token": auth["session_token"]})
    assert client.get("/children", headers=headers).status_code == 401


def test_todays_plan_is_read_rather_than_cached(client, no_limit):
    """The plan carries a cursor that moves as the day is taught."""
    auth = register(client, "plan-cache@example.com")
    child = make_child(client, auth)

    first = client.get(f"/plans/{child['child_id']}/today").json()
    second = client.get(f"/plans/{child['child_id']}/today").json()
    assert first["items"] == second["items"]
    # Nothing about the plan carries a cache header: it is a child's own state.
    response = client.get(f"/plans/{child['child_id']}/today")
    assert "ETag" not in response.headers


# --------------------------------------------------------------------------
# Conditional responses
# --------------------------------------------------------------------------


def test_curriculum_is_revalidated_rather_than_re_sent(client, no_limit):
    first = client.get("/curriculum")
    assert first.status_code == 200
    etag = first.headers["ETag"]
    assert "max-age" in first.headers["Cache-Control"]

    again = client.get("/curriculum", headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert not again.content


def test_a_changed_answer_gets_a_new_etag(client, no_limit):
    topics = client.get("/curriculum/classes")
    other = client.get("/curriculum")
    assert topics.headers["ETag"] != other.headers["ETag"]


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------


def test_a_path_is_sorted_into_its_route_class():
    assert bucket_for("/auth/login") == "auth"
    assert bucket_for("/speech/say") == "speech"
    assert bucket_for("/playground/teacher/turn") == "ai"
    assert bucket_for("/conductor/abc/open") == "ai"
    assert bucket_for("/curriculum") == "read"
    assert bucket_for("/plans/abc/today") == "read"


def test_a_bucket_refuses_and_then_refills():
    limiter = RateLimiter()
    limit = Limit(requests=2, per_seconds=1.0, burst=2)

    assert limiter.check(key="k", bucket="b", limit=limit, now=0.0).allowed
    assert limiter.check(key="k", bucket="b", limit=limit, now=0.0).allowed
    refused = limiter.check(key="k", bucket="b", limit=limit, now=0.0)
    assert not refused.allowed
    assert refused.retry_after >= 1

    # Half a second later one token has come back.
    assert limiter.check(key="k", bucket="b", limit=limit, now=0.5).allowed


def test_time_away_does_not_bank_requests():
    """A caller gone for a week comes back with a burst, not a week's worth."""
    limiter = RateLimiter()
    limit = Limit(requests=10, per_seconds=60.0, burst=10)

    limiter.check(key="k", bucket="b", limit=limit, now=0.0)
    for _ in range(10):
        assert limiter.check(key="k", bucket="b", limit=limit, now=100_000.0).allowed
    assert not limiter.check(key="k", bucket="b", limit=limit, now=100_000.0).allowed


def test_two_callers_do_not_share_a_bucket():
    limiter = RateLimiter()
    limit = Limit(requests=1, per_seconds=60.0, burst=1)

    assert limiter.check(key="one", bucket="b", limit=limit, now=0.0).allowed
    assert limiter.check(key="two", bucket="b", limit=limit, now=0.0).allowed
    assert not limiter.check(key="one", bucket="b", limit=limit, now=0.0).allowed


def test_a_signed_in_caller_is_counted_by_token_not_by_address():
    """Carrier-grade NAT is the reason. Thousands of unrelated families share
    one public address on an Indian mobile network, and a per-IP-only limiter
    would have them taking each other's class offline."""
    one = caller_key({"authorization": "Bearer token-one"}, "203.0.113.7")
    two = caller_key({"authorization": "Bearer token-two"}, "203.0.113.7")
    assert one != two
    # And the token itself is not the key: it is a credential.
    assert "token-one" not in one


def test_a_signed_out_caller_is_counted_by_address():
    assert caller_key({}, "203.0.113.7") == "ip:203.0.113.7"


def test_a_forwarded_address_is_believed_only_when_configured():
    headers = {"x-forwarded-for": "198.51.100.9, 10.0.0.1"}
    assert client_ip(headers, "10.0.0.1", trust_forwarded=True) == "198.51.100.9"
    assert client_ip(headers, "10.0.0.1", trust_forwarded=False) == "10.0.0.1"


def test_the_api_refuses_a_caller_who_asks_too_fast(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("RATE_LIMIT_READ_PER_MINUTE", "3")
    get_settings.cache_clear()
    try:
        codes = [client.get("/curriculum/classes").status_code for _ in range(6)]
    finally:
        get_settings.cache_clear()

    assert codes[:3] == [200, 200, 200]
    assert 429 in codes


def test_a_refusal_says_what_to_do_and_is_readable_by_a_person(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("RATE_LIMIT_READ_PER_MINUTE", "1")
    get_settings.cache_clear()
    try:
        client.get("/curriculum/classes")
        refused = client.get("/curriculum/classes")
    finally:
        get_settings.cache_clear()

    assert refused.status_code == 429
    body = refused.json()
    # The app's own error envelope, so an existing client reads it already.
    assert body["error"]["code"] == "TOO_MANY_REQUESTS"
    assert "wait" in body["error"]["message"].lower()
    assert int(refused.headers["Retry-After"]) >= 1
    assert refused.headers["X-RateLimit-Remaining"] == "0"


def test_health_is_never_rate_limited(client, monkeypatch):
    """It is what the platform polls to decide this instance is alive. Limiting
    it is how a busy server gets restarted for being busy."""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("RATE_LIMIT_READ_PER_MINUTE", "1")
    monkeypatch.setenv("RATE_LIMIT_IP_PER_MINUTE", "1")
    get_settings.cache_clear()
    try:
        codes = [client.get("/health").status_code for _ in range(10)]
    finally:
        get_settings.cache_clear()
    assert codes == [200] * 10


def test_the_limiter_can_be_switched_off(client, no_limit):
    codes = [client.get("/curriculum/classes").status_code for _ in range(30)]
    assert set(codes) == {200}


def test_a_broken_limiter_does_not_break_the_class(client, monkeypatch):
    """It fails open on purpose. A bug in here should cost a log line, never a
    child's lesson."""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    get_settings.cache_clear()

    def explode(*_args, **_kwargs):
        raise RuntimeError("the limiter is broken")

    monkeypatch.setattr(middleware.limiter, "check", explode)
    try:
        assert client.get("/curriculum/classes").status_code == 200
    finally:
        get_settings.cache_clear()


def test_the_response_carries_what_is_left(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("RATE_LIMIT_READ_PER_MINUTE", "10")
    get_settings.cache_clear()
    try:
        response = client.get("/curriculum/classes")
    finally:
        get_settings.cache_clear()

    assert response.headers["X-RateLimit-Limit"] == "10"
    assert response.headers["X-RateLimit-Bucket"] == "read"
    assert int(response.headers["X-RateLimit-Remaining"]) < 10


def test_health_reports_the_caches(client, no_limit):
    body = client.get("/health").json()
    assert "caches" in body
    assert "curriculum.overview" in body["caches"]
    assert set(body["caches"]["curriculum.overview"]) >= {"hits", "misses", "size", "hit_rate"}


def test_a_response_says_how_long_it_took(client, no_limit):
    response = client.get("/curriculum/classes")
    assert response.headers["Server-Timing"].startswith("app;dur=")
