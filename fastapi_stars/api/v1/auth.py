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
    Нормализует TON-адрес к non-bounceable строке.

    :param address_str: Адрес кошелька в любом поддерживаемом формате.
    :return: Нормализованная non-bounceable строка адреса или None, если адрес невалиден.
    """
    try:
        return Address(address_str).to_str(is_bounceable=False)
    except Exception:
        return None


def _assign_ref_chain_for_new_user(
    new_user: User, ref_wallet_raw: str, max_levels: int = 3
) -> None:
    """
    Создаёт реферальную цепочку для только что созданного пользователя.

    Формирует связи вида:
      new_user ← referrer (lvl=1) ← referrer2 (lvl=2) ← referrer3 (lvl=3)

    Ограничения и защита:
    * Цепочка строится максимум до `max_levels` уровней.
    * Исключаются циклы и самореферал.
    * Идём по полю `User.referrer` "вверх" по дереву.

    :param new_user: Новый пользователь, для которого строится цепочка.
    :param ref_wallet_raw: Адрес (или то, что на него похоже) предполагаемого реферера.
    :param max_levels: Максимальная глубина цепочки (по умолчанию 3).
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


@router.post(
    "/tonconnect",
    response_model=TokenPair,
    summary="Логин через TonConnect",
    description=(
        "Верифицирует доказательство TonConnect (подпись, домен, payload) и авторизует пользователя по TON-адресу. "
        "Для вызова требуется **гостевой** токен (полученный из `/guest`), включающий `ton_verify` payload. "
        "При первой авторизации пользователя дополнительно привязывает реферальную цепочку и переносит заказы из гостевой сессии."
    ),
    responses={
        200: {
            "description": "Успешная авторизация, выданы пара токенов (access/refresh)."
        },
        400: {
            "description": "Некорректный адрес кошелька или доказательство TonConnect."
        },
        401: {"description": "Недействительная сессия/тип токена."},
    },
)
def tonconnect_login(
    proof: TonConnectProof, principal: Principal = Depends(current_principal)
):
    """
    Проверяет корректность TonConnect-доказательства и выдаёт пару JWT токенов пользователя.

    Требования:
    * Текущая сессия должна быть **гостевой**.
    * Подпись и payload проверяются с помощью `verify_ton_proof`.

    Побочные эффекты:
    * При первичной регистрации назначаются реферальные связи.
    * Заказы из гостевой сессии переносятся на пользователя.
    """
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


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Обновление пары токенов",
    description=(
        "Принимает **refresh** токен, проверяет, что его тип корректен и пользователь существует, "
        "после чего выдаёт новую пару `access`/`refresh`."
    ),
    responses={
        200: {"description": "Токены успешно обновлены."},
        401: {"description": "Неверный тип токена или пользователь не найден."},
    },
)
def refresh_tokens(body: RefreshIn):
    """
    Обновляет JWT-токены по действительному refresh-токену.
    """
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


@router.post(
    "/guest",
    response_model=GuestTokenOut,
    summary="Создание гостевого токена",
    description=(
        "Создаёт анонимную гостевую сессию и возвращает JWT для гостя вместе с `ton_verify` payload. "
        "Этот payload должен быть использован при последующей авторизации через TonConnect в `/tonconnect`."
    ),
    responses={
        200: {"description": "Гостевой токен создан."},
    },
)
def create_guest(
    ref: Annotated[
        str,
        Query(
            ...,
            max_length=100,
            description=(
                "Код реферала: TON-адрес **или** реф-алиас. "
                "Если пользователь с таким значением не найден — реферал игнорируется."
            ),
            examples=["EQD...myWallet", "cool-invite"],
        ),
    ] = None,
):
    """
    Возвращает гостевой JWT и значение `ton_verify`, необходимое для TonConnect-доказательства.
    """
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


@router.get(
    "/session",
    response_model=SessionValidation,
    summary="Проверка валидности текущей сессии",
    description=(
        "Возвращает тип текущего токена (`guest` или `user`) и, для пользователя, технический формат адреса кошелька."
    ),
    responses={
        200: {"description": "Сессия валидна."},
        401: {"description": "Недействительная сессия."},
    },
)
def validate_session(principal: Principal = Depends(current_principal)):
    """
    Проверяет токен из авторизации запроса и сообщает его тип.

    Для пользователя дополнительно возвращается `wallet_address` в техническом формате (not user-friendly).
    """
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
