"""Signing in with Google.

The ID token is the whole of the security here, so these tests sign real RS256
tokens with a key pair made in the test and hand Google's public key to the
verifier. Nothing is stubbed inside `google_auth_service.verify` itself - what
is replaced is only where the public key comes from, which in production is
Google's published key set over HTTPS.

What is pinned:

* a well-formed token for this app's client id signs the parent in;
* a token minted for a *different* client id is refused, which is the check
  that stops a token from somebody else's Google app being replayed here;
* an unverified email address is refused, because the account is matched by
  email and an unverified one would be a way into somebody else's;
* an expired token, a tampered one and one signed by the wrong key are refused;
* a parent who registered with a password and then uses the Google button on
  the same address keeps the account and the child behind it;
* Google never grades, unlocks or scores anything - it only says who this is.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.models import Parent
from app.db.session import session_scope
from app.main import app
from app.services import google_auth_service


CLIENT_ID = "123456789-test.apps.googleusercontent.com"
EMAIL = "parent@example.com"


@pytest.fixture()
def google_keys(monkeypatch):
    """A key pair standing in for Google's, and the client id it signs for."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class _Key:
        key = private_key.public_key()

    class _Client:
        def get_signing_key_from_jwt(self, _token):
            return _Key()

    monkeypatch.setenv("GOOGLE_CLIENT_ID", CLIENT_ID)
    get_settings.cache_clear()
    monkeypatch.setattr(google_auth_service, "_client", lambda: _Client())
    try:
        yield private_key
    finally:
        get_settings.cache_clear()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def token(
    private_key,
    *,
    email: str = EMAIL,
    email_verified: bool = True,
    audience: str = CLIENT_ID,
    issuer: str = "https://accounts.google.com",
    subject: str = "google-subject-1",
    name: str = "A Parent",
    age: timedelta = timedelta(minutes=0),
) -> str:
    issued = datetime.now(timezone.utc) - age
    return jwt.encode(
        {
            "iss": issuer,
            "aud": audience,
            "sub": subject,
            "email": email,
            "email_verified": email_verified,
            "name": name,
            "iat": issued,
            "exp": issued + timedelta(hours=1),
        },
        private_key,
        algorithm="RS256",
    )


# --------------------------------------------------------------------------
# The happy path
# --------------------------------------------------------------------------


def test_a_new_google_account_is_created_and_signed_in(client, google_keys):
    response = client.post("/auth/google", json={"credential": token(google_keys)})
    assert response.status_code == 200
    body = response.json()

    assert body["user"]["email"] == EMAIL
    assert body["user"]["name"] == "A Parent"
    # One button for signing in and signing up, so the server is what tells the
    # client to send this parent through setting a child up.
    assert body["is_new_account"] is True
    # The session is this app's own, not Google's token handed back.
    assert body["session_token"] != token(google_keys)
    assert body["token_type"] == "Bearer"

    who = client.get("/auth/session", headers={"Authorization": f"Bearer {body['session_token']}"})
    assert who.json()["user"]["email"] == EMAIL


def test_signing_in_twice_returns_to_the_same_account(client, google_keys):
    first = client.post("/auth/google", json={"credential": token(google_keys)}).json()
    second = client.post("/auth/google", json={"credential": token(google_keys)}).json()

    assert first["user"]["id"] == second["user"]["id"]
    # The second time is not a new account, so the client sends them to the
    # child they already have rather than back through setting one up.
    assert second["is_new_account"] is False


def test_a_google_account_is_matched_by_subject_not_by_email(client, google_keys):
    """A parent who changes the address on their Google account is still them."""
    first = client.post("/auth/google", json={"credential": token(google_keys)}).json()
    moved = client.post(
        "/auth/google",
        json={"credential": token(google_keys, email="new-address@example.com")},
    ).json()

    assert moved["user"]["id"] == first["user"]["id"]
    assert moved["is_new_account"] is False


def test_a_google_account_has_no_password(client, google_keys):
    """And a blank one is not a way into it."""
    client.post("/auth/google", json={"credential": token(google_keys)})

    with session_scope() as session:
        parent = session.query(Parent).filter(Parent.email == EMAIL).one()
        assert parent.password_hash is None
        assert parent.google_subject == "google-subject-1"

    refused = client.post("/auth/login", json={"email": EMAIL, "password": ""})
    assert refused.status_code == 422  # the field's own minimum length
    refused = client.post("/auth/login", json={"email": EMAIL, "password": "anything"})
    assert refused.status_code == 401


