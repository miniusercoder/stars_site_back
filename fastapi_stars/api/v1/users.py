from fastapi import APIRouter, Depends, HTTPException

from fastapi_stars.api.deps import current_principal, Principal
from fastapi_stars.schemas.users import UserOut
from django_stars.stars_app.models import User

router = APIRouter()


@router.get("/me", response_model=UserOut)
def me(principal: Principal = Depends(current_principal)):
    if principal["kind"] != "user":
        raise HTTPException(
            status_code=403, detail="Access forbidden: not a user principal"
        )
    user = principal["user"]
    return UserOut.model_validate(user)
