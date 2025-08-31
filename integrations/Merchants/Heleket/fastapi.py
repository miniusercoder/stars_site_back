from base64 import b64encode
from hashlib import md5

import ujson
from fastapi import APIRouter, Body
from fastapi.responses import HTMLResponse
from loguru import logger

from django_stars.stars_app.models import PaymentSystem, Payment

router = APIRouter()


@router.post("/heleket", response_class=HTMLResponse)
def heleket(data=Body()):
    if not isinstance(data, dict):
        return HTMLResponse("Fail", 500)
    try:
        payment_system = PaymentSystem.objects.get(name=PaymentSystem.Names.HELEKET)
    except PaymentSystem.DoesNotExist:
        return HTMLResponse("fail", status_code=400)
    sign = data.get("sign")
    del data["sign"]
    local_signature = md5(
        b64encode(
            ujson.dumps(
                data,
                ensure_ascii=False,
                separators=(",", ":"),
                escape_forward_slashes=True,
            ).encode("utf-8")
        )
        + payment_system.access_key.encode("utf-8")
    ).hexdigest()
    if local_signature != sign:
        logger.error(f"Wrong sign {local_signature} {sign}")
        return HTMLResponse("Fail", 400)
    payment = Payment.objects.filter(id=data["order_id"]).first()
    if not payment:
        logger.error("Not exist")
        return HTMLResponse("Fail", 500)
    if payment.status != payment.Status.CREATED:
        logger.error("Bad status")
        return HTMLResponse("Fail", 500)
    payment.status = payment.Status.CONFIRMED
    payment.save(update_fields=("status",))
    return "ok"
