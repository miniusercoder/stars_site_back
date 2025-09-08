import re
from typing import Annotated, assert_never

from django.db.models import Sum, Q
from django.utils import timezone
from fastapi import APIRouter, Path, HTTPException, Depends, status, Query
from redis import Redis

from django_stars.stars_app.models import Order, PaymentMethod, PaymentSystem
from fastapi_stars.api.deps import current_principal
from fastapi_stars.schemas.auth import Principal
from fastapi_stars.schemas.info import (
    HeaderPrices,
    PricesWithCurrency,
    PriceWithCurrency,
    Item,
    ProjectStats,
    TelegramUserResponse,
    TelegramUserIn,
    TelegramUser,
    GiftsResponse,
    GiftModel,
    PaymentMethodsResponse,
    PaymentMethodModel,
)
from fastapi_stars.settings import settings
from fastapi_stars.utils.prices import (
    get_stars_price,
    get_premium_price,
    get_ton_price,
)
from integrations.Currencies import USDT
from integrations.fragment import FragmentAPI
from integrations.gifts import get_gift_sender
from integrations.telegram_bot import bot
from integrations.wallet.helpers import get_wallet

router = APIRouter()

r = Redis(host="localhost", port=6379, decode_responses=True)


@router.get(
    "/project_stats",
    response_model=ProjectStats,
    summary="Сводная статистика проекта",
    description=(
        "Возвращает агрегаты по завершённым заказам: количество Stars и Premium за **сегодня** "
        "и за **всё время**. Результат кэшируется в Redis на 10 минут."
    ),
    responses={
        200: {"description": "Статистика успешно получена (может быть из кэша)."}
    },
)
def get_project_stats():
    """
    Считает агрегаты по завершённым заказам `Order`:
    * Stars: `today` и `total`
    * Premium: `today` и `total`

    Кэш-ключ: `stars_site:project_stats` (TTL 600 сек).
    """
    cached_stats = r.get("stars_site:project_stats")
    if cached_stats:
        return ProjectStats.model_validate_json(cached_stats)

    today_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    stars_today = (
        Order.objects.filter(
            is_refund=False,
            created_at__gte=today_date,
            status=Order.Status.COMPLETED,
            type=Order.Type.STARS,
        ).aggregate(Sum("amount"))["amount__sum"]
        or 0
    )
    stars_total = (
        Order.objects.filter(
            is_refund=False,
            status=Order.Status.COMPLETED,
            type=Order.Type.STARS,
        ).aggregate(Sum("amount"))["amount__sum"]
        or 0
    )

    premium_today = (
        Order.objects.filter(
            is_refund=False,
            created_at__gte=today_date,
            status=Order.Status.COMPLETED,
            type=Order.Type.PREMIUM,
        ).aggregate(Sum("amount"))["amount__sum"]
        or 0
    )
    premium_total = (
        Order.objects.filter(
            is_refund=False,
            status=Order.Status.COMPLETED,
            type=Order.Type.PREMIUM,
        ).aggregate(Sum("amount"))["amount__sum"]
        or 0
    )

    project_stats = ProjectStats(
        stars_today=stars_today,
        stars_total=stars_total,
        premium_today=premium_today,
        premium_total=premium_total,
    )

    r.set("stars_site:project_stats", project_stats.model_dump_json(), ex=600)
    return project_stats


