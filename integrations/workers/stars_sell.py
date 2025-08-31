import json
import time
from threading import main_thread

import tonutils.exceptions
from loguru import logger
from telebot import apihelper
from telebot.types import LinkPreviewOptions

from I18N import get_translator
from services.wallet.helpers import get_wallet
from src.imports import app, Database, config


def stars_refund_worker():
    while main_thread().is_alive():
        with open("config.json", "r") as f:
            json_config = json.load(f)
        offset = json_config.get("stars_refund_offset", 0)
        try:
            transactions = app.get_star_transactions(offset=offset, limit=100)
        except apihelper.ApiTelegramException:
            time.sleep(5)
            continue
        for transaction in transactions.transactions:
            if transaction.receiver is None:
                continue
            sell_request = Database.get_sell_stars_request_by_invoice_id(transaction.id)
            if not sell_request:
                logger.debug(
                    f"Sell request not found for transaction {transaction.id}, receiver: {transaction.receiver}"
                )
                continue
            if sell_request.status != sell_request.Status.ON_HOLD:
                continue
            sell_request.status = sell_request.Status.REFUNDED
            sell_request.save()
            user = sell_request.user
            _ = get_translator(user.language)
            message = _(
                "⚠️ <b>Заявка #{} на продажу звёзд была отклонена из-за возврата звёзд со стороны Telegram.</b>\n\n"
                "<i>❓Есть вопросы насчёт возврата? Напишите в @<u>{}</u>.</i>"
            ).format(sell_request.id, config.support_contact)
            try:
                app.send_message(sell_request.user.tg, message)
            except apihelper.ApiTelegramException:
                pass
            admin_message = (
                "<b>⚠️ Произошёл рефаунд звёзд</b>\n\n"
                f"ID заказа: {sell_request.id}\n"
                f"Пользователь: @{user.username} (<a href='tg://user?id={user.tg}'>{user.tg}</a>)\n"
                f"Сумма: {sell_request.amount} звёзд"
            )
            try:
                app.send_message(config.sell_stars_channel, admin_message)
            except apihelper.ApiTelegramException:
                pass
        offset += len(transactions.transactions)
        with open("config.json", "r") as f:
            json_config = json.load(f)
        json_config["stars_refund_offset"] = offset
        with open("config.json", "w") as f:
            json.dump(json_config, f, indent=4)
        time.sleep(300)


