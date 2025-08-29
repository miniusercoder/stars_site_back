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


@router.post("/tonconnect", response_model=TokenPair)
def tonconnect_login(
    proof: TonConnectProof, principal: Principal = Depends(current_principal)
):
    if not principal["kind"] == "guest":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only guest sessions can use TonConnect login",
        )
    try:
        subject = Address(proof.account.address)
    except AddressError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid wallet address"
        )
    if not verify_ton_proof(
        proof.account.public_key,
        TonProof.from_dict(proof.model_dump()),
        subject,
        principal["payload"]["ton_verify"],
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TonConnect proof"
        )
    subject = subject.to_str()
    user, _ = User.objects.get_or_create(wallet_address=subject)

    gs = GuestSession.objects.get_or_create(pk=principal["payload"]["sid"])[0]
    # Order.objects.filter(guest_session=gs).update(
    #     user=user, guest_session=None
    # )
    gs.claimed_by_user = user
    gs.save(update_fields=("claimed_by_user",))

    # выдаём обычные access/refresh
    return TokenPair(
        access=create_user_token(
            str(user.pk),
            settings.jwt_secret,
            settings.jwt_alg,
            settings.jwt_access_ttl,
            "access",
        ),
        refresh=create_user_token(
            str(user.pk),
            settings.jwt_secret,
            settings.jwt_alg,
            settings.jwt_refresh_ttl,
            "refresh",
        ),
    )


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


@router.post("/guest", response_model=GuestTokenOut)
def create_guest():
    sid = str(uuid4())
    payload_hash = generate_proof_payload()
    token = create_guest_token(
        settings.jwt_secret, settings.jwt_alg, settings.jwt_guest_ttl, sid, payload_hash
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
