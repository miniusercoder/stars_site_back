from fastapi_stars.settings import settings
from .main import Wallet


def get_wallet() -> Wallet:
    return Wallet(
        api_key=settings.ton_api_key,
        mnemonic=settings.ton_mnemonic,
        is_testnet=False,
    )