@router.post(
    "/validate_user",
    response_model=TelegramUserResponse,
    summary="Проверка Telegram-получателя",
    description=(
        "Проверяет существование и состояние получателя в зависимости от типа заказа: "
        "`star`, `premium`, `ton` или `gift`. Результат кэшируется на 5 минут. "
        "Требуется авторизация (guest/user)."
    ),
    responses={
        200: {
            "description": "Проверка выполнена. Возвращает данные получателя или ошибку."
        }
    },
)
def validate_telegram_user(
    user: TelegramUserIn, _: Principal = Depends(current_principal)
):
    """
    Для `order_type`:
    * **star** — ищет получателя Stars.
    * **premium** — ищет получателя Premium. Может вернуть `already_subscribed`.
    * **ton** — ищет получателя TON.
    * **gift** — валидация получателя в gifts-сервисе, затем загрузка данных из Fragment.

    Кэш-ключ: `stars_site:tg_user_{username}_{order_type}` (TTL 300 сек).
    """
    cached = r.get("stars_site:tg_user_{}_{}".format(user.username, user.order_type))
    if cached:
        return TelegramUserResponse.model_validate_json(cached)

    fragment = FragmentAPI(get_wallet())
    result = None
    match user.order_type:
        case "star":
            try:
                recipient = fragment.get_stars_recipient(user.username).model_copy()
            except ValueError:
                result = TelegramUserResponse(
                    success=False, error="not_found", result=None
                )
            else:
                recipient.photo = (
                    re.findall(r'"([^"]+)"', recipient.photo)[0]
                    if recipient.photo
                    else None
                )
                result = TelegramUserResponse(
                    success=True,
                    result=TelegramUser.model_validate(recipient, from_attributes=True),
                    error=None,
                )
        case "premium":
            try:
                recipient = fragment.get_premium_recipient(user.username).model_copy()
            except ValueError as e:
                if len(e.args) > 0 and e.args[0] == "already_subscribed":
                    result = TelegramUserResponse(
                        success=False, error="already_subscribed", result=None
                    )
                else:
                    result = TelegramUserResponse(
                        success=False, error="not_found", result=None
                    )
            else:
                recipient.photo = (
                    re.findall(r'"([^"]+)"', recipient.photo)[0]
                    if recipient.photo
                    else None
                )
                result = TelegramUserResponse(
                    success=True,
                    result=TelegramUser.model_validate(recipient, from_attributes=True),
                    error=None,
                )
        case "ton":
            try:
                recipient = fragment.get_ton_recipient(user.username).model_copy()
            except ValueError:
                result = TelegramUserResponse(
                    success=False, error="not_found", result=None
                )
            else:
                recipient.photo = (
                    re.findall(r'"([^"]+)"', recipient.photo)[0]
                    if recipient.photo
                    else None
                )
                result = TelegramUserResponse(
                    success=True,
                    result=TelegramUser.model_validate(recipient, from_attributes=True),
                    error=None,
                )
        case "gift":
            if not get_gift_sender().validate_recipient(user.username):
                result = TelegramUserResponse(
                    success=False, error="not_found", result=None
                )
            else:
                try:
                    recipient = fragment.get_stars_recipient(user.username).model_copy()
                except ValueError:
                    result = TelegramUserResponse(
                        success=False, error="not_found", result=None
                    )
                else:
                    recipient.photo = (
                        re.findall(r'"([^"]+)"', recipient.photo)[0]
                        if recipient.photo
                        else None
                    )
                    result = TelegramUserResponse(
                        success=True,
                        result=TelegramUser.model_validate(
                            recipient, from_attributes=True
                        ),
                        error=None,
                    )
        case _:
            assert_never(user.order_type)
    if not result:
        result = TelegramUserResponse(success=False, error="not_found", result=None)
    r.set(
        "stars_site:tg_user_{}_{}".format(user.username, user.order_type),
        result.model_dump_json(),
        ex=300,
    )
    return result


