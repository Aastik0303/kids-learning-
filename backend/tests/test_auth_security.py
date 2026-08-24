"""What stops someone getting into a parent's account.

The password hash was already expensive. That makes each guess slow; it does not
make guessing pointless, and an endpoint that answers an unlimited number of
guesses is a password oracle however slow it is. These tests pin the three
things that close that: a failure counter with a lockout, a reset flow whose
tokens are single-use and expiring, and answers that never reveal which email
addresses are registered.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.db.models import AuthSession, AuthThrottle, PasswordReset
from app.db.repositories import security
from app.db.session import session_scope
from app.main import app
from app.services import auth_service


EMAIL = "parent@example.com"
PASSWORD = "demo1234"


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def registered(client: TestClient):
    response = client.post("/auth/register", json={"name": "Parent", "email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    return response.json()["session_token"]


def wrong_login(client: TestClient, password: str = "not-the-password"):
    return client.post("/auth/login", json={"email": EMAIL, "password": password})


# --------------------------------------------------------------------------
# Throttling and lockout
# --------------------------------------------------------------------------


def test_a_wrong_password_is_counted(client: TestClient, registered):
    wrong_login(client)
    wrong_login(client)

    with session_scope() as session:
        row = session.get(AuthThrottle, f"login:{EMAIL}")
        assert row.failures == 2
        assert row.locked_until is None


def test_the_account_locks_after_the_limit(client: TestClient, registered):
    for _ in range(security.FAILURE_LIMIT):
        assert wrong_login(client).status_code == 401

    locked = wrong_login(client)
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"

    # The right password is refused too - otherwise the lockout would be a way
    # to find out when a guess was correct.
    still_locked = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert still_locked.status_code == 429


def test_a_successful_sign_in_forgets_the_failures(client: TestClient, registered):
    for _ in range(security.FAILURE_LIMIT - 1):
        wrong_login(client)

    assert client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 200
    with session_scope() as session:
        assert session.get(AuthThrottle, f"login:{EMAIL}") is None

    # And the counter really is back at zero, not one below the limit.
    assert wrong_login(client).status_code == 401


def test_an_old_window_starts_again_rather_than_accumulating(client: TestClient, registered):
    """Eight failures spread over a week is a forgetful parent, not an attack."""
    now = auth_service._now()
    key = f"login:{EMAIL}"
    with session_scope() as session:
        for _ in range(security.FAILURE_LIMIT - 1):
            security.record_failure(session, key=key, now=now - timedelta(hours=2))

        row = security.record_failure(session, key=key, now=now)
        assert row.failures == 1
        assert row.locked_until is None


def test_the_lock_expires(client: TestClient, registered):
    now = auth_service._now()
    key = f"login:{EMAIL}"
    with session_scope() as session:
        for _ in range(security.FAILURE_LIMIT):
            security.record_failure(session, key=key, now=now)
        assert security.locked_until(session, key=key, now=now) is not None
        assert security.locked_until(session, key=key, now=now + security.LOCKOUT + timedelta(minutes=1)) is None


def test_a_locked_account_does_not_say_so_to_the_reset_endpoint(client: TestClient, registered):
    for _ in range(security.FAILURE_LIMIT):
        wrong_login(client)

    body = client.post("/auth/password/forgot", json={"email": EMAIL}).json()

    assert body["ok"] is True
    assert body["message"]


# --------------------------------------------------------------------------
# Password reset
# --------------------------------------------------------------------------


def test_a_reset_sets_a_new_password_and_signs_every_device_out(client: TestClient, registered):
    token = client.post("/auth/password/forgot", json={"email": EMAIL}).json()["reset_token"]
    assert token

    reset = client.post("/auth/password/reset", json={"token": token, "password": "brand-new-pass"})
    assert reset.status_code == 200

    # The old session is gone, the old password no longer works, the new one does.
    assert client.get("/auth/session", headers={"X-Demo-Session": registered}).json()["user"] is None
    assert client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 401
    assert client.post("/auth/login", json={"email": EMAIL, "password": "brand-new-pass"}).status_code == 200


def test_a_reset_token_is_single_use(client: TestClient, registered):
    token = client.post("/auth/password/forgot", json={"email": EMAIL}).json()["reset_token"]
    client.post("/auth/password/reset", json={"token": token, "password": "brand-new-pass"})

    again = client.post("/auth/password/reset", json={"token": token, "password": "another-pass"})

    assert again.status_code == 400
    assert again.json()["error"]["code"] == "INVALID_RESET"


def test_asking_again_invalidates_the_first_link(client: TestClient, registered):
    """A leaked older email must not stay usable."""
    first = client.post("/auth/password/forgot", json={"email": EMAIL}).json()["reset_token"]
    second = client.post("/auth/password/forgot", json={"email": EMAIL}).json()["reset_token"]
    assert first != second

    assert client.post("/auth/password/reset", json={"token": first, "password": "aaaaaaaa"}).status_code == 400
    assert client.post("/auth/password/reset", json={"token": second, "password": "bbbbbbbb"}).status_code == 200


def test_an_expired_token_is_refused(client: TestClient, registered):
    now = auth_service._now()
    token = client.post("/auth/password/forgot", json={"email": EMAIL}).json()["reset_token"]

    with session_scope() as session:
        assert security.consume_reset(session, token=token, now=now + security.RESET_TTL + timedelta(minutes=1)) is None


def test_only_the_hash_of_a_token_is_stored(client: TestClient, registered):
    """A database dump must not be a set of live reset links."""
    token = client.post("/auth/password/forgot", json={"email": EMAIL}).json()["reset_token"]

    with session_scope() as session:
        row = session.scalar(session.query(PasswordReset).statement)
        assert row.token_hash != token
        assert row.token_hash == security.token_hash(token)


def test_an_unknown_address_gets_the_same_answer(client: TestClient, registered):
    """Otherwise this endpoint tells you which parents use the app."""
    known = client.post("/auth/password/forgot", json={"email": EMAIL}).json()
    unknown = client.post("/auth/password/forgot", json={"email": "nobody@example.com"}).json()

    assert known["ok"] == unknown["ok"]
    assert known["message"] == unknown["message"]
    assert unknown["reset_token"] is None


def test_production_never_returns_the_token(client: TestClient, registered, monkeypatch):
    """The token comes back only because there is no mailer yet, and that
    exception has to stop at the production boundary."""

    class _Production:
        env = "production"
        password_hash_rounds = 1000

    monkeypatch.setattr(auth_service, "get_settings", lambda: _Production())

    body = client.post("/auth/password/forgot", json={"email": EMAIL}).json()

    assert body["ok"] is True
    assert body["reset_token"] is None


def test_a_new_account_needs_a_real_password(client: TestClient):
    short = client.post("/auth/register", json={"name": "P", "email": "short@example.com", "password": "1234"})

    assert short.status_code == 422


def test_sessions_survive_a_reset_for_other_parents(client: TestClient, registered):
    """Revoking sessions must not reach past the account being reset."""
    other = client.post(
        "/auth/register", json={"name": "Other", "email": "other@example.com", "password": PASSWORD}
    ).json()["session_token"]

    token = client.post("/auth/password/forgot", json={"email": EMAIL}).json()["reset_token"]
    client.post("/auth/password/reset", json={"token": token, "password": "brand-new-pass"})

    assert client.get("/auth/session", headers={"X-Demo-Session": other}).json()["user"]["email"] == "other@example.com"
    with session_scope() as session:
        assert session.query(AuthSession).count() == 1
