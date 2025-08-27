from datetime import timedelta
from uuid import uuid4

from django.utils import timezone
from fastapi import APIRouter, HTTPException, status, Depends
from pytoniq_core import Address, AddressError
from tonutils.tonconnect.models import TonProof
from tonutils.tonconnect.utils import generate_proof_payload
from tonutils.tonconnect.utils.verifiers import verify_ton_proof

from django_stars.stars_app.models import User, GuestSession
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

GUEST_TTL_SEC = 7 * 24 * 3600  # 7 дней


@router.post("/tonconnect", tags=["auth"])
def tonconnect_login(
    proof: TonConnectProof, principal: Principal = Depends(current_principal)
):
    if not principal["kind"] == "guest":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only guest sessions can use TonConnect login",
        )
    try:
        subject = Address(proof.account.address).to_str()
    except AddressError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid wallet address"
        )
    if not verify_ton_proof(
        proof.account.public_key,
        TonProof.from_dict(proof.model_dump()),
        subject,
        principal["guest"].ton_verify,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TonConnect proof"
        )
    user, _ = User.objects.get_or_create(wallet_address=subject)

    # если пришёл guest_token — переназначаем
    gs = principal["guest"]
    # Order.objects.filter(guest_session=gs).update(
    #     user=user, guest_session=None
    # )
    gs.is_active = False
    gs.claimed_by_user_id = user.pk
    gs.save(update_fields=["is_active", "claimed_by_user_id"])

    # выдаём обычные access/refresh
    return {
        "access": create_user_token(
            str(user.pk),
            settings.jwt_secret,
            settings.jwt_alg,
            settings.jwt_access_ttl,
            "access",
        ),
        "refresh": create_user_token(
            str(user.pk),
            settings.jwt_secret,
            settings.jwt_alg,
            settings.jwt_refresh_ttl,
            "refresh",
        ),
    }


@router.post("/refresh", response_model=TokenPair)
def refresh_tokens(body: RefreshIn):
    payload = decode_any(body.refresh, settings.jwt_secret, settings.jwt_alg)
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
            settings.jwt_secret,
            settings.jwt_alg,
            settings.jwt_access_ttl,
            "access",
        ),
        refresh=create_user_token(
            user_id,
            settings.jwt_secret,
            settings.jwt_alg,
            settings.jwt_refresh_ttl,
            "refresh",
        ),
    )


@router.post("/guest", response_model=GuestTokenOut, tags=["auth"])
def create_guest():
    sid = str(uuid4())
    payload_hash = generate_proof_payload()
    GuestSession.objects.create(
        id=sid,
        expires_at=timezone.now() + timedelta(seconds=GUEST_TTL_SEC),
        ton_verify=payload_hash,
        is_active=True,
    )
    token = create_guest_token(
        settings.jwt_secret, settings.jwt_alg, GUEST_TTL_SEC, sid, payload_hash
    )
    return GuestTokenOut(
        guest=token,
        ton_verify=payload_hash,
    )


@router.get("/session", response_model=SessionValidation, tags=["auth"])
def validate_session(principal: Principal = Depends(current_principal)):
    if principal["kind"] == "guest":
        gs = principal["guest"]
        if gs.expires_at <= timezone.now():
            return SessionValidation(success=False)
        return SessionValidation(success=True, token_type=principal["kind"])
    elif principal["kind"] == "user":
        return SessionValidation(success=True, token_type=principal["kind"])
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
        )
