import json, redis, requests

r = redis.Redis(host="localhost", port=6379, decode_responses=True)


class TON:
    @classmethod
    def ton_to_usd(cls, usd: float, rate: float | None = None):
        rate = cls.get_rate()
        return float(usd * rate)

    @classmethod
    def usd_to_ton(cls, ton: float, rate: float | None = None):
        rate = cls.get_rate()
        return float(ton / rate)

    @staticmethod
    def get_rate() -> float:
        try:
            rate = float(r.get("ton_rate"))
        except TypeError:
            rate = None
        if rate is not None:
            return rate
        rate = None
        tries = 0
        s = requests.session()
        while tries < 3:
            tries += 1
            try:
                response = s.get(
                    "https://www.okx.com/api/v5/public/mark-price?instId=TON-USDT"
                ).json()
            except json.JSONDecodeError:
                continue
            try:
                rate = float(response["data"][0]["markPx"])
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
            else:
                break
        if rate:
            r.set("ton_rate", rate, ex=30)
        return rate


class USDT:
    @classmethod
    def rub_to_usd(cls, usd: float):
        rate = cls.get_rate()
        return float(usd / rate)

    @classmethod
    def usd_to_rub(cls, usdt: float):
        rate = cls.get_rate()
        return float(usdt * rate)

    @staticmethod
    def get_rate() -> float:
        try:
            rate = float(r.get("usdt_rate_rapira"))
        except TypeError:
            rate = None
        if rate is not None:
            return rate
        rate = None
        tries = 0
        s = requests.session()
        while tries < 3:
            tries += 1
            try:
                response = s.get("https://api.rapira.net/open/market/rates").json()
            except json.JSONDecodeError:
                continue
            try:
                for pair in response["data"]:
                    if pair["symbol"] == "USDT/RUB":
                        rate = float(pair["close"])
            except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                continue
            else:
                break
        if rate:
            r.set("usdt_rate_rapira", rate, ex=30)
            return rate
        else:
            from .cbrf import CBRF

            rate = CBRF.get_rate("usd")
            r.set("usdt_rate_rapira", rate, ex=30)

            return rate


__all__ = [
    "TON",
    "USDT",
]
