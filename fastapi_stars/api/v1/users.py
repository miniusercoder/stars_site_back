from typing import Annotated, Optional

from django.db.models import Q
from fastapi import APIRouter, Depends
from fastapi.params import Query

from django_stars.stars_app.models import Order, Payment
from fastapi_stars.api.deps import Principal, user_principal
from fastapi_stars.schemas.users import (
    UserOut,
    SuccessResponse,
    RefAliasIn,
    OrdersResponse,
    OrderModel,
    PaymentsResponse,
    PaymentModel,
)

router = APIRouter()


@router.get("/me", response_model=UserOut)
def me(principal: Principal = Depends(user_principal)):
    user = principal["user"]
    return UserOut.model_validate(user)


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
    my_payments = (Payment.objects.filter(user=user))[offset : offset + on_page]
    return PaymentsResponse(
        items=[
            PaymentModel.model_validate(payment, from_attributes=True)
            for payment in my_payments
        ]
    )
