import asyncio
import time
from typing import Type

from loguru import logger
from pytoniq_core import Address
from tonutils.client import TonapiClient as ApiClient
from tonutils.jetton import JettonMasterStandard, JettonWalletStandard
from tonutils.utils import to_amount
from tonutils.wallet import HighloadWalletV3 as WalletClass
from tonutils.wallet import Wallet as TonWallet
from tonutils.wallet.messages import StonfiSwapJettonToTONMessage, TransferJettonMessage

from fastapi_stars.settings import settings
from integrations.Currencies import TON
from integrations.utils.singleton import Singleton
from integrations.wallet.types import TonTransactionMessage


class Wallet(metaclass=Singleton):
    """Custom TON Wallet base class, with transaction confirm and queue (sync version)"""

    VALID_UNTIL = 240  # seconds
    FINISH_SLEEP = 10
    NO_CONFIRM_SLEEP = 60

    def __init__(
        self,
        api_key: str,
        mnemonic: list[str],
        is_testnet: bool = False,
        wallet_class: Type[TonWallet] = WalletClass,
    ) -> None:
        self._api_key = api_key
        self._mnemonic = mnemonic
        self.is_testnet = is_testnet
        self._client: ApiClient | None = None

        self._w: TonWallet = self.get_wallet(wallet_class)

    def get_balance(self) -> float:
        return asyncio.run(self._w.balance())

    def get_wallet(self, wallet_class: Type[TonWallet]) -> TonWallet:
        wallet, _, _, _ = wallet_class.from_mnemonic(self.client, self._mnemonic)
        return wallet

    def transfer(self, message: TonTransactionMessage):
        return asyncio.run(
            self._w.raw_transfer(
                messages=[
                    self._w.create_wallet_internal_message(
                        destination=Address(message.address),
                        value=message.amount,
                        body=message.payload,
                    ),
                ],
                valid_until=int(time.time()) + self.VALID_UNTIL,
            )
        )

    def jetton_transfer(
        self,
        destination: str,
        amount: float,
        jetton_address: str,
        jetton_decimals: int,
        comment: str = "",
    ):
        return asyncio.run(
            self._w.transfer_message(
                message=TransferJettonMessage(
                    destination=Address(destination),
                    jetton_master_address=jetton_address,
                    jetton_amount=amount,
                    jetton_decimals=jetton_decimals,
                    forward_payload=comment,
                )
            )
        )

    @property
    def client(self):
        if not self._client:
            self._client = ApiClient(api_key=self._api_key, is_testnet=self.is_testnet)
        return self._client

    @property
    def wallet(self):
        return self._w

    def get_jetton_balance(self, jetton_address: str, jetton_decimals: int) -> float:
        jetton_wallet_address = asyncio.run(
            JettonMasterStandard.get_wallet_address(
                client=self.client,
                owner_address=self._w.address,
                jetton_master_address=jetton_address,
            )
        )

        jetton_wallet_data = asyncio.run(
            JettonWalletStandard.get_wallet_data(
                client=self.client,
                jetton_wallet_address=jetton_wallet_address,
            )
        )
        return to_amount(jetton_wallet_data.balance, jetton_decimals)

    def swap_usdt_to_ton(
        self,
        to_receive_ton_amount: float | None = None,
        usdt_to_sell: float | None = None,
    ):
        if to_receive_ton_amount is None and usdt_to_sell is None:
            return "", 0, 0
        rate = TON.get_rate()
        if not usdt_to_sell:
            usdt_amount = round(to_receive_ton_amount * rate, 6)
        else:
            usdt_amount = usdt_to_sell - 0.1
            to_receive_ton_amount = round(usdt_to_sell / rate, 6)

        msg_hash = asyncio.run(
            self._w.transfer_message(
                message=StonfiSwapJettonToTONMessage(
                    jetton_master_address=settings.usdt_jetton_address,
                    jetton_amount=usdt_amount,
                    jetton_decimals=6,
                    min_amount=(
                        to_receive_ton_amount
                        - (to_receive_ton_amount * 0.015)  # 1.5% slippage
                    ),
                ),
            )
        )

        return msg_hash, to_receive_ton_amount, usdt_amount

    def log_wallet_info(self):
        balance = self.get_balance()
        logger.info("TON {} Wallet balance: {} TON", self._w.address.to_str(), balance)
