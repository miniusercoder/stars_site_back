import re
from typing import Literal, Tuple, Annotated

from django.db.models import Sum
from django.utils import timezone
from fastapi import APIRouter, Path, HTTPException, Depends, status
from redis import Redis

from django_stars.stars_app.models import Price, Order
from fastapi_stars.api.deps import current_principal
from fastapi_stars.schemas.auth import Principal
from fastapi_stars.schemas.info import (
    HeaderPrices,
    PricesWithCurrency,
    PriceWithCurrency,
    Item,
    ProjectStats,
    TelegramUserResponse,
    TelegramUserIn,
    TelegramUser,
    GiftsResponse,
    GiftModel,
)
from fastapi_stars.settings import settings
from integrations.Currencies import TON, USDT
from integrations.fragment import FragmentAPI
from integrations.telegram_bot import bot
from integrations.wallet.helpers import get_wallet

router = APIRouter()
r = Redis(host="localhost", port=6379, decode_responses=True)


def _get_premium_price(amount: int) -> Tuple[float, float, float]:
    if amount not in {3, 6, 12}:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invalid quantity for premium order"
        )
    amount: Literal[3, 6, 12]
    try:
        if amount == 3:
            price = Price.objects.get(type=Price.Type.PREMIUM_3)
        elif amount == 6:
            price = Price.objects.get(type=Price.Type.PREMIUM_6)
        elif amount == 12:
            price = Price.objects.get(type=Price.Type.PREMIUM_12)
    except Price.DoesNotExist:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invalid quantity for premium order"
        )
    return price.white_price, price.price, TON.usd_to_ton(price.white_price)


@router.get("/project_stats", response_model=ProjectStats)
def get_project_stats():
    cached_stats = r.get("stars_site:project_stats")
    if cached_stats:
        return ProjectStats.model_validate_json(cached_stats)

    today_date = timezone.now().date()
    stars_today = (
        Order.objects.filter(
            is_refund=False,
            created_at__gte=today_date,
            status=Order.Status.COMPLETED,
            type=Order.Type.STARS,
        ).aggregate(Sum("amount"))["amount__sum"]
        or 0
    )
    stars_total = (
        Order.objects.filter(
            is_refund=False,
            status=Order.Status.COMPLETED,
            type=Order.Type.STARS,
        ).aggregate(Sum("amount"))["amount__sum"]
        or 0
    )

    premium_today = (
        Order.objects.filter(
            is_refund=False,
            created_at__gte=today_date,
            status=Order.Status.COMPLETED,
            type=Order.Type.PREMIUM,
        ).aggregate(Sum("amount"))["amount__sum"]
        or 0
    )
    premium_total = (
        Order.objects.filter(
            is_refund=False,
            status=Order.Status.COMPLETED,
            type=Order.Type.PREMIUM,
        ).aggregate(Sum("amount"))["amount__sum"]
        or 0
    )

    project_stats = ProjectStats(
        stars_today=stars_today,
        stars_total=stars_total,
        premium_today=premium_today,
        premium_total=premium_total,
    )

    r.set("stars_site:project_stats", project_stats.model_dump_json(), ex=600)
    return project_stats


@router.post("/validate_user", response_model=TelegramUserResponse)
def validate_telegram_user(
    user: TelegramUserIn, _: Principal = Depends(current_principal)
):
    cached = r.get(f"stars_site:tg_user_{user.username}")
    if cached:
        return TelegramUserResponse.model_validate_json(cached)

    fragment = FragmentAPI(get_wallet())
    try:
        recipient = fragment.get_stars_recipient(user.username)
    except ValueError:
        result = TelegramUserResponse(success=False, error="not_found")
    else:
        recipient.photo = (
            re.findall(r'"([^"]+)"', recipient.photo)[0] if recipient.photo else None
        )
        result = TelegramUserResponse(
            success=True,
            result=TelegramUser.model_validate(recipient, from_attributes=True),
        )
    r.set(f"stars_site:tg_user_{user.username}", result.model_dump_json(), ex=300)
    return result


