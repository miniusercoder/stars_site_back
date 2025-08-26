from datetime import timedelta
from uuid import uuid4

from django.utils import timezone
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

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
)
from fastapi_stars.settings import settings

router = APIRouter()

GUEST_TTL_SEC = 7 * 24 * 3600  # 7 дней


# fastapi_app/api/v1/auth.py (добавка в ваш /auth/tonconnect)
class TonConnectProof(BaseModel):
    wallet_address: str
    signature: str
    guest_token: str | None = None


@router.post("/tonconnect", tags=["auth"])
def tonconnect_login(proof: TonConnectProof):
    # ... верификация TonConnect, поиск/создание AppUser user ...
    subject = TonConnectProof.wallet_address
    user, _ = User.objects.get_or_create(wallet_address=subject)

    # если пришёл guest_token — переназначаем
    if proof.guest_token:
        payload = decode_any(proof.guest_token, settings.jwt_secret, settings.jwt_alg)
        if payload.get("type") == "guest":
            sid = payload["sid"]
            try:
                gs = GuestSession.objects.get(pk=sid, is_active=True)
                # Order.objects.filter(guest_session=gs).update(
                #     user=user, guest_session=None
                # )
                gs.is_active = False
                gs.claimed_by_user_id = user.pk
                gs.save(update_fields=["is_active", "claimed_by_user_id"])
            except GuestSession.DoesNotExist:
                pass  # молча игнорируем

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
    GuestSession.objects.create(
        id=sid,
        expires_at=timezone.now() + timedelta(seconds=GUEST_TTL_SEC),
        is_active=True,
    )
    token = create_guest_token(
        settings.jwt_secret, settings.jwt_alg, GUEST_TTL_SEC, sid
    )
    return GuestTokenOut(guest=token)


@router.get("/session", response_model=SessionValidation, tags=["auth"])
def validate_session(principal: Principal = Depends(current_principal)):
    if principal["kind"] == "guest":
        gs = principal["guest"]
        if gs.expires_at <= timezone.now():
            return SessionValidation(success=False)
        return SessionValidation(success=True)
    elif principal["kind"] == "user":
        return SessionValidation(success=True)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
        )
