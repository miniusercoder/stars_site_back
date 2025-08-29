from fastapi import APIRouter
from redis import Redis

router = APIRouter()
r = Redis(host="localhost", port=6379, decode_responses=True)
