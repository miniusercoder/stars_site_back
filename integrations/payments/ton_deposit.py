import time
from threading import main_thread

import requests
from loguru import logger
from pytoniq_core import Address

from django_stars.stars_app.models import TonTransaction
from fastapi_stars.settings import settings


def check_ton_deposits():
    account_id = Address(settings.deposit_ton_address)
    account_id = f"{account_id.wc}:{account_id.hash_part.hex()}"
    jetton_address = Address(settings.usdt_jetton_address)
    jetton_address = f"{jetton_address.wc}:{jetton_address.hash_part.hex()}"

    params = {
        "limit": 100,
        "sort_order": "desc",
    }

    url = f"https://tonapi.io/v2/accounts/{account_id}/events"

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {settings.ton_api_key.get_secret_value()}",
    }

    while main_thread().is_alive():
        try:
            response = requests.get(url, params=params, headers=headers)
        except requests.exceptions.RequestException:
            logger.exception("Error fetching transactions")
            time.sleep(3)
            continue
        if response.status_code == 200:
            events = response.json().get("events", [])
            for event in events:
                try:
                    if event.get("in_progress", False):
                        continue
                    transaction_hash = event.get("event_id", "")
                    actions = event.get("actions", [])
                    for action in actions:
                        if action.get("type") == "JettonTransfer":
                            transfer = action.get("JettonTransfer", {})
                            transfer_jetton_address = transfer.get("jetton", {}).get(
                                "address", ""
                            )
                            if transfer_jetton_address != jetton_address:
                                continue
                            currency = "USDT"
                            amount = float(transfer.get("amount", 0))
                            # amount = amount / 10**6
                            # Convert to human-readable format
                        elif action.get("type") == "TonTransfer":
                            transfer = action.get("TonTransfer", {})
                            currency = "TON"
                            amount = float(transfer.get("amount", 0))
                            # amount = amount / 10**9  # Convert to human-readable format
                        else:
                            continue
                        recipient = transfer.get("recipient", {}).get("address", "")
                        if recipient != account_id:
                            continue
                        sender_address = transfer.get("sender", {}).get("address", "")
                        comment = transfer.get("comment", "")
                        sender_address = Address(sender_address).to_str(
                            is_bounceable=False
                        )
                        if TonTransaction.objects.filter(
                            hash=transaction_hash
                        ).exists():
                            continue
                        ton_transaction = TonTransaction.objects.filter(
                            payment__id=comment
                        ).first()
                        if not ton_transaction:
                            continue
                        if (
                            currency != ton_transaction.currency
                            or amount != ton_transaction.amount
                        ):
                            continue
                        ton_transaction.hash = transaction_hash
                        ton_transaction.source = sender_address
                        ton_transaction.save(update_fields=("hash", "source"))
                        ton_transaction.payment.status = (
                            ton_transaction.payment.Status.CONFIRMED
                        )
                        ton_transaction.payment.save(update_fields=("status",))
                except Exception:
                    logger.exception(
                        f"Error processing transaction {event.get('event_id', '')}"
                    )
        else:
            print(f"Failed to fetch transactions. Status code: {response.status_code}")
        time.sleep(3)
