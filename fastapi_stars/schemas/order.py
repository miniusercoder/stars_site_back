from typing import Literal, TypedDict

from pydantic import BaseModel, Field

from fastapi_stars.schemas.info import Item


class TonMessage(BaseModel):
    """Единичное сообщение для TonConnect-перевода."""

    address: str = Field(
        ...,
        description="TON-адрес получателя перевода (user-friendly).",
        examples=["EQB..."],
    )
    amount: str = Field(
        ...,
        description="Сумма перевода в наноистингах (nanoton/usdt nano) строкой.",
        examples=["1000000000"],
    )
    payload: str | None = Field(
        None,
        description="Доп. payload для перевода (если требуется).",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"address": "EQC...recipient", "amount": "2500000000", "payload": None}
            ]
        }
    }


class TonConnectMessage(BaseModel):
    """Сообщение TonConnect для инициирования перевода в кошельке пользователя."""

    validUntil: int = Field(
        ...,
        description="UNIX time (сек), до которого сообщение действительно.",
        examples=[1710000000],
    )
    messages: list[TonMessage] = Field(
        ..., description="Список переводов, которые должен подписать пользователь."
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "validUntil": 1710000000,
                    "messages": [
                        {
                            "address": "EQC...recipient",
                            "amount": "2500000000",
                            "payload": None,
                        }
                    ],
                }
            ]
        }
    }


class OrderItem(BaseModel):
    """Платёжные реквизиты для фронта после создания заказа."""

    order_id: int = Field(
        ..., description="Идентификатор созданного заказа.", examples=[12345]
    )
    pay_url: str | None = Field(
        None,
        description="Ссылка на оплату у внешнего мерчанта. Присутствует, если метод оплаты не TonConnect.",
        examples=[None, "https://merchant/pay/xyz"],
    )
    ton_transaction: TonConnectMessage | None = Field(
        None,
        description="TonConnect-пакет для кошелька пользователя. Присутствует, если метод оплаты — TonConnect.",
    )

    @classmethod
    def validate(cls, value):
        # Логика проверки: должен быть задан хотя бы один из pay_url или ton_transaction
        if not (value.get("pay_url") or value.get("ton_transaction")):
            raise ValueError(
                "Должен быть задан хотя бы один из pay_url или ton_transaction"
            )
        return value

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "order_id": 1001,
                    "pay_url": "https://merchant/pay/abc",
                    "ton_transaction": None,
                },
                {
                    "order_id": 1002,
                    "pay_url": None,
                    "ton_transaction": {
                        "validUntil": 1710000000,
                        "messages": [
                            {
                                "address": "EQC...recipient",
                                "amount": "2500000000",
                                "payload": None,
                            }
                        ],
                    },
                },
            ]
        }
    }


class OrderResponse(BaseModel):
    """Универсальный ответ на создание заказа/платежа."""

    success: bool = Field(..., description="Флаг успешности операции.")
    error: (
        Literal[
            "invalid_amount",
            "invalid_recipient",
            "gift_not_found",
            "internal_error",
            "payment_creation_failed",
            "invalid_payment_method",
        ]
        | None
    ) = Field(
        None,
        description=(
            "Код ошибки: \n"
            "- `invalid_amount` — нарушены ограничения по количеству; \n"
            "- `invalid_recipient` — некорректный получатель; \n"
            "- `gift_not_found` — подарок не найден/недоступен; \n"
            "- `internal_error` — внутренняя ошибка создания заказа; \n"
            "- `payment_creation_failed` — не удалось создать платёж/линк; \n"
            "- `invalid_payment_method` — метод оплаты не найден или несовместим с типом заказа."
        ),
    )
    result: OrderItem | None = Field(
        None,
        description="Платёжные данные при успешном создании заказа.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "error": None,
                    "result": {
                        "order_id": 1001,
                        "pay_url": "https://merchant/pay/abc",
                        "ton_transaction": None,
                    },
                },
                {"success": False, "error": "invalid_amount", "result": None},
            ]
        }
    }


class GiftPayload(TypedDict):
    """Payload для заказа типа `gift`."""

    gift_id: str


class OrderIn(BaseModel):
    """Входные данные для создания заказа."""

    item_type: Item = Field(
        ...,
        alias="type",
        description="Тип заказа: `star`, `premium`, `ton`, `gift`.",
        examples=["star"],
    )
    payload: GiftPayload | None = Field(
        None,
        description="Доп. данные (требуется для `gift`: `payload.gift_id`).",
        examples=[None, {"gift_id": "happy_birthday_001"}],
    )
    payment_method: int = Field(
        ..., description="ID платёжного метода.", examples=[1, 2, 3]
    )
    amount: int = Field(
        ...,
        gt=0,
        description=(
            "Количество. \n"
            "• для `star` — от **50** до **10000**; \n"
            "• для `premium` — только одно из **{3, 6, 12}**; \n"
            "• для `ton` — любое `> 0`; \n"
            "• для `gift` — всегда `1` (выставляется автоматически)."
        ),
        examples=[50, 500, 3, 6, 12, 1000],
    )
    recipient: str = Field(
        ...,
        description="Идентификатор получателя (Telegram username без `@` или иной ожидаемый формат).",
        examples=["telegram"],
    )

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "examples": [
                {
                    "type": "star",
                    "amount": 500,
                    "recipient": "telegram",
                    "payment_method": 2,
                    "payload": None,
                },
                {
                    "type": "premium",
                    "amount": 12,
                    "recipient": "telegram",
                    "payment_method": 3,
                },
                {
                    "type": "ton",
                    "amount": 5,
                    "recipient": "EQB...user",
                    "payment_method": 10,
                },
                {
                    "type": "gift",
                    "amount": 1,
                    "recipient": "telegram",
                    "payment_method": 4,
                    "payload": {"gift_id": "happy_birthday_001"},
                },
            ]
        },
    }
