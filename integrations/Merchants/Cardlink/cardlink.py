import json

import requests
from loguru import logger
from pydantic import BaseModel

from ..models import BillSchema


class BalanceSchema(BaseModel):
    status: bool = True
    balance: float | int
    freeze_balance: float | int


class CardLink:
    __slots__ = ["__shop_id", "__shop_key"]
    __shop_id: str
    __shop_key: str
    __base_url = "https://cardlink.link/api/v1"

    def __init__(self, shop_id: str, shop_key: str):
        self.__shop_id = shop_id
        self.__shop_key = shop_key

    def create_bill(
        self, order_id: str, amount: float, user_id: int, method: str = None
    ) -> BillSchema:
        url = f"{self.__base_url}/bill/create"
        headers = {
            "Authorization": "Bearer " + self.__shop_key,
        }
        amount = amount + amount * 0.005  # 0.5% commission
        amount = round(amount, 2)
        data = {
            "amount": "{:.2f}".format(amount),
            "shop_id": self.__shop_id,
            "order_id": order_id,
            "type": "normal",
            "currency_in": "RUB",
            "payer_pays_commission": "1",
            "payer_email": f"{user_id}@example.com",
        }
        data.update({"payment_method": method} if method else {})
        response = requests.post(url, data, headers=headers)
        try:
            result = response.json()
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON response: {response.text}")
            return BillSchema(status=False)
        if not result.get("success", False):
            logger.error(f"{response.status_code=} {result=}")
            return BillSchema(status=False)
        return BillSchema(id=result["bill_id"], url=result["link_page_url"])
