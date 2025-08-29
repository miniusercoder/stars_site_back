from telebot import TeleBot

from fastapi_stars.settings import settings

bot = TeleBot(settings.bot_token, threaded=False, parse_mode="HTML")
