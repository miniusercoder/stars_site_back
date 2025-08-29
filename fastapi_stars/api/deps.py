from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

from django_stars.stars_app.models import User
from fastapi_stars.auth.jwt_utils import decode_any
from fastapi_stars.schemas.auth import Principal
from fastapi_stars.settings import settings

security = HTTPBearer(auto_error=True)


def current_principal(credentials=Depends(security)) -> Principal:
    payload = decode_any(credentials.credentials, settings.jwt_secret.get_secret_value(), settings.jwt_alg)
    typ = payload.get("type")
    if typ == "access":
        uid = payload.get("sub")
        try:
            return {
                "kind": "user",
                "user": User.objects.get(pk=uid),
                "payload": payload,
            }
        except User.DoesNotExist:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )
    elif typ == "guest":
        return {"kind": "guest", "payload": payload}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unsupported token type"
        )
