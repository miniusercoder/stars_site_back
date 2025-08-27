from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "stars_site_backend"
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])
    stars_markup: int = 9

    jwt_secret: str
    jwt_alg: str = "HS256"
    jwt_access_ttl: int = 3600  # 1 час
    jwt_refresh_ttl: int = 30 * 24 * 3600  # 30 дней

    ton_api_key: str
    ton_mnemonic: str
    usdt_jetton_address: str = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"

    tonconnect_url: str
    tonconnect_name: str
    tonconnect_icon_url: str

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
