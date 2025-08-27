from typing import TypedDict, Literal, Optional

from pydantic import BaseModel

from django_stars.stars_app.models import User, GuestSession

type AuthType = Literal["user", "guest"]


class Principal(TypedDict, total=False):
    kind: AuthType
    user: User
    guest: GuestSession


class TokenPair(BaseModel):
    access: str
    refresh: str


class RefreshIn(BaseModel):
    refresh: str


class GuestTokenOut(BaseModel):
    guest: str  # guest JWT
    ton_verify: str


class SessionValidation(BaseModel):
    success: bool
    token_type: Optional[AuthType] = None
