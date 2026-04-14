# bot.py - Final version with admin functions
import os
import sys
import time
import logging
import logging.handlers
import subprocess
import threading
import atexit
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import ChatAction, InlineKeyboardButton, InlineKeyboardMarkup
from user_db import init_db, is_authorized_user_simple, get_user_info
from config import TELEGRAM_TOKEN, ADMIN_USER_ID, ADMIN_USER_IDS, MAP_URL, SCHEME_URL, validate_config

is_authenticated = is_authorized_user_simple

DB_PATH = '/home/gomoncli/zadarma/users.db'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler('bot.log', maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def create_pid_file():
    pid_file = "/home/gomoncli/zadarma/bot.pid"
    try:
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"📁 PID файл створено: {pid_file} (PID: {os.getpid()})")
        
        def cleanup_pid():
            try:
                if os.path.exists(pid_file):
                    os.remove(pid_file)
                    logger.info(f"📁 PID файл видалено: {pid_file}")
            except Exception as e:
                logger.error(f"❌ Помилка видалення PID файлу: {e}")
        
        atexit.register(cleanup_pid)
        
        import signal
        def signal_handler(signum, frame):
            logger.info(f"📡 Отримано сигнал {signum}, завершуємо роботу...")
            cleanup_pid()
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
    except Exception as e:
        logger.error(f"❌ Помилка створення PID файлу: {e}")

def send_error_to_admin(bot, message):
    try:
        bot.send_message(chat_id=ADMIN_USER_ID, text=message, parse_mode='Markdown')
        logger.info(f"📤 Повідомлення про помилку відправлено адміну: {message}")
    except Exception as e:
        logger.error(f"❌ Не вдалося відправити повідомлення адміну: {e}")

def start_command(bot, update):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name

    logger.info(f"👤 /start викликано користувачем: {user_id} (@{username}, {first_name})")

    # Deep link: /start connect_380XXXXXXXXX — автоприв'язка телефону з PWA
    text = update.message.text or ''
    parts = text.split()
    if len(parts) > 1 and parts[1].startswith('connect_'):
        phone = parts[1][8:]
        digits = ''.join(filter(str.isdigit, phone))
        # Normalize to 380XXXXXXXXX
        if len(digits) == 10 and digits[0] == '0':
            digits = '38' + digits
        elif len(digits) == 9:
            digits = '380' + digits
        if len(digits) >= 11:
            # Не перезаписувати якщо вже прив'язаний інший номер
            import sqlite3 as _sq
            _uc = _sq.connect('/home/gomoncli/zadarma/users.db')
            _existing = _uc.execute('SELECT phone FROM users WHERE telegram_id=?', (user_id,)).fetchone()
            _uc.close()
            if _existing and _existing[0] and _existing[0] != digits:
                logger.info(f"Deep link connect: {user_id} already has phone {_existing[0]}, ignoring {digits}")
                bot.send_message(chat_id=update.message.chat_id,
                    text=f"Telegram вже підключено до номеру {_existing[0][-10:].replace('380','0',1)}",
                    parse_mode='Markdown')
                return
            from user_db import store_user
            store_user(user_id, digits, username, first_name)
            logger.info(f"Deep link connect: {user_id} -> {digits}")
            bot.send_message(
                chat_id=update.message.chat_id,
                text=(
                    f"Telegram підключено!\n\n"
                    f"Тепер ви отримуватимете нагадування про записи, "
                    f"акції та персональні рекомендації.\n\n"
                    f"/app - Наш застосунок, який точно Вам допоможе\n"
                    f"/my_services - Ваші минулі і майбутні записи\n"
                    f"/map - Знайти нас на мапі\n"
                    f"/scheme - Побачити будівлю на фото\n"
                    f"/channel - Актуальні новини та акції в ТГ каналі\n"
                    f"/call - Зателефонувати лікарю Вікторії\n\n"
                    f"Швидкий доступ: кнопка ☰ (меню) зліва внизу"
                ),
                parse_mode='Markdown'
            )
            return
        else:
            logger.warning(f"⚠️ Deep link connect: invalid phone '{phone}' from {user_id}")

    try:
        if is_authenticated(user_id):
            welcome_message = (
                f"Вітаємо, {first_name}!\n\n"
                "Ви авторизовані в системі Dr. Gomon Cosmetology\n\n"
                "/app - Наш застосунок, який точно Вам допоможе\n"
                "/my_services - Ваші минулі і майбутні записи\n"
                "/map - Знайти нас на мапі\n"
                "/scheme - Побачити будівлю на фото\n"
                "/channel - Актуальні новини та акції в ТГ каналі\n"
                "/call - Зателефонувати лікарю Вікторії\n\n"
                "Швидкий доступ: кнопка ☰ (меню) зліва внизу"
            )

            bot.send_message(chat_id=update.message.chat_id, text=welcome_message, parse_mode='Markdown')
        else:
            unauthorized_message = (
                f"Вітаємо, {first_name}!\n\n"
                "Для авторизації поділіться номером телефону\n\n"
                "Після авторизації ви зможете отримувати OTP-коди "
                "для входу в застосунок через цей бот.\n"
                "Якщо код не приходить у Telegram -- перевiрте SMS."
            )

            bot.send_message(chat_id=update.message.chat_id, text=unauthorized_message, parse_mode='Markdown')

            try:
                from telegram import KeyboardButton, ReplyKeyboardMarkup

                keyboard = [[KeyboardButton("Поділитися номером", request_contact=True)]]
                reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
                button_message = "Натисніть кнопку нижче для авторизації:"
                
                # Відправляємо зображення з текстом і кнопкою
                try:
                    with open('/home/gomoncli/zadarma/introscreen.png', 'rb') as photo:
                        bot.send_photo(
                            chat_id=update.message.chat_id, 
                            photo=photo,
                            caption=button_message,
                            reply_markup=reply_markup
                        )
                except FileNotFoundError:
                    # Якщо файл не знайдено, відправляємо просто текст з кнопкою
                    bot.send_message(
                        chat_id=update.message.chat_id,
                        text=button_message,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
            except Exception:
                fallback_message = (
                    "📱 Відправте свій номер телефону текстом\n\n"
                    "📝 Формат: +380XXXXXXXXX"
                )
                bot.send_message(chat_id=update.message.chat_id, text=fallback_message, parse_mode='Markdown')
            
    except Exception as e:
        logger.exception(f"❌ Критична помилка в start_command: {e}")
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Технічна помилка. Зверніться до підтримки: 073-310-31-10",
            parse_mode='Markdown'
        )

