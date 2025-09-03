from pydantic import BaseModel, ConfigDict, Field

from django_stars.stars_app.models import Order


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # Pydantic v2: ORM mode
    id: int
    wallet_address: str
    ref_alias: str | None


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


class OrdersResponse(BaseModel):
    items: list[OrderModel]
