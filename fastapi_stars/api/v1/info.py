from fastapi import APIRouter
from fastapi_cache.decorator import cache

from fastapi_stars.schemas.info import BasePrices, PricesWithCurrency, PriceWithCurrency
from fastapi_stars.settings import settings
from integrations.Currencies import TON, USDT
from integrations.fragment import FragmentAPI
from integrations.wallet.helpers import get_wallet

router = APIRouter()


@router.get("/prices", tags=["info"], response_model=BasePrices)
@cache(expire=60)
def get_prices():
    ton_price_in_usd = TON.ton_to_usd(1)
    ton_price_in_rub = USDT.usd_to_rub(ton_price_in_usd)

    fragment = FragmentAPI(get_wallet())
    price_for_500_stars = fragment.get_stars_price(500).usd
    stars_markup = settings.stars_markup
    price_for_500_stars = price_for_500_stars + price_for_500_stars * stars_markup / 100
    price_per_star_usd = price_for_500_stars / 500
    price_per_star_rub = USDT.usd_to_rub(price_per_star_usd)

    return BasePrices(
        ton=PricesWithCurrency(
            price_usd=PriceWithCurrency(
                currency="usd",
                price=ton_price_in_usd,
            ),
            price_rub=PriceWithCurrency(
                currency="rub",
                price=ton_price_in_rub,
            ),
        ),
        star=PricesWithCurrency(
            price_usd=PriceWithCurrency(
                currency="usd",
                price=price_per_star_usd,
            ),
            price_rub=PriceWithCurrency(
                currency="rub",
                price=price_per_star_rub,
            ),
        ),
    )
