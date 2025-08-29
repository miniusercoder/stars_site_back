from fastapi import APIRouter, Depends
from redis import Redis

from fastapi_stars.api.deps import current_principal
from fastapi_stars.schemas.auth import Principal
from fastapi_stars.schemas.order import OrderIn, OrderResponse

router = APIRouter()
r = Redis(host="localhost", port=6379, decode_responses=True)


@router.post("/create", response_model=OrderResponse)
def create_order(order_in: OrderIn, _: Principal = Depends(current_principal)):
    pass
