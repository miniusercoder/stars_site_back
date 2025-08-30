from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "stars_site_backend"
    allowed_origins: list[str] = Field(default_factory=lambda: ["*"])
    stars_markup: int = 9
    gifts_markup: int = 25
    bot_token: SecretStr
    media_url: str = "https://helperstars.tg/media/"

    jwt_secret: SecretStr
    jwt_alg: str = "HS256"
    jwt_access_ttl: int = 3600  # 1 час
    jwt_refresh_ttl: int = 30 * 24 * 3600  # 30 дней
    jwt_guest_ttl: int = 7 * 24 * 3600  # 7 дней

    ton_api_key: SecretStr
    ton_mnemonic: SecretStr
    usdt_jetton_address: str = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"

    tonconnect_url: str
    tonconnect_name: str
    tonconnect_icon_url: str

    available_gifts: list[str] = Field(
        default_factory=lambda: [
            "5170145012310081615",
            "5170233102089322756",
            "5170250947678437525",
            "5168103777563050263",
            "5170144170496491616",
            "5170314324215857265",
            "5170564780938756245",
            "5168043875654172773",
            "5170690322832818290",
            "5170521118301225164",
            "6028601630662853006",
        ]
    )

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
