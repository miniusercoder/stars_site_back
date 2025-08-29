import random

from fastapi import APIRouter, Depends
from redis import Redis

from django_stars.stars_app.models import GuestSession
from fastapi_stars.api.deps import current_principal
from fastapi_stars.schemas.auth import Principal
from fastapi_stars.schemas.order import OrderIn, OrderResponse

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
    return OrderResponse(order_id=random.randint(1, 10000), pay_url="https:///wata.pro")