@router.get(
    "/header_prices",
    response_model=HeaderPrices,
    summary="Базовые цены для хэдера",
    description=(
        "Возвращает ориентировочные цены для TON и Stars в валютах USD и RUB. "
        "Данные кэшируются на 60 секунд."
    ),
    responses={200: {"description": "Цены успешно получены (может быть из кэша)."}},
)
def get_header_prices():
    """
    Источники:
    * `get_ton_price(1)` — цена 1 TON в USD, пересчёт в RUB.
    * `get_stars_price(500)` — средняя цена Stars (делим на 500 для цены за 1 Star).

    Кэш-ключ: `stars_site:base_prices` (TTL 60 сек).
    """
    cached_prices = r.get("stars_site:base_prices")
    if cached_prices:
        return HeaderPrices.model_validate_json(cached_prices)

    ton_price_in_usd, _ = get_ton_price(1)
    ton_price_in_rub = USDT.usd_to_rub(ton_price_in_usd)

    price_per_star_usd, _ = get_stars_price(500)
    price_per_star_usd /= 500
    price_per_star_rub = USDT.usd_to_rub(price_per_star_usd)

    prices = HeaderPrices(
        ton=PricesWithCurrency(
            price_usd=PriceWithCurrency(
                currency="usd",
                price=ton_price_in_usd,
            ),
            price_rub=PriceWithCurrency(
                currency="rub",
                price=ton_price_in_rub,
            ),
        ),
        star=PricesWithCurrency(
            price_usd=PriceWithCurrency(
                currency="usd",
                price=price_per_star_usd,
            ),
            price_rub=PriceWithCurrency(
                currency="rub",
                price=price_per_star_rub,
            ),
        ),
    )

    r.set("stars_site:base_prices", prices.model_dump_json(), ex=60)
    return prices


@router.get(
    "/price/{type}/{amount}",
    response_model=PricesWithCurrency,
    summary="Расчёт цены заказа",
    description=(
        "Возвращает стоимость для выбранного типа и количества: `star`, `premium` или `ton`. "
        "Допустимые значения `amount` зависят от типа. Результат кэшируется на 5 минут."
    ),
    responses={
        200: {"description": "Цена успешно рассчитана (может быть из кэша)."},
        400: {"description": "Некорректный тип `item_type`."},
        422: {"description": "Нарушены ограничения по `amount` для выбранного типа."},
    },
)
def get_order_price(
    item_type: Annotated[Item, Path(alias="type", description="Тип предмета заказа")],
    amount: Annotated[
        int,
        Path(
            gt=0,
            description=(
                "Количество.\n"
                "Для 'star' — от 50 до 10000.\n"
                "Для 'premium' — только одно из {3, 6, 12}."
            ),
            examples=[50, 500, 3, 6, 12, 1000],
        ),
    ],
    _: Principal = Depends(current_principal),
):
    """
    Правила валидации:
    * **star**: `50 ≤ amount ≤ 10000`
    * **premium**: `amount ∈ {3, 6, 12}`
    * **ton**: любое `amount > 0`

    Кэш-ключ: `stars_site:price_{item_type}_{amount}` (TTL 300 сек).
    """
    price_usd = r.get("stars_site:price_{}_{}".format(item_type, amount))
    if not price_usd:
        if item_type == "star":
            if not (50 <= amount <= 10000):
                raise HTTPException(
                    status_code=422,
                    detail={
                        "loc": ["path", "amount"],
                        "msg": "Для item_type='star' параметр 'amount' должен быть в диапазоне 50..10000.",
                        "type": "value_error.amount.range",
                    },
                )
            price_usd, _ = get_stars_price(amount)
        elif item_type == "premium":
            if amount not in {3, 6, 12}:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "loc": ["path", "amount"],
                        "msg": "Для item_type='premium' параметр 'amount' должен быть одним из {3, 6, 12}.",
                        "type": "value_error.amount.literal",
                    },
                )
            price_usd, _ = get_premium_price(amount)  # type: ignore
        elif item_type == "ton":
            price_usd, _ = get_ton_price(amount)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid item_type. Must be one of 'star', 'premium', or 'ton'.",
            )
        r.set(
            "stars_site:price_{}_{}".format(item_type, amount),
            price_usd,
            ex=300,
        )
    else:
        price_usd = float(price_usd)
    price_rub = USDT.usd_to_rub(price_usd)
    return PricesWithCurrency(
        price_usd=PriceWithCurrency(currency="usd", price=price_usd),
        price_rub=PriceWithCurrency(currency="rub", price=price_rub),
    )


