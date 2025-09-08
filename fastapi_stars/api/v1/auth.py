from typing import Annotated, Optional
from uuid import uuid4

from django.db import transaction
from django.db.models import Q
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.params import Query
from pytoniq_core import Address, AddressError
from tonutils.tonconnect.models import TonProof
from tonutils.tonconnect.utils import generate_proof_payload
from tonutils.tonconnect.utils.verifiers import verify_ton_proof

from django_stars.stars_app.models import User, GuestSession, Order, Referral
from fastapi_stars.api.deps import Principal, current_principal
from fastapi_stars.auth.jwt_utils import (
    create_guest_token,
    decode_any,
    create_user_token,
)
from fastapi_stars.schemas.auth import (
    TokenPair,
    RefreshIn,
    GuestTokenOut,
    SessionValidation,
    TonConnectProof,
)
from fastapi_stars.settings import settings

router = APIRouter()


def _normalize_wallet(address_str: str) -> Optional[str]:
    """
    Нормализует TON-адрес в non-bounceable строку. Возвращает None, если адрес невалиден.
    """
    try:
        return Address(address_str).to_str(is_bounceable=False)
    except Exception:
        return None


def _assign_ref_chain_for_new_user(
    new_user: User, ref_wallet_raw: str, max_levels: int = 3
) -> None:
    """
    Создаёт Referral-связи new_user ← referrer (lvl=1) ← referrer2 (lvl=2) ← referrer3 (lvl=3).
    Вызывается ТОЛЬКО при первичном создании new_user.
    """
    ref_wallet = _normalize_wallet(ref_wallet_raw)
    if not ref_wallet:
        return

    # Стартовый реферер (уровень 1)
    current_ref = User.objects.filter(wallet_address=ref_wallet).first()
    if not current_ref or current_ref == new_user:
        return  # не существует или самореферал — игнорируем

    visited = {new_user.pk}  # защита от циклов
    level = 1

    while current_ref and level <= max_levels:
        if current_ref.pk in visited or current_ref == new_user:
            break
        visited.add(current_ref.pk)

        # Создаём связь, если её нет (unique_together защитит от гонок)
        Referral.objects.get_or_create(
            referrer=current_ref,
            referred=new_user,
            defaults={"level": level, "profit": 0.0},
        )

        # Переходим к рефереру текущего реферера (т.е. к "дедушке")
        current_ref = current_ref.referrer
        level += 1


@router.post("/tonconnect", response_model=TokenPair)
def tonconnect_login(
    proof: TonConnectProof, principal: Principal = Depends(current_principal)
):
    if principal["kind"] != "guest":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only guest sessions can use TonConnect login",
        )

    # Валидация адреса из доказательства
    try:
        subject_addr = Address(proof.account.address)
    except AddressError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid wallet address"
        )

    # Криптопроверка подписи
    if not verify_ton_proof(
        proof.account.public_key,
        TonProof.from_dict(proof.model_dump()),
        subject_addr,
        principal["payload"]["ton_verify"],
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TonConnect proof"
        )

    subject = subject_addr.to_str(is_bounceable=False)

    with transaction.atomic():
        user, created = User.objects.get_or_create(wallet_address=subject)

        # Назначаем рефоводов только если это свежая регистрация
        if created and principal["payload"].get("ref"):
            _assign_ref_chain_for_new_user(
                new_user=user,
                ref_wallet_raw=principal["payload"]["ref"],
                max_levels=3,
            )

        # Привязываем гостевую сессию и заказы
        gs = GuestSession.objects.filter(pk=principal["payload"]["sid"]).first()
        if gs:
            Order.objects.filter(guest_session=gs).update(user=user, guest_session=None)
            gs.claimed_by_user = user
            gs.save(update_fields=("claimed_by_user",))

    # Выдаём обычные access/refresh
    return TokenPair(
        access=create_user_token(
            str(user.pk),
            settings.jwt_secret.get_secret_value(),
            settings.jwt_alg,
            settings.jwt_access_ttl,
            "access",
        ),
        refresh=create_user_token(
            str(user.pk),
            settings.jwt_secret.get_secret_value(),
            settings.jwt_alg,
            settings.jwt_refresh_ttl,
            "refresh",
        ),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh_tokens(body: RefreshIn):
    payload = decode_any(
        body.refresh, settings.jwt_secret.get_secret_value(), settings.jwt_alg
    )
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
        )
    user_id = payload.get("sub")
    if not user_id or not User.objects.filter(pk=user_id).exists():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    return TokenPair(
        access=create_user_token(
            user_id,
            settings.jwt_secret.get_secret_value(),
            settings.jwt_alg,
            settings.jwt_access_ttl,
            "access",
        ),
        refresh=create_user_token(
            user_id,
            settings.jwt_secret.get_secret_value(),
            settings.jwt_alg,
            settings.jwt_refresh_ttl,
            "refresh",
        ),
    )


@router.post("/guest", response_model=GuestTokenOut)
def create_guest(ref: Annotated[str, Query(..., max_length=100)] = None):
    if ref:
        ref_user = User.objects.filter(Q(wallet_address=ref) | Q(ref_alias=ref)).first()
        if not ref_user:
            ref = None
        else:
            ref = ref_user.wallet_address
    sid = str(uuid4())
    payload_hash = generate_proof_payload()
    token = create_guest_token(
        settings.jwt_secret.get_secret_value(),
        settings.jwt_alg,
        settings.jwt_guest_ttl,
        sid,
        payload_hash,
        ref,
    )
    return GuestTokenOut(
        guest=token,
        ton_verify=payload_hash,
    )


@router.get("/session", response_model=SessionValidation)
def validate_session(principal: Principal = Depends(current_principal)):
    if principal["kind"] == "guest":
        return SessionValidation(success=True, token_type=principal["kind"])
    elif principal["kind"] == "user":
        return SessionValidation(
            success=True,
            token_type=principal["kind"],
            wallet_address=Address(principal["user"].wallet_address).to_str(
                is_user_friendly=False
            ),
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
        )
