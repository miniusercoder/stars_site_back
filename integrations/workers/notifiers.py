from telebot import apihelper, types
from telebot.types import LinkPreviewOptions

from I18N import get_translator
from bot.models import Order
from src.Merchants.CBRF import CBRF
from src.imports import app, config


def notify_about_error(order: Order, error_detail: str = ""):
    _ = get_translator(order.user.language or "ru")
    message = (
        _(
            "<b>❌ Во время обработки заказа #{order_id} возникла ошибка.\n\n"
            "Полная стоимость заказа {price:.2f} USD ({price_rub:.2f} RUB) была возвращена на ваш баланс.</b>"
        ).format(
            order_id=order.id, price=order.price, price_rub=CBRF.usd_to_rub(order.price)
        )
        + error_detail
    )
    try:
        app.send_message(
            order.user.tg,
            message,
            reply_parameters=types.ReplyParameters(
                message_id=order.message_id, chat_id=order.chat_id
            ),
        )
    except apihelper.ApiTelegramException:
        try:
            app.send_message(
                order.user.tg,
                message,
            )
        except apihelper.ApiTelegramException:
            pass
    try:
        app.send_message(
            config.orders_channel,
            f"<b>❌ Ошибка при обработке заказа #{order.id} от @{order.user.username} ("
            f"<a href='tg://user?id={order.user.tg}'>{order.user.tg}</a>)</b>\n\n",
        )
    except apihelper.ApiTelegramException:
        pass


def notify_about_success(order: Order):
    _ = get_translator(order.user.language or "ru")
    if order.type == Order.Type.TON_WALLET:
        tx_message = _(
            "Транзакция: <a href='https://tonviewer.com/transaction/{tx_hash}'>{tx_hash}</a>\n\n"
        ).format(tx_hash=order.tx_hash)
    else:
        tx_message = ""
    message = _(
        "<b>✅ Заказ №{order_id} успешно выполнен, товар будет доставлен в течение 1 минуты.</b>\n\n"
        + tx_message
        + "<i>❓Есть вопросы или столкнулись с проблемой? Обратитесь в поддержку — </i><i>@{support_contact}</i>."
    ).format(order_id=order.id, support_contact=config.support_contact)
    try:
        app.send_message(
            order.user.tg,
            message,
            reply_parameters=types.ReplyParameters(
                message_id=order.message_id, chat_id=order.chat_id
            ),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except apihelper.ApiTelegramException:
        try:
            app.send_message(
                order.user.tg,
                message,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except apihelper.ApiTelegramException:
            pass
