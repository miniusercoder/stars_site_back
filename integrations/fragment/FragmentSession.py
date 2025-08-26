import json
import re
import time
from base64 import b64encode
from hashlib import sha256
from typing import Dict, Optional, Tuple

import requests
import requests.cookies
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from loguru import logger
from tonutils.wallet import Wallet


class FragmentSession:
    TC_APPDOMAIN: str = "fragment.com"
    _cookies: Optional[requests.cookies.RequestsCookieJar]

    def __init__(self, wallet: Wallet):
        self.wallet = wallet
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"
            }
        )
        self._cookies = None

    def close(self):
        self.session.close()

    def get_account(self):
        wallet_state_init = self.wallet.state_init.serialize().to_boc()
        wallet_state_init_base64 = b64encode(wallet_state_init).decode()

        workchain = self.wallet.address.wc
        address_hash = self.wallet.address.hash_part

        return {
            "address": f"{workchain}:{address_hash.hex()}",
            "chain": "-239",
            "walletStateInit": wallet_state_init_base64,
            "publicKey": self.wallet.public_key.hex(),
        }

    @staticmethod
    def get_device():
        return {
            "platform": "windows",
            "appName": "tonkeeper",
            "appVersion": "0.3.3",
            "maxProtocolVersion": 2,
            "features": [
                {
                    "name": "SendTransaction",
                    "maxMessages": 500,
                    "extraCurrencySupported": True,
                },
                {"name": "SignData", "types": ["text", "binary", "cell"]},
            ],
        }

    def _generate_proof(self, payload_hex: str) -> Tuple[dict, dict, dict]:
        workchain = self.wallet.address.wc
        address_hash = self.wallet.address.hash_part
        timestamp = int(time.time())

        domain_bytes = self.TC_APPDOMAIN.encode("utf-8")
        message = (
            b"ton-proof-item-v2/"
            + workchain.to_bytes(4, "little")
            + address_hash
            + len(domain_bytes).to_bytes(4, "little")
            + domain_bytes
            + timestamp.to_bytes(8, "little")
            + payload_hex.encode()
        )

        signature_message = b"\xff\xffton-connect" + sha256(message).digest()
        final_hash = sha256(signature_message).digest()

        private_key = Ed25519PrivateKey.from_private_bytes(self.wallet.private_key[:32])
        signature = private_key.sign(final_hash)

        proof = {
            "timestamp": timestamp,
            "domain": {"lengthBytes": len(domain_bytes), "value": self.TC_APPDOMAIN},
            "signature": b64encode(signature).decode(),
            "payload": payload_hex,
        }

        account = self.get_account()
        device = self.get_device()
        return account, device, proof

    def _fetch_session_tokens(self) -> Tuple[Optional[str], Optional[str]]:
        response = self.session.get("https://fragment.com/")
        text = response.text
        session_hash_match = re.search(r'apiUrl":"\\/api\?hash=(.+?)"', text)
        ton_proof_match = re.search(r'"ton_proof":"(.+?)"', text)

        if session_hash_match and ton_proof_match:
            return session_hash_match.group(1), ton_proof_match.group(1)

        return None, None

    def _send_proof_to_fragment(
        self, account: dict, device: dict, proof: dict, session_hash: str
    ) -> bool:
        data = {
            "account": json.dumps(account),
            "device": json.dumps(device),
            "proof": json.dumps(proof),
            "method": "checkTonProofAuth",
        }

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://fragment.com",
            "Referer": "https://fragment.com/",
        }

        cookies = {"stel_dt": "-180"}

        response = self.session.post(
            f"https://fragment.com/api?hash={session_hash}",
            data=data,
            headers=headers,
            cookies=cookies,
        )

        logger.info("Proof data successfully sent to Fragment")
        self._cookies = response.cookies
        return response.json().get("verified", False)

    def authenticate(self) -> Dict[str, str]:
        logger.info("Starting authentication process on Fragment")

        session_hash, ton_proof = self._fetch_session_tokens()
        if not session_hash or not ton_proof:
            logger.error("Failed to obtain session tokens from Fragment")
            return {}

        logger.info(f"Session hash obtained: {session_hash}")
        account, device, proof = self._generate_proof(ton_proof)

        result = self._send_proof_to_fragment(account, device, proof, session_hash)
        if result:
            logger.info("Authentication completed successfully")
            return requests.utils.dict_from_cookiejar(self._cookies)
        else:
            logger.error("Authentication failed")
            return {}
