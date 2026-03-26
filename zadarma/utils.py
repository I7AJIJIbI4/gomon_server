# utils.py

import logging
import requests
from config import TELEGRAM_TOKEN, ADMIN_USER_ID

logger = logging.getLogger(__name__)

def send_error_to_admin(message, bot=None):
    if bot:
        try:
            bot.send_message(chat_id=ADMIN_USER_ID, text=message)
        except Exception as e:
            print(f"❌ Помилка надсилання повідомлення адміну через бота: {e}")
    else:
        # fallback через Telegram API
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": ADMIN_USER_ID, "text": message}
        try:
            requests.post(url, data=payload, timeout=10)
        except Exception as e:
            print(f"❌ Помилка надсилання повідомлення адміну: {e}")
