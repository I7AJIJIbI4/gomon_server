# auth.py - Enhanced version with better logging
import logging
import requests
from telegram import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from user_db import store_user, is_authorized_user
from config import ADMIN_USER_ID, TELEGRAM_TOKEN

logger = logging.getLogger(__name__)

def request_contact_handler(bot, update):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    
    logger.info(f"📲 request_contact_handler викликано для користувача: {user_id} (@{username}, {first_name})")
    
    try:
        keyboard = [[KeyboardButton("Поділитися контактом", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        chat_id = update.effective_chat.id
        
        bot.send_message(
            chat_id=chat_id, 
            text="Будь ласка, поділіться своїм номером телефону для авторизації:", 
            reply_markup=reply_markup
        )
        
        logger.info(f"✅ Відправлено запит на контакт для користувача {user_id}")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в request_contact_handler: {e}")
        send_admin_error(f"❗️ Помилка в request_contact_handler: {e}")

def contact_handler(bot, update):
    try:
        contact = update.message.contact
        telegram_id = contact.user_id
        phone = contact.phone_number
        username = update.message.from_user.username
        first_name = update.message.from_user.first_name
        
        logger.info(f"📞 Отримано контакт від користувача: {telegram_id} (@{username}, {first_name}), телефон: {phone}")
        
        # Прибираємо клавіатуру
        reply_markup = ReplyKeyboardRemove()
        
        # Зберігаємо користувача
        store_user(telegram_id, phone, username, first_name)
        logger.info(f"💾 Користувач {telegram_id} збережений в базі")
        
        # Перевіряємо авторизацію
        if is_authorized_user(telegram_id):
            update.message.reply_text(
                "✅ Авторизація успішна. Ви можете користуватись всіма можливостями бота.",
                reply_markup=reply_markup
            )
            logger.info(f"✅ Користувач {telegram_id} ({first_name}) успішно авторизований")
        else:
            update.message.reply_text(
                "🚫 На жаль, Вас немає в нашій базі клієнтів. Якщо ви вважаєте, що це помилка, або бажаєте стати нашим клієнтом — будь ласка зверніться до лікаря.",
                reply_markup=reply_markup
            )
            logger.warning(f"⛔️ Користувач {telegram_id} ({first_name}) не авторизований")
            send_admin_error(f"⛔️ Неавторизований користувач {first_name} @{username} ({phone}) намагався авторизуватись.")
            
    except Exception as e:
        logger.exception(f"❌ Помилка в contact_handler: {e}")
        send_admin_error(f"❗️ Помилка в contact_handler: {e}")

def is_authenticated(telegram_id: int) -> bool:
    result = is_authorized_user(telegram_id)
    logger.debug(f"🔍 Перевірка авторизації для {telegram_id}: {'✅' if result else '❌'}")
    return result

def send_admin_error(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_USER_ID,
        "text": message
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"📤 Повідомлення адміну відправлено: {message}")
        else:
            logger.error(f"❌ Помилка відправки адміну (код {response.status_code}): {message}")
    except Exception as e:
        logger.error(f"❌ Помилка надсилання повідомлення адміну: {e}")