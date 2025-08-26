import json

import redis
import requests

r = redis.Redis(host="localhost", port=6379, decode_responses=True)


class CBRF:
    @staticmethod
    def get_rate(currency: str = "USD") -> float:
        """
        Получение курса валюты
        :param currency: Код валюты
        :return: Курс валюты
        """
        rate = None
        tries = 0
        s = requests.session()
        while tries < 3:
            tries += 1
            response = s.get("https://www.cbr-xml-daily.ru/daily_json.js")
            try:
                rate = float(
                    response.json()["Valute"][currency]["Value"]
                    / response.json()["Valute"][currency]["Nominal"]
                )
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
            else:
                break
        if rate:
            r.set(f"cbrf_{currency}", rate, ex=3600)
        return rate
