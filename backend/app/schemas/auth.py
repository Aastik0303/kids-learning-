from pydantic import BaseModel, Field


class UserPublic(BaseModel):
    id: str
    name: str
    email: str


class RegisterRequest(BaseModel):
    email: str
    name: str = Field(min_length=1)
    password: str = Field(min_length=4)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=4)


class AuthResponse(BaseModel):
    session_token: str
    user: UserPublic


class LogoutRequest(BaseModel):
    session_token: str


class SessionResponse(BaseModel):
    user: UserPublic | None = None
