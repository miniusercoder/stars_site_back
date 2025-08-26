import base64
import binascii
import json

import requests
from loguru import logger


def is_b64(addr: str) -> bool:
    try:
        base64.urlsafe_b64decode(addr)
        return True
    except binascii.Error:
        return False


class IncompleteTransactionError(Exception):
    """
    Exception raised when a transaction is incomplete.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundTransactionError(Exception):
    """
    Exception raised when a transaction is not found.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class TonCenterError(Exception):
    """
    Base exception for TonCenter service errors.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class TonCenter:
    """
    TonCenter service for interacting with the TON blockchain.
    """

    __client: requests.Session | None = None

    def __init__(self, api_key: str):
        """
        Initialize the TonCenter service with the provided API key.

        :param api_key: The API key for TonCenter.
        """
        self.api_key = api_key
        self.base_url = "https://toncenter.com/api/v3"
        self.headers = {"X-API-Key": self.api_key}

    @property
    def client(self):
        """
        Returns the base URL for the TonCenter API.

        :return: The base URL for the TonCenter API.
        """
        if self.__client:
            return self.__client
        self.__client = requests.Session()
        self.__client.headers.update(self.headers)
        return self.__client

    def get_transaction_by_msg_hash(
        self, msg_hash: str, body_msg_hash: str | None = None
    ) -> tuple[dict, str] | None:
        """
        Fetch a transaction by its message hash.

        :param body_msg_hash: The body message hash of the transaction, if available.
        :param msg_hash: The message hash of the transaction.
        :return: The transaction data as a JSON object.
        """
        if not is_b64(msg_hash):
            msg_hash = base64.urlsafe_b64encode(bytes.fromhex(msg_hash)).decode("utf-8")
        url = f"{self.base_url}/traces"
        params = {
            "msg_hash": msg_hash,
            "limit": 1,
        }
        response = self.client.get(url, params=params)
        try:
            response = response.json()
        except json.JSONDecodeError:
            error_message = response.text
            logger.error(f"TonCenter API error: {error_message}")
            raise TonCenterError(f"TonCenter API error: {error_message}")
        if response.get("error"):
            error_message = response["error"]
            logger.error(f"TonCenter API error: {error_message}")
            raise TonCenterError(f"TonCenter API error: {error_message}")
        transactions = response.get("traces", [])
        if len(transactions) == 0:
            raise NotFoundTransactionError(
                f"Transaction with msg_hash {msg_hash} not found."
            )
        transaction = transactions[0]
        if (
            transaction["is_incomplete"]
            or transaction["trace_info"].get("pending_messages", 0) != 0
        ):
            raise IncompleteTransactionError(
                f"Transaction with msg_hash {msg_hash} is incomplete. "
                "Please try again later or check the transaction status."
            )
        parent_transaction_id = transaction["transactions_order"][0]
        parent_transaction = transaction["transactions"].get(parent_transaction_id)
        if not body_msg_hash:
            return parent_transaction, ""
        for _transaction in transaction.get("transactions", {}).values():
            for out_msg in _transaction.get("out_msgs", []):
                if out_msg.get("message_content", {}).get("hash") == body_msg_hash:
                    return out_msg, transaction["trace_id"]
        logger.error(
            f"Transaction with body_msg_hash {body_msg_hash} not found in msg_hash {msg_hash}."
        )
        logger.debug(json.dumps(transaction))
        raise NotFoundTransactionError(
            f"Transaction with body_msg_hash {body_msg_hash} not found in msg_hash {msg_hash}."
        )
