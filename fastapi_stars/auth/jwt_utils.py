import time
import jwt
from fastapi import HTTPException, status


def now_ts() -> int:
    return int(time.time())


def create_guest_token(secret: str, alg: str, ttl_sec: int, sid: str) -> str:
    iat = now_ts()
    return jwt.encode(
        {"sid": sid, "iat": iat, "exp": iat + ttl_sec, "type": "guest"},
        secret,
        algorithm=alg,
    )


def create_user_token(
    user_id: str, secret: str, alg: str, ttl: int, token_type: str
) -> str:
    iat = now_ts()
    return jwt.encode(
        {
            "sub": user_id,
            "iat": iat,
            "exp": iat + ttl,
            "type": token_type,
        },
        secret,
        algorithm=alg,
    )


def decode_any(token: str, secret: str, alg: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=[alg])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
