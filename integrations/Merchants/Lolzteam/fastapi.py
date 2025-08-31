from fastapi import APIRouter, Body, Header
from fastapi.responses import HTMLResponse
from loguru import logger

from django_stars.stars_app.models import PaymentSystem, Payment

router = APIRouter()


@router.post("/lolzteam", response_class=HTMLResponse)
def lolzteam(data=Body(), secret_key=Header(alias="x-secret-key")):
    try:
        payment_system = PaymentSystem.objects.get(name=PaymentSystem.Names.LOLZTEAM)
    except PaymentSystem.DoesNotExist:
        return "fail"
    if secret_key != payment_system.secret_key:
        logger.error(f"Invalid secret key in webhook: {secret_key}")
        return HTMLResponse("Fail", 403)
    if not isinstance(data, dict):
        logger.error("Webhook received with non-dict payload: {}", data)
        return HTMLResponse("Fail", 500)

    if data.get("status") != "paid":
        logger.info("Payment not completed yet or failed: {}", data)
        return "ok"

    payment = Payment.objects.filter(id=data.get("payment_id")).first()
    if not payment:
        return HTMLResponse("Fail", 500)

    if payment.status != payment.Status.CREATED:
        return HTMLResponse("Fail", 500)

    payment.status = payment.Status.CONFIRMED
    payment.save(update_fields=("status",))
    return "ok"
