if True:  # Не сортировать этот импорт
    from fastapi_stars.scripts import init_django  # noqa: F401

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi_stars.api.routing import api_router
from fastapi_stars.settings import settings

app = FastAPI(
    title="HelperStars Site API",
    version="1.0.0",
    servers=[
        {"url": "https://helperstars.tg", "description": "Production"},
        {"url": "http://127.0.0.1:8000", "description": "Local"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
