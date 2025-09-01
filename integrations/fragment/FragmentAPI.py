import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag
from loguru import logger
from tonutils.wallet import HighloadWalletV3 as WalletClass

from .FragmentSession import FragmentSession
from .types import (
    PremiumBuy,
    PremiumRecipient,
    StarsBuy,
    StarsPrice,
    StarsRecipient,
)
from ..utils.singleton import Singleton
from ..wallet import Wallet


class FragmentAPI(metaclass=Singleton):
    ENDPOINT = "https://fragment.com"
    COOKIES_FILE = Path("fragment_cookies.json")

    _stars_recipients_cache: dict[str, tuple[datetime, StarsRecipient]] = {}
    _prem_recipients_cache: dict[str, tuple[datetime, PremiumRecipient]] = {}
    _ton_recipients_cache: dict[str, tuple[datetime, PremiumRecipient]] = {}
    _session_hash: Optional[str]
    _w: Wallet

    def __init__(self, wallet: Wallet) -> None:
        self._client: requests.Session = requests.Session()
        self._client.headers.update(self.get_headers())
        self._session_hash = None
        self._w = wallet
        self._load_cookies()

    def get_stars_recipient(self, username: str) -> StarsRecipient:
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        if (
            username in self._stars_recipients_cache
            and self._stars_recipients_cache[username][0] > one_hour_ago
        ):
            cached = self._stars_recipients_cache[username]
            return cached[1]

        resp = self._request(
            data={
                "method": "searchStarsRecipient",
                "quantity": "",
                "query": username,
            }
        )
        if not resp.get("ok"):
            logger.error(resp)
            raise ValueError("No recipient in response")
        recipient = StarsRecipient.model_validate(resp["found"])
        self._stars_recipients_cache[username] = (now, recipient)
        return recipient

    def get_stars_price(self, quantity: int) -> StarsPrice:
        resp = self._request(
            data={
                "method": "updateStarsPrices",
                "quantity": quantity,
            }
        )

        soup = BeautifulSoup(resp["cur_price"], "html.parser")

        ton_element = soup.find("div", class_="tm-value icon-before icon-ton")
        if not isinstance(ton_element, Tag):
            raise ValueError("stars TON price element not found or invalid")

        usd_element = soup.find("div", class_="tm-radio-desc wide-only")
        if not isinstance(usd_element, Tag):
            raise ValueError("stars USD price element not found or invalid")

        ton_value = float(ton_element.get_text(strip=True))

        usd_text = usd_element.get_text(strip=True)
        result = re.search(r"\d+[.\d+]*", usd_text)
        if not result:
            raise ValueError(f"No regexp match for USD price text: {usd_text}")
        usd_value = float(result.group())

        return StarsPrice(ton=ton_value, usd=usd_value)

    def stars_buy(
        self, recipient: str, quantity: int = 50, is_anonymous=False
    ) -> StarsBuy:
        init_stars_buy = self._request(
            data={
                "recipient": recipient,
                "quantity": quantity,
                "method": "initBuyStarsRequest",
            }
        )
        if not init_stars_buy.get("req_id"):
            logger.error(init_stars_buy)
            raise ValueError("No req_id in response")

        session = FragmentSession(self._w.get_wallet(WalletClass))
        account, device = session.get_account(), session.get_device()
        session.close()

        transaction_data = self._request(
            data={
                "account": json.dumps(account, separators=(",", ":")),
                "device": json.dumps(device, separators=(",", ":")),
                "transaction": "1",
                "id": init_stars_buy["req_id"],
                "show_sender": "0" if is_anonymous else "1",
                "method": "getBuyStarsLink",
            }
        )

        if not transaction_data.get("ok"):
            logger.error(transaction_data)
            raise ValueError("No transaction in response")

        return StarsBuy.model_validate(transaction_data)

    def get_premium_recipient(self, username: str) -> PremiumRecipient:
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        if (
            username in self._prem_recipients_cache
            and self._prem_recipients_cache[username][0] > one_hour_ago
        ):
            cached = self._prem_recipients_cache[username]
            return cached[1]

        resp = self._request(
            data={
                "method": "searchPremiumGiftRecipient",
                "months": "3",
                "query": username,
            }
        )
        if "error" in resp and "already subscribed" in resp["error"]:
            raise ValueError("already_subscribed")
        if not resp.get("ok"):
            logger.error(resp)
            raise ValueError("No recipient in response")
        recipient = PremiumRecipient.model_validate(resp["found"])
        self._prem_recipients_cache[username] = (now, recipient)
        return recipient

    def premium_buy(
        self, recipient: str, months: int = 3, is_anonymous=False
    ) -> PremiumBuy:
        init_stars_buy = self._request(
            data={
                "recipient": recipient,
                "months": months,
                "method": "initGiftPremiumRequest",
            }
        )
        if not init_stars_buy.get("req_id"):
            logger.error(init_stars_buy)
            raise ValueError("No req_id in response")

        session = FragmentSession(self._w.get_wallet(WalletClass))
        account, device = session.get_account(), session.get_device()
        session.close()

        transaction_data = self._request(
            data={
                "account": json.dumps(account, separators=(",", ":")),
                "device": json.dumps(device, separators=(",", ":")),
                "transaction": "1",
                "id": init_stars_buy["req_id"],
                "show_sender": "0" if is_anonymous else "1",
                "method": "getGiftPremiumLink",
            }
        )

        if not transaction_data.get("ok"):
            logger.error(transaction_data)
            raise ValueError("No transaction in response")

        return PremiumBuy.model_validate(transaction_data)

    def get_ton_recipient(self, username: str) -> PremiumRecipient:
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        if (
            username in self._ton_recipients_cache
            and self._ton_recipients_cache[username][0] > one_hour_ago
        ):
            cached = self._ton_recipients_cache[username]
            return cached[1]

        resp = self._request(
            data={
                "method": "searchAdsTopupRecipient",
                "query": username,
            }
        )
        if not resp.get("ok"):
            logger.error(resp)
            raise ValueError("No recipient in response")
        recipient = PremiumRecipient.model_validate(resp["found"])
        self._ton_recipients_cache[username] = (now, recipient)
        return recipient

    def ton_buy(self, recipient: str, amount: float, is_anonymous=False) -> PremiumBuy:
        init_ton_buy = self._request(
            data={
                "recipient": recipient,
                "amount": amount,
                "method": "initAdsTopupRequest",
            }
        )
        if not init_ton_buy.get("req_id"):
            logger.error(init_ton_buy)
            raise ValueError("No req_id in response")

        session = FragmentSession(self._w.get_wallet(WalletClass))
        account, device = session.get_account(), session.get_device()
        session.close()

        transaction_data = self._request(
            data={
                "account": json.dumps(account, separators=(",", ":")),
                "device": json.dumps(device, separators=(",", ":")),
                "transaction": "1",
                "id": init_ton_buy["req_id"],
                "show_sender": "0" if is_anonymous else "1",
                "method": "getAdsTopupLink",
            }
        )

        if not transaction_data.get("ok"):
            logger.error(transaction_data)
            raise ValueError("No transaction in response")

        return PremiumBuy.model_validate(transaction_data)

    def _request(self, tries=0, **kwargs) -> dict:
        if tries >= 3:
            raise Exception("Too many request attempts")
        if not self._session_hash:
            self._get_session_hash()

        endpoint = f"{self.ENDPOINT}/api?hash={self._session_hash}"
        response = self._client.post(endpoint, **kwargs)

        data = response.json()
        if isinstance(data, dict) and data.get("error") in (
            "Bad request",
            "Access denied",
        ):
            logger.error(f"Bad request or access denied: {data}")
            time.sleep(1)
            self._update_session()
            time.sleep(1)
            return self._request(tries=tries + 1, **kwargs)

        self._save_cookies()
        return self._validate_response(data)

    def _update_session(self):
        session = FragmentSession(self._w.get_wallet(WalletClass))
        session_cookies = session.authenticate()
        if not session_cookies:
            raise Exception("Failed to get session cookies")
        logger.debug(session_cookies)
        self._client.cookies.clear()
        self._client.cookies.update(session_cookies)
        self._session_hash = None
        session.close()
        self._save_cookies()

    def _get_session_hash(self):
        resp = self._client.get(url=self.ENDPOINT)
        session_hash = re.findall(r'apiUrl":"\\/api\?hash=(.+?)"', resp.text)[0]
        self._session_hash = session_hash

    def _load_cookies(self):
        if not self.COOKIES_FILE.exists():
            return
        try:
            with self.COOKIES_FILE.open("r", encoding="utf-8") as f:
                cookies_data = json.load(f)
            for key, value in cookies_data.items():
                self._client.cookies.set(key, value)
            logger.info("Loaded cookies from file: {}", self.COOKIES_FILE)
        except Exception as e:
            logger.error("Failed to load cookies: {}", e)

    def _save_cookies(self):
        try:
            cookies_data = requests.utils.dict_from_cookiejar(self._client.cookies)
            with self.COOKIES_FILE.open("w", encoding="utf-8") as f:
                json.dump(cookies_data, f)
        except Exception as e:
            logger.error("Failed to save cookies: {}", e)

    @staticmethod
    def _validate_response(response: dict) -> dict:
        if response.get("detail"):
            raise Exception(response["detail"])
        return response

    @staticmethod
    def get_headers() -> dict:
        return {
            "Origin": "https://fragment.com",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
        }

    @classmethod
    def find_cached_recipient(
        cls, username: str
    ) -> StarsRecipient | PremiumRecipient | None:
        return (
            cls._stars_recipients_cache.get(username, (None, None))[1]
            or cls._prem_recipients_cache.get(username, (None, None))[1]
        )
