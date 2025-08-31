import hashlib

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse

from django_stars.stars_app.models import PaymentSystem, Payment

router = APIRouter()


# noinspection PyPep8Naming
@router.post("/freekassa", response_class=HTMLResponse)
def freekassa(
    MERCHANT_ID=Form(None),
    AMOUNT=Form(None),
    MERCHANT_ORDER_ID=Form(None),
    SIGN=Form(None),
):
    try:
        payment_system = PaymentSystem.objects.get(name=PaymentSystem.Names.FREEKASSA)
    except PaymentSystem.DoesNotExist:
        return "fail"
    sign_list = map(
        str,
        [
            MERCHANT_ID,
            AMOUNT,
            payment_system.secret_key.split(",")[1],
            MERCHANT_ORDER_ID,
        ],
    )
    md5 = hashlib.md5()
    sign = ":".join(sign_list).encode()
    md5.update(sign)
    sign = md5.hexdigest()
    if SIGN == sign:
        payment_id = MERCHANT_ORDER_ID
        payment = Payment.objects.filter(id=payment_id).first()
        if not payment or payment.status != payment.Status.CREATED:
            return "YES"
        payment.status = Payment.Status.CONFIRMED
        payment.save(update_fields=("status",))
        return "YES"
    return "YES"