# --------------------------------------------------------------------------
# Linking, so one parent is not two accounts
# --------------------------------------------------------------------------


def test_the_google_button_joins_an_account_registered_with_a_password(client, google_keys):
    registered = client.post(
        "/auth/register", json={"name": "Parent", "email": EMAIL, "password": "a-real-password"}
    ).json()
    child = client.post(
        "/children",
        json={
            "session_token": registered["session_token"],
            "name": "Aria",
            "birth_year": 2021,
            "birth_month": 4,
            "preferred_language": "en",
        },
    )
    assert child.status_code == 200

    google = client.post("/auth/google", json={"credential": token(google_keys)}).json()
    assert google["user"]["id"] == registered["user"]["id"]
    assert google["is_new_account"] is False

    # The same parent, so the same child - not a new empty account.
    children = client.get(
        "/children", headers={"Authorization": f"Bearer {google['session_token']}"}
    ).json()
    assert [c["name"] for c in children] == ["Aria"]

    # And the password still works: linking Google does not take it away.
    assert client.post("/auth/login", json={"email": EMAIL, "password": "a-real-password"}).status_code == 200


# --------------------------------------------------------------------------
# What is refused
# --------------------------------------------------------------------------


def test_a_token_for_another_app_is_refused(client, google_keys):
    """The audience check, and it is the important one.

    A Google-signed token says "this person signed into the app named in `aud`".
    Accepting one minted for somebody else's app would let whoever runs that app
    sign in here as any of their users.
    """
    response = client.post(
        "/auth/google",
        json={"credential": token(google_keys, audience="999-someone-else.apps.googleusercontent.com")},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_GOOGLE_TOKEN"


def test_an_unverified_email_is_refused(client, google_keys):
    response = client.post(
        "/auth/google", json={"credential": token(google_keys, email_verified=False)}
    )
    assert response.status_code == 401

    with session_scope() as session:
        assert session.query(Parent).count() == 0


def test_an_expired_token_is_refused(client, google_keys):
    response = client.post(
        "/auth/google", json={"credential": token(google_keys, age=timedelta(hours=3))}
    )
    assert response.status_code == 401


def test_a_token_from_the_wrong_issuer_is_refused(client, google_keys):
    response = client.post(
        "/auth/google", json={"credential": token(google_keys, issuer="https://evil.example.com")}
    )
    assert response.status_code == 401


def test_a_token_signed_with_another_key_is_refused(client, google_keys):
    someone_else = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    response = client.post("/auth/google", json={"credential": token(someone_else)})
    assert response.status_code == 401


def test_a_tampered_token_is_refused(client, google_keys):
    good = token(google_keys)
    header, payload, signature = good.split(".")
    response = client.post("/auth/google", json={"credential": f"{header}.{payload}x.{signature}"})
    assert response.status_code == 401


def test_google_sign_in_is_off_where_it_is_not_configured(client, monkeypatch):
    """No client id means no audience to pin, so the feature is off rather than
    running without its most important check."""
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    get_settings.cache_clear()
    try:
        config = client.get("/auth/google/config").json()
        assert config == {"enabled": False, "client_id": ""}

        refused = client.post("/auth/google", json={"credential": "anything at all"})
        assert refused.status_code == 503
        assert refused.json()["error"]["code"] == "GOOGLE_SIGN_IN_UNAVAILABLE"
    finally:
        get_settings.cache_clear()


def test_the_config_endpoint_offers_the_button_when_configured(client, google_keys):
    config = client.get("/auth/google/config").json()
    assert config == {"enabled": True, "client_id": CLIENT_ID}


# --------------------------------------------------------------------------
# The boundary that matters more than any of this
# --------------------------------------------------------------------------


def test_google_decides_nothing_about_a_child(client, google_keys):
    """Signing in with Google says who the parent is and nothing else.

    No stars, no unlocked topics, no completed levels and no certificate come
    out of an identity provider. This is the same boundary the answer key keeps:
    only the deterministic evaluator moves a child's progress.
    """
    auth = client.post("/auth/google", json={"credential": token(google_keys)}).json()
    headers = {"Authorization": f"Bearer {auth['session_token']}"}

    child = client.post(
        "/children",
        json={
            "session_token": auth["session_token"],
            "name": "Aria",
            "birth_year": 2021,
            "birth_month": 4,
            "preferred_language": "en",
        },
    ).json()

    assert child["stars"] == 0
    progress = client.get(f"/progress/{child['child_id']}", headers=headers).json()["child"]
    assert progress["stars"] == 0
    assert progress.get("certificate_eligible") in (False, None)
