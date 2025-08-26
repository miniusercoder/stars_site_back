from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pytoniq_core import Cell


class TonTransactionMessage(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    address: str
    amount: int  # in grams
    payload: str | Cell | None = None


class TonTransaction(BaseModel):
    valid_until: datetime = Field(alias="validUntil")
    messages: list[TonTransactionMessage]
