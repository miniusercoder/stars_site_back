from typing import Annotated, Optional

from django.db.models import Q, Sum, Count
from fastapi import APIRouter, Depends
from fastapi.params import Query

from django_stars.stars_app.models import Order, Payment, User, Referral
from fastapi_stars.api.deps import Principal, user_principal
from fastapi_stars.schemas.info import PriceWithCurrency, PricesWithCurrency
from fastapi_stars.schemas.users import (
    UserOut,
    SuccessResponse,
    RefAliasIn,
    OrdersResponse,
    OrderModel,
    PaymentsResponse,
    PaymentModel,
    UserStatistic,
    StatsForOrderType,
    ReferralsResponse,
    ReferralItem,
    ReferralsCountResponse,
)
from integrations.Currencies import USDT

router = APIRouter()


def get_my_orders_stats(user: User, order_type: Order.Type) -> tuple[int, float]:
    """Внутренняя утилита для агрегации статистики заказов пользователя по типу."""
    orders = Order.objects.filter(
        is_refund=False,
        user=user,
        type=order_type,
        status__in=(Order.Status.COMPLETED, Order.Status.BLOCKCHAIN_WAITING),
    )
    orders_amount = orders.aggregate(Sum("amount"))["amount__sum"]
    orders_price = orders.aggregate(Sum("price"))["price__sum"]
    return orders_amount or 0, orders_price or 0


@router.get(
    "/me",
    response_model=UserOut,
    summary="Мои данные и сводная статистика",
    description=(
        "Возвращает публичные данные текущего пользователя и агрегированную статистику "
        "по заказам (STARS, PREMIUM, TON), а также общую сумму пополнений (deposit) "
        "в привязке к курсам USD и RUB."
    ),
    responses={
        200: {"description": "Успешное получение данных пользователя и статистики"},
        401: {"description": "Недействительная сессия/тип токена."},
    },
)
def me(principal: Principal = Depends(user_principal)):
    stars_stats = get_my_orders_stats(principal["user"], Order.Type.STARS)
    premium_stats = get_my_orders_stats(principal["user"], Order.Type.PREMIUM)
    ton_stats = get_my_orders_stats(principal["user"], Order.Type.TON)
    total_deposit = (
        Payment.objects.filter(
            order__user=principal["user"], status=Payment.Status.CONFIRMED
        ).aggregate(Sum("sum"))["sum__sum"]
        or 0
    )
    user_stats = UserStatistic(
        stars=StatsForOrderType(
            amount=stars_stats[0],
            price=PricesWithCurrency(
                price_usd=PriceWithCurrency(price=stars_stats[1], currency="usd"),
                price_rub=PriceWithCurrency(
                    price=USDT.usd_to_rub(stars_stats[1]), currency="rub"
                ),
            ),
        ),
        premium=StatsForOrderType(
            amount=premium_stats[0],
            price=PricesWithCurrency(
                price_usd=PriceWithCurrency(price=premium_stats[1], currency="usd"),
                price_rub=PriceWithCurrency(
                    price=USDT.usd_to_rub(premium_stats[1]), currency="rub"
                ),
            ),
        ),
        ton=StatsForOrderType(
            amount=ton_stats[0],
            price=PricesWithCurrency(
                price_usd=PriceWithCurrency(price=ton_stats[1], currency="usd"),
                price_rub=PriceWithCurrency(
                    price=USDT.usd_to_rub(ton_stats[1]), currency="rub"
                ),
            ),
        ),
        deposit=PricesWithCurrency(
            price_usd=PriceWithCurrency(price=total_deposit, currency="usd"),
            price_rub=PriceWithCurrency(
                price=USDT.usd_to_rub(total_deposit), currency="rub"
            ),
        ),
    )
    user = principal["user"]
    return UserOut(
        id=user.id,
        wallet_address=user.wallet_address,
        ref_alias=user.ref_alias,
        stats=user_stats,
    )


@router.post(
    "/ref_alias",
    response_model=SuccessResponse,
    summary="Установить реферальный алиас",
    description=(
        "Устанавливает или обновляет реферальный алиас текущего пользователя. "
        "Алиас должен быть длиной 5–64 символа."
    ),
    responses={
        200: {"description": "Алиас успешно сохранён"},
        400: {"description": "Невалидный алиас (длина, формат и т.п.)"},
        401: {"description": "Недействительная сессия/тип токена."},
    },
)
def set_ref_alias(
    ref_alias: RefAliasIn, principal: Principal = Depends(user_principal)
):
    user = principal["user"]
    user.ref_alias = ref_alias.ref_alias
    user.save(update_fields=("ref_alias",))
    return SuccessResponse(success=True)


