"""How a request says which parent it is.

Two headers are read, in this order:

  Authorization: Bearer <jwt>   - the standard shape, and what new clients use
  X-Demo-Session: <token>       - what the web and mobile clients send today

Both carry the same string. The second is kept because renaming the header
would sign every installed client out at once, and because the mobile app is
shipped rather than deployed - it cannot be updated in step with the server.
Whatever arrives is verified in `jwt_service` and looked up in `auth_sessions`
before it means anything, so neither header is trusted for being present.
"""

from fastapi import Header

from app.services.errors import app_error


def _from_authorization(value: str | None) -> str | None:
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def optional_token(
    authorization: str | None = Header(default=None),
    x_demo_session: str | None = Header(default=None),
) -> str | None:
    """The bearer, or `None`. For endpoints a signed-out visitor may call."""
    return _from_authorization(authorization) or (x_demo_session or None)


def required_token(
    authorization: str | None = Header(default=None),
    x_demo_session: str | None = Header(default=None),
) -> str:
    """The bearer, or a 401.

    A missing token is 401 and not FastAPI's 422: "you are not signed in" is
    what happened, and the client's answer to it is to sign in rather than to
    fix its request.
    """
    token = optional_token(authorization, x_demo_session)
    if not token:
        raise app_error("MISSING_SESSION", "Please log in again.", 401)
    return token
