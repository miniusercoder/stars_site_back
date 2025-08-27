from typing import TypedDict, Literal, Optional

from pydantic import BaseModel, Field

from django_stars.stars_app.models import User, GuestSession

type AuthType = Literal["user", "guest"]


class Principal(TypedDict, total=False):
    kind: AuthType
    user: User
    guest: GuestSession
    payload: dict


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


class TonProofDomain(BaseModel):
    lengthBytes: str
    value: str


class TonProofResponse(BaseModel):
    timestamp: str
    domain: TonProofDomain
    signature: str
    payload: str


class TonAccount(BaseModel):
    address: str
    network: str
    wallet_state_init: str = Field(None, alias="walletStateInit")
    public_key: str = Field(None, alias="publicKey")


class TonConnectProof(BaseModel):
    proof: TonProofResponse
    account: TonAccount
