import random

from fastapi import APIRouter, Depends
from redis import Redis

from django_stars.stars_app.models import GuestSession
from fastapi_stars.api.deps import current_principal
from fastapi_stars.schemas.auth import Principal
from fastapi_stars.schemas.order import OrderIn, OrderResponse, OrderItem
from fastapi_stars.utils.prices import get_stars_price
from integrations.fragment import FragmentAPI
from integrations.wallet.helpers import get_wallet

router = APIRouter()
r = Redis(host="localhost", port=6379, decode_responses=True)


@router.post("/create", response_model=OrderResponse)
def create_order(order_in: OrderIn, principal: Principal = Depends(current_principal)):
    if principal["kind"] == "guest":
        gs, _ = GuestSession.objects.get_or_create(id=principal["payload"]["sid"])
        user = None
    else:
        gs = None
        user = principal["user"]
    fragment = FragmentAPI(get_wallet())
    match order_in.item_type:
        case "star":
            if not (50 <= order_in.amount <= 10000):
                return OrderResponse(success=False, error="invalid_amount")
            try:
                fragment.get_stars_recipient(order_in.recipient)
            except ValueError:
                return OrderResponse(success=False, error="invalid_recipient")
            order_price = get_stars_price(order_in.amount)
    return OrderResponse(
        success=True,
        result=OrderItem(
            order_id=random.randint(1, 10000), pay_url="https:///wata.pro"
        ),
    )
