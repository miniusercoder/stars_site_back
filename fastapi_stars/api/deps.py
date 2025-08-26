from django.utils import timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

from django_stars.stars_app.models import User, GuestSession  # ваша доменная модель
from fastapi_stars.auth.jwt_utils import decode_any
from fastapi_stars.schemas.auth import Principal
from fastapi_stars.settings import settings

security = HTTPBearer(auto_error=True)


def current_principal(credentials=Depends(security)) -> Principal:
    payload = decode_any(credentials.credentials, settings.jwt_secret, settings.jwt_alg)
    typ = payload.get("type")
    if typ == "access":
        uid = payload.get("sub")
        try:
            return {"kind": "user", "user": User.objects.get(pk=uid)}
        except User.DoesNotExist:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )
    elif typ == "guest":
        sid = payload.get("sid")
        try:
            gs = GuestSession.objects.get(pk=sid, is_active=True)
        except GuestSession.DoesNotExist:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Guest session invalid"
            )
        if gs.expires_at <= timezone.now():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Guest session expired"
            )
        return {"kind": "guest", "guest": gs}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unsupported token type"
        )
