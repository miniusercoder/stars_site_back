import ctypes
from enum import IntEnum

from loguru import logger

from fastapi_stars.settings import settings
from integrations.utils.singleton import Singleton


class ErrorCodes(IntEnum):
    SUCCESS = 0
    CREATE_CLIENT_ERROR = -1
    CONNECT_ERROR = -2
    INVALID_USERNAME = -3
    PAYMENT_FORM_ERROR = -4
    SEND_GIFT_ERROR = -5
    CLIENT_NOT_INITIALIZED = -6


class GiftSender(metaclass=Singleton):
    initialized = False
    lib = None

    def __init__(self, api_id: int, api_hash: str):
        self.lib = ctypes.CDLL("./libtg.so")

        # Установка сигнатур функций
        self.lib.SendGift.argtypes = [ctypes.c_char_p, ctypes.c_int64, ctypes.c_int]
        self.lib.SendGift.restype = ctypes.c_int
        self.lib.ValidateRecipient.argtypes = [ctypes.c_char_p]
        self.lib.ValidateRecipient.restype = ctypes.c_int
        self.lib.Init.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p]
        self.lib.Init.restype = ctypes.c_int

        init_result = self.lib.Init(
            api_id,
            api_hash.encode("utf-8"),
            "stars.dat".encode("utf-8"),
        )
        logger.info(f"Initialization result: {ErrorCodes(init_result).name}")
        # Проверка успешной инициализации
        if init_result != 0:
            logger.error(
                f"Failed to initialize the library: {ErrorCodes(init_result).name}"
            )
            return
        self.initialized = True

    def validate_recipient(self, username: str) -> bool:
        if not self.initialized:
            raise RuntimeError("GiftSender not initialized")
        result = self.lib.ValidateRecipient(username.encode("utf-8"))
        if result == ErrorCodes.SUCCESS:
            return True
        elif result == ErrorCodes.INVALID_USERNAME:
            return False
        else:
            logger.error(
                f"Error while validating recipient {username}: {ErrorCodes(result).name}"
            )
            return False

    def send_gift(self, username: str, gift_id: int, anonymous: bool) -> bool:
        if not self.initialized:
            raise RuntimeError("GiftSender not initialized")
        try:
            sent_result = self.lib.SendGift(
                username.encode("utf-8"), int(gift_id), int(anonymous)
            )
        except Exception:
            logger.exception(f"Error while sending gift to {username}")
            return False

        if sent_result != ErrorCodes.SUCCESS:
            logger.error(
                f"Error while sending gift to {username}: {ErrorCodes(sent_result).name}"
            )
            return False
        return True


def get_gift_sender() -> GiftSender:
    return GiftSender(
        settings.telegram_api_id,
        settings.telegram_api_hash.get_secret_value(),
    )
