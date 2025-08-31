from hashlib import md5
from typing import Annotated

from I18N import get_translator
from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse
from loguru import logger
from src.imports import config, Database, app
from src.main import referral_deposit_handler
from telebot import apihelper

router = APIRouter()


@router.post("/cardlink", response_class=HTMLResponse)
def cardlink(
    amount: Annotated[str, Form(alias="OutSum")],
    payment_id: Annotated[str, Form(alias="InvId")],
    signature: Annotated[str, Form(alias="SignatureValue")],
    status: Annotated[str, Form(alias="Status")],
):
    local_signature = (
        md5(f"{amount}:{payment_id}:{config.cardlink_key}".encode()).hexdigest().upper()
    )
    if local_signature == signature:
        if status != "SUCCESS":
            return HTMLResponse("fail", 400)
        payment_id = payment_id
        db = Database()
        payment = db.get_payment(payment_id)
        if not payment:
            logger.debug(f"Cardlink: Payment with ID {payment_id} not found.")
            return HTMLResponse("fail", 400)
        payment.refresh_from_db(fields=("status",))
        if payment.status != 0:
            logger.debug(f"Cardlink: Payment {payment_id} already processed.")
            return HTMLResponse("fail", 400)
        db.set_payment_status(payment.id, 1)
        payment.refresh_from_db(fields=("user",))
        user = payment.user
        user_db = Database(user.tg, app)
        amount = payment.sum
        message = (
            "<b>♻ <b>Новое пополнение!</b>\n"
            f'😎 <b>Пользователь:</b> @{user.username} (<a href="tg://user?id={user.tg}">{user.tg}</a>)\n'
            f"💰 <b>Сумма:</b> <code>{round(amount, 2)} USD</code>\n"
            f"❓ <b>Тип пополнения:</b> <code>CardLink</code></b>\n"
        ) + referral_deposit_handler(user, amount)
        user_db.change_balance(amount)
        db.set_payment_sum(payment.id, amount)
        app.send_message(
            config.deposits_channel,
            message,
        )
        _ = get_translator(user.language)
        try:
            app.send_message(
                payment.user_id,
                _(
                    "✅ <b>Счёт успешно оплачен.</b>\n\n"
                    "💰 <b>На баланс зачислено</b> <code>{:.2f} USD</code>"
                ).format(amount),
            )
        except apihelper.ApiTelegramException:
            pass
        return HTMLResponse("ok", 200)
    logger.debug("Cardlink: Signature mismatch.")
    return HTMLResponse("fail", status_code=400)