def contact_handler(bot, update):
    user_id = update.effective_user.id
    username = update.effective_user.username or "N/A"
    first_name = update.effective_user.first_name or "N/A"
    
    logger.info(f"📱 Отримано контакт від користувача: {user_id} (@{username})")
    
    try:
        contact = update.message.contact
        phone_number = contact.phone_number
        
        from user_db import store_user
        from telegram import ReplyKeyboardRemove
        
        store_result = store_user(user_id, phone_number, username, first_name)
        
        success_message = (
            f"✅ Дякуємо, {first_name}!\n\n"
            f"📱 Ваш номер {phone_number} збережено\n"
            f"🔍 Перевіряємо дозволи доступу...\n\n"
            f"Зачекайте, будь ласка..."
        )
        
        bot.send_message(
            chat_id=update.message.chat_id, 
            text=success_message,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
        
        if is_authenticated(user_id):
            authorized_message = (
                f"Вітаємо, {first_name}!\n\n"
                "Ви авторизовані в системі Dr. Gomon Cosmetology\n\n"
                "/app - Наш застосунок, який точно Вам допоможе\n"
                "/my_services - Ваші минулі і майбутні записи\n"
                "/map - Знайти нас на мапі\n"
                "/scheme - Побачити будівлю на фото\n"
                "/channel - Актуальні новини та акції в ТГ каналі\n"
                "/call - Зателефонувати лікарю Вікторії\n\n"
                "Швидкий доступ: кнопка ☰ (меню) зліва внизу"
            )

            bot.send_message(chat_id=update.message.chat_id, text=authorized_message, parse_mode='Markdown')
        else:
            denied_message = (
                "Ваш номер не зареєстровано в системі Dr. Gomon Cosmetology\n\n"
                "Для реєстрації зверніться:\n"
                "- Телефон: +380733103110\n"
                "- Instagram Direct: https://ig.me/m/dr.gomon\n\n"
                "Якщо ви наш клiєнт i код не приходить:\n"
                "- Перевiрте папку Спам в SMS\n"
                "- Введiть gomon в пошуку повiдомлень\n"
                "- Або напишiть нам: https://ig.me/m/dr.gomon\n\n"
                "/app - Наш застосунок, який точно Вам допоможе\n"
                "/start - Авторизуватись для отримання сповiщень\n"
                "/map - Знайти нас на мапi\n"
                "/scheme - Побачити будiвлю на фото\n"
                "/channel - Актуальнi новини та акцiї в ТГ каналi\n"
                "/call - Зателефонувати лiкарю Вiкторiї"
            )

            bot.send_message(chat_id=update.message.chat_id, text=denied_message, parse_mode='Markdown')
            
    except Exception as e:
        logger.exception(f"❌ Помилка в contact_handler: {e}")
        from telegram import ReplyKeyboardRemove
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Виникла помилка. Спробуйте пізніше",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )

def call_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"📞 /call викликано користувачем: {user_id}")
    
    try:
        call_message = (
            "📞 Телефон лікаря Вікторії\n\n"
            "📱 +380996093860\n\n"
            "💡 Натисніть на номер для виклику"
        )
        
        bot.send_message(chat_id=update.message.chat_id, text=call_message, parse_mode='Markdown')
        logger.info(f"📞 Телефон лікаря відправлено користувачу {user_id}")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в call_command: {e}")
        bot.send_message(chat_id=update.message.chat_id, text="❌ Помилка отримання телефону", parse_mode='Markdown')

def map_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"🗺️ /map викликано користувачем: {user_id}")
    
    try:
        map_message = (
            "🗺️ Розташування Dr. Gomon Cosmetology на мапі\n\n"
            "📍 Посилання: https://maps.app.goo.gl/iqNLsScEutJhVKLi7\n\n"
            "🚗 Оберіть зручний маршрут"
        )
        
        bot.send_message(chat_id=update.message.chat_id, text=map_message, parse_mode='Markdown')
        logger.info(f"🗺️ Карта відправлена користувачу {user_id}")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в map_command: {e}")
        bot.send_message(chat_id=update.message.chat_id, text="❌ Помилка отримання карти", parse_mode='Markdown')

