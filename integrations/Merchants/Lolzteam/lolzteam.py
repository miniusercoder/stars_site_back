import json

import requests
from loguru import logger

from fastapi_stars.settings import settings
from ..models import BillSchema


class LolzTeam:
    __slots__ = ["__token", "__merchant_id"]
    __token: str
    __merchant_id: str

    API_URL = "https://prod-api.lzt.market"
    COMMENT = "Payment for HelperStars"

    def __init__(self, merchant_id: str, token: str):
        self.__merchant_id = merchant_id
        self.__token = token

    def create_bill(self, order_id: str, amount: float, return_url: str) -> BillSchema:
        amount += amount * 0.05

        payload = {
            "currency": "rub",
            "amount": amount,
            "payment_id": order_id,
            "comment": self.COMMENT,
            "url_success": return_url,
            "url_callback": f"{settings.site_url}/api/merchant/lolzteam",
            "merchant_id": self.__merchant_id,
        }

        try:
            response = requests.post(
                f"{self.API_URL}/invoice",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.__token}",
                },
            )
        except requests.RequestException as e:
            logger.error(f"[LolzTeam] Request failed: {e}")
            return BillSchema(status=False)

        try:
            response_data = response.json()
        except json.JSONDecodeError:
            logger.error(f"[LolzTeam] Invalid JSON response {response.text}")
            return BillSchema(status=False)

        invoice = response_data.get("invoice")
        if not invoice or not invoice.get("payment_id") or not invoice.get("url"):
            logger.error(f"[LolzTeam] Failed to create bill: {response_data}")
            return BillSchema(status=False)

        return BillSchema(
            id=invoice["payment_id"],
            url=invoice["url"],
        )
