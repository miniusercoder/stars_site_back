from hashlib import md5
from typing import Annotated

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse
from loguru import logger

from django_stars.stars_app.models import PaymentSystem, Payment

router = APIRouter()


@router.post("/cardlink", response_class=HTMLResponse)
def cardlink(
    amount: Annotated[str, Form(alias="OutSum")],
    payment_id: Annotated[str, Form(alias="InvId")],
    signature: Annotated[str, Form(alias="SignatureValue")],
    status: Annotated[str, Form(alias="Status")],
):
    try:
        payment_system = PaymentSystem.objects.get(name=PaymentSystem.Names.CARDLINK)
    except PaymentSystem.DoesNotExist:
        return HTMLResponse("fail", status_code=400)
    local_signature = (
        md5(f"{amount}:{payment_id}:{payment_system.access_key}".encode())
        .hexdigest()
        .upper()
    )
    if local_signature == signature:
        if status != "SUCCESS":
            return HTMLResponse("fail", 400)
        payment_id = payment_id
        payment = Payment.objects.filter(id=payment_id).first()
        if not payment:
            logger.debug(f"Cardlink: Payment with ID {payment_id} not found.")
            return HTMLResponse("fail", 400)
        payment.refresh_from_db(fields=("status",))
        if payment.status != payment.Status.CREATED:
            logger.debug(f"Cardlink: Payment {payment_id} already processed.")
            return HTMLResponse("fail", 400)
        payment.status = payment.Status.CONFIRMED
        payment.save(update_fields=("status",))
        return HTMLResponse("ok", 200)
    logger.debug("Cardlink: Signature mismatch.")
    return HTMLResponse("fail", status_code=400)
