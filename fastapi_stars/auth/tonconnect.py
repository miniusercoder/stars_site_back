# Здесь вы интегрируете проверку TonConnect proof (подписи кошелька).
# Функция должна вернуть уникальный идентификатор субъекта (wallet address / public key).
# Пока — примитивный заглушечный валидатор.

from fastapi import HTTPException, status


def verify_tonconnect_proof(proof: dict) -> str:
    # TODO: верифицировать подпись/chain state и извлечь адрес
    wallet = proof.get("wallet_address")
    signature = proof.get("signature")
    if not wallet or not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid proof"
        )
    # условно считаем валидным
    return wallet
