from typing import Literal

from django_stars.stars_app.models import Price
from fastapi_stars.settings import settings
from integrations.Currencies import TON
from integrations.fragment import FragmentAPI
from integrations.wallet.helpers import get_wallet


def get_stars_price(amount: int) -> tuple[float, float]:
    """
    :param amount: Количество звёзд
    :return: (price_with_markup, white_price)
    """

    fragment = FragmentAPI(get_wallet())
    white_price = fragment.get_stars_price(amount).usd
    stars_markup = settings.stars_markup
    price = float(white_price + white_price * stars_markup / 100)
    return price, white_price


def get_premium_price(amount: Literal[3, 6, 12]) -> tuple[float, float]:
    if amount not in {3, 6, 12}:
        raise ValueError("Invalid quantity for premium order")
    try:
        if amount == 3:
            price = Price.objects.get(type=Price.Type.PREMIUM_3)
        elif amount == 6:
            price = Price.objects.get(type=Price.Type.PREMIUM_6)
        elif amount == 12:
            price = Price.objects.get(type=Price.Type.PREMIUM_12)
        else:
            raise ValueError("Invalid quantity for premium order")
    except Price.DoesNotExist:
        raise ValueError("Invalid quantity for premium order")
    return price.price, price.white_price


def get_ton_price(amount: float) -> tuple[float, float]:
    white_price = TON.ton_to_usd(amount)
    price = float(white_price + white_price * settings.ton_markup / 100)
    return price, white_price