@router.get(
    "/orders",
    response_model=OrdersResponse,
    summary="Мои заказы (список с фильтрами и пагинацией)",
    description=(
        "Возвращает список заказов текущего пользователя. "
        "Можно фильтровать по типу заказа и искать по `recipient_username`. "
        "Статусы `CANCEL` и `CREATING` исключаются."
    ),
    responses={
        200: {"description": "Список заказов с пагинацией"},
        401: {"description": "Недействительная сессия/тип токена."},
    },
)
@router.get("/orders", response_model=OrdersResponse, summary="Мои заказы ...")
def get_my_orders(
    search_query: Annotated[
        Optional[str],
        Query(
            title="Поиск",
            description="Подстрочный поиск по recipient_username.",
            example="john",
        ),
    ] = None,
    order_type: Annotated[
        Optional[Order.Type],
        Query(
            title="Тип заказа",
            description="Фильтр по типу заказа (STARS, PREMIUM, TON).",
            example="STARS",
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(
            ge=0,
            title="Смещение",
            description="Сколько элементов пропустить.",
            example=0,
        ),
    ] = 0,
    on_page: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            title="На странице",
            description="Максимум элементов в ответе.",
            example=10,
        ),
    ] = 10,
    principal: Principal = Depends(user_principal),
):
    user = principal["user"]
    search_query = search_query or ""
    order_type = Q(type=order_type) if order_type else Q()
    my_orders = (
        Order.objects.filter(
            ~Q(status__in=(Order.Status.CANCEL, Order.Status.CREATING)), user=user
        )
        .filter(recipient_username__icontains=search_query)
        .filter(order_type)
        .order_by("-id")
    )
    total_orders = my_orders.count()
    my_orders = my_orders[offset : offset + on_page]
    return OrdersResponse(
        items=[
            OrderModel.model_validate(order, from_attributes=True)
            for order in my_orders
        ],
        total=total_orders,
    )


@router.get(
    "/payments",
    response_model=PaymentsResponse,
    summary="Мои платежи (список с пагинацией)",
    description="Возвращает список платежей по заказам текущего пользователя.",
    responses={
        200: {"description": "Список платежей с пагинацией"},
        401: {"description": "Недействительная сессия/тип токена."},
    },
)
@router.get("/payments", response_model=PaymentsResponse, summary="Мои платежи ...")
def get_my_payments(
    on_page: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            title="На странице",
            description="Максимум элементов в ответе.",
            example=10,
        ),
    ] = 10,
    offset: Annotated[
        int,
        Query(
            ge=0,
            le=100,
            title="Смещение",
            description="Сколько элементов пропустить.",
            example=0,
        ),
    ] = 0,
    principal: Principal = Depends(user_principal),
):
    user = principal["user"]
    my_payments = Payment.objects.filter(order__user=user).order_by("-created_at")
    total_payments = my_payments.count()
    my_payments = my_payments[offset : offset + on_page]
    return PaymentsResponse(
        items=[
            PaymentModel.model_validate(payment, from_attributes=True)
            for payment in my_payments
        ],
        total=total_payments,
    )


@router.get(
    "/referrals",
    response_model=ReferralsResponse,
    summary="Мои рефералы (список по уровням, поиск и пагинация)",
    description=(
        "Возвращает список рефералов текущего пользователя. "
        "Поддерживает фильтрацию по уровню (1–3), поиск по кошельку/алиасу приглашённого, "
        "а также пагинацию."
    ),
    responses={
        200: {"description": "Список рефералов с пагинацией"},
        401: {"description": "Недействительная сессия/тип токена."},
    },
)
@router.get("/referrals", response_model=ReferralsResponse, summary="Мои рефералы ...")
def get_my_referrals(
    search_query: Annotated[
        Optional[str],
        Query(
            description="Поиск по wallet или алиасу приглашённого.",
            example="EQB1...abcd",  # или "my_invite"
        ),
    ] = None,
    level: Annotated[
        Optional[int],
        Query(
            ge=1,
            le=3,
            description="Уровень реферала (1–3).",
            example=1,
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(
            ge=0,
            description="Смещение (для пагинации).",
            example=0,
        ),
    ] = 0,
    on_page: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Количество элементов на странице.",
            example=10,
        ),
    ] = 10,
    principal: "Principal" = Depends(user_principal),
):
    user = principal["user"]

    qs = (
        Referral.objects.filter(referrer=user)
        .select_related("referred")
        .order_by("level", "-id")
    )

    if level:
        qs = qs.filter(level=level)

    if search_query:
        sq = search_query.strip()
        if sq:
            qs = qs.filter(
                Q(referred__wallet_address__icontains=sq)
                | Q(referred__ref_alias__icontains=sq)
            )

    total = qs.count()
    qs = qs[offset : offset + on_page]

    items = [
        ReferralItem(
            wallet_address=f"{ref.referred.wallet_address[:4]}...{ref.referred.wallet_address[-4:]}",
            level=ref.level,
            profit=float(ref.profit),
        )
        for ref in qs
    ]

    return ReferralsResponse(items=items, total=total)


@router.get(
    "/referrals/count",
    response_model=ReferralsCountResponse,
    summary="Получить количество рефералов по уровням",
    description=(
        "Возвращает общее количество рефералов и 1, 2 и 3 уровней по отдельности для текущего пользователя."
    ),
    responses={
        200: {"description": "Успешный ответ с количеством рефералов по уровням"},
        401: {"description": "Недействительная сессия/тип токена."},
    },
)
def get_my_referrals_count(principal: "Principal" = Depends(user_principal)):
    user = principal["user"]
    referrals = (
        Referral.objects.filter(referrer=user)
        .values("level")
        .annotate(count=Count("id"))
    )

    referrals_profit = Referral.objects.filter(referrer=user).aggregate(
        profit=Sum("profit")
    )
    referrals_profit_sum = referrals_profit["profit"] or 0.0

    level_counts = {1: 0, 2: 0, 3: 0}
    for entry in referrals:
        level_counts[entry["level"]] = entry["count"]

    total_count = sum(level_counts.values())

    return ReferralsCountResponse(
        level_1=level_counts[1],
        level_2=level_counts[2],
        level_3=level_counts[3],
        total=total_count,
        total_reward=referrals_profit_sum,
    )
