from typing import Literal

from pydantic import BaseModel, Field, field_validator

from fastapi_stars.settings import settings

type Item = Literal["star", "premium", "ton", "gift"]


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
    order_type: Item = Field("star", alias="type")


class TelegramUser(BaseModel):
    name: str
    photo: str | None = None


class TelegramUserResponse(BaseModel):
    success: bool
    error: Literal["not_found", "already_subscribed"] | None = None
    result: TelegramUser | None = None


class GiftModel(BaseModel):
    id: str
    emoji: str
    prices: PricesWithCurrency


class GiftsResponse(BaseModel):
    gifts: list[GiftModel]


class PaymentMethodModel(BaseModel):
    id: int
    name: str
    icon: str | None = None

    @field_validator("icon", mode="before")
    @classmethod
    def serialize_icon(cls, value):
        if not value:
            return None
        return f"{settings.site_url}{value.url}"


class PaymentMethodsResponse(BaseModel):
    methods: list[PaymentMethodModel]
