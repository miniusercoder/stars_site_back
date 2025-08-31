import ctypes
import threading
import time
from enum import IntEnum

from django.db.models import F, Q
from django.utils import timezone
from loguru import logger
from telebot import apihelper, types

from bot.models import Order
from services.fragment import FragmentAPI
from services.wallet.helpers import get_wallet
from src.imports import Database, config, app
from src.workers.notifiers import notify_about_success, notify_about_error

db = Database()
SWAP_MINIMUM = 200  # Минимальное количество звезд для обмена


class ErrorCodes(IntEnum):
    SUCCESS = 0
    CREATE_CLIENT_ERROR = -1
    CONNECT_ERROR = -2
    INVALID_USERNAME = -3
    PAYMENT_FORM_ERROR = -4
    SEND_GIFT_ERROR = -5
    CLIENT_NOT_INITIALIZED = -6


def check_stars_balance():
    if not config.business_connection_id:
        logger.error("Business connection ID is not set in the config.")
        return

    while threading.main_thread().is_alive():
        try:
            stars_balance = app.get_business_account_star_balance(
                config.business_connection_id
            )
        except apihelper.ApiTelegramException:
            logger.exception(f"Error fetching stars balance")
            time.sleep(10)
            continue
        if stars_balance.amount < SWAP_MINIMUM:
            try:
                business_connection = app.get_business_connection(
                    config.business_connection_id
                )
            except apihelper.ApiTelegramException:
                logger.exception(f"Error fetching stars balance")
                time.sleep(10)
                continue
            message = (
                f"<b>❗️ На аккаунте слишком мало звёзд ({stars_balance.amount}).</b>"
            )
            if not business_connection.user.username:
                message += "\n\nУ аккаунта нет username, невозможно создать заказ на покупку звёзд."
            else:
                try:
                    stars_recipient = FragmentAPI(get_wallet()).get_stars_recipient(
                        business_connection.user.username
                    )
                except Exception:
                    logger.exception("Error while fetching stars recipient")
                    message += "\n\nНе удалось получить recipient для аккаунта. Не докупаю звёзды."
                else:
                    db = Database()
                    for admin in config.admins:
                        user = db.find_user(admin)
                        if user:
                            db._user_id = user.tg
                            break
                    order = db.add_order(Order.Type.STARS)
                    order.recipient = stars_recipient.recipient
                    order.recipient_username = business_connection.user.username
                    order.amount = 1000
                    order.status = order.Status.CREATED
                    order.save()
                    message += (
                        f"\n\nСоздан заказ на покупку звёзд для аккаунта @{business_connection.user.username}.\n"
                        f"ID заказа: {order.id}."
                    )
            for admin in config.admins:
                try:
                    app.send_message(
                        admin,
                        message,
                        link_preview_options=types.LinkPreviewOptions(is_disabled=True),
                    )
                except apihelper.ApiTelegramException:
                    pass
        time.sleep(180)


def gifts_worker():
    # Загрузка библиотеки
    lib = ctypes.CDLL("./libtg.so")

    # Установка сигнатур функций
    lib.SendGift.argtypes = [ctypes.c_char_p, ctypes.c_int64, ctypes.c_int]
    lib.SendGift.restype = ctypes.c_int
    lib.Init.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p]
    lib.Init.restype = ctypes.c_int

    init_result = lib.Init(
        config.api_id, config.api_hash.encode("utf-8"), "stars.dat".encode("utf-8")
    )
    logger.info(f"Initialization result: {ErrorCodes(init_result).name}")
    # Проверка успешной инициализации
    if init_result != 0:
        logger.error(
            f"Failed to initialize the library: {ErrorCodes(init_result).name}"
        )
        return

    while threading.main_thread().is_alive():
        try:
            orders = db.get_created_orders(Q(type=Order.Type.GIFT_REGULAR))
        except Exception:
            logger.exception("Error while fetching created orders")
            time.sleep(3)
            continue
        for order in orders:
            order.status = Order.Status.IN_PROGRESS
            order.take_in_work = timezone.now()
            order.save()

            try:
                sent_result = lib.SendGift(
                    order.recipient_username.encode("utf-8"),
                    int(order.inner_message_hash),
                    int(order.anonymous_sent),
                )
            except Exception:
                logger.exception(f"Error while sending gift for order {order.id}")
                order.refresh_from_db()
                order.status = order.Status.ERROR
                order.save()
                order.user.refresh_from_db()
                order.user.balance = F("balance") + order.price
                order.user.save(update_fields=("balance",))
                try:
                    notify_about_error(order)
                except Exception:
                    logger.exception("")
                continue

            if sent_result != ErrorCodes.SUCCESS:
                logger.error(
                    f"Error while sending gift for order {order.id}: {ErrorCodes(sent_result).name}"
                )
                order.refresh_from_db()
                order.status = order.Status.ERROR
                order.save()
                order.user.refresh_from_db()
                order.user.balance = F("balance") + order.price
                order.user.save(update_fields=("balance",))
                error_detail = ""
                match sent_result:
                    case ErrorCodes.INVALID_USERNAME:
                        error_detail = "\n\n<b>Детали ошибки: <i>Неверный username получателя.</i></b>"
                    case ErrorCodes.PAYMENT_FORM_ERROR | ErrorCodes.SEND_GIFT_ERROR:
                        error_detail = (
                            "\n\n<b>Детали ошибки: <i>Ошибка при отправке подарка. "
                            "Пожалуйста, обратитесь в поддержку.</i></b>"
                        )
                try:
                    notify_about_error(order, error_detail)
                except Exception:
                    logger.exception("")
                continue
            order.refresh_from_db()
            order.status = order.Status.COMPLETED
            order.save()
            logger.success(f"Order {order.id} completed")
            try:
                notify_about_success(order)
            except Exception:
                logger.exception("")
        time.sleep(5)
