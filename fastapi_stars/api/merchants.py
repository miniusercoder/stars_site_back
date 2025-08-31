from fastapi import APIRouter

from integrations.Merchants.CryptoPay.fastapi import router as cryptopay
from integrations.Merchants.Cardlink.fastapi import router as cardlink
from integrations.Merchants.Heleket.fastapi import router as heleket

merchants_router = APIRouter()
merchants_router.include_router(cryptopay)
merchants_router.include_router(cardlink)
merchants_router.include_router(heleket)
