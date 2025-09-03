from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.params import Query

from django_stars.stars_app.models import Order
from fastapi_stars.api.deps import current_principal, Principal, user_principal
from fastapi_stars.schemas.users import UserOut, SuccessResponse, RefAliasIn

router = APIRouter()


@router.get("/me", response_model=UserOut)
def me(principal: Principal = Depends(user_principal)):
    user = principal["user"]
    return UserOut.model_validate(user)


@router.post("/ref_alias", response_model=SuccessResponse)
def set_ref_alias(
    ref_alias: RefAliasIn, principal: Principal = Depends(user_principal)
):
    user = principal["user"]
    user.ref_alias = ref_alias.ref_alias
    user.save(update_fields=("ref_alias",))
    return SuccessResponse()


@router.get("/orders")
def get_my_orders(
    search_query: Annotated[Optional[str], Query(...)] = None,
    order_type: Annotated[Optional[Order.Type], Query(...)] = None,
    principal: Principal = Depends(user_principal),
):
    pass
