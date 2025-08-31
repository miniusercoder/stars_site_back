from django_stars.stars_app.models import Order
from fastapi_stars.settings import settings
from integrations.Merchants.CryptoPay import CryptoPay


def generate_pay_link(order: Order):
    payment = order.payment.first()
    match payment.method.system.name:
        case "CryptoPay":
            cryptopay = CryptoPay(payment.method.system.access_key)
            link = cryptopay.create_bill(
                payment.id,
                "USD",
                order.price,
                f"Pay for HelperStars #{order.id}",
                settings.pay_success_url,
            )
            if link.status:
                return link.pay_url
            return None
    return None