def scheme_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"🧭 /scheme викликано користувачем: {user_id}")

    AERIAL   = '/home/gomoncli/public_html/sitepro/location-aerial.jpg'
    ENTRANCE = '/home/gomoncli/public_html/sitepro/location-entrance.jpg'

    media = []
    try:
        from telegram import InputMediaPhoto
        for path in (AERIAL, ENTRANCE):
            try:
                media.append(open(path, 'rb'))
            except FileNotFoundError:
                pass

        if len(media) == 2:
            bot.send_media_group(
                chat_id=update.message.chat_id,
                media=[
                    InputMediaPhoto(media[0], caption="📍 ЖК Графський — вигляд зверху"),
                    InputMediaPhoto(media[1], caption="🏠 Вхід: другі ворота/хвіртка, ліворуч"),
                ]
            )
        elif len(media) == 1:
            bot.send_photo(
                chat_id=update.message.chat_id,
                photo=media[0],
                caption="📍 Схема проїзду до Dr. Gómon\nЖК Графський — другі ворота/хвіртка, ліворуч",
                parse_mode='Markdown'
            )
        else:
            bot.send_message(
                chat_id=update.message.chat_id,
                text="📍 ЖК Графський, другі ворота/хвіртка, ліворуч\n🗺️ /map — посилання на карту",
                parse_mode='Markdown'
            )

        logger.info(f"🧭 Схема ({len(media)} фото) відправлена користувачу {user_id}")

    except Exception as e:
        logger.exception(f"❌ Помилка в scheme_command: {e}")
        bot.send_message(chat_id=update.message.chat_id, text="❌ Помилка отримання схеми", parse_mode='Markdown')
    finally:
        for f in media:
            f.close()


def app_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"📱 /app викликано користувачем: {user_id}")
    try:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="Наш застосунок, який точно Вам допоможе:\n\nhttps://drgomon.beauty/go",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.exception(f"❌ Помилка в app_command: {e}")


def channel_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"📢 /channel викликано користувачем: {user_id}")

    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [[InlineKeyboardButton(
            text="Dr.Gomon. Косметологічні будні",
            url="https://t.me/+amEiOBPDbv04MDcy"
        )]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.send_message(
            chat_id=update.message.chat_id,
            text="Актуальні новини та акції в нашому ТГ каналі:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        logger.info(f"📢 Канал відправлено користувачу {user_id}")
    except Exception as e:
        logger.exception(f"❌ Помилка в channel_command: {e}")
        bot.send_message(chat_id=update.message.chat_id, text="❌ Помилка отримання посилання на канал", parse_mode='Markdown')

def test_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"🧪 /test викликано користувачем: {user_id}")
    
    try:
        test_message = (
            "🧪 Тест бота:\n\n"
            f"✅ Бот працює\n"
            f"👤 Ваш ID: {user_id}\n"
            f"🕐 Час: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🔐 Авторизований: {'✅ Так' if is_authenticated(user_id) else '❌ Ні'}"
        )
        
        bot.send_message(chat_id=update.message.chat_id, text=test_message, parse_mode='Markdown')
        logger.info(f"🧪 Тест відправлено користувачу {user_id}")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в test_command: {e}")
        bot.send_message(chat_id=update.message.chat_id, text="❌ Помилка тестування", parse_mode='Markdown')

def status_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"📊 /status викликано користувачем: {user_id}")
    
    try:
        user_info = get_user_info(user_id)
        auth_status = is_authenticated(user_id)
        
        status_text = f"📊 Статус бота:\n\n"
        status_text += f"👤 Користувач: {user_id}\n"
        status_text += f"🔐 Авторизований: {'✅ Так' if auth_status else '❌ Ні'}\n"
        status_text += f"🤖 Бот: ✅ Працює\n"
        status_text += f"📅 Час: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if user_info:
            status_text += f"💾 База даних:\n"
            status_text += f"  👥 Користувачів: {user_info['users_count']}\n"
            status_text += f"  🏥 Клієнтів: {user_info['clients_count']}\n"
            status_text += f"  📱 Ви в базі: {'✅ Так' if user_info['user_in_db'] else '❌ Ні'}\n"
            
            if user_info['user_data']:
                phone = user_info['user_data'][1]
                status_text += f"  📞 Ваш телефон: {phone}\n"
        
        bot.send_message(chat_id=update.message.chat_id, text=status_text, parse_mode='Markdown')
        logger.info(f"📊 Статус відправлено користувачу {user_id}")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в status_command: {e}")
        bot.send_message(chat_id=update.message.chat_id, text="❌ Помилка при отриманні статусу", parse_mode='Markdown')

def restart_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"🔄 /restart викликано користувачем: {user_id}")
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id, 
            text="❌ Ця команда доступна тільки адміністратору",
            parse_mode='Markdown'
        )
        return
    
    try:
        bot.send_message(chat_id=update.message.chat_id, text="🔄 Перезапуск бота...", parse_mode='Markdown')
        logger.info("🔄 Перезапуск бота...")
        os._exit(0)
        
    except Exception as e:
        logger.exception(f"❌ Помилка перезапуску: {e}")
        bot.send_message(chat_id=update.message.chat_id, text="❌ Помилка перезапуску", parse_mode='Markdown')

