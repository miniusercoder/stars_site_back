from typing import Literal

from pydantic import BaseModel

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
