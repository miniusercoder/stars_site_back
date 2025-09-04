from typing import Annotated, Optional

from django.db.models import Q, Sum
from fastapi import APIRouter, Depends
from fastapi.params import Query

from django_stars.stars_app.models import Order, Payment, User
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
)
from integrations.Currencies import USDT

router = APIRouter()


def get_my_orders_stats(user: User, order_type: Order.Type) -> tuple[int, float]:
    orders = Order.objects.filter(
        is_refund=False,
        user=user,
        type=order_type,
        status__in=(Order.Status.COMPLETED, Order.Status.BLOCKCHAIN_WAITING),
    )
    orders_amount = orders.aggregate(Sum("amount"))["amount__sum"]
    orders_price = orders.aggregate(Sum("price"))["price__sum"]
    return orders_amount or 0, orders_price or 0


@router.get("/me", response_model=UserOut)
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


@router.post("/ref_alias", response_model=SuccessResponse)
def set_ref_alias(
    ref_alias: RefAliasIn, principal: Principal = Depends(user_principal)
):
    user = principal["user"]
    user.ref_alias = ref_alias.ref_alias
    user.save(update_fields=("ref_alias",))
    return SuccessResponse()


@router.get("/orders", response_model=OrdersResponse)
def get_my_orders(
    search_query: Annotated[Optional[str], Query(...)] = None,
    order_type: Annotated[Optional[Order.Type], Query(...)] = None,
    offset: Annotated[int, Query(...)] = 0,
    on_page: Annotated[int, Query(...)] = 10,
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
    )[offset : offset + on_page]
    return OrdersResponse(
        items=[
            OrderModel.model_validate(order, from_attributes=True)
            for order in my_orders
        ]
    )


@router.get("/payments", response_model=PaymentsResponse)
def get_my_payments(
    offset: Annotated[int, Query(...)] = 0,
    on_page: Annotated[int, Query(...)] = 10,
    principal: Principal = Depends(user_principal),
):
    user = principal["user"]
    my_payments = (Payment.objects.filter(order__user=user).order_by("-created_at"))[
        offset : offset + on_page
    ]
    return PaymentsResponse(
        items=[
            PaymentModel.model_validate(payment, from_attributes=True)
            for payment in my_payments
        ]
    )
