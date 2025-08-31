from typing import Optional

import requests

from ..models import BillSchema


def get_in_crypto(asset: str, amount: float):
    if asset in ["USDT", "BUSD", "USDC"]:
        return amount
    rate = requests.get(
        f"https://www.okx.com/api/v5/public/mark-price?instId={asset}-USDT"
    ).json()
    try:
        rate = float(rate["data"][0]["markPx"])
    except (ValueError, KeyError, IndexError):
        return 0
    return amount / rate


class CryptoPay:
    __api_key: str = ""
    __http: requests.Session
    __api_domain: str = "https://pay.crypt.bot"  # Mainnet

    def __init__(self, crytopay_api_key: str):
        self.__api_key = crytopay_api_key
        self.__http = requests.Session()
        self.__http.headers = {"Crypto-Pay-API-Token": self.__api_key}

    def get_me(self):
        return self.__request("getMe")

    def create_bill(
        self,
        payment_id: str,
        currency: str,
        amount: float,
        description: str,
        success_url: str | None = None,
    ) -> BillSchema:
        response = self.__request(
            "createInvoice",
            {
                "currency_type": "fiat",
                "fiat": currency,
                "amount": round(amount + amount * 0.03, 8),
                "description": description,
                "swap_to": "USDT",
                "paid_btn_url": success_url,
                "payload": payment_id,
            },
        )
        if not response["ok"]:
            return BillSchema(status=False)
        return BillSchema(
            id=str(response["result"]["invoice_id"]),
            url=response["result"]["pay_url"],
        )

    def get_invoice(self, invoice_id: int):
        response = self.__request("getInvoices", {"invoice_ids": invoice_id})  # 87336
        if not response["ok"]:
            return None
        if len(response["result"]["items"]) < 1:
            return None
        return response["result"]["items"][0]

    def __request(self, method_name: str, params: Optional[dict] = None):
        if params is None:
            params = {}
        response = self.__http.post(
            self.__api_domain + "/api/" + method_name, data=params
        ).json()
        return response
