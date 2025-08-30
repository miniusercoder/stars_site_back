from typing import Literal, TypedDict

from pydantic import BaseModel, Field

from fastapi_stars.schemas.info import Item


class PriceWithCurrency(BaseModel):
    price: float
    currency: Literal["rub", "usd"] = "usd"


class PricesWithCurrency(BaseModel):
    price_rub: PriceWithCurrency
    price_usd: PriceWithCurrency


class OrderItem(BaseModel):
    order_id: int
    pay_url: str | None
    ton_transaction: str | None

    @classmethod
    def validate(cls, value):
        if not (value.get("pay_url") or value.get("ton_transaction")):
            raise ValueError(
                "Должен быть задан хотя бы один из pay_url или ton_transaction"
            )
        return value


class OrderResponse(BaseModel):
    success: bool
    error: (
        Literal[
            "invalid_amount",
            "invalid_recipient",
            "gift_not_found",
            "internal_error",
            "payment_creation_failed",
            "invalid_payment_type",
        ]
        | None
    ) = None
    result: OrderItem | None = None


class GiftPayload(TypedDict):
    gift_id: str


class OrderIn(BaseModel):
    item_type: Item = Field(..., alias="type")
    payload: GiftPayload | None = None
    payment_method: int
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
