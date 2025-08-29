from typing import Literal, TypedDict

from pydantic import BaseModel, Field

from fastapi_stars.schemas.info import Item


class PriceWithCurrency(BaseModel):
    price: float
    currency: Literal["rub", "usd"] = "usd"


class PricesWithCurrency(BaseModel):
    price_rub: PriceWithCurrency
    price_usd: PriceWithCurrency


class OrderResponse(BaseModel):
    order_id: str
    pay_url: str


class GiftPayload(TypedDict):
    gift_id: str


class OrderIn(BaseModel):
    item_type: Item = Field(..., alias="type")
    payload: GiftPayload | None = None
    amount: int = Field(
        ...,
        gt=0,
        description=(
            "Количество.\n"
            "Для 'star' — от 50 до 10000.\n"
            "Для 'premium' — только одно из {3, 6, 12}."
        ),
    )
    recipient: str
