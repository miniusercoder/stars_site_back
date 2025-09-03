from django_stars.stars_app.models import Order
from fastapi_stars.settings import settings
from integrations.Currencies import USDT
from integrations.Merchants.Cardlink import CardLink
from integrations.Merchants.CryptoPay import CryptoPay
from integrations.Merchants.FreeKassa import FreeKassa
from integrations.Merchants.Heleket import Heleket
from integrations.Merchants.Lolzteam import LolzTeam


def generate_pay_link(order: Order, user_ip: str):
    payment = order.payment.first()
    link = None
    match payment.method.system.name:
        case payment.method.system.Names.CRYPTOPAY:
            cryptopay = CryptoPay(payment.method.system.access_key)
            link = cryptopay.create_bill(
                payment.id,
                "USD",
                order.price,
                f"Pay for HelperStars #{order.id}",
                settings.pay_success_url,
            )
        case payment.method.system.Names.CARDLINK:
            cardlink = CardLink(
                payment.method.system.shop_id, payment.method.system.access_key
            )
            amount = USDT.usd_to_rub(order.price)
            link = cardlink.create_bill(payment.id, amount)
        case payment.method.system.Names.HELEKET:
            heleket = Heleket(
                payment.method.system.shop_id, payment.method.system.access_key
            )
            link = heleket.create_bill(
                payment.id, order.price, settings.pay_success_url
            )
        case payment.method.system.Names.FREEKASSA:
            amount = USDT.usd_to_rub(order.price)
            freekassa = FreeKassa(
                payment.method.system.shop_id,
                payment.method.system.secret_key.split(",")[0],
                payment.method.system.access_key,
            )
            if payment.method.code:
                link = freekassa.create_bill(
                    payment.id,
                    amount,
                    payment.method.code,
                    user_ip,
                    order.recipient_username + "@example.com",
                )
            else:
                link = freekassa.create_sci(payment.id, amount)
        case payment.method.system.Names.LOLZTEAM:
            lolzteam = LolzTeam(
                payment.method.system.shop_id,
                payment.method.system.access_key,
            )
            amount = USDT.usd_to_rub(order.price)
            link = lolzteam.create_bill(payment.id, amount, settings.pay_success_url)
    if link and link.status:
        payment.payment_id = link.id
        payment.save(update_fields=("payment_id",))
        return link.url
    return None
