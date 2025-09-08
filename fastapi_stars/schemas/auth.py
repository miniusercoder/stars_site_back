from typing import TypedDict, Literal, Optional

from pydantic import BaseModel, Field

from django_stars.stars_app.models import User, GuestSession

# Тип с допустимыми значениями для вида сессии/токена
type AuthType = Literal["user", "guest"]


class Principal(TypedDict, total=False):
    """
    Контекст текущего принципала, предоставляемый зависимостью `current_principal`.

    Поля:
    - kind: тип аутентификации (`"user"` или `"guest"`).
    - user: объект пользователя (если `kind == "user"`).
    - guest: объект гостевой сессии (если `kind == "guest"`).
    - payload: произвольные данные, связанные с текущим токеном (в т.ч. `sid`, `ref`, `ton_verify` для гостя).
    """

    kind: AuthType
    user: User
    guest: GuestSession
    payload: dict


class TokenPair(BaseModel):
    """Пара JWT-токенов, выдаваемая при логине/обновлении."""

    access: str = Field(..., description="Короткоживущий токен доступа (JWT).")
    refresh: str = Field(..., description="Долгоживущий токен обновления (JWT).")

    model_config = {
        "json_schema_extra": {
            "examples": [{"access": "eyJhbGciOi...", "refresh": "eyJhbGciOi..."}]
        }
    }


class RefreshIn(BaseModel):
    """Запрос на обновление токенов по refresh."""

    refresh: str = Field(..., description="Действительный refresh-токен (JWT).")

    model_config = {"json_schema_extra": {"examples": [{"refresh": "eyJhbGciOi..."}]}}


class GuestTokenOut(BaseModel):
    """Ответ при создании гостевой сессии."""

    guest: str = Field(..., description="Гостевой JWT.")
    ton_verify: str = Field(
        ...,
        description="Payload, который должен быть подписан кошельком в TonConnect-доказательстве.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "guest": "eyJhbGciOi...",
                    "ton_verify": "A1B2C3D4E5F6...",
                }
            ]
        }
    }


class SessionValidation(BaseModel):
    """Ответ проверки валидности текущей сессии/токена."""

    success: bool = Field(..., description="Флаг успешной проверки.")
    token_type: Optional[AuthType] = Field(
        None, description="Тип токена: `user` или `guest`."
    )
    wallet_address: Optional[str] = Field(
        None,
        description="Технический (not user-friendly) адрес кошелька пользователя. Присутствует только для `user`.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"success": True, "token_type": "guest"},
                {
                    "success": True,
                    "token_type": "user",
                    "wallet_address": "0:abcd1234ef... (hex/raw)",
                },
            ]
        }
    }


class TonProofDomain(BaseModel):
    """Домен, для которого подписывается TonConnect-доказательство."""

    lengthBytes: int = Field(..., description="Длина значения домена в байтах.")
    value: str = Field(..., description="Строковое значение домена.")

    model_config = {
        "json_schema_extra": {"examples": [{"lengthBytes": 8, "value": "your.app"}]}
    }


class TonProofResponse(BaseModel):
    """Данные доказательства TonConnect."""

    timestamp: int = Field(..., description="UNIX-время подписи.")
    domain: TonProofDomain = Field(..., description="Информация о домене.")
    signature: str = Field(..., description="Подпись кошелька.")
    payload: str = Field(
        ..., description="Подписанный payload (совпадает с `ton_verify`)."
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timestamp": 1710000000,
                    "domain": {"lengthBytes": 8, "value": "your.app"},
                    "signature": "base64/hex-строка подписи",
                    "payload": "A1B2C3D4E5F6...",
                }
            ]
        }
    }


class TonAccount(BaseModel):
    """Информация о кошельке TON, присылаемая клиентом TonConnect."""

    address: str = Field(..., description="Адрес кошелька (user-friendly).")
    chain: str = Field(..., description="Идентификатор сети (e.g. `-239` для mainnet).")
    wallet_state_init: str = Field(
        None,
        alias="walletStateInit",
        description="StateInit кошелька.",
    )
    public_key: str = Field(
        None,
        alias="publicKey",
        description="Публичный ключ кошелька в hex/base64 (зависит от клиента).",
    )

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "examples": [
                {
                    "address": "EQB...userFriendly",
                    "chain": "-239",
                    "walletStateInit": None,
                    "publicKey": "0xABCDEF...",
                }
            ]
        },
    }


class TonConnectProof(BaseModel):
    """Запрос на логин через TonConnect."""

    proof: TonProofResponse = Field(..., description="Доказательство TonConnect.")
    account: TonAccount = Field(..., description="Данные аккаунта/кошелька TON.")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "proof": {
                        "timestamp": 1710000000,
                        "domain": {"lengthBytes": 8, "value": "your.app"},
                        "signature": "base64/hex-строка подписи",
                        "payload": "A1B2C3D4E5F6...",
                    },
                    "account": {
                        "address": "EQB...userFriendly",
                        "chain": "-239",
                        "walletStateInit": None,
                        "publicKey": "0xABCDEF...",
                    },
                }
            ]
        }
    }
