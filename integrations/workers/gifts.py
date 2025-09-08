import threading
import time

from django.utils import timezone
from loguru import logger

from django_stars.stars_app.models import Payment, Order
from integrations.gifts import get_gift_sender


def gifts_worker():
    sender = get_gift_sender()

    while threading.main_thread().is_alive():
        try:
            orders = Order.objects.filter(
                status=Order.Status.CREATED,
                type=Order.Type.GIFT_REGULAR,
                payment__status=Payment.Status.CONFIRMED,
            )
        except Exception:
            logger.exception("Error while fetching created orders")
            time.sleep(3)
            continue
        for order in orders:
            order.status = Order.Status.IN_PROGRESS
            order.take_in_work = timezone.now()
            order.save()

            gift_id = order.payload.get("gift_id") if order.payload else None

            if not gift_id:
                logger.error(f"Order {order.id} has no gift_id in payload")
                order.refresh_from_db()
                order.status = order.Status.ERROR
                order.save()
                # order.user.refresh_from_db()
                # order.user.balance = F("balance") + order.price
                # order.user.save(update_fields=("balance",))
                # try:
                #     notify_about_error(order, "\n\n<b>Детали ошибки: <i>Подарок не найден.</i></b>")
                # except Exception:
                #     logger.exception("")
                continue

            try:
                sent_result = sender.send_gift(
                    order.recipient_username,
                    gift_id,
                    False,
                )
            except Exception:
                logger.exception(f"Error while sending gift for order {order.id}")
                order.refresh_from_db()
                order.status = order.Status.ERROR
                order.save()
                # order.user.refresh_from_db()
                # order.user.balance = F("balance") + order.price
                # order.user.save(update_fields=("balance",))
                # try:
                #     notify_about_error(order)
                # except Exception:
                #     logger.exception("")
                continue

            if not sent_result:
                order.refresh_from_db()
                order.status = order.Status.ERROR
                order.save()
                # order.user.refresh_from_db()
                # order.user.balance = F("balance") + order.price
                # order.user.save(update_fields=("balance",))
                # error_detail = ""
                # match sent_result:
                #     case ErrorCodes.INVALID_USERNAME:
                #         error_detail = "\n\n<b>Детали ошибки: <i>Неверный username получателя.</i></b>"
                #     case ErrorCodes.PAYMENT_FORM_ERROR | ErrorCodes.SEND_GIFT_ERROR:
                #         error_detail = (
                #             "\n\n<b>Детали ошибки: <i>Ошибка при отправке подарка. "
                #             "Пожалуйста, обратитесь в поддержку.</i></b>"
                #         )
                # try:
                #     notify_about_error(order, error_detail)
                # except Exception:
                #     logger.exception("")
                continue
            order.refresh_from_db()
            order.status = order.Status.COMPLETED
            order.save()
            logger.success(f"Order {order.id} completed")
            # try:
            #     notify_about_success(order)
            # except Exception:
            #     logger.exception("")
        time.sleep(5)
