from telebot import TeleBot

from fastapi_stars.settings import settings

bot = TeleBot(settings.bot_token.get_secret_value(), threaded=False, parse_mode="HTML")
