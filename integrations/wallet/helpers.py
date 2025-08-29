from fastapi_stars.settings import settings
from .main import Wallet


def get_wallet() -> Wallet:
    return Wallet(
        api_key=settings.ton_api_key.get_secret_value(),
        mnemonic=settings.ton_mnemonic.get_secret_value(),
        is_testnet=False,
    )
