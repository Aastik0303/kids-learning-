"""The emailed sign-in code, and the things it must not become.

The password proves what somebody knows; the code proves they still hold the
address the account is on. Most of what is pinned here is therefore negative -
the ways a second factor stops being one:

* a correct password must not return a session, or the code is decoration;
* the code must not appear in the response, except on a development machine
  with no mailer, and never in production;
* the challenge must die after a few guesses, or six digits is a million tries;
* a fresh challenge must not reset the account throttle, or whoever has the
  password can grind codes for ever;
* a code must work once;
* Google sign-in must skip it entirely - Google already proved the address.

No real SMTP is reached: `mailer.send` is replaced with an outbox, which is
also how the test reads the code the parent would have been sent.
"""

import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.models import SignInChallenge
from app.db.session import session_scope
from app.main import app
from app.services import mailer

EMAIL = "parent@example.com"
PASSWORD = "a-real-password"


@pytest.fixture()
def outbox(monkeypatch):
    """Every message the app tried to send, instead of a mail server."""
    sent: list[mailer.Message] = []
    monkeypatch.setattr(mailer, "send", lambda message: sent.append(message))
    # `configured` is what the callers ask before promising anything.
    monkeypatch.setattr(mailer, "configured", lambda settings=None: True)
    return sent


@pytest.fixture()
def otp_on(monkeypatch):
    monkeypatch.setenv("AUTH_OTP_ENABLED", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def registered(client: TestClient):
    response = client.post(
        "/auth/register", json={"name": "Parent", "email": EMAIL, "password": PASSWORD}
    )
    assert response.status_code == 200
    return response.json()


def code_from(outbox) -> str:
    assert outbox, "nothing was sent"
    found = re.search(r"\b(\d{6})\b", outbox[-1].text)
    assert found, outbox[-1].text
    return found.group(1)


def sign_in(client: TestClient, password: str = PASSWORD):
    return client.post("/auth/login", json={"email": EMAIL, "password": password})


# --------------------------------------------------------------------------
# The flow
# --------------------------------------------------------------------------


def test_a_right_password_is_not_a_session(client, registered, otp_on, outbox):
    """The whole point. If this returns a token, the code is decoration."""
    body = sign_in(client).json()

    assert body["otp_required"] is True
    assert "session_token" not in body
    assert "access_token" not in body
    # Nothing in the challenge is a bearer for anything.
    assert client.get(
        "/auth/session", headers={"Authorization": f"Bearer {body['challenge_id']}"}
    ).json()["user"] is None


def test_the_code_goes_to_the_inbox_and_not_to_the_caller(client, registered, otp_on, outbox):
    body = sign_in(client).json()

    assert body["dev_code"] is None
    assert len(outbox) == 1
    assert outbox[0].to == EMAIL
    # It is in the mail, and the mail says what to do if it was not you.
    assert re.search(r"\b\d{6}\b", outbox[0].text)
    assert "not signing in" in outbox[0].text


def test_the_code_finishes_the_sign_in(client, registered, otp_on, outbox):
    challenge = sign_in(client).json()
    verified = client.post(
        "/auth/otp/verify",
        json={"challenge_id": challenge["challenge_id"], "code": code_from(outbox)},
    )

    assert verified.status_code == 200
    token = verified.json()["session_token"]
    assert client.get("/auth/session", headers={"Authorization": f"Bearer {token}"}).json()["user"][
        "email"
    ] == EMAIL


def test_a_pasted_code_with_spaces_still_works(client, registered, otp_on, outbox):
    """Mail clients and phone keyboards put spaces through a six-digit number."""
    challenge = sign_in(client).json()
    code = code_from(outbox)
    spaced = f" {code[:3]}-{code[3:]} "

    verified = client.post(
        "/auth/otp/verify", json={"challenge_id": challenge["challenge_id"], "code": spaced}
    )
    assert verified.status_code == 200


def test_the_screen_says_where_the_code_went_without_saying_the_address(
    client, registered, otp_on, outbox
):
    hint = sign_in(client).json()["email_hint"]

    assert hint != EMAIL
    assert hint.endswith("@example.com")
    assert "•" in hint


# --------------------------------------------------------------------------
# What is refused
# --------------------------------------------------------------------------


def test_a_wrong_code_is_refused(client, registered, otp_on, outbox):
    challenge = sign_in(client).json()
    refused = client.post(
        "/auth/otp/verify", json={"challenge_id": challenge["challenge_id"], "code": "000000"}
    )

    assert refused.status_code == 401
    assert refused.json()["error"]["code"] == "INVALID_CODE"


def test_a_code_works_once(client, registered, otp_on, outbox):
    challenge = sign_in(client).json()
    code = code_from(outbox)
    payload = {"challenge_id": challenge["challenge_id"], "code": code}

    assert client.post("/auth/otp/verify", json=payload).status_code == 200
    assert client.post("/auth/otp/verify", json=payload).status_code == 401


def test_the_challenge_dies_after_a_few_guesses(client, registered, otp_on, outbox, monkeypatch):
    """Six digits is one of a million only while the guesses are few."""
    monkeypatch.setenv("AUTH_OTP_MAX_ATTEMPTS", "3")
    get_settings.cache_clear()

    challenge = sign_in(client).json()
    real = code_from(outbox)
    for _ in range(3):
        client.post(
            "/auth/otp/verify", json={"challenge_id": challenge["challenge_id"], "code": "111111"}
        )

    # Even the right code is no good now: the challenge is spent.
    refused = client.post(
        "/auth/otp/verify", json={"challenge_id": challenge["challenge_id"], "code": real}
    )
    assert refused.status_code == 401
    get_settings.cache_clear()


def test_an_unknown_challenge_looks_like_an_expired_one(client, registered, otp_on, outbox):
    """Telling them apart would say which handles are real."""
    refused = client.post(
        "/auth/otp/verify", json={"challenge_id": "not-a-real-challenge-handle", "code": "123456"}
    )
    assert refused.status_code == 401
    assert refused.json()["error"]["code"] == "INVALID_CODE"


def test_an_expired_code_is_refused(client, registered, otp_on, outbox):
    challenge = sign_in(client).json()
    code = code_from(outbox)

    with session_scope() as session:
        row = session.query(SignInChallenge).one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    refused = client.post(
        "/auth/otp/verify", json={"challenge_id": challenge["challenge_id"], "code": code}
    )
    assert refused.status_code == 401


def test_opening_a_new_challenge_spends_the_old_one(client, registered, otp_on, outbox):
    """Two live challenges is two live codes, and the older is usually the one
    an attacker caused to be sent."""
    first = sign_in(client).json()
    first_code = code_from(outbox)
    sign_in(client)

    refused = client.post(
        "/auth/otp/verify", json={"challenge_id": first["challenge_id"], "code": first_code}
    )
    assert refused.status_code == 401


def test_a_fresh_challenge_does_not_reset_the_account_throttle(
    client, registered, otp_on, outbox, monkeypatch
):
    """Otherwise whoever holds the password grinds the code for ever: open a
    challenge, guess, open another, guess again."""
    monkeypatch.setenv("AUTH_OTP_MAX_ATTEMPTS", "2")
    get_settings.cache_clear()

    for _ in range(6):
        challenge = sign_in(client).json()
        if "challenge_id" not in challenge:
            break
        for _ in range(2):
            client.post(
                "/auth/otp/verify",
                json={"challenge_id": challenge["challenge_id"], "code": "999999"},
            )

    locked = sign_in(client)
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    get_settings.cache_clear()


def test_a_wrong_password_never_sends_mail(client, registered, otp_on, outbox):
    """A code is not a thing to send to somebody who failed the first factor."""
    refused = sign_in(client, password="not-the-password")

    assert refused.status_code == 401
    assert outbox == []


# --------------------------------------------------------------------------
# Sending it again
# --------------------------------------------------------------------------


def test_another_code_can_be_sent_and_the_old_one_stops_working(
    client, registered, otp_on, outbox, monkeypatch
):
    monkeypatch.setenv("AUTH_OTP_RESEND_COOLDOWN_SECONDS", "0")
    get_settings.cache_clear()

    challenge = sign_in(client).json()
    first_code = code_from(outbox)
    assert client.post(
        "/auth/otp/resend", json={"challenge_id": challenge["challenge_id"]}
    ).status_code == 200
    second_code = code_from(outbox)

    assert first_code != second_code
    assert client.post(
        "/auth/otp/verify", json={"challenge_id": challenge["challenge_id"], "code": first_code}
    ).status_code == 401
    assert client.post(
        "/auth/otp/verify", json={"challenge_id": challenge["challenge_id"], "code": second_code}
    ).status_code == 200
    get_settings.cache_clear()


def test_send_it_again_is_not_a_way_to_mail_a_stranger(client, registered, otp_on, outbox):
    """The cooldown is the point: without it the button sends as fast as it can
    be pressed, at an address chosen by whoever has the password."""
    challenge = sign_in(client).json()
    refused = client.post("/auth/otp/resend", json={"challenge_id": challenge["challenge_id"]})

    assert refused.status_code == 429
    assert refused.json()["error"]["code"] == "OTP_RESEND_TOO_SOON"
    assert len(outbox) == 1


def test_there_is_a_ceiling_on_how_many_codes_one_sign_in_sends(
    client, registered, otp_on, outbox, monkeypatch
):
    monkeypatch.setenv("AUTH_OTP_RESEND_COOLDOWN_SECONDS", "0")
    monkeypatch.setenv("AUTH_OTP_MAX_SENDS", "2")
    get_settings.cache_clear()

    challenge = sign_in(client).json()
    assert client.post(
        "/auth/otp/resend", json={"challenge_id": challenge["challenge_id"]}
    ).status_code == 200
    refused = client.post("/auth/otp/resend", json={"challenge_id": challenge["challenge_id"]})

    assert refused.status_code == 429
    assert refused.json()["error"]["code"] == "OTP_TOO_MANY_SENDS"
    get_settings.cache_clear()


# --------------------------------------------------------------------------
# The boundaries
# --------------------------------------------------------------------------


def test_google_sign_in_never_asks_for_a_code(client, otp_on, outbox, monkeypatch):
    """Google has already proved the address, with its own second factor. A
    code on top is friction that buys nothing."""
    from app.services import google_auth_service

    monkeypatch.setattr(
        google_auth_service,
        "verify",
        lambda credential: google_auth_service.GoogleIdentity(
            subject="google-1", email="google-parent@example.com", name="Parent"
        ),
    )

    body = client.post("/auth/google", json={"credential": "pretend-token"}).json()
    assert body["session_token"]
    assert outbox == []


def test_production_never_puts_the_code_in_the_response(client, registered, otp_on, monkeypatch):
    """The development door - a code in the body when there is no mailer - is
    the one thing that would turn this feature off completely."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SMTP_HOST", "")
    get_settings.cache_clear()
    try:
        refused = sign_in(client)
        # No mailer in production is a refusal, not a sign-in without a code.
        assert refused.status_code == 503
        assert refused.json()["error"]["code"] == "MAIL_NOT_CONFIGURED"
    finally:
        get_settings.cache_clear()


def test_without_a_mailer_in_development_the_flow_can_still_be_finished(
    client, registered, otp_on, monkeypatch
):
    monkeypatch.setenv("SMTP_HOST", "")
    get_settings.cache_clear()
    try:
        challenge = sign_in(client).json()
        assert challenge["dev_code"]
        verified = client.post(
            "/auth/otp/verify",
            json={"challenge_id": challenge["challenge_id"], "code": challenge["dev_code"]},
        )
        assert verified.status_code == 200
    finally:
        get_settings.cache_clear()


def test_the_code_is_not_stored_as_itself(client, registered, otp_on, outbox):
    """A dump of this table must not be a drawer full of sign-ins in progress."""
    challenge = sign_in(client).json()
    code = code_from(outbox)

    with session_scope() as session:
        row = session.query(SignInChallenge).one()
        assert code not in row.code_hash
        assert challenge["challenge_id"] not in row.challenge_hash
        assert len(row.code_hash) == 64


def test_turning_it_off_signs_in_with_the_password_alone(client, registered, outbox, monkeypatch):
    """One setting, so a deployment that cannot send mail is not a deployment
    nobody can sign in to."""
    monkeypatch.setenv("AUTH_OTP_ENABLED", "0")
    get_settings.cache_clear()
    try:
        body = sign_in(client).json()
        assert body["session_token"]
        assert outbox == []
    finally:
        get_settings.cache_clear()
