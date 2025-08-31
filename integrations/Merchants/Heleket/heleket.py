import json
from base64 import b64encode
from hashlib import md5

import requests
from loguru import logger

from fastapi_stars.settings import settings
from ..models import BillSchema


class Heleket:
    __slots__ = ["__shop_key", "__shop_id"]
    __shop_id: str | int
    __shop_key: str

    def __init__(self, shop_id: str | int, key: str):
        self.__shop_id = shop_id
        self.__shop_key = key

    def create_bill(
        self, order_id: str, amount: float, success_url: str | None = None
    ) -> BillSchema:
        params = {
            "amount": "{:.2f}".format(amount),
            "currency": "USD",
            "order_id": order_id,
            "url_return": success_url,
            "url_callback": f"{settings.site_url}/api/merchant/heleket",
            "subtract": 100,
            "course_source": "Binance",
        }
        sign = md5(
            b64encode(json.dumps(params).encode("utf-8"))
            + self.__shop_key.encode("utf-8")
        ).hexdigest()
        try:
            response = requests.post(
                "https://api.heleket.com/v1/payment",
                json=params,
                headers={
                    "merchant": self.__shop_id,
                    "sign": sign,
                },
            )
        except requests.RequestException:
            return BillSchema(status=False)
        try:
            response = response.json()
        except json.JSONDecodeError:
            with open(f"logs/heleket_{order_id}.html", "wb") as f:
                f.write(response.content)
            return BillSchema(status=False)
        if (
            not isinstance(response, dict)
            or not response.get("result")
            or not response["result"].get("uuid")
            or not response["result"].get("url")
        ):
            logger.error(f"[Heleket] Failed to create bill: {response}")
            return BillSchema(status=False)
        response = response["result"]
        return BillSchema(
            id=response["uuid"],
            url=response["url"],
        )
