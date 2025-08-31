import asyncio
import hashlib
import hmac
import json

from fastapi import APIRouter, Header, Request
from fastapi.responses import HTMLResponse

from django_stars.stars_app.models import PaymentSystem, Payment

router = APIRouter()


@router.post("/cryptopay", response_class=HTMLResponse)
def cryptopay(
    request: Request, signature: str = Header(alias="crypto-pay-api-signature")
):
    try:
        payment_system = PaymentSystem.objects.get(name=PaymentSystem.Names.CRYPTOPAY)
    except PaymentSystem.DoesNotExist:
        return "fail"
    data = asyncio.run(request.body())
    secret = hashlib.sha256(payment_system.access_key.encode()).digest()
    local_signature = hmac.new(
        secret,
        data,
        "sha256",
    ).hexdigest()
    if local_signature == signature:
        invoice = json.loads(data)["payload"]
        if invoice["status"] != "paid":
            return "ok"
        payment_id = invoice["payload"]
        payment = Payment.objects.filter(id=payment_id).first()
        if not payment:
            return "fail"
        if payment.status != payment.Status.CREATED:
            return "fail"
        payment.status = Payment.Status.CONFIRMED
        payment.save(update_fields=("status",))
        return "ok"
    print(signature, local_signature)
    with open("cryptopay.json", "wb") as f:
        f.write(data)
    return "fail"
