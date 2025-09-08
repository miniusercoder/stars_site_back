from pydantic import BaseModel, ConfigDict, Field, UUID4, field_validator

from django_stars.stars_app.models import Order, Payment
from fastapi_stars.schemas.info import (
    PaymentMethodModel,
    PricesWithCurrency,
)


class StatsForOrderType(BaseModel):
    amount: int
    price: PricesWithCurrency


class UserStatistic(BaseModel):
    stars: StatsForOrderType
    premium: StatsForOrderType
    ton: StatsForOrderType
    deposit: PricesWithCurrency


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # Pydantic v2: ORM mode
    id: int
    wallet_address: str
    ref_alias: str | None
    stats: UserStatistic


class SuccessResponse(BaseModel):
    success: bool = True


class RefAliasIn(BaseModel):
    ref_alias: str = Field(None, max_length=64, min_length=5)


class OrderModel(BaseModel):
    id: int
    type: Order.Type
    status: Order.Status
    price: float
    amount: int
    recipient_username: str
    created_at: int

    @field_validator("created_at", mode="before")
    @classmethod
    def create_date_validator(cls, value):
        return int(value.timestamp())


class OrdersResponse(BaseModel):
    items: list[OrderModel]


class PaymentModel(BaseModel):
    id: UUID4
    method: PaymentMethodModel
    sum: float
    status: Payment.Status
    created_at: int

    @field_validator("created_at", mode="before")
    @classmethod
    def create_date_validator(cls, value):
        return int(value.timestamp())


class PaymentsResponse(BaseModel):
    items: list[PaymentModel]


class ReferralItem(BaseModel):
    wallet_address: str
    level: int
    profit: float


class ReferralsResponse(BaseModel):
    items: list[ReferralItem]
