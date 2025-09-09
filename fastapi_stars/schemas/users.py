from pydantic import BaseModel, ConfigDict, Field, UUID4, field_validator

from django_stars.stars_app.models import Order, Payment
from fastapi_stars.schemas.info import (
    PaymentMethodModel,
    PricesWithCurrency,
)


class StatsForOrderType(BaseModel):
    amount: int = Field(
        ...,
        description="Количество единиц (например, штук/подписок) по типу заказа.",
        json_schema_extra={"example": 3},
    )
    price: PricesWithCurrency = Field(
        ..., description="Сумма по типу заказа в нескольких валютах."
    )


class UserStatistic(BaseModel):
    stars: StatsForOrderType = Field(
        ..., description="Статистика по заказам типа STARS."
    )
    premium: StatsForOrderType = Field(
        ..., description="Статистика по заказам типа PREMIUM."
    )
    ton: StatsForOrderType = Field(..., description="Статистика по заказам типа TON.")
    deposit: PricesWithCurrency = Field(
        ..., description="Итоговая сумма подтверждённых пополнений (deposit)."
    )


class UserOut(BaseModel):
    """Ответ для эндпоинта /me."""

    model_config = ConfigDict(from_attributes=True)  # Pydantic v2: ORM mode
    id: int = Field(
        ...,
        description="Идентификатор пользователя.",
        json_schema_extra={"example": 42},
    )
    wallet_address: str = Field(
        ...,
        description="Адрес кошелька пользователя.",
        json_schema_extra={"example": "EQB1...abcd"},
    )
    ref_alias: str | None = Field(
        None,
        description="Реферальный алиас пользователя, если задан.",
        json_schema_extra={"example": "my_invite"},
    )
    stats: UserStatistic = Field(..., description="Сводная статистика пользователя.")


class SuccessResponse(BaseModel):
    success: bool = Field(
        True,
        description="Флаг успешного выполнения операции.",
        json_schema_extra={"example": True},
    )


class RefAliasIn(BaseModel):
    ref_alias: str = Field(
        None,
        description="Реферальный алиас (5–64 символа).",
        max_length=64,
        min_length=5,
        json_schema_extra={"example": "cool_ref_2025"},
    )


class OrderModel(BaseModel):
    id: int = Field(..., description="ID заказа.", json_schema_extra={"example": 101})
    type: Order.Type = Field(
        ...,
        description="Тип заказа (STARS, PREMIUM, TON и т.д.).",
        json_schema_extra={"example": "STARS"},
    )
    status: Order.Status = Field(
        ..., description="Статус заказа.", json_schema_extra={"example": "COMPLETED"}
    )
    price: float = Field(
        ...,
        description="Итоговая сумма заказа в базовой валюте (USD).",
        json_schema_extra={"example": 19.99},
    )
    amount: int = Field(
        ...,
        description="Количество единиц (например, подписок/звёзд) в заказе.",
        json_schema_extra={"example": 2},
    )
    recipient_username: str = Field(
        ...,
        description="Имя получателя, на которого оформлен заказ.",
        json_schema_extra={"example": "john_doe"},
    )
    created_at: int = Field(
        ...,
        description="UNIX-время (секунды) создания заказа.",
        json_schema_extra={"example": 1720521600},
    )

    @field_validator("created_at", mode="before")
    @classmethod
    def create_date_validator(cls, value):
        return int(value.timestamp())


class OrdersResponse(BaseModel):
    items: list[OrderModel] = Field(..., description="Список заказов.")
    total: int = Field(
        ...,
        description="Общее количество найденных заказов (для пагинации).",
        json_schema_extra={"example": 37},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [
                        {
                            "id": 101,
                            "type": "STARS",
                            "status": "COMPLETED",
                            "price": 19.99,
                            "amount": 2,
                            "recipient_username": "john_doe",
                            "created_at": 1720521600,
                        }
                    ],
                    "total": 37,
                }
            ]
        }
    }


class PaymentModel(BaseModel):
    id: UUID4 = Field(
        ...,
        description="ID платежа (UUID4).",
        json_schema_extra={"example": "5d9c6a9e-2b2b-4ef2-9c9d-9b8f7c6a5d4e"},
    )
    method: PaymentMethodModel = Field(..., description="Платёжный метод.")
    sum: float = Field(
        ...,
        description="Сумма платежа в базовой валюте (USD).",
        json_schema_extra={"example": 9.99},
    )
    status: Payment.Status = Field(
        ..., description="Статус платежа.", json_schema_extra={"example": "CONFIRMED"}
    )
    created_at: int = Field(
        ...,
        description="UNIX-время (секунды) создания платежа.",
        json_schema_extra={"example": 1720521600},
    )

    @field_validator("created_at", mode="before")
    @classmethod
    def create_date_validator(cls, value):
        return int(value.timestamp())


class PaymentsResponse(BaseModel):
    items: list[PaymentModel] = Field(..., description="Список платежей.")
    total: int = Field(
        ...,
        description="Общее количество найденных платежей (для пагинации).",
        json_schema_extra={"example": 12},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [
                        {
                            "id": "5d9c6a9e-2b2b-4ef2-9c9d-9b8f7c6a5d4e",
                            "method": {"code": "USDT_TRC20", "title": "USDT TRC-20"},
                            "sum": 9.99,
                            "status": "CONFIRMED",
                            "created_at": 1720521600,
                        }
                    ],
                    "total": 12,
                }
            ]
        }
    }


class ReferralItem(BaseModel):
    wallet_address: str = Field(
        ...,
        description="Сокращённый адрес кошелька реферала.",
        json_schema_extra={"example": "EQB1...abcd"},
    )
    level: int = Field(
        ...,
        ge=1,
        le=3,
        description="Уровень реферала (1–3).",
        json_schema_extra={"example": 1},
    )
    profit: float = Field(
        ...,
        description="Суммарная прибыль от реферала на этом уровне.",
        json_schema_extra={"example": 12.34},
    )


class ReferralsResponse(BaseModel):
    items: list[ReferralItem] = Field(..., description="Список рефералов.")
    total: int = Field(
        ...,
        description="Общее количество рефералов (для пагинации).",
        json_schema_extra={"example": 25},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [
                        {"wallet_address": "EQB1...abcd", "level": 1, "profit": 12.34},
                        {"wallet_address": "EQC2...efgh", "level": 2, "profit": 1.5},
                    ],
                    "total": 25,
                }
            ]
        }
    }


class ReferralsCountResponse(BaseModel):
    level_1: int = Field(..., description="Количество рефералов 1 уровня")
    level_2: int = Field(..., description="Количество рефералов 2 уровня")
    level_3: int = Field(..., description="Количество рефералов 3 уровня")
    total: int = Field(..., description="Общее количество рефералов")
    total_reward: float = Field(..., description="Общая сумма вознаграждений")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "level_1": 5,
                    "level_2": 3,
                    "level_3": 2,
                    "total": 10,
                    "total_reward": 123.45,
                }
            ]
        }
    }
