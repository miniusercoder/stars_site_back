from typing import assert_never
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from loguru import logger
from pytoniq_core import Address
from redis import Redis
from tonutils.utils import to_nano

from django_stars.stars_app.models import (
    GuestSession,
    PaymentMethod,
    Order,
    Payment,
    PaymentSystem,
    TonTransaction,
)
from fastapi_stars.api.deps import current_principal
from fastapi_stars.schemas.auth import Principal
from fastapi_stars.schemas.order import OrderIn, OrderResponse, OrderItem
from fastapi_stars.settings import settings
from fastapi_stars.utils.prices import get_stars_price, get_premium_price, get_ton_price
from fastapi_stars.utils.tc_messages import build_tonconnect_message
from integrations.Currencies import TON
from integrations.Merchants.utils import generate_pay_link
from integrations.fragment import FragmentAPI
from integrations.gifts import get_gift_sender
from integrations.telegram_bot import bot
from integrations.wallet.helpers import get_wallet

router = APIRouter()
r = Redis(host="localhost", port=6379, decode_responses=True)


@router.post(
    "/create",
    response_model=OrderResponse,
    summary="Создать заказ и платёж",
    description=(
        "Создаёт заказ для типов: `star`, `premium`, `ton`, `gift` и инициирует платёж. "
        "Возвращает либо `pay_url` (для внешних мерчантов), либо объект `ton_transaction` (для TonConnect). "
        "Гости могут оплачивать все типы, **кроме** `ton` (TonConnect доступен только пользователям)."
    ),
    responses={
        200: {"description": "Заказ успешно создан. Возвращает платёжные данные."},
        400: {"description": "Неверные входные данные."},
        422: {"description": "Нарушены ограничения по количеству/полям."},
    },
)
def create_order(
    request: Request,
    order_in: OrderIn,
    principal: Principal = Depends(current_principal),
):
    """
    Бизнес-правила:
    * **star** — `50 ≤ amount ≤ 10000`, получатель должен существовать.
    * **premium** — `amount ∈ {3, 6, 12}`, получатель должен существовать.
    * **ton** — метод оплаты *обязательно* из группы TonConnect; получатель должен существовать.
      Для гостей возвращается ошибка `payment_creation_failed`.
    * **gift** — требуется `payload.gift_id` из `settings.available_gifts` и валидный получатель.

    Результат:
    * Для методов TonConnect возвращается `ton_transaction` (а `pay_url` = `null`).
    * Для остальных методов возвращается `pay_url` (а `ton_transaction` = `null`).
    """
    if principal["kind"] == "guest":
        gs, _ = GuestSession.objects.get_or_create(id=principal["payload"]["sid"])
        user = None
    else:
        gs = None
        user = principal["user"]
    wallet = get_wallet()
    fragment = FragmentAPI(wallet)
    ton_methods = PaymentMethod.objects.filter(
        system__name=PaymentSystem.Names.TON_CONNECT
    )
    try:
        chosen_payment_method = PaymentMethod.objects.get(id=order_in.payment_method)
    except PaymentMethod.DoesNotExist:
        return OrderResponse(success=False, error="invalid_payment_method")
    order_price = 0.0
    white_price = 0.0
    order_payload = {}
    order_type = None
    recipient = None
    match order_in.item_type:
        case "star":
            if not (50 <= order_in.amount <= 10000):
                return OrderResponse(success=False, error="invalid_amount")
            try:
                recipient = fragment.get_stars_recipient(order_in.recipient).recipient
            except ValueError:
                return OrderResponse(success=False, error="invalid_recipient")
            order_price, white_price = get_stars_price(order_in.amount)
            order_payload = {}
            order_type = Order.Type.STARS
        case "premium":
            if order_in.amount not in {3, 6, 12}:
                return OrderResponse(success=False, error="invalid_amount")
            try:
                recipient = fragment.get_premium_recipient(order_in.recipient).recipient
            except ValueError:
                return OrderResponse(success=False, error="invalid_recipient")
            order_price, white_price = get_premium_price(order_in.amount)  # type: ignore
            order_payload = {}
            order_type = Order.Type.PREMIUM
        case "ton":
            if not ton_methods.filter(id=chosen_payment_method.id).exists():
                return OrderResponse(success=False, error="invalid_payment_method")
            try:
                recipient = fragment.get_ton_recipient(order_in.recipient).recipient
            except ValueError:
                return OrderResponse(success=False, error="invalid_recipient")
            order_price, white_price = get_ton_price(order_in.amount)  # type: ignore
            order_payload = {}
            order_type = Order.Type.TON
        case "gift":
            gift_id = order_in.payload.get("gift_id") if order_in.payload else None
            if not gift_id:
                return OrderResponse(success=False, error="gift_not_found")
            if gift_id not in settings.available_gifts:
                return OrderResponse(success=False, error="gift_not_found")
            gifts = bot.get_available_gifts().gifts
            gifts = list(filter(lambda x: x.id == gift_id, gifts))
            if len(gifts) == 0:
                return OrderResponse(success=False, error="gift_not_found")
            gift = gifts[0]
            if not get_gift_sender().validate_recipient(order_in.recipient):
                return OrderResponse(success=False, error="invalid_recipient")
            white_price = get_stars_price(500)[1] / 500
            white_price = gift.star_count * white_price
            order_price = round(
                white_price + white_price / 100 * settings.gifts_markup, 2
            )
            order_in.amount = 1
            order_payload = order_in.payload
            order_type = Order.Type.GIFT_REGULAR
        case _:
            assert_never(order_in.item_type)
    if not order_type:
        return OrderResponse(success=False, error="internal_error")
    order = Order.objects.create(
        user=user,
        guest_session=gs,
        type=order_type,
        status=Order.Status.CREATED,
        amount=order_in.amount,
        price=order_price,
        white_price=white_price,
        recipient=recipient,
        recipient_username=order_in.recipient,
        payload=order_payload,
    )
    payment_id = str(uuid4())
    payment = Payment.objects.create(
        id=payment_id,
        method=chosen_payment_method,
        sum=order.price,
        status=Payment.Status.CREATED,
        order=order,
    )
    if ton_methods.filter(id=chosen_payment_method.id).exists():
        if not principal["kind"] == "user":
            return OrderResponse(success=False, error="payment_creation_failed")
        if "USDT" in chosen_payment_method.name:
            transaction_type = "usdt"
            price_to_send = to_nano(order.price, 6)
        else:
            transaction_type = "ton"
            price_to_send = to_nano(TON.usd_to_ton(order.price))
        TonTransaction.objects.create(
            amount=price_to_send,
            currency=transaction_type.upper(),
            user=principal["user"],
            payment=payment,
        )
        ton_transaction = build_tonconnect_message(
            payment_id,
            user_wallet_address=Address(principal["user"].wallet_address),
            recipient_address=Address(settings.deposit_ton_address),
            amount=price_to_send,
            transfer_type=transaction_type,  # type: ignore
        )
        if "error" in ton_transaction:
            logger.error(
                f"Error creating TonConnect message: {ton_transaction['error']}"
            )
            return OrderResponse(success=False, error="payment_creation_failed")
        pay_url = None
    else:
        ton_transaction = None
        pay_url = generate_pay_link(order, request.client.host)
        if not pay_url:
            logger.error(f"Error creating payment link for order #{order.id}")
            return OrderResponse(success=False, error="payment_creation_failed")

    return OrderResponse(
        success=True,
        result=OrderItem(
            order_id=order.id,
            pay_url=pay_url,
            ton_transaction=ton_transaction,
        ),
    )
