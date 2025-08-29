from fastapi import APIRouter
from redis import Redis

from fastapi_stars.schemas.order import OrderIn, OrderResponse

router = APIRouter()
r = Redis(host="localhost", port=6379, decode_responses=True)


@router.post("/create", tags=["orders"], response_model=OrderResponse)
def create_order(order_in: OrderIn):
    pass
