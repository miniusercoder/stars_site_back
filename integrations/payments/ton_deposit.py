import hashlib
import hmac
import time
from threading import main_thread

import nacl.exceptions
import requests
from Cryptodome.Cipher import AES
from bot.models import User, TonTransaction
from loguru import logger
from nacl.bindings import (
    crypto_sign_ed25519_sk_to_curve25519,
    crypto_sign_ed25519_pk_to_curve25519,
    crypto_scalarmult,
)
from pytoniq_core import Address
from services.wallet.helpers import get_wallet
from src.imports import config
from src.main import process_ton_transaction


def decrypt_comment(
    encrypted_comment: str,
    sender_address: str,
    our_private_key: bytes,
    our_public_key: bytes,
) -> str:
    salt = (
        Address(sender_address)
        .to_str(
            is_user_friendly=True,
            is_url_safe=True,
            is_bounceable=True,
            is_test_only=False,
        )
        .encode()
    )
    decoded_message = bytes.fromhex(encrypted_comment)
    pub_xor = decoded_message[0:32]
    msg_key = decoded_message[32:48]
    encrypted_data = decoded_message[48:]

    _their_public_key = bytes([a ^ b for a, b in zip(pub_xor, our_public_key)])

    our_private_key = crypto_sign_ed25519_sk_to_curve25519(
        our_private_key + our_public_key
    )
    their_public_key = crypto_sign_ed25519_pk_to_curve25519(_their_public_key)

    shared_key = crypto_scalarmult(
        our_private_key,
        their_public_key,
    )

    # Generate encryption key using HMAC with shared key
    h = hmac.new(shared_key, msg_key, hashlib.sha512)
    x = h.digest()

    # Encrypt data using AES in CBC mode
    c = AES.new(key=x[0:32], mode=AES.MODE_CBC, iv=x[32:48])
    decrypted = c.decrypt(encrypted_data)

    # Validate message key
    got_msg_key = hmac.new(
        salt,
        decrypted,
        hashlib.sha512,
    ).digest()[:16]
    if got_msg_key != msg_key:
        raise ValueError("Message key does not match")

    # Validate and strip prefix
    prefix_len = decrypted[0]
    if prefix_len < 16 or prefix_len > 31:
        raise ValueError("Invalid prefix length")

    message = decrypted[prefix_len:]
    message = message.decode("utf-8")

    return message


def check_ton_deposits():
    account_id = Address(config.deposit_ton_address)
    account_id = f"{account_id.wc}:{account_id.hash_part.hex()}"
    jetton_address = Address(config.usdt_jetton_address)
    jetton_address = f"{jetton_address.wc}:{jetton_address.hash_part.hex()}"
    wallet = get_wallet().wallet
    wallet_address = f"{wallet.address.wc}:{wallet.address.hash_part.hex()}"

    params = {
        "limit": 100,
        "sort_order": "desc",
    }

    url = f"https://tonapi.io/v2/accounts/{account_id}/events"

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {config.ton_api_key.get_secret_value()}",
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
                            amount = amount / 10**6
                            # Convert to human-readable format
                        elif action.get("type") == "TonTransfer":
                            transfer = action.get("TonTransfer", {})
                            currency = "TON"
                            amount = float(transfer.get("amount", 0))
                            amount = amount / 10**9  # Convert to human-readable format
                        else:
                            continue
                        recipient = transfer.get("recipient", {}).get("address", "")
                        if recipient != account_id:
                            continue
                        sender_address = transfer.get("sender", {}).get("address", "")
                        encrypted_comment = transfer.get("encrypted_comment")
                        if (
                            encrypted_comment is not None
                            and wallet_address == account_id
                        ):
                            try:
                                comment = decrypt_comment(
                                    encrypted_comment.get("cipher_text"),
                                    sender_address,
                                    wallet.private_key[:32],
                                    wallet.public_key,
                                )
                            except (ValueError, nacl.exceptions.CryptoError):
                                logger.exception(
                                    f"Failed to decrypt comment for transaction {transaction_hash}",
                                )
                                comment = transfer.get("comment", "")
                        else:
                            comment = transfer.get("comment", "")
                        sender_address = Address(sender_address).to_str()
                        if TonTransaction.objects.filter(
                            hash=transaction_hash
                        ).exists():
                            continue
                        try:
                            user = User.objects.get(tg=int(comment))
                        except (User.DoesNotExist, ValueError):
                            continue
                        else:
                            transaction = TonTransaction.objects.create(
                                source=sender_address,
                                hash=transaction_hash,
                                amount=amount,
                                currency=currency,
                                user=user,
                            )
                            process_ton_transaction(transaction)
                except Exception:
                    logger.exception(
                        f"Error processing transaction {event.get('event_id', '')}"
                    )
        else:
            print(f"Failed to fetch transactions. Status code: {response.status_code}")
        time.sleep(3)
