import os
import time
from datetime import timedelta

import django
import requests
import telebot
from django.db.models import F
from django.utils import timezone as tz
from loguru import logger
from telebot import TeleBot

os.environ["DJANGO_SETTINGS_MODULE"] = "titov_stars.settings"
django.setup()


def check_day_orders():
    from bot.models import Order
    from src.imports import config

    bot = TeleBot(config.token, parse_mode="HTML")

    orders = Order.objects.filter(
        status=Order.Status.COMPLETED,
        create_date__gte=tz.localtime() - timedelta(days=2),
    ).order_by("-id")
    logger.info(f"Checking {orders.count()} completed orders from the last day.")

    for order in orders:
        if not order.msg_hash:
            logger.error(f"Order {order.id} has no transaction hash.")
            continue
        url = f"https://tonapi.io/v2/traces/{order.msg_hash}"
        headers = {
            "accept": "application/json",
            "Authorization": "Bearer AGWKOIJR44CV2KYAAAAL4IBB6UOPIW2XMAQTSPRYK2RF5EYURGXVN46HCMKTWB6QKH5CHIQ",
        }
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to fetch transaction {order.id}: {response.text}")
            continue
        transaction_data = response.json()
        if (
            not transaction_data.get("transaction", {}).get("success", False)
            or len(transaction_data.get("children", [])) == 0
        ):
            try:
                bot.send_message(
                    order.user.tg,
                    f"<b>📥 Вам пришёл возврат по заказу <i>#{order.id}</i> суммой {round(order.price, 2)} USD</b>",
                    reply_to_message_id=order.message_id,
                )
            except telebot.apihelper.ApiTelegramException:
                try:
                    bot.send_message(
                        order.user.tg,
                        f"<b>📥 Вам пришёл возврат по заказу <i>#{order.id}</i> суммой {round(order.price, 2)} USD</b>",
                    )
                except telebot.apihelper.ApiTelegramException:
                    pass
            order.status = Order.Status.ERROR
            order.is_refund = True
            order.save()
            user = order.user
            user.refresh_from_db()
            user.balance = F("balance") + order.price
            user.save(update_fields=("balance",))
            logger.error(f"Transaction {order.id} was not successful.")
            continue
        logger.success(f"Transaction {order.id} was successful.")
        time.sleep(1)


if __name__ == "__main__":
    check_day_orders()
