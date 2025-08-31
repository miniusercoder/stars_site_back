from fastapi import APIRouter

from integrations.Merchants.Cardlink.fastapi import router as cardlink
from integrations.Merchants.CryptoPay.fastapi import router as cryptopay
from integrations.Merchants.FreeKassa.fastapi import router as freekassa
from integrations.Merchants.Heleket.fastapi import router as heleket
from integrations.Merchants.Lolzteam.fastapi import router as lolzteam

merchants_router = APIRouter()
merchants_router.include_router(cryptopay)
merchants_router.include_router(cardlink)
merchants_router.include_router(heleket)
merchants_router.include_router(freekassa)
merchants_router.include_router(lolzteam)