def sync_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"🔄 /sync викликано користувачем: {user_id}")
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id, 
            text="❌ Ця команда доступна тільки адміністратору",
            parse_mode='Markdown'
        )
        return
    
    try:
        sync_message = (
            "🔄 Ручна синхронізація клієнтів запущена...\n\n"
            "📊 Автоматична синхронізація відбувається:\n"
            "🌅 09:00 - Ранкова синхронізація\n"
            "🌆 21:00 - Вечірня синхронізація\n\n"
            "📱 Результати будуть надіслані в Telegram"
        )
        
        bot.send_message(
            chat_id=update.message.chat_id, 
            text=sync_message,
            parse_mode='Markdown'
        )
        
        import subprocess
        subprocess.Popen(["/home/gomoncli/zadarma/sync_with_notification.sh"])  # fire-and-forget

        logger.info(f"✅ Ручна синхронізація запущена користувачем {user_id}")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в sync_command: {e}")
        bot.send_message(
            chat_id=update.message.chat_id, 
            text="❌ Помилка при запуску ручної синхронізації",
            parse_mode='Markdown'
        )

def help_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"❓ /help викликано користувачем: {user_id}")
    
    try:
        if user_id in ADMIN_USER_IDS:
            help_message = (
                "Команди:\n\n"
                "/app - Наш застосунок, який точно Вам допоможе\n"
                "/my_services - Ваші минулі і майбутні записи\n"
                "/map - Знайти нас на мапі\n"
                "/scheme - Побачити будівлю на фото\n"
                "/channel - Актуальні новини та акції в ТГ каналі\n"
                "/call - Зателефонувати лікарю Вікторії\n\n"
                "Адмін:\n"
                "/monitor - Моніторинг API\n"
                "/diagnostic - Системна діагностика\n"
                "/logs - Останні записи логів\n"
                "/sync - Синхронізація клієнтів\n"
                "/restart - Перезапуск бота"
            )
        elif is_authenticated(user_id):
            help_message = (
                "Команди:\n\n"
                "/app - Наш застосунок, який точно Вам допоможе\n"
                "/my_services - Ваші минулі і майбутні записи\n"
                "/map - Знайти нас на мапі\n"
                "/scheme - Побачити будівлю на фото\n"
                "/channel - Актуальні новини та акції в ТГ каналі\n"
                "/call - Зателефонувати лікарю Вікторії"
            )
        else:
            help_message = (
                "Ви не авторизовані.\n\n"
                "/start - Авторизуватись для отримання сповіщень\n"
                "/app - Наш застосунок, який точно Вам допоможе\n"
                "/map - Знайти нас на мапі\n"
                "/scheme - Побачити будівлю на фото\n"
                "/channel - Актуальні новини та акції в ТГ каналі\n"
                "/call - Зателефонувати лікарю Вікторії\n\n"
                "Якщо код для входу не приходить:\n"
                "- Перевiрте папку Спам в SMS\n"
                "- Введiть gomon в пошуку повiдомлень\n\n"
                "Для реєстрації: +380733103110 або https://ig.me/m/dr.gomon"
            )
        
        bot.send_message(
            chat_id=update.message.chat_id,
            text=help_message,
            parse_mode='Markdown'
        )
        logger.info(f"❓ Довідка відправлена користувачу {user_id}")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в help_command: {e}")
        simple_help = (
            "🤖 ДОВІДКА\n\n"
            "Основні команди:\n"
            "/call - Телефон лікаря\n"
            "/map - Карта\n"
            "Техпідтримка: +380733103110"
        )
        bot.send_message(chat_id=update.message.chat_id, text=simple_help, parse_mode='Markdown')

def monitor_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"📊 /monitor викликано користувачем: {user_id}")
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Ця команда доступна тільки адміністратору",
            parse_mode='Markdown'
        )
        return

    try:
        import os
        bot.send_message(
            chat_id=update.message.chat_id,
            text="📊 Запускаю API моніторинг...",
            parse_mode='Markdown'
        )
        
        # Запустити api_monitor.py та зберегти результат у файл
        with open("/tmp/monitor_result.txt", "w") as _mf:
            subprocess.run(["python3", "api_monitor.py"], cwd="/home/gomoncli/zadarma", stdout=_mf, stderr=subprocess.STDOUT, timeout=120)

        # Прочитати результат
        try:
            with open("/tmp/monitor_result.txt", "r", encoding="utf-8") as f:
                output = f.read()
            if len(output) > 3900:
                output = output[:3900] + "\n\n... (обрізано)"
            bot.send_message(
                chat_id=update.message.chat_id,
                text=f"📊 МОНІТОРИНГ API:\n\n{output}",
                parse_mode='Markdown'
            )
        except Exception as e:
            bot.send_message(
                chat_id=update.message.chat_id,
                text=f"❌ Помилка читання результату: {e}",
                parse_mode='Markdown'
            )
        
        logger.info(f"📊 Моніторинг API відправлено адміну")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в monitor_command: {e}")
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Помилка моніторингу API",
            parse_mode='Markdown'
        )

