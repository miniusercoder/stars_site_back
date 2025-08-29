from typing import Literal

from pydantic import BaseModel, Field

type Item = Literal["star", "premium", "ton"]


class PriceWithCurrency(BaseModel):
    price: float
    currency: Literal["rub", "usd"] = "usd"


class PricesWithCurrency(BaseModel):
    price_rub: PriceWithCurrency
    price_usd: PriceWithCurrency


class HeaderPrices(BaseModel):
    star: PricesWithCurrency
    ton: PricesWithCurrency


class ItemPrice(BaseModel):
    amount: int
    prices: PricesWithCurrency


class ProjectStats(BaseModel):
    stars_today: int
    stars_total: int
    premium_today: int
    premium_total: int


class TelegramUserIn(BaseModel):
    username: str = Field(None, pattern=r"^[a-zA-Z0-9_]{5,32}$")


class TelegramUser(BaseModel):
    name: str
    photo: str | None = None


class TelegramUserResponse(BaseModel):
    success: bool
    error: Literal["not_found"] | None = None
    result: TelegramUser | None = None


class GiftModel(BaseModel):
    id: str
    emoji: str
    prices: PricesWithCurrency


class GiftsResponse(BaseModel):
    gifts: list[GiftModel]
