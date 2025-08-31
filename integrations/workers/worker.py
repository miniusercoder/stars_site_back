import asyncio
import binascii
import threading
import time
from base64 import b64encode, urlsafe_b64decode
from datetime import timedelta

import nacl.exceptions
import tonutils.exceptions
from django.db.models import Q
from django.utils import timezone
from loguru import logger
from pytoniq_core import Cell, begin_cell, Address, WalletMessage
from tonutils.utils import to_nano
from tonutils.wallet.op_codes import TEXT_COMMENT_OPCODE

from django_stars.stars_app.models import Order, Payment
from fastapi_stars.settings import settings
from integrations.fragment import FragmentAPI
from integrations.fragment.toncenter import (
    TonCenter,
    IncompleteTransactionError,
    NotFoundTransactionError,
)
from integrations.wallet.helpers import get_wallet

NO_CONFIRM_SLEEP = 5


def check_transaction_worker():
    toncenter = TonCenter(settings.toncenter_key.get_secret_value())
    while threading.main_thread().is_alive():
        try:
            orders = Order.objects.filter(status=Order.Status.BLOCKCHAIN_WAITING)
        except Exception:
            logger.exception("Error while fetching waiting orders")
            time.sleep(3)
            continue
        for order in orders:
            try:
                _, tx_id = toncenter.get_transaction_by_msg_hash(
                    order.msg_hash, order.inner_message_hash
                )
            except IncompleteTransactionError:
                logger.info(
                    f"Transaction {order.msg_hash} is not complete yet, skipping"
                )
                continue
            except NotFoundTransactionError:
                if order.take_in_work <= timezone.now() - timedelta(seconds=360):
                    logger.error(
                        f"Transaction with msg_hash {order.msg_hash} not found."
                    )
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
            except ValueError:
                # for admin in config.admins:
                #     try:
                #         bot.send_message(
                #             admin,
                #             f"Error while checking transaction {order.msg_hash}:\n"
                #             f"{order.inner_message_hash}\n"
                #             f"{order.type} {order.amount} to {order.recipient}",
                #         )
                #     except apihelper.ApiTelegramException:
                #         pass
                logger.exception(f"Error while checking transaction {order.msg_hash}")
                continue
            except Exception:
                logger.exception(f"Error while checking transaction {order.msg_hash}")
                continue
            else:
                try:
                    tx_id = urlsafe_b64decode(tx_id)
                except binascii.Error:
                    logger.error(
                        f"Invalid transaction hash for order {order.id}: {order.msg_hash}"
                    )
                    continue
                tx_id = tx_id.hex()
                order.refresh_from_db()
                order.tx_hash = tx_id
                order.status = order.Status.COMPLETED
                order.save()
                logger.success(f"Order {order.id} completed with tx {tx_id}")
                # try:
                #     notify_about_success(order)
                # except Exception:
                #     logger.exception("")
        time.sleep(2)


def send_transaction_worker():
    wallet = get_wallet()
    fragment = FragmentAPI(wallet)

    while threading.main_thread().is_alive():
        try:
            orders = Order.objects.filter(
                status=Order.Status.CREATED, payment__status=Payment.Status.CONFIRMED
            ).filter(
                Q(type=Order.Type.PREMIUM)
                | Q(type=Order.Type.STARS)
                | Q(type=Order.Type.TON)
            )
        except Exception:
            logger.exception("Error while fetching created orders")
            time.sleep(3)
            continue
        for order in orders:
            order.status = Order.Status.IN_PROGRESS
            order.take_in_work = timezone.now()
            order.save()
        messages = []
        for order in orders:
            body_hash = ""
            transfer_msg: WalletMessage | None = None
            buy_message = None
            try:
                match order.type:
                    case Order.Type.PREMIUM:
                        buy_message = fragment.premium_buy(
                            order.recipient, order.amount, order.anonymous_sent
                        )
                    case Order.Type.STARS:
                        buy_message = fragment.stars_buy(
                            order.recipient, order.amount, order.anonymous_sent
                        )
                    case Order.Type.TON:
                        buy_message = fragment.ton_buy(
                            order.recipient, order.amount, order.anonymous_sent
                        )
                    case Order.Type.TON_WALLET:
                        destination = Address(order.recipient)
                        try:
                            body = asyncio.run(
                                wallet.wallet.build_encrypted_comment_body(
                                    text=f"HelperStars #{order.id}",
                                    destination=destination,
                                )
                            )
                        except (
                            tonutils.exceptions.APIClientError,
                            nacl.exceptions.CryptoError,
                            TimeoutError,
                        ):
                            body = (
                                begin_cell()
                                .store_uint(TEXT_COMMENT_OPCODE, 32)
                                .store_string(f"HelperStars #{order.id}")
                                .end_cell()
                            )
                        amount = to_nano(order.amount)
                        body_hash = b64encode(body.hash).decode()
                        transfer_msg = wallet.wallet.create_wallet_internal_message(
                            destination=destination,
                            value=amount,
                            body=body,
                        )
                    case _:
                        continue
            except Exception:
                logger.exception(
                    f"Error while creating buy message for order {order.id}"
                )
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
            if order.type != order.Type.TON_WALLET:
                buy_message = buy_message.transaction.messages[0]
                buy_message.payload = (
                    f"{buy_message.payload}{'=' * (len(buy_message.payload) % 4)}"
                )
                body = Cell.one_from_boc(buy_message.payload)
                body_hash = b64encode(body.hash).decode()
                transfer_msg = wallet.wallet.create_wallet_internal_message(
                    destination=Address(buy_message.address),
                    value=buy_message.amount,
                    body=body,
                )
            order.refresh_from_db()
            order.inner_message_hash = body_hash
            order.save()
            if transfer_msg:
                messages.append(transfer_msg)
        if len(messages) > 0:
            try:
                wallet.log_wallet_info()
                external_message_id = asyncio.run(
                    wallet.wallet.raw_transfer(messages=messages)
                )
            except (tonutils.exceptions.APIClientError, TimeoutError):
                logger.exception("APIClientError while sending transaction")
                for order in orders:
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
            external_message_id = b64encode(bytes.fromhex(external_message_id)).decode()
            logger.info(f"Transaction {external_message_id} sent!")
            for order in orders:
                order.refresh_from_db()
                order.msg_hash = external_message_id
                order.status = order.Status.BLOCKCHAIN_WAITING
                order.take_in_work = timezone.now()
                order.save()
        time.sleep(3)
