from pydantic import BaseModel


class TokenPair(BaseModel):
    access: str
    refresh: str


class RefreshIn(BaseModel):
    refresh: str


class GuestTokenOut(BaseModel):
    guest: str  # guest JWT


class SessionValidation(BaseModel):
    success: bool
