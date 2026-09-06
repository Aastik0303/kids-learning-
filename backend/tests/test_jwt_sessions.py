"""A parent's bearer is a signed token, and the row behind it still rules.

Two things are being held here at once. The signature makes a forged, tampered
or expired token refusable without a database query. The `auth_sessions` row
named by the `jti` claim is what makes a real token revocable - because a
parent tapping "sign out", or resetting a password because somebody else may
know it, has to actually end the session.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services import jwt_service


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def register(client, email="jwt-parent@example.com"):
    response = client.post(
        "/auth/register",
        json={"email": email, "name": "Parent", "password": "a-long-enough-password"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_registration_returns_a_signed_bearer_token(client):
    body = register(client)

    # The old field and the new one carry the same string, so a client that has
    # not been updated keeps working.
    assert body["session_token"] == body["access_token"]
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == int(jwt_service.ttl().total_seconds())

    claims = jwt_service.decode(body["access_token"])
    assert claims is not None
    assert claims["sub"] == body["user"]["id"]
    assert claims["email"] == "jwt-parent@example.com"
    assert claims["iss"] == get_settings().jwt_issuer
    # The session row it stands for. This is what a sign-out deletes.
    assert claims["jti"]

    # Nothing secret rides in a payload anybody holding the token can read.
    assert "password" not in claims and "password_hash" not in claims


def test_login_returns_a_token_the_api_accepts_both_ways(client):
    register(client)
    token = client.post(
        "/auth/login",
        json={"email": "jwt-parent@example.com", "password": "a-long-enough-password"},
    ).json()["access_token"]

    legacy = client.get("/auth/session", headers={"X-Demo-Session": token})
    bearer = client.get("/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert legacy.json()["user"]["email"] == "jwt-parent@example.com"
    assert bearer.json()["user"]["email"] == "jwt-parent@example.com"

    assert client.get("/children", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_a_request_with_no_token_is_401_and_not_422(client):
    """Not signed in is something the client can act on; a malformed request is not."""
    assert client.get("/children").status_code == 401


def test_a_tampered_token_is_refused(client):
    token = register(client)["access_token"]
    settings = get_settings()
    claims = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )

    # Re-signed with a key this server does not hold.
    forged = jwt.encode(claims, "a-key-the-server-does-not-have", algorithm="HS256")
    assert jwt_service.decode(forged) is None
    assert client.get("/auth/session", headers={"Authorization": f"Bearer {forged}"}).json()["user"] is None

    # `alg: none` - the classic way a JWT verifier is talked into skipping the
    # signature. The algorithm is pinned, so it is not.
    unsigned = jwt.encode(claims, key="", algorithm="none")
    assert jwt_service.decode(unsigned) is None


def test_an_expired_token_is_refused(client):
    body = register(client)
    settings = get_settings()
    stale = datetime.now(timezone.utc) - timedelta(days=1)
    expired = jwt.encode(
        {
            "sub": body["user"]["id"],
            "email": body["user"]["email"],
            "jti": jwt_service.decode(body["access_token"])["jti"],
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": stale - timedelta(days=30),
            "exp": stale,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert jwt_service.decode(expired) is None
    assert client.get("/auth/session", headers={"Authorization": f"Bearer {expired}"}).json()["user"] is None


def test_signing_out_ends_a_perfectly_valid_token(client):
    """The signature is still good afterwards. The session is not.

    This is the whole reason the `jti` is checked against `auth_sessions` on
    every request rather than the token being trusted on its signature alone.
    """
    token = register(client)["access_token"]
    assert client.post("/auth/logout", json={"session_token": token}).status_code == 200

    assert jwt_service.decode(token) is not None
    assert client.get("/auth/session", headers={"Authorization": f"Bearer {token}"}).json()["user"] is None
    assert client.get("/children", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_a_password_reset_ends_every_signed_token(client):
    token = register(client)["access_token"]
    reset = client.post(
        "/auth/password/forgot", json={"email": "jwt-parent@example.com"}
    ).json()["reset_token"]
    assert client.post(
        "/auth/password/reset", json={"token": reset, "password": "a-brand-new-password"}
    ).status_code == 200

    assert client.get("/auth/session", headers={"Authorization": f"Bearer {token}"}).json()["user"] is None


def test_an_opaque_token_from_before_this_change_still_works(client):
    """A session row's own key, which is what clients held until now.

    Those tokens are live in people's browsers and must go on working until
    they expire, so a bearer that is not a valid JWT is looked up as a row key.
    """
    from app.db.repositories import learners
    from app.db.session import session_scope

    register(client)
    with session_scope() as session:
        parent = learners.parent_by_email(session, "jwt-parent@example.com")
        legacy_token = learners.open_session(session, parent).token

    assert jwt_service.session_token_of(legacy_token) == legacy_token
    assert client.get(
        "/auth/session", headers={"X-Demo-Session": legacy_token}
    ).json()["user"]["email"] == "jwt-parent@example.com"


def test_production_refuses_to_sign_with_no_secret(monkeypatch):
    """An unset key in production closes sign-in rather than opening it.

    A default signing key is the same as no signature: anybody who can read the
    source can mint a token for any parent.
    """
    from fastapi import HTTPException

    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(HTTPException) as raised:
            jwt_service.issue(session_token="x", parent_id="y", email="z@example.com")
        assert raised.value.status_code == 503
    finally:
        get_settings.cache_clear()
