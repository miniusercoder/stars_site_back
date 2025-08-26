from fastapi import APIRouter
from redis import Redis

from fastapi_stars.schemas.info import BasePrices, PricesWithCurrency, PriceWithCurrency
from fastapi_stars.settings import settings
from integrations.Currencies import TON, USDT
from integrations.fragment import FragmentAPI
from integrations.wallet.helpers import get_wallet

router = APIRouter()
r = Redis(host="localhost", port=6379, decode_responses=True)


@router.get("/prices", tags=["info"], response_model=BasePrices)
def get_prices():
    cached_prices = r.get("stars_site:base_prices")
    if cached_prices:
        return BasePrices.model_validate_json(cached_prices)

    ton_price_in_usd = TON.ton_to_usd(1)
    ton_price_in_rub = USDT.usd_to_rub(ton_price_in_usd)

    fragment = FragmentAPI(get_wallet())
    price_for_500_stars = fragment.get_stars_price(500).usd
    stars_markup = settings.stars_markup
    price_for_500_stars = price_for_500_stars + price_for_500_stars * stars_markup / 100
    price_per_star_usd = price_for_500_stars / 500
    price_per_star_rub = USDT.usd_to_rub(price_per_star_usd)

    prices = BasePrices(
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

    r.set("stars_site:base_prices", prices.model_dump_json(), ex=300)
    return prices