def diagnostic_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"🔧 /diagnostic викликано користувачем: {user_id}")
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Ця команда доступна тільки адміністратору",
            parse_mode='Markdown'
        )
        return

    try:
        import subprocess
        import os
        
        diagnostic_info = []
        diagnostic_info.append("🔧 СИСТЕМНА ДІАГНОСТИКА")
        diagnostic_info.append("=" * 30)
        
        # Статус бота
        diagnostic_info.append("🤖 СТАТУС БОТА:")
        diagnostic_info.append(f"   PID: {os.getpid()}")
        diagnostic_info.append(f"   Час роботи: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Дискове простір
        try:
            df_result = subprocess.run(['df', '-h', '/home/gomoncli'],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     timeout=120)
            if df_result.returncode == 0:
                lines = df_result.stdout.decode('utf-8').strip().split('\n')
                if len(lines) > 1:
                    diagnostic_info.append("💾 ДИСК:")
                    diagnostic_info.append(f"   {lines[1]}")
        except Exception:
            pass
        
        # Процеси Python
        try:
            ps_result = subprocess.run(['ps', 'aux'],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     timeout=120)
            if ps_result.returncode == 0:
                ps_output = ps_result.stdout.decode('utf-8')
                python_procs = [line for line in ps_output.split('\n') if 'python' in line and 'zadarma' in line]
                diagnostic_info.append("🐍 PYTHON ПРОЦЕСИ:")
                for proc in python_procs[:3]:  # Показати тільки перші 3
                    parts = proc.split()
                    if len(parts) > 10:
                        diagnostic_info.append(f"   PID:{parts[1]} CPU:{parts[2]}% MEM:{parts[3]}%")
        except Exception:
            pass
        
        # Файли конфігурації
        diagnostic_info.append("📁 ФАЙЛИ:")
        config_files = ['config.py', 'users.db', 'bot.log']
        for file in config_files:
            if os.path.exists(f'/home/gomoncli/zadarma/{file}'):
                stat = os.stat(f'/home/gomoncli/zadarma/{file}')
                size = stat.st_size
                if size > 1024*1024:
                    size_str = f"{size/(1024*1024):.1f}MB"
                elif size > 1024:
                    size_str = f"{size/1024:.1f}KB"
                else:
                    size_str = f"{size}B"
                diagnostic_info.append(f"   ✅ {file} ({size_str})")
            else:
                diagnostic_info.append(f"   ❌ {file} відсутній")
        
        # Останні помилки з логу
        try:
            with open('/home/gomoncli/zadarma/bot.log', 'r', encoding='utf-8') as f:
                lines = f.readlines()
                error_lines = [line for line in lines[-50:] if 'ERROR' in line]
                if error_lines:
                    diagnostic_info.append("🚨 ОСТАННІ ПОМИЛКИ:")
                    for error in error_lines[-3:]:  # Останні 3 помилки
                        diagnostic_info.append(f"   {error.strip()[:100]}...")
                else:
                    diagnostic_info.append("✅ Помилок не знайдено")
        except Exception:
            diagnostic_info.append("⚠️ Не вдалося прочитати лог")
        
        output = '\n'.join(diagnostic_info)
        if len(output) > 4000:
            output = output[:3900] + "\n\n... (обрізано)"
        
        bot.send_message(
            chat_id=update.message.chat_id,
            text=output,
            parse_mode='Markdown'
        )
        logger.info(f"🔧 Діагностика відправлена адміну")

    except Exception as e:
        logger.exception(f"❌ Помилка в diagnostic_command: {e}")
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Помилка при виконанні діагностики",
            parse_mode='Markdown'
        )

def logs_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"📋 /logs викликано користувачем: {user_id}")
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Ця команда доступна тільки адміністратору",
            parse_mode='Markdown'
        )
        return

    try:
        import os

        logs_info = []
        logs_info.append("📋 ОСТАННІ ЗАПИСИ ЛОГІВ")
        logs_info.append("=" * 25)
        
        log_files = [
            ('bot.log', '🤖 БОТ'),
            ('webhook_processor.log', '🔗 WEBHOOK'),
            ('bot_cron.log', '⏰ CRON'),
        ]
        
        for log_file, title in log_files:
            log_path = f'/home/gomoncli/zadarma/{log_file}'
            if os.path.exists(log_path):
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        recent_lines = lines[-5:]  # Останні 5 рядків
                        
                    logs_info.append(f"\n{title} ({log_file}):")
                    for line in recent_lines:
                        # Скоротити довгі рядки
                        clean_line = line.strip()
                        if len(clean_line) > 100:
                            clean_line = clean_line[:95] + "..."
                        logs_info.append(f"  {clean_line}")
                        
                except Exception as e:
                    logs_info.append(f"\n{title}: ❌ Помилка читання ({e})")
            else:
                logs_info.append(f"\n{title}: ❌ Файл не знайдено")
        
        # Додати загальну інформацію про логи
        try:
            total_size = 0
            log_count = 0
            for file in os.listdir('/home/gomoncli/zadarma/'):
                if file.endswith('.log'):
                    total_size += os.path.getsize(f'/home/gomoncli/zadarma/{file}')
                    log_count += 1
            
            size_mb = total_size / (1024 * 1024)
            logs_info.append(f"\n📊 ЗАГАЛОМ: {log_count} файлів, {size_mb:.1f}MB")
        except Exception:
            pass
        
        output = '\n'.join(logs_info)
        if len(output) > 4000:
            output = output[:3900] + "\n\n... (обрізано)"
        
        bot.send_message(
            chat_id=update.message.chat_id,
            text=output,
            parse_mode='Markdown'
        )
        logger.info(f"📋 Логи відправлені адміну")

    except Exception as e:
        logger.exception(f"❌ Помилка в logs_command: {e}")
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Помилка при читанні логів",
            parse_mode='Markdown'
        )

