import hashlib
import hmac
import json
import time

import requests
from loguru import logger
from pydantic import BaseModel


class BillSchema(BaseModel):
    status: bool = True
    id: str | int = ""
    url: str = ""


class BalanceSchema(BaseModel):
    status: bool = True
    balance: float | int
    freeze_balance: float | int


class FreeKassa:
    __shop_id: str | int
    __shop_secret: str
    __shop_api_key: str
    __shop_email_domain: str
    __shop_ip: str
    minimals: dict[str, float]
    minimals = {
        "36": 10,
        "44": 10,
    }

    def __init__(
        self, shop_id: str | int = "", shop_secret: str = "", shop_api_Key: str = ""
    ):
        self.__shop_id = shop_id
        self.__shop_secret = shop_secret
        self.__shop_api_key = shop_api_Key

    def create_bill(
        self, order_id: str, amount: float, method: str, buyer_ip: str, email: str
    ) -> BillSchema:
        """
        Создание счета
        :param buyer_ip: IP покупателя
        :param order_id: Локальный ID заказа
        :param amount: Сумма в рублях
        :param method: Метод оплаты
        :return: Объект счета (BillSchema)
        """
        url = "https://api.fk.life/v1/orders/create"
        method = {"i": method} if method else {}
        amount = "{:.2f}".format(amount)
        data = {
            "shopId": self.__shop_id,
            "nonce": str(int(round(time.time() * 1000))),
            "paymentId": order_id,
            "ip": buyer_ip,
            "email": email,
            "amount": amount,
            "currency": "RUB",
        }
        data.update(method)
        sorted_items = sorted(data.items())
        sign_str = "|".join(str(v) for k, v in sorted_items)
        sign = hmac.new(
            self.__shop_api_key.encode(), sign_str.encode(), hashlib.sha256
        ).hexdigest()
        data["signature"] = sign
        result = requests.post(url, json=data)
        try:
            result = result.json()
        except json.JSONDecodeError:
            logger.error(f"FreeKassa: Failed to parse JSON response {result.text=}")
            return BillSchema(status=False)
        if not result.get("location"):
            logger.error(f"FreeKassa: Failed to get url {result=} {data=}")
            return BillSchema(status=False)
        return BillSchema(id=result["orderId"], url=result["location"])

    def create_sci(self, payment_id: str, amount: float) -> BillSchema:
        key = ":".join(
            map(str, [self.__shop_id, amount, self.__shop_secret, "RUB", payment_id])
        )
        sign = hashlib.md5(key.encode())
        link = (
            "https://pay.freekassa.com/?"
            f"m={self.__shop_id}&"
            f"oa={amount}&"
            f"currency=RUB&"
            f"o={payment_id}&"
            f"s={sign.hexdigest()}"
        )
        return BillSchema(id=payment_id, url=link)
