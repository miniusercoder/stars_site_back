from typing import Literal

from pydantic import BaseModel


class PriceWithCurrency(BaseModel):
    price: float
    currency: Literal["rub", "usd"] = "usd"


class PricesWithCurrency(BaseModel):
    price_rub: PriceWithCurrency
    price_usd: PriceWithCurrency


class BasePrices(BaseModel):
    star: PricesWithCurrency
    ton: PricesWithCurrency


class ItemPrice(BaseModel):
    amount: int
    prices: PricesWithCurrency
