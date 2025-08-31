import asyncio
import time
from base64 import b64encode
from typing import Literal

from loguru import logger
from pytoniq_core import begin_cell, Address
from tonutils.jetton import JettonMasterStandard, JettonWalletStandard
from tonutils.utils import to_nano
from tonutils.wallet.op_codes import TEXT_COMMENT_OPCODE

from fastapi_stars.settings import settings
from integrations.wallet.helpers import get_wallet


def get_jetton_wallet(owner_address: Address | str, jetton_master: str):
    try:
        user_jetton_wallet_address = asyncio.run(
            JettonMasterStandard.get_wallet_address(
                client=get_wallet().wallet.client,
                owner_address=owner_address,
                jetton_master_address=jetton_master,
            )
        )
    except Exception:
        logger.exception("Error getting jetton wallet address")
        raise ValueError("Error getting jetton wallet address")
    return user_jetton_wallet_address


def build_tonconnect_message(
    payment_id: str,
    user_wallet_address: Address,
    recipient_address: Address,
    amount: float,
    transfer_type: Literal["ton", "usdt"],
) -> dict:
    comment_body = (
        begin_cell()
        .store_uint(TEXT_COMMENT_OPCODE, 32)
        .store_snake_string(payment_id)
        .end_cell()
    )
    if transfer_type == "usdt":
        try:
            user_jetton_wallet_address = get_jetton_wallet(
                owner_address=user_wallet_address,
                jetton_master=settings.usdt_jetton_address,
            )
        except ValueError:
            return {"error": "error_getting_jetton_wallet"}
        jetton_transfer_message = b64encode(
            JettonWalletStandard.build_transfer_body(
                recipient_address=recipient_address,
                jetton_amount=to_nano(amount, 6),
                forward_amount=to_nano(0.000000001),
                forward_payload=comment_body,
            ).to_boc()
        ).decode()
        return {
            "validUntil": int(time.time()) + 300,
            "messages": [
                {
                    "address": user_jetton_wallet_address.to_str(),
                    "amount": str(to_nano(0.05)),
                    "payload": jetton_transfer_message,
                }
            ],
        }
    elif transfer_type == "ton":
        comment_body = (
            begin_cell()
            .store_uint(TEXT_COMMENT_OPCODE, 32)
            .store_snake_string(payment_id)
            .end_cell()
        )
        return {
            "validUntil": int(time.time()) + 300,
            "messages": [
                {
                    "address": recipient_address.to_str(),
                    "amount": str(to_nano(amount)),
                    "payload": b64encode(comment_body.to_boc()).decode(),
                }
            ],
        }
    return {"error": "invalid transfer type"}
