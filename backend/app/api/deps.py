"""How a request says which parent it is.

Two headers are read, in this order:

  Authorization: Bearer <jwt>   - the standard shape, and what both clients send
  X-Demo-Session: <token>       - the prototype's own header, kept for builds
                                  that are already installed

Both carry the same string. The second is a leftover from when this was a
prototype and is deprecated: the web app and the mobile source both send
`Authorization` now. It stays because the mobile app is shipped rather than
deployed - a build on somebody's phone cannot be updated in step with the
server - and dropping it would sign those installs out. It can go once the
older builds have aged out.

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
    # `x_demo_session` is the deprecated header above; see the module docstring.
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