def _show_admin_panel(bot, chat_id):
    keyboard = [
        [InlineKeyboardButton("💳 Прийняти оплату", callback_data="pay_start")],
        [InlineKeyboardButton("📊 Моніторинг",    callback_data="admin_monitor"),
         InlineKeyboardButton("🔧 Діагностика",   callback_data="admin_diag")],
        [InlineKeyboardButton("📋 Логи",           callback_data="admin_logs"),
         InlineKeyboardButton("🔄 Синхронізація", callback_data="admin_sync")],
    ]
    bot.send_message(
        chat_id=chat_id,
        text="👑 Адмін-панель Dr. Gomon",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


def admin_command(bot, update):
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        return
    _show_admin_panel(bot, update.message.chat_id)


def _do_monitor(bot, chat_id):
    bot.send_message(chat_id=chat_id, text="📊 Запускаю API моніторинг...", parse_mode='Markdown')
    with open("/tmp/monitor_result.txt", "w") as _mf:
        subprocess.run(["python3", "api_monitor.py"], cwd="/home/gomoncli/zadarma", stdout=_mf, stderr=subprocess.STDOUT, timeout=120)
    try:
        with open("/tmp/monitor_result.txt", "r", encoding="utf-8") as f:
            output = f.read()
        if len(output) > 3900:
            output = output[:3900] + "\n\n... (обрізано)"
        bot.send_message(chat_id=chat_id, text="📊 МОНІТОРИНГ API:\n\n{}".format(output), parse_mode='Markdown')
    except Exception as e:
        bot.send_message(chat_id=chat_id, text="❌ Помилка читання результату: {}".format(e), parse_mode='Markdown')


def _do_logs(bot, chat_id):
    logs_info = ["📋 ОСТАННІ ЗАПИСИ ЛОГІВ", "=" * 25]
    log_files = [
        ('bot.log', '🤖 БОТ'),
        ('webhook_processor.log', '🔗 WEBHOOK'),
        ('bot_cron.log', '⏰ CRON'),
    ]
    for log_file, title in log_files:
        log_path = '/home/gomoncli/zadarma/{}'.format(log_file)
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[-5:]
                logs_info.append("\n{} ({}):".format(title, log_file))
                for line in lines:
                    clean = line.strip()
                    logs_info.append("  {}".format(clean[:100] + "..." if len(clean) > 100 else clean))
            except Exception as e:
                logs_info.append("\n{}: ❌ Помилка читання ({})".format(title, e))
        else:
            logs_info.append("\n{}: ❌ Файл не знайдено".format(title))
    output = '\n'.join(logs_info)
    if len(output) > 4000:
        output = output[:3900] + "\n\n... (обрізано)"
    bot.send_message(chat_id=chat_id, text=output, parse_mode='Markdown')


def _do_diagnostic(bot, chat_id):
    import subprocess
    info = ["🔧 СИСТЕМНА ДІАГНОСТИКА", "=" * 30,
            "🤖 PID: {}  Час: {}".format(os.getpid(), time.strftime('%Y-%m-%d %H:%M:%S'))]
    try:
        df = subprocess.run(['df', '-h', '/home/gomoncli'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        if df.returncode == 0:
            lines = df.stdout.decode('utf-8').strip().split('\n')
            if len(lines) > 1:
                info.append("💾 ДИСК: {}".format(lines[1]))
    except Exception:
        pass
    try:
        ps = subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        procs = [l for l in ps.stdout.decode('utf-8').split('\n') if 'python' in l and 'zadarma' in l]
        info.append("🐍 PYTHON ПРОЦЕСИ:")
        for p in procs[:3]:
            parts = p.split()
            if len(parts) > 3:
                info.append("   PID:{} CPU:{}% MEM:{}%".format(parts[1], parts[2], parts[3]))
    except Exception:
        pass
    output = '\n'.join(info)
    if len(output) > 4000:
        output = output[:3900] + "\n\n... (обрізано)"
    bot.send_message(chat_id=chat_id, text=output, parse_mode='Markdown')


def _do_sync(bot, chat_id):
    import subprocess
    bot.send_message(chat_id=chat_id, text="🔄 Ручна синхронізація запущена...", parse_mode='Markdown')
    subprocess.Popen(["/home/gomoncli/zadarma/sync_with_notification.sh"])  # fire-and-forget
    subprocess.Popen(["/usr/bin/python3", "/home/gomoncli/zadarma/sync_appointments.py"],  # fire-and-forget
                     cwd="/home/gomoncli/zadarma")


def admin_callback(bot, update):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    if user_id not in ADMIN_USER_IDS:
        query.answer("❌ Доступ заборонено")
        return

    query.answer()
    data = query.data

    if data == 'pay_start':
        _pay_state[user_id] = True
        bot.send_message(
            chat_id=chat_id,
            text=(
                "💳 <b>Нова оплата</b>\n\n"
                "Введіть суму та опис через пробіл:\n"
                "<code>900 DrumRoll всього тіла</code>\n\n"
                "Або /admin для скасування"
            ),
            parse_mode='HTML'
        )
    elif data == 'admin_monitor':
        _do_monitor(bot, chat_id)
    elif data == 'admin_diag':
        _do_diagnostic(bot, chat_id)
    elif data == 'admin_logs':
        _do_logs(bot, chat_id)
    elif data == 'admin_sync':
        _do_sync(bot, chat_id)


def general_text_handler(bot, update):
    """Обробляє текстові повідомлення — тільки введення суми для LiqPay (адміни)."""
    user_id = update.effective_user.id

    # Admin payment flow — only for admins in pay state
    if user_id not in ADMIN_USER_IDS or not _pay_state.get(user_id):
        return

    text = update.message.text.strip()
    parts = text.split(None, 1)

    if len(parts) < 2:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="⚠️ Формат: <b>сума опис</b>\nПриклад: <code>900 DrumRoll всього тіла</code>",
            parse_mode='HTML'
        )
        return

    try:
        amount = float(parts[0].replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except ValueError:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="⚠️ Некоректна сума. Спробуйте ще раз.",
            parse_mode='Markdown'
        )
        return

    description = parts[1]
    _pay_state.pop(user_id, None)

    # TODO: генерувати реальне посилання після додавання LiqPay ключів
    # from liqpay import LiqPay
    # url = LiqPay(PUBLIC_KEY, PRIVATE_KEY).create_payment_url(...)
    bot.send_message(
        chat_id=update.message.chat_id,
        text=(
            "⚙️ LiqPay ключі ще не налаштовані.\n\n"
            "Буде: посилання на оплату <b>{:.0f} грн</b> — {}".format(amount, description)
        ),
        parse_mode='HTML'
    )
    logger.info(f"💳 Адмін {user_id} ініціював оплату: {amount} грн — {description}")


## media_message_handler removed — messages are captured by tg_business_listener.py


def error_handler(bot, update, error):
    error_str = str(error)
    
    if any(x in error_str.lower() for x in [
        'connection aborted', 'connection broken', 'connection reset',
        'remote end closed', 'httpconnectionpool', 'read timeout',
        'connection timeout', 'temporary failure'
    ]):
        logger.warning(f"⚠️ Мережева помилка (ігнорується): {error}")
        return
    
    logger.error(f"❌ Критична помилка в обробці апдейту: {error}")
    
    if update:
        logger.error(f"📝 Апдейт: {update.to_dict()}")
        
        try:
            if update.message:
                update.message.reply_text(
                    "❌ Сталася помилка при обробці команди. Будь ласка, спробуйте ще раз або зверніться до підтримки",
                    parse_mode='Markdown'
                )
        except Exception:
            pass
    
    send_error_to_admin(bot, f"❌ Критична помилка: {error}")

# Import sync functions
from sync_stubs import (
    handle_sync_status_command, handle_sync_test_command, handle_sync_help_command,
    handle_sync_clean_command, handle_sync_full_command, handle_sync_user_command
)


# -- Channel post handler for news feed --
def save_channel_post(bot, update):
    import sqlite3 as _sq
    FEED_DB = '/home/gomoncli/zadarma/feed.db'
    msg = update.channel_post or update.edited_channel_post
    if not msg:
        return
    text = msg.text or msg.caption or ''
    media_type = None
    file_id = None
    thumb_id = None
    if msg.photo:
        media_type = 'photo'
        file_id = msg.photo[-1].file_id
    elif msg.video:
        media_type = 'video'
        file_id = msg.video.file_id
        if msg.video.thumb:
            thumb_id = msg.video.thumb.file_id
    is_edit = bool(update.edited_channel_post)
    try:
        conn = _sq.connect(FEED_DB)
        if is_edit:
            conn.execute(
                'UPDATE posts SET text=?, media_type=?, file_id=?, thumb_id=? WHERE tg_msg_id=?',
                (text, media_type, file_id, thumb_id, msg.message_id)
            )
            logger.info(f'Channel post updated: {msg.message_id}')
        else:
            conn.execute(
                'INSERT OR IGNORE INTO posts (tg_msg_id, text, date, media_type, file_id, thumb_id) VALUES (?,?,?,?,?,?)',
                (msg.message_id, text, int(msg.date.timestamp()), media_type, file_id, thumb_id)
            )
            logger.info(f'Channel post saved: {msg.message_id}')
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f'Feed save error: {e}')

def my_services_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"my_services_command called by user: {user_id}")

    import sqlite3
    import json
    from datetime import datetime

    DB_PATH = "/home/gomoncli/zadarma/users.db"

    SPECIALIST_NAMES = {
        'victoria': 'Вікторія',
        'anastasia': 'Анастасія',
    }

    try:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        row = conn.execute(
            "SELECT phone FROM users WHERE telegram_id=?", (user_id,)
        ).fetchone()

        if not row:
            conn.close()
            bot.send_message(
                chat_id=update.message.chat_id,
                text=(
                    "Номер телефону не прив'язаний. "
                    "Поділіться номером через кнопку нижче "
                    "або відкрийте додаток: https://drgomon.beauty/go"
                ),
                parse_mode='Markdown'
            )
            return

        phone = row[0]

        # --- collect appointments from clients.services_json ---
        appointments = []
        client_row = conn.execute(
            "SELECT services_json FROM clients WHERE phone=? OR phone LIKE '%' || ?",
            (phone, phone[-9:])
        ).fetchone()
        if client_row and client_row[0]:
            try:
                services = json.loads(client_row[0])
                for s in services:
                    is_cancelled = s.get('status', '').upper() == 'CANCELLED'
                    proc_name = s.get('service', '')
                    if is_cancelled:
                        proc_name = '~' + proc_name + '~ (скасовано)'
                    appointments.append({
                        'date': s.get('date', ''),
                        'time': '{:02d}:00'.format(int(s['hour'])) if s.get('hour') is not None else '',
                        'procedure': proc_name,
                        'specialist': SPECIALIST_NAMES.get(
                            (s.get('specialist') or '').lower(), ''
                        ),
                        'cancelled': is_cancelled,
                    })
            except (json.JSONDecodeError, TypeError):
                pass

        # --- collect from manual_appointments ---
        manual_rows = conn.execute(
            "SELECT date, time, procedure_name, specialist, status FROM manual_appointments "
            "WHERE client_phone=?",
            (phone,)
        ).fetchall()
        for mr in manual_rows:
            m_cancelled = (mr[4] or '').upper() == 'CANCELLED'
            m_proc = mr[2] or ''
            if m_cancelled:
                m_proc = '~' + m_proc + '~ (скасовано)'
            appointments.append({
                'date': mr[0] or '',
                'time': mr[1] or '',
                'procedure': m_proc,
                'specialist': SPECIALIST_NAMES.get(
                    (mr[3] or '').lower(), ''
                ),
                'cancelled': m_cancelled,
            })

        conn.close()

        # --- split into upcoming / done ---
        today_str = datetime.now().strftime('%Y-%m-%d')
        upcoming = []
        done = []
        for a in appointments:
            if a['date'] >= today_str:
                upcoming.append(a)
            else:
                done.append(a)

        upcoming.sort(key=lambda x: x['date'])
        done.sort(key=lambda x: x['date'], reverse=True)

        # --- format message ---
        def fmt_date(d):
            try:
                dt = datetime.strptime(d, '%Y-%m-%d')
                return dt.strftime('%d.%m.%Y')
            except (ValueError, TypeError):
                return d

        lines = []

        if not upcoming and not done:
            lines.append("Записів не знайдено")
        else:
            lines.append("Ваші записи:")
            lines.append("")

            if upcoming:
                lines.append("Заплановані:")
                for a in upcoming:
                    parts = []
                    parts.append(fmt_date(a['date']))
                    if a['time']:
                        parts.append('о {}'.format(a['time']))
                    line = '- ' + ' '.join(parts)
                    if a['procedure']:
                        line += ' -- {}'.format(a['procedure'])
                    if a['specialist']:
                        line += ' ({})'.format(a['specialist'])
                    lines.append(line)
                lines.append("")

            if done:
                lines.append("Останні:")
                for a in done[:5]:
                    line = '- {}'.format(fmt_date(a['date']))
                    if a['procedure']:
                        line += ' -- {}'.format(a['procedure'])
                    lines.append(line)
                lines.append("")

            lines.append("Записатись:")
            lines.append("- Додаток: https://drgomon.beauty/go")
            lines.append("- Telegram: https://t.me/DrGomonCosmetology")
            lines.append("- Instagram Direct: https://ig.me/m/dr.gomon")

        bot.send_message(
            chat_id=update.message.chat_id,
            text='\n'.join(lines),
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.exception(f"Error in my_services_command: {e}")
        bot.send_message(
            chat_id=update.message.chat_id,
            text="Помилка при завантаженні записів. Спробуйте пізніше.",
            parse_mode='Markdown'
        )


def main():
    logger.info("🚀 Бот запускається...")
    
    create_pid_file()
    
    try:
        logger.info("⚙️ Перевіряємо конфігурацію...")
        validate_config()
        logger.info("✅ Конфігурація валідна")
        
        init_db()
        logger.info("✅ База даних ініціалізована")
        
    except Exception as e:
        logger.error(f"❌ Критична помилка ініціалізації: {e}")
        sys.exit(1)

    updater = Updater(TELEGRAM_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start_command))
    dp.add_handler(CommandHandler("app", app_command))
    dp.add_handler(MessageHandler(Filters.contact, contact_handler))
    dp.add_handler(CommandHandler("call", call_command))
    dp.add_handler(CommandHandler("map", map_command))
    dp.add_handler(CommandHandler("scheme", scheme_command))
    dp.add_handler(CommandHandler("channel", channel_command))
    dp.add_handler(CommandHandler("restart", restart_command))
    dp.add_handler(CommandHandler("test", test_command))
    dp.add_handler(CommandHandler("status", status_command))
    dp.add_handler(CommandHandler("sync", sync_command))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("my_services", my_services_command))
    dp.add_handler(CommandHandler("services", my_services_command))
    dp.add_handler(CommandHandler("monitor", monitor_command))
    dp.add_handler(CommandHandler("diagnostic", diagnostic_command))
    dp.add_handler(CommandHandler("logs", logs_command))
    
    # Команди управління синхронізацією
    dp.add_handler(CommandHandler("sync_status", handle_sync_status_command))
    dp.add_handler(CommandHandler("sync_clean", handle_sync_clean_command))
    dp.add_handler(CommandHandler("sync_full", handle_sync_full_command))
    dp.add_handler(CommandHandler("sync_test", handle_sync_test_command))
    dp.add_handler(CommandHandler("sync_user", handle_sync_user_command))
    dp.add_handler(CommandHandler("sync_help", handle_sync_help_command))
    
    dp.add_handler(CommandHandler("admin", admin_command))
    dp.add_handler(CallbackQueryHandler(admin_callback, pattern='^(pay_start|admin_monitor|admin_diag|admin_logs|admin_sync)$'))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command & ~Filters.update.channel_posts, general_text_handler))
    # media_message_handler removed — DM messages captured by tg_business_listener.py
    dp.add_handler(MessageHandler(Filters.update.channel_posts | Filters.update.edited_channel_post, save_channel_post))
    dp.add_error_handler(error_handler)
    
    logger.info("✅ Всі обробники додані")
    logger.info("✅ Стартуємо polling...")
    updater.start_polling()
    
    logger.info("🤖 Бот успішно запущений та чекає на повідомлення...")
    logger.info("ℹ️  Для зупинки натисніть Ctrl+C")
    
    updater.idle()

if __name__ == '__main__':
    main()