def send_usdt_worker():
    while main_thread().is_alive():
        to_send = Database.get_stars_sell_requests_to_send()
        wallet = get_wallet()
        for transaction in to_send:
            usdt_balance = wallet.get_jetton_balance(config.usdt_jetton_address, 6)
            if usdt_balance - 0.1 < transaction.price:
                logger.warning(
                    f"Not enough USDT balance to send {transaction.price} for transaction {transaction.id}"
                )
                continue
            try:
                msg_id = wallet.jetton_transfer(
                    destination=transaction.ton_wallet,
                    amount=transaction.price,
                    jetton_address=config.usdt_jetton_address,
                    jetton_decimals=6,
                    comment=transaction.ton_memo or "",
                )
            except tonutils.exceptions.APIClientError:
                logger.exception(
                    f"Error while sending USDT for transaction {transaction.id}"
                )
                continue
            transaction.status = transaction.Status.COMPLETED
            transaction.tx_hash = msg_id
            transaction.save()
            _ = get_translator(transaction.user.language)
            message = _(
                "<b>✅ Средства за продажу звёзд по заявке #{request_id} успешно отправлены.</b>\n\n"
                "💰<b> Транзакция:</b> <a href='https://tonviewer.com/transaction/{tx_hash}'>{tx_hash}</a>\n\n"
            ).format(request_id=transaction.id, tx_hash=msg_id)
            try:
                app.send_message(
                    transaction.user.tg,
                    message,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            except apihelper.ApiTelegramException:
                logger.exception(
                    f"Error while sending message to user {transaction.user.tg} for transaction {transaction.id}"
                )

            referrals_reward = 0
            referral_admin_message = ""
            white_price = transaction.amount * 0.013
            if transaction.user.refer and (
                Database.find_user(transaction.user.refer)
                or Database.get_referral_link(name=transaction.user.refer)
            ):
                if Database.get_referral_link(name=transaction.user.refer):
                    link = Database.get_referral_link(name=transaction.user.refer)
                    link.orders += 1
                    link.profit += white_price - transaction.price
                    link.save()
                else:
                    referral_admin_message = "\n\n"
                    # 3-х уровневая реферальная система
                    # Рефералу 1 уровня - 25% от заработка (order.price - order.white_price)
                    # Рефералу 2 уровня - 10% от заработка
                    # Рефералу 3 уровня - 5% от заработка
                    refer_user_1 = Database.find_user(transaction.user.refer)
                    order_profit = white_price - transaction.price
                    match refer_user_1.tg:
                        case 5903333556:
                            refer_profit_1 = order_profit * 0.50
                        case 7931457294:
                            refer_profit_1 = order_profit * 0.50
                        case _:
                            refer_profit_1 = order_profit * 0.25
                    refer_user_1.referral_balance += refer_profit_1
                    refer_user_1.referrals_profit += refer_profit_1
                    refer_user_1.save()
                    referrals_reward += refer_profit_1
                    referral_admin_message += (
                        f"Рефоводу 1 уровня @{refer_user_1.username} "
                        f'(<a href="tg://user?id={refer_user_1.tg}">{refer_user_1.tg}</a>) '
                        + "Начислено {:.2f} USD\n".format(refer_profit_1)
                    )
                    if refer_user_1.refer and Database.find_user(refer_user_1.refer):
                        refer_user_2 = Database.find_user(refer_user_1.refer)
                        match refer_user_2.tg:
                            case 5903333556:
                                refer_profit_2 = order_profit * 0
                            case 7931457294:
                                refer_profit_2 = order_profit * 0
                            case _:
                                refer_profit_2 = order_profit * 0.10
                        refer_user_2.referral_balance += refer_profit_2
                        refer_user_2.referrals_profit += refer_profit_2
                        refer_user_2.save()
                        referrals_reward += refer_profit_2
                        referral_admin_message += (
                            f"Рефоводу 2 уровня @{refer_user_2.username} "
                            f'(<a href="tg://user?id={refer_user_2.tg}">{refer_user_2.tg}</a>) '
                            + "Начислено {:.2f} USD\n".format(refer_profit_2)
                        )
                        if refer_user_2.refer and Database.find_user(
                            refer_user_2.refer
                        ):
                            refer_user_3 = Database.find_user(refer_user_2.refer)
                            match refer_user_3.tg:
                                case 5903333556:
                                    refer_profit_3 = order_profit * 0
                                case 7931457294:
                                    refer_profit_3 = order_profit * 0
                                case _:
                                    refer_profit_3 = order_profit * 0.05
                            refer_user_3.referral_balance += refer_profit_3
                            refer_user_3.referrals_profit += refer_profit_3
                            refer_user_3.save()
                            referrals_reward += refer_profit_3
                            referral_admin_message += (
                                f"Рефоводу 3 уровня @{refer_user_3.username} "
                                f'(<a href="tg://user?id={refer_user_3.tg}">{refer_user_3.tg}</a>) '
                                + "Начислено {:.2f} USD\n".format(refer_profit_3)
                            )
                    transaction.refresh_from_db()
                    transaction.referrals_reward = referrals_reward
                    transaction.save()
            admin_message = (
                "<b>✅ Средства за продажу звёзд успешно отправлены</b>\n\n"
                f"ID заказа: {transaction.id}\n"
                f"Пользователь: @{transaction.user.username} (<a href='tg://user?id={transaction.user.tg}'>{transaction.user.tg}</a>)\n"
                + "Сумма: {:.2f} USDT\n".format(transaction.price)
                + f"Транзакция: <a href='https://tonviewer.com/transaction/{msg_id}'>{msg_id}</a>"
            )
            admin_message += referral_admin_message
            try:
                app.send_message(
                    config.sell_stars_channel,
                    admin_message,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            except apihelper.ApiTelegramException:
                logger.exception(
                    f"Error while sending message to channel {config.sell_stars_channel} for transaction {transaction.id}"
                )
            time.sleep(10)
        time.sleep(60)