@router.get("/header_prices", response_model=HeaderPrices)
def get_header_prices():
    cached_prices = r.get("stars_site:base_prices")
    if cached_prices:
        return HeaderPrices.model_validate_json(cached_prices)

    ton_price_in_usd = TON.ton_to_usd(1)
    ton_price_in_rub = USDT.usd_to_rub(ton_price_in_usd)

    fragment = FragmentAPI(get_wallet())
    price_for_500_stars = fragment.get_stars_price(500).usd
    stars_markup = settings.stars_markup
    price_for_500_stars = price_for_500_stars + price_for_500_stars * stars_markup / 100
    price_per_star_usd = price_for_500_stars / 500
    price_per_star_rub = USDT.usd_to_rub(price_per_star_usd)

    prices = HeaderPrices(
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

    r.set("stars_site:base_prices", prices.model_dump_json(), ex=60)
    return prices


@router.get("/price/{type}/{amount}", response_model=PricesWithCurrency)
def get_order_price(
    item_type: Annotated[Item, Path(alias="type")],
    amount: Annotated[
        int,
        Path(
            gt=0,
            description=(
                "Количество.\n"
                "Для 'star' — от 50 до 10000.\n"
                "Для 'premium' — только одно из {3, 6, 12}."
            ),
        ),
    ],
    _: Principal = Depends(current_principal),
):
    if item_type == "star":
        if not (50 <= amount <= 10000):
            raise HTTPException(
                status_code=422,
                detail={
                    "loc": ["path", "amount"],
                    "msg": "Для item_type='star' параметр 'amount' должен быть в диапазоне 50..10000.",
                    "type": "value_error.amount.range",
                },
            )

        cached_price = r.get("stars_site:star_price")
        if cached_price:
            price_per_star_usd = cached_price
        else:
            fragment = FragmentAPI(get_wallet())
            price_for_stars = fragment.get_stars_price(amount).usd
            stars_markup = settings.stars_markup
            price_for_stars = price_for_stars + price_for_stars * stars_markup / 100
            price_per_star_usd = price_for_stars
        price_per_star_rub = USDT.usd_to_rub(price_per_star_usd)

        prices = PricesWithCurrency(
            price_usd=PriceWithCurrency(currency="usd", price=price_per_star_usd),
            price_rub=PriceWithCurrency(currency="rub", price=price_per_star_rub),
        )
        r.set(f"stars_site:star_price_{amount}", prices.model_dump_json(), ex=60)
        return prices
    elif item_type == "premium":
        if amount not in {3, 6, 12}:
            raise HTTPException(
                status_code=422,
                detail={
                    "loc": ["path", "amount"],
                    "msg": "Для item_type='premium' параметр 'amount' должен быть одним из {3, 6, 12}.",
                    "type": "value_error.amount.literal",
                },
            )

        cached_prices = r.get(f"stars_site:premium_price_{amount}")
        if cached_prices:
            return PricesWithCurrency.model_validate_json(cached_prices)

        _, price_per_premium_usd, _ = _get_premium_price(amount)
        price_per_premium_rub = USDT.usd_to_rub(price_per_premium_usd)

        prices = PricesWithCurrency(
            price_usd=PriceWithCurrency(currency="usd", price=price_per_premium_usd),
            price_rub=PriceWithCurrency(currency="rub", price=price_per_premium_rub),
        )
        r.set(f"stars_site:premium_price_{amount}", prices.model_dump_json(), ex=60)
        return prices
    elif item_type == "ton":
        ton_price_in_usd = TON.ton_to_usd(amount)
        ton_price_in_rub = USDT.usd_to_rub(ton_price_in_usd)

        prices = PricesWithCurrency(
            price_usd=PriceWithCurrency(currency="usd", price=ton_price_in_usd),
            price_rub=PriceWithCurrency(currency="rub", price=ton_price_in_rub),
        )
        return prices


@router.get("/gifts", response_model=GiftsResponse)
def get_gifts(_: Principal = Depends(current_principal)):
    cached = r.get("stars_site:gifts")
    if cached:
        return GiftsResponse.model_validate_json(cached)

    fragment = FragmentAPI(get_wallet())
    price_for_500_stars = fragment.get_stars_price(500).usd
    price_per_star = price_for_500_stars / 500
    gifts = bot.get_available_gifts().gifts
    gifts = filter(lambda x: x.id in settings.available_gifts, gifts)
    gifts = sorted(gifts, key=lambda x: x.star_count)

    result = []

    for gift in gifts:
        gift_price = gift.star_count * price_per_star
        gift_price = round(gift_price + gift_price / 100 * settings.gifts_markup, 2)
        gift_price_rub = USDT.usd_to_rub(gift_price)

        result.append(
            GiftModel(
                id=gift.id,
                emoji=gift.sticker.emoji,
                prices=PricesWithCurrency(
                    price_usd=PriceWithCurrency(currency="usd", price=gift_price),
                    price_rub=PriceWithCurrency(currency="rub", price=gift_price_rub),
                ),
            )
        )

    gifts_response = GiftsResponse(gifts=result)
    r.set("stars_site:gifts", gifts_response.model_dump_json(), ex=600)
    return gifts_response