@router.get(
    "/gifts",
    response_model=GiftsResponse,
    summary="Список доступных подарков",
    description=(
        "Возвращает доступные подарки с ценой в USD и RUB. Цены рассчитываются по текущей цене Stars. "
        "Результат кэшируется на 10 минут."
    ),
    responses={
        200: {"description": "Список подарков сформирован (может быть из кэша)."}
    },
)
def get_gifts(_: Principal = Depends(current_principal)):
    """
    Источники данных:
    * Fragment: цена Stars (берём цену за 500 Stars, делим на 500).
    * Telegram bot: список доступных подарков.
    * Маркап: `settings.gifts_markup` (%).

    Кэш-ключ: `stars_site:gifts` (TTL 600 сек).
    """
    cached = r.get("stars_site:gifts")
    if cached:
        return GiftsResponse.model_validate_json(cached)

    fragment = FragmentAPI(get_wallet())
    price_for_500_stars = fragment.get_stars_price(500).usd
    price_per_star = price_for_500_stars / 500
    gifts = bot.get_available_gifts().gifts
    gifts = filter(lambda x: x.id in settings.available_gifts, gifts)
    gifts = sorted(gifts, key=lambda x: x.star_count)

    result = []

    for gift in gifts:
        gift_price = gift.star_count * price_per_star
        gift_price = round(gift_price + gift_price / 100 * settings.gifts_markup, 2)
        gift_price_rub = USDT.usd_to_rub(gift_price)

        result.append(
            GiftModel(
                id=gift.id,
                emoji=gift.sticker.emoji,
                prices=PricesWithCurrency(
                    price_usd=PriceWithCurrency(currency="usd", price=gift_price),
                    price_rub=PriceWithCurrency(currency="rub", price=gift_price_rub),
                ),
            )
        )

    gifts_response = GiftsResponse(gifts=result)
    r.set("stars_site:gifts", gifts_response.model_dump_json(), ex=600)
    return gifts_response


@router.get(
    "/available_payment_methods",
    response_model=PaymentMethodsResponse,
    summary="Доступные платёжные методы",
    description=(
        "Возвращает отсортированный список платёжных методов, доступных для указанной суммы и типа заказа. "
        "Для `type=ton` доступ к методам TonConnect возможен только для авторизованных пользователей."
    ),
    responses={
        200: {"description": "Методы успешно получены."},
        403: {"description": "Доступ запрещён для `type=ton` и гостевой сессии."},
    },
)
def available_payment_methods(
    order_price: Annotated[
        float,
        Query(
            ge=0,
            description="Сумма заказа в USD, неотрицательное число.",
            examples=[0, 9.99, 100.0],
        ),
    ],
    order_type: Annotated[
        Item,
        Query(
            description="Тип заказа",
            alias="type",
            examples=["star", "premium", "ton", "gift"],
        ),
    ] = "star",
    principal: Principal = Depends(current_principal),
):
    """
    Логика отбора:
    * Базово исключаем TonConnect из выдачи.
    * Для **user** добавляем TonConnect (если удовлетворяет `min_amount`).
    * Если `order_type == "ton"`, фильтруем **только** TonConnect.
    * Итог сортируется по `-order, name`.
    """
    if order_type == "ton" and principal["kind"] != "user":
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: only user can use 'ton' order type",
        )
    methods = PaymentMethod.objects.filter(
        ~Q(system__name=PaymentSystem.Names.TON_CONNECT),
        system__is_active=True,
        min_amount__lte=order_price,
    )
    if principal["kind"] == "user":
        ton_methods = PaymentMethod.objects.filter(
            system__name=PaymentSystem.Names.TON_CONNECT,
            system__is_active=True,
            min_amount__lte=order_price,
        )
        methods = methods | ton_methods
    if order_type == "ton":
        methods = methods.filter(system__name=PaymentSystem.Names.TON_CONNECT)
    methods = methods.order_by("-order", "name")
    return PaymentMethodsResponse(
        methods=[
            PaymentMethodModel.model_validate(m, from_attributes=True) for m in methods
        ]
    )
