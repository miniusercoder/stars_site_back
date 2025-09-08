from typing import Literal

from pydantic import BaseModel, Field, field_validator

from fastapi_stars.settings import settings

# Разрешённые типы предметов/заказов
type Item = Literal["star", "premium", "ton", "gift"]


class PriceWithCurrency(BaseModel):
    """Числовая цена с указанием валюты."""

    price: float = Field(
        ..., description="Стоимость в указанной валюте.", examples=[1.23, 99.99]
    )
    currency: Literal["rub", "usd"] = Field(
        "usd",
        description="Код валюты. Поддерживаются `usd` и `rub`.",
        examples=["usd"],
    )


class PricesWithCurrency(BaseModel):
    """Цена в двух валютах — RUB и USD."""

    price_rub: PriceWithCurrency = Field(..., description="Цена в рублях.")
    price_usd: PriceWithCurrency = Field(..., description="Цена в долларах США.")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "price_usd": {"currency": "usd", "price": 12.34},
                    "price_rub": {"currency": "rub", "price": 1200.56},
                }
            ]
        }
    }


class HeaderPrices(BaseModel):
    """Набор ориентировочных цен для отображения в заголовке сайта/приложения."""

    star: PricesWithCurrency = Field(..., description="Цена Stars (за 1 Star).")
    ton: PricesWithCurrency = Field(..., description="Цена TON (за 1 TON).")


class ItemPrice(BaseModel):
    """Цена для конкретного количества предмета."""

    amount: int = Field(
        ...,
        description="Количество единиц предмета.",
        examples=[50, 500, 3, 6, 12, 1000],
    )
    prices: PricesWithCurrency = Field(..., description="Цена в USD и RUB.")


class ProjectStats(BaseModel):
    """Сводная статистика по заказам."""

    stars_today: int = Field(
        ..., description="Количество Stars, купленных сегодня.", examples=[0, 1500]
    )
    stars_total: int = Field(
        ..., description="Количество Stars за всё время.", examples=[250000]
    )
    premium_today: int = Field(
        ...,
        description="Premium-подписок, оформленных сегодня.",
        examples=[0, 12],
    )
    premium_total: int = Field(
        ..., description="Premium-подписок за всё время.", examples=[5433]
    )


class TelegramUserIn(BaseModel):
    """Входные данные для проверки Telegram-получателя."""

    username: str = Field(
        None,
        pattern=r"^[a-zA-Z0-9_]{5,32}$",
        description="Telegram username без @, 5–32 символов: латиница/цифры/нижнее подчёркивание.",
        examples=["durov", "telegram"],
    )
    order_type: Item = Field(
        "star",
        alias="type",
        description="Тип заказа для проверки: `star`, `premium`, `ton`, `gift`.",
        examples=["star"],
    )


class TelegramUser(BaseModel):
    """Короткие сведения о Telegram-пользователе/канале."""

    name: str = Field(..., description="Отображаемое имя.")
    photo: str | None = Field(
        None,
        description="URL аватарки (если доступен).",
        examples=[None, "https://.../avatar.jpg"],
    )


class TelegramUserResponse(BaseModel):
    """Результат валидации Telegram-получателя."""

    success: bool = Field(..., description="Флаг успешной проверки.")
    error: Literal["not_found", "already_subscribed"] | None = Field(
        None,
        description="Код ошибки. `already_subscribed` — для Premium, если уже оформлена подписка.",
    )
    result: TelegramUser | None = Field(
        None, description="Данные получателя при `success=True`."
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "result": {"name": "Alice", "photo": "https://.../a.jpg"},
                    "error": None,
                },
                {"success": False, "result": None, "error": "not_found"},
            ]
        }
    }


class GiftModel(BaseModel):
    """Описание подарка и его цена."""

    id: str = Field(..., description="Идентификатор подарка.")
    emoji: str = Field(..., description="Эмодзи подарка.", examples=["🎁"])
    prices: PricesWithCurrency = Field(..., description="Цена подарка в валютах.")


class GiftsResponse(BaseModel):
    """Список доступных подарков."""

    gifts: list[GiftModel] = Field(..., description="Отсортированный список подарков.")


class PaymentMethodModel(BaseModel):
    """Модель платёжного метода для фронта."""

    id: int = Field(..., description="ID метода оплаты.")
    name: str = Field(..., description="Человекочитаемое имя метода.")
    icon: str | None = Field(None, description="Абсолютный URL иконки (если есть).")

    @field_validator("icon", mode="before")
    @classmethod
    def serialize_icon(cls, value):
        if not value:
            return None
        return f"{settings.site_url}{value.url}"


class PaymentMethodsResponse(BaseModel):
    """Список платёжных методов, доступных к использованию."""

    methods: list[PaymentMethodModel] = Field(
        ..., description="Методы оплаты, отсортированные по приоритету."
    )
