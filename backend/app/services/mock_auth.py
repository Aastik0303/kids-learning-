"""Prototype authentication only. Replace with secure authentication and persistent storage before production."""

import hashlib
import re
from uuid import uuid4

from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, SessionResponse, UserPublic
from app.services.errors import app_error
from app.services.mock_storage import mock_sessions, mock_users


def _hash_password(password: str) -> str:
    # PROTOTYPE: sha256 is not password hashing for production.
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _validate_email(email: str) -> None:
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise app_error("INVALID_EMAIL", "Use a well-formed demo email address.")


def register(payload: RegisterRequest) -> AuthResponse:
    _validate_email(payload.email)
    email = payload.email.lower()
    if email in mock_users:
        raise app_error("EMAIL_EXISTS", "This demo email is already registered.")

    user_id = f"user_{len(mock_users) + 101}"
    user = {
        "id": user_id,
        "name": payload.name,
        "email": email,
        "password_hash": _hash_password(payload.password),
    }
    mock_users[email] = user
    return _issue_session(user)


def login(payload: LoginRequest) -> AuthResponse:
    email = payload.email.lower()
    user = mock_users.get(email)
    if not user or user["password_hash"] != _hash_password(payload.password):
        raise app_error("INVALID_LOGIN", "The demo login details did not match.", 401)
    return _issue_session(user)


def logout(session_token: str) -> None:
    mock_sessions.pop(session_token, None)


def get_user_for_token(session_token: str) -> dict:
    user_id = mock_sessions.get(session_token)
    if not user_id:
        raise app_error("MISSING_SESSION", "Please log in again.", 401)
    for user in mock_users.values():
        if user["id"] == user_id:
            return user
    raise app_error("MISSING_SESSION", "Please log in again.", 401)


def session(session_token: str | None) -> SessionResponse:
    if not session_token or session_token not in mock_sessions:
        return SessionResponse()
    user = get_user_for_token(session_token)
    return SessionResponse(user=UserPublic(**user))


def _issue_session(user: dict) -> AuthResponse:
    token = f"demo-{uuid4()}"
    mock_sessions[token] = user["id"]
    return AuthResponse(session_token=token, user=UserPublic(**user))
