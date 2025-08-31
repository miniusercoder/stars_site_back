from fastapi import APIRouter
from integrations.Merchants.CryptoPay.fastapi import router as cryptopay

merchants_router = APIRouter()
merchants_router.include_router(cryptopay)
