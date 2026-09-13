"""Google Sign-In: verifying the ID token the browser hands back.

What arrives from the client is a Google **ID token** - a JWT signed by Google
with a key only Google holds. It is verified here, on the server, and never
trusted for arriving: a client could post any string at this endpoint, so the
only thing that makes it an identity is the signature and the claims checked
below.

Four checks, and each of them is load-bearing:

* **the signature**, against Google's published keys. Google rotates them, so
  the key set is fetched over HTTPS by key id and cached rather than pinned.
* **the audience**, against `GOOGLE_CLIENT_ID`. This is the one that matters
  most. A token signed by Google is not by itself a statement about *this*
  app - it says "this person signed into the app whose client id is in `aud`".
  Accepting any Google-signed token would let anybody who can get a user to
  sign into their own Google app replay that token here and be that user.
  An unset client id means there is nothing to pin, so sign-in is refused
  rather than run without the check.
* **the issuer**, which Google spells two ways and has done for years.
* **`email_verified`**, because an unverified address on a Google account is
  not proof of anything, and this app matches an existing parent account by
  email.

Nothing here decides whether the parent is allowed in; it only says who Google
says they are. The account is found or created in `auth_service`, and the
session that follows is the app's ordinary `auth_sessions` row and JWT - a
Google token is never itself a bearer for this API.
"""

import logging
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient

from app.config import get_settings
from app.services.errors import app_error


logger = logging.getLogger(__name__)

# Google has issued both spellings for years, and a verifier that accepts only
# one of them rejects real tokens.
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

# One client per process. It caches the key set and only goes back to Google
# when a token names a key id it has not seen - which is what happens on a
# rotation, a few times a year, rather than on every sign-in.
_jwks_client: PyJWKClient | None = None
_jwks_url: str = ""


@dataclass(frozen=True)
class GoogleIdentity:
    """Who Google says this is. Never more than the account needs."""

    # Google's stable id for the account. An email address can be changed;
    # this cannot, which is why it is what a linked account is remembered by.
    subject: str
    email: str
    name: str


def _client() -> PyJWKClient:
    global _jwks_client, _jwks_url
    url = get_settings().google_jwks_url
    if _jwks_client is None or _jwks_url != url:
        _jwks_client = PyJWKClient(url, cache_keys=True)
        _jwks_url = url
    return _jwks_client


def _refused() -> Exception:
    """One message for every way a token can fail.

    Which check it failed is useful to us and to nobody else, so it is logged
    and not answered.
    """
    return app_error(
        "INVALID_GOOGLE_TOKEN",
        "We could not confirm that Google sign-in. Please try again.",
        401,
    )


def verify(credential: str) -> GoogleIdentity:
    """The identity inside a Google ID token, or a 401/503.

    503 when the feature is not configured, because that is this server's
    problem rather than the parent's; 401 for anything the token itself failed.
    """
    settings = get_settings()
    if not settings.google_sign_in_enabled:
        raise app_error(
            "GOOGLE_SIGN_IN_UNAVAILABLE",
            "Google sign-in is not available right now. Please use your email and password.",
            503,
        )
    if not credential or not credential.strip():
        raise _refused()

    try:
        key = _client().get_signing_key_from_jwt(credential).key
        claims = jwt.decode(
            credential,
            key,
            # Pinned. Google signs ID tokens with RS256, and letting the token
            # name its own algorithm is how a verifier is talked into `none`.
            algorithms=["RS256"],
            audience=settings.google_client_id.strip(),
            issuer=list(GOOGLE_ISSUERS),
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except Exception as error:  # noqa: BLE001 - a network failure and a forged
        # token both end here, and both are "we could not confirm that".
        logger.warning("Google ID token refused: %s", error)
        raise _refused() from error

    email = str(claims.get("email") or "").strip().lower()
    # `email_verified` is what separates "Google knows this address is theirs"
    # from "somebody typed it in". This app matches an existing parent account
    # by email, so an unverified one would be a way into somebody else's.
    if not email or claims.get("email_verified") is not True:
        logger.warning("Google ID token had no verified email address")
        raise _refused()

    subject = str(claims.get("sub") or "").strip()
    if not subject:
        raise _refused()

    # Google does not promise a name, and a parent with none should still be
    # able to sign in. The local part of the address is a better greeting than
    # an empty header.
    name = str(claims.get("name") or "").strip() or email.split("@")[0]
    return GoogleIdentity(subject=subject, email=email, name=name)
