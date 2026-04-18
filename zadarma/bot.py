# bot.py - Migrated to python-telegram-bot v20+
import os
import sys
import time
import logging
import logging.handlers
import subprocess
import atexit
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.constants import ChatAction
from user_db import init_db, is_authorized_user_simple, get_user_info
from config import TELEGRAM_TOKEN, ADMIN_USER_ID, ADMIN_USER_IDS, MAP_URL, SCHEME_URL, validate_config

is_authenticated = is_authorized_user_simple

DB_PATH = '/home/gomoncli/zadarma/users.db'

_pay_state = {}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler('bot.log', maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# Reply keyboard for authenticated users
def _get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📋 Мої записи"), KeyboardButton("💰 Мій баланс")],
        [KeyboardButton("📱 Додаток", web_app=WebAppInfo(url="https://drgomon.beauty/app/")), KeyboardButton("📍 Як знайти")],
        [KeyboardButton("💬 Контакти"), KeyboardButton("🤖 ШІ асистент")],
        [KeyboardButton("📢 Канал акцій")]
    ], resize_keyboard=True)


def create_pid_file():
    pid_file = "/home/gomoncli/zadarma/bot.pid"
    try:
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"PID file created: {pid_file} (PID: {os.getpid()})")

        def cleanup_pid():
            try:
                if os.path.exists(pid_file):
                    os.remove(pid_file)
                    logger.info(f"PID file removed: {pid_file}")
            except Exception as e:
                logger.error(f"Error removing PID file: {e}")

        atexit.register(cleanup_pid)

        import signal
        def signal_handler(signum, frame):
            logger.info(f"Signal {signum} received, shutting down...")
            cleanup_pid()
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    except Exception as e:
        logger.error(f"Error creating PID file: {e}")


async def send_error_to_admin(bot, message):
    try:
        await bot.send_message(chat_id=ADMIN_USER_ID, text=message)
        logger.info(f"Error message sent to admin: {message}")
    except Exception as e:
        logger.error(f"Failed to send error message to admin: {e}")


async def start_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name

    logger.info(f"/start called by user: {user_id} (@{username}, {first_name})")

    # Deep link: /start connect_380XXXXXXXXX — auto-link phone from PWA
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
            # Don't overwrite if already linked to a different number
            import sqlite3 as _sq
            _uc = _sq.connect('/home/gomoncli/zadarma/users.db')
            _existing = _uc.execute('SELECT phone FROM users WHERE telegram_id=?', (user_id,)).fetchone()
            _uc.close()
            if _existing and _existing[0] and _existing[0] != digits:
                logger.info(f"Deep link connect: {user_id} already has phone {_existing[0]}, ignoring {digits}")
                await update.message.reply_text(
                    f"Telegram вже підключено до номеру {_existing[0][-10:].replace('380','0',1)}")
                return
            from user_db import store_user
            store_user(user_id, digits, username, first_name)
            logger.info(f"Deep link connect: {user_id} -> {digits}")
            await update.message.reply_text(
                f"Telegram підключено!\n\n"
                f"Тепер ви отримуватимете нагадування про записи, "
                f"акції та персональні рекомендації.\n\n"
                f"Оберіть потрібне з меню нижче або скористайтесь командами:\n\n"
                f"/my_services - Мої записи\n"
                f"/contact - Контакти лікаря\n"
                f"/map - Як нас знайти\n"
                f"/channel - Канал акцій та новин",
                reply_markup=_get_main_keyboard()
            )
            return
        else:
            logger.warning(f"Deep link connect: invalid phone '{phone}' from {user_id}")

    try:
        if is_authenticated(user_id):
            welcome_message = (
                f"Вітаємо, {first_name}! \n\n"
                "Раді бачити вас у Dr. Gomon Cosmetology\n\n"
                "Оберіть потрібне з меню нижче або скористайтесь командами:\n\n"
                "/my_services - Мої записи\n"
                "/balance - Мій баланс\n"
                "/contact - Контакти лікаря\n"
                "/map - Як нас знайти\n"
                "/scheme - Фото локації\n"
                "/channel - Канал акцій та новин"
            )

            await update.message.reply_text(
                welcome_message,
                reply_markup=_get_main_keyboard()
            )
        else:
            unauthorized_message = (
                f"Вітаємо, {first_name}!\n\n"
                "Для авторизації поділіться номером телефону\n\n"
                "Після авторизації ви зможете отримувати OTP-коди "
                "для входу в застосунок через цей бот.\n"
                "Якщо код не приходить у Telegram -- перевiрте SMS."
            )

            await update.message.reply_text(unauthorized_message)

            try:
                from telegram import ReplyKeyboardMarkup as RKM

                keyboard = [[KeyboardButton("Поділитися номером", request_contact=True)]]
                reply_markup = RKM(keyboard, one_time_keyboard=True, resize_keyboard=True)
                button_message = "Натисніть кнопку нижче для авторизації:"

                # Send image with text and button
                try:
                    with open('/home/gomoncli/zadarma/introscreen.png', 'rb') as photo:
                        await context.bot.send_photo(
                            chat_id=update.message.chat_id,
                            photo=photo,
                            caption=button_message,
                            reply_markup=reply_markup
                        )
                except FileNotFoundError:
                    # If file not found, send just text with button
                    await update.message.reply_text(
                        button_message,
                        reply_markup=reply_markup)
            except Exception:
                fallback_message = (
                    "📱 Відправте свій номер телефону текстом\n\n"
                    "📝 Формат: +380XXXXXXXXX"
                )
                await update.message.reply_text(fallback_message)

    except Exception as e:
        logger.exception(f"Critical error in start_command: {e}")
        await update.message.reply_text(
            "❌ Технічна помилка. Зверніться до підтримки: 073-310-31-10")


async def contact_handler(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "N/A"
    first_name = update.effective_user.first_name or "N/A"

    logger.info(f"Contact received from user: {user_id} (@{username})")

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

        await update.message.reply_text(
            success_message,
            reply_markup=ReplyKeyboardRemove())

        if is_authenticated(user_id):
            authorized_message = (
                f"Вітаємо, {first_name}!\n\n"
                "Ви авторизовані в системі Dr. Gomon Cosmetology\n\n"
                "/app - Наш застосунок, який точно Вам допоможе\n"
                "/my_services - Ваші минулі і майбутні записи\n"
                "/map - Знайти нас на мапі\n"
                "/scheme - Побачити будівлю на фото\n"
                "/channel - Актуальні новини та акції в ТГ каналі\n"
                "/call - Зателефонувати лікарю Вікторії\n/contact - Написати лікарю (Instagram/Telegram)\n\n"
                "Швидкий доступ: кнопка ☰ (меню) зліва внизу"
            )

            await update.message.reply_text(
                authorized_message,
                reply_markup=_get_main_keyboard()
            )
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
                "/call - Зателефонувати лiкарю Вiкторiї\n/contact - Написати лiкарю"
            )

            await update.message.reply_text(denied_message)

    except Exception as e:
        logger.exception(f"Error in contact_handler: {e}")
        from telegram import ReplyKeyboardRemove
        await update.message.reply_text(
            "❌ Виникла помилка. Спробуйте пізніше",
            reply_markup=ReplyKeyboardRemove())


async def call_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/call called by user: {user_id}")

    try:
        call_message = (
            "📞 Телефон лікаря Вікторії\n\n"
            "📱 +380733103110\n\n"
            "💡 Натисніть на номер для виклику"
        )

        await update.message.reply_text(call_message)
        logger.info(f"Phone sent to user {user_id}")

    except Exception as e:
        logger.exception(f"Error in call_command: {e}")
        await update.message.reply_text("❌ Помилка отримання телефону")


async def contact_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/contact called by user: {user_id}")

    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Instagram Direct", url="https://ig.me/m/dr.gomon")],
            [InlineKeyboardButton("Telegram", url="https://t.me/DrGomonCosmetology")],
            [InlineKeyboardButton("Зателефонувати 073-310-31-10", url="tel:+380733103110")],
        ])
        await update.message.reply_text(
            "💬 Зв'язатись з лікарем Вікторією\n\n"
            "Оберіть зручний спосіб:",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.exception(f"Error in contact_command: {e}")
        await update.message.reply_text("❌ Помилка")


async def map_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/map called by user: {user_id}")

    AERIAL   = '/home/gomoncli/public_html/sitepro/location-aerial.jpg'
    ENTRANCE = '/home/gomoncli/public_html/sitepro/location-entrance.jpg'

    try:
        from telegram import InputMediaPhoto
        media = []
        for path in (AERIAL, ENTRANCE):
            try:
                media.append(open(path, 'rb'))
            except FileNotFoundError:
                pass

        if media:
            captions = [
                "📍 БЦ Галерея, 6 поверх\nвул. Смілянська, 23, Черкаси\n\n🚪 Лівий вхід «Ліфт» (поруч з кафе «Шарлотка»)\n\n🗺 Google Maps: https://maps.app.goo.gl/6mLtqfEi8RJycP4d8",
                ""
            ]
            media_group = []
            for i, f in enumerate(media):
                media_group.append(InputMediaPhoto(f, caption=captions[i] if i < len(captions) else ""))
            await context.bot.send_media_group(chat_id=update.message.chat_id, media=media_group)
        else:
            await update.message.reply_text(
                "📍 БЦ Галерея, 6 поверх\nвул. Смілянська, 23, Черкаси\n\n"
                "🗺 Google Maps: https://maps.app.goo.gl/6mLtqfEi8RJycP4d8"
            )
        logger.info(f"Map sent to user {user_id}")

    except Exception as e:
        logger.exception(f"Error in map_command: {e}")
        await update.message.reply_text("❌ Помилка отримання карти")
    finally:
        for f in media:
            if hasattr(f, 'close'):
                f.close()


async def scheme_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/scheme called by user: {user_id}")

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
            await context.bot.send_media_group(
                chat_id=update.message.chat_id,
                media=[
                    InputMediaPhoto(media[0], caption="📍 БЦ Галерея, 6 поверх — вигляд зверху\nвул. Смілянська, 23 (перехрестя бул. Шевченка та вул. Смілянської)"),
                    InputMediaPhoto(media[1], caption="🚪 Лівий вхід з написом «Ліфт» (поруч з кафе «Шарлотка»)\nПіднімайтесь на 6 поверх — там є вказівні стрілки"),
                ]
            )
        elif len(media) == 1:
            await context.bot.send_photo(
                chat_id=update.message.chat_id,
                photo=media[0],
                caption="📍 БЦ Галерея, 6 поверх\nЛівий вхід «Ліфт», поруч з кафе «Шарлотка»")
        else:
            await update.message.reply_text(
                "📍 БЦ Галерея, 6 поверх, вул. Смілянська, 23\nЛівий вхід «Ліфт», поруч з кафе «Шарлотка»\n🗺️ /map — посилання на карту")

        logger.info(f"Scheme ({len(media)} photos) sent to user {user_id}")

    except Exception as e:
        logger.exception(f"Error in scheme_command: {e}")
        await update.message.reply_text("❌ Помилка отримання схеми")
    finally:
        for f in media:
            f.close()


async def app_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/app called by user: {user_id}")
    try:
        await update.message.reply_text(
            "Наш застосунок, який точно Вам допоможе:\n\nhttps://drgomon.beauty/go")
    except Exception as e:
        logger.exception(f"Error in app_command: {e}")


async def channel_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/channel called by user: {user_id}")

    try:
        keyboard = [[InlineKeyboardButton(
            text="Dr.Gomon. Косметологічні будні",
            url="https://t.me/+amEiOBPDbv04MDcy"
        )]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Актуальні новини та акції в нашому ТГ каналі:",
            reply_markup=reply_markup)
        logger.info(f"Channel sent to user {user_id}")
    except Exception as e:
        logger.exception(f"Error in channel_command: {e}")
        await update.message.reply_text("❌ Помилка отримання посилання на канал")


async def test_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/test called by user: {user_id}")

    try:
        test_message = (
            "🧪 Тест бота:\n\n"
            f"✅ Бот працює\n"
            f"👤 Ваш ID: {user_id}\n"
            f"🕐 Час: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🔐 Авторизований: {'✅ Так' if is_authenticated(user_id) else '❌ Ні'}"
        )

        await update.message.reply_text(test_message)
        logger.info(f"Test sent to user {user_id}")

    except Exception as e:
        logger.exception(f"Error in test_command: {e}")
        await update.message.reply_text("❌ Помилка тестування")


async def status_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/status called by user: {user_id}")

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

        await update.message.reply_text(status_text)
        logger.info(f"Status sent to user {user_id}")

    except Exception as e:
        logger.exception(f"Error in status_command: {e}")
        await update.message.reply_text("❌ Помилка при отриманні статусу")


async def restart_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/restart called by user: {user_id}")

    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(
            "❌ Ця команда доступна тільки адміністратору")
        return

    try:
        await update.message.reply_text("🔄 Перезапуск бота...")
        logger.info("Restarting bot...")
        os._exit(0)

    except Exception as e:
        logger.exception(f"Error in restart: {e}")
        await update.message.reply_text("❌ Помилка перезапуску")


async def sync_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/sync called by user: {user_id}")

    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(
            "❌ Ця команда доступна тільки адміністратору")
        return

    try:
        sync_message = (
            "🔄 Ручна синхронізація клієнтів запущена...\n\n"
            "📊 Автоматична синхронізація відбувається:\n"
            "🌅 09:00 - Ранкова синхронізація\n"
            "🌆 21:00 - Вечірня синхронізація\n\n"
            "📱 Результати будуть надіслані в Telegram"
        )

        await update.message.reply_text(sync_message)

        subprocess.Popen(["/home/gomoncli/zadarma/sync_with_notification.sh"])  # fire-and-forget

        logger.info(f"Manual sync started by user {user_id}")

    except Exception as e:
        logger.exception(f"Error in sync_command: {e}")
        await update.message.reply_text(
            "❌ Помилка при запуску ручної синхронізації")


async def help_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/help called by user: {user_id}")

    try:
        if user_id in ADMIN_USER_IDS:
            help_message = (
                "Команди:\n\n"
                "/app - Наш застосунок, який точно Вам допоможе\n"
                "/my_services - Ваші минулі і майбутні записи\n"
                "/map - Знайти нас на мапі\n"
                "/scheme - Побачити будівлю на фото\n"
                "/channel - Актуальні новини та акції в ТГ каналі\n"
                "/call - Зателефонувати лікарю Вікторії\n/contact - Написати лікарю (Instagram/Telegram)\n\n"
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
                "/call - Зателефонувати лікарю Вікторії\n/contact - Написати лікарю (Instagram/Telegram)\n\n"
                "Якщо код для входу не приходить:\n"
                "- Перевiрте папку Спам в SMS\n"
                "- Введiть gomon в пошуку повiдомлень\n\n"
                "Для реєстрації: +380733103110 або https://ig.me/m/dr.gomon"
            )

        await update.message.reply_text(help_message)
        logger.info(f"Help sent to user {user_id}")

    except Exception as e:
        logger.exception(f"Error in help_command: {e}")
        simple_help = (
            "🤖 ДОВІДКА\n\n"
            "Основні команди:\n"
            "/call - Телефон лікаря\n"
            "/map - Карта\n"
            "Техпідтримка: +380733103110"
        )
        await update.message.reply_text(simple_help)


async def monitor_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/monitor called by user: {user_id}")

    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(
            "❌ Ця команда доступна тільки адміністратору")
        return

    try:
        await update.message.reply_text("📊 Запускаю API моніторинг...")

        # Run api_monitor.py and save result to file
        with open("/tmp/monitor_result.txt", "w") as _mf:
            subprocess.run(["python3", "api_monitor.py"], cwd="/home/gomoncli/zadarma", stdout=_mf, stderr=subprocess.STDOUT, timeout=120)

        # Read result
        try:
            with open("/tmp/monitor_result.txt", "r", encoding="utf-8") as f:
                output = f.read()
            if len(output) > 3900:
                output = output[:3900] + "\n\n... (обрізано)"
            await update.message.reply_text(
                f"📊 МОНІТОРИНГ API:\n\n{output}")
        except Exception as e:
            await update.message.reply_text(
                f"❌ Помилка читання результату: {e}")

        logger.info("API monitoring sent to admin")

    except Exception as e:
        logger.exception(f"Error in monitor_command: {e}")
        await update.message.reply_text(
            "❌ Помилка моніторингу API")


async def diagnostic_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/diagnostic called by user: {user_id}")

    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(
            "❌ Ця команда доступна тільки адміністратору")
        return

    try:
        diagnostic_info = []
        diagnostic_info.append("🔧 СИСТЕМНА ДІАГНОСТИКА")
        diagnostic_info.append("=" * 30)

        # Bot status
        diagnostic_info.append("🤖 СТАТУС БОТА:")
        diagnostic_info.append(f"   PID: {os.getpid()}")
        diagnostic_info.append(f"   Час роботи: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Disk space
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

        # Python processes
        try:
            ps_result = subprocess.run(['ps', 'aux'],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     timeout=120)
            if ps_result.returncode == 0:
                ps_output = ps_result.stdout.decode('utf-8')
                python_procs = [line for line in ps_output.split('\n') if 'python' in line and 'zadarma' in line]
                diagnostic_info.append("🐍 PYTHON ПРОЦЕСИ:")
                for proc in python_procs[:3]:
                    parts = proc.split()
                    if len(parts) > 10:
                        diagnostic_info.append(f"   PID:{parts[1]} CPU:{parts[2]}% MEM:{parts[3]}%")
        except Exception:
            pass

        # Config files
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

        # Last errors from log
        try:
            with open('/home/gomoncli/zadarma/bot.log', 'r', encoding='utf-8') as f:
                lines = f.readlines()
                error_lines = [line for line in lines[-50:] if 'ERROR' in line]
                if error_lines:
                    diagnostic_info.append("🚨 ОСТАННІ ПОМИЛКИ:")
                    for error in error_lines[-3:]:
                        diagnostic_info.append(f"   {error.strip()[:100]}...")
                else:
                    diagnostic_info.append("✅ Помилок не знайдено")
        except Exception:
            diagnostic_info.append("⚠️ Не вдалося прочитати лог")

        output = '\n'.join(diagnostic_info)
        if len(output) > 4000:
            output = output[:3900] + "\n\n... (обрізано)"

        await update.message.reply_text(output)
        logger.info("Diagnostic sent to admin")

    except Exception as e:
        logger.exception(f"Error in diagnostic_command: {e}")
        await update.message.reply_text(
            "❌ Помилка при виконанні діагностики")


async def logs_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/logs called by user: {user_id}")

    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(
            "❌ Ця команда доступна тільки адміністратору")
        return

    try:
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
                        recent_lines = lines[-5:]

                    logs_info.append(f"\n{title} ({log_file}):")
                    for line in recent_lines:
                        clean_line = line.strip()
                        if len(clean_line) > 100:
                            clean_line = clean_line[:95] + "..."
                        logs_info.append(f"  {clean_line}")

                except Exception as e:
                    logs_info.append(f"\n{title}: ❌ Помилка читання ({e})")
            else:
                logs_info.append(f"\n{title}: ❌ Файл не знайдено")

        # Total log info
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

        await update.message.reply_text(output)
        logger.info("Logs sent to admin")

    except Exception as e:
        logger.exception(f"Error in logs_command: {e}")
        await update.message.reply_text(
            "❌ Помилка при читанні логів")


async def _show_admin_panel(bot, chat_id):
    keyboard = [
        [InlineKeyboardButton("💳 Прийняти оплату", callback_data="pay_start")],
        [InlineKeyboardButton("📊 Моніторинг",    callback_data="admin_monitor"),
         InlineKeyboardButton("🔧 Діагностика",   callback_data="admin_diag")],
        [InlineKeyboardButton("📋 Логи",           callback_data="admin_logs"),
         InlineKeyboardButton("🔄 Синхронізація", callback_data="admin_sync")],
    ]
    await bot.send_message(
        chat_id=chat_id,
        text="👑 Адмін-панель Dr. Gomon",
        reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        return
    await _show_admin_panel(context.bot, update.message.chat_id)


async def _do_monitor(bot, chat_id):
    await bot.send_message(chat_id=chat_id, text="📊 Запускаю API моніторинг...")
    with open("/tmp/monitor_result.txt", "w") as _mf:
        subprocess.run(["python3", "api_monitor.py"], cwd="/home/gomoncli/zadarma", stdout=_mf, stderr=subprocess.STDOUT, timeout=120)
    try:
        with open("/tmp/monitor_result.txt", "r", encoding="utf-8") as f:
            output = f.read()
        if len(output) > 3900:
            output = output[:3900] + "\n\n... (обрізано)"
        await bot.send_message(chat_id=chat_id, text="📊 МОНІТОРИНГ API:\n\n{}".format(output))
    except Exception as e:
        await bot.send_message(chat_id=chat_id, text="❌ Помилка читання результату: {}".format(e))


async def _do_logs(bot, chat_id):
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
    await bot.send_message(chat_id=chat_id, text=output)


async def _do_diagnostic(bot, chat_id):
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
    await bot.send_message(chat_id=chat_id, text=output)


async def _do_sync(bot, chat_id):
    await bot.send_message(chat_id=chat_id, text="🔄 Ручна синхронізація запущена...")
    subprocess.Popen(["/home/gomoncli/zadarma/sync_with_notification.sh"])  # fire-and-forget
    subprocess.Popen(["/usr/bin/python3", "/home/gomoncli/zadarma/sync_appointments.py"],  # fire-and-forget
                     cwd="/home/gomoncli/zadarma")


async def admin_callback(update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    if user_id not in ADMIN_USER_IDS:
        await query.answer("❌ Доступ заборонено")
        return

    await query.answer()
    data = query.data

    if data == 'pay_start':
        _pay_state[user_id] = True
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "💳 <b>Нова оплата</b>\n\n"
                "Введіть суму та опис через пробіл:\n"
                "<code>900 DrumRoll всього тіла</code>\n\n"
                "Або /admin для скасування"
            ),
            parse_mode='HTML')
    elif data == 'admin_monitor':
        await _do_monitor(context.bot, chat_id)
    elif data == 'admin_diag':
        await _do_diagnostic(context.bot, chat_id)
    elif data == 'admin_logs':
        await _do_logs(context.bot, chat_id)
    elif data == 'admin_sync':
        await _do_sync(context.bot, chat_id)


async def general_text_handler(update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text messages -- payment input for admins + keyboard button routing."""
    user_id = update.effective_user.id
    text = (update.message.text or '').strip()

    # Keyboard button routing
    if text == "📋 Мої записи":
        return await my_services_command(update, context)
    elif text == "💰 Мій баланс":
        return await balance_command(update, context)
    elif text == "📍 Як знайти":
        return await map_command(update, context)
    elif text == "📞 Зателефонувати":
        return await call_command(update, context)
    elif text == "💬 Контакти":
        return await contact_command(update, context)
    elif text == "🤖 ШІ асистент":
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Написати GomonAI", url="https://t.me/DrGomonCosmetology")],
        ])
        return await update.message.reply_text(
            "🤖 GomonAI — ваш AI-асистент\n\n"
            "Підбере процедуру, розповість про ціни, "
            "проаналізує фото шкіри та допоможе скасувати запис.\n\n"
            "Натисніть кнопку нижче — ШІ відповість миттєво!",
            reply_markup=kb
        )
    elif text == "📢 Канал акцій":
        return await channel_command(update, context)

    # Admin payment flow -- only for admins in pay state
    if user_id not in ADMIN_USER_IDS or not _pay_state.get(user_id):
        return

    parts = text.split(None, 1)

    if len(parts) < 2:
        await update.message.reply_text(
            "⚠️ Формат: <b>сума опис</b>\nПриклад: <code>900 DrumRoll всього тіла</code>")
        return

    try:
        amount = float(parts[0].replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ Некоректна сума. Спробуйте ще раз.")
        return

    description = parts[1]
    _pay_state.pop(user_id, None)

    # TODO: generate real link after adding LiqPay keys
    await update.message.reply_text(
        "⚙️ LiqPay ключі ще не налаштовані.\n\n"
        "Буде: посилання на оплату <b>{:.0f} грн</b> — {}".format(amount, description))
    logger.info(f"Admin {user_id} initiated payment: {amount} UAH -- {description}")


## media_message_handler removed -- messages are captured by tg_business_listener.py


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    error_str = str(error)

    if any(x in error_str.lower() for x in [
        'connection aborted', 'connection broken', 'connection reset',
        'remote end closed', 'httpconnectionpool', 'read timeout',
        'connection timeout', 'temporary failure'
    ]):
        logger.warning(f"Network error (ignored): {error}")
        return

    logger.error(f"Critical error processing update: {error}")

    if update:
        try:
            logger.error(f"Update: {update.to_dict()}")
        except Exception:
            pass

        try:
            if update.message:
                await update.message.reply_text(
                    "❌ Сталася помилка при обробці команди. Будь ласка, спробуйте ще раз або зверніться до підтримки")
        except Exception:
            pass

    await send_error_to_admin(context.bot, f"❌ Критична помилка: {error}")


# Import sync functions
from sync_stubs import (
    handle_sync_status_command, handle_sync_test_command, handle_sync_help_command,
    handle_sync_clean_command, handle_sync_full_command, handle_sync_user_command
)


# -- Channel post handler for news feed --
async def save_channel_post(update, context: ContextTypes.DEFAULT_TYPE):
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
        if msg.video.thumbnail:
            thumb_id = msg.video.thumbnail.file_id
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


async def balance_command(update, context: ContextTypes.DEFAULT_TYPE):
    """Show client's deposit + cashback balance."""
    user_id = update.effective_user.id
    import sqlite3
    DB_PATH = "/home/gomoncli/zadarma/users.db"

    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        row = conn.execute("SELECT phone FROM users WHERE telegram_id=?", (user_id,)).fetchone()
        if not row:
            conn.close()
            await update.message.reply_text(
                "Номер телефону не прив'язаний.\n"
                "Поділіться номером через кнопку нижче або відкрийте додаток: https://drgomon.beauty/go")
            return

        phone = row[0]

        # Deposit balance
        dep = conn.execute(
            "SELECT COALESCE(SUM(amount_uah), 0) FROM deposits WHERE phone=? AND status='Approved'",
            (phone,)).fetchone()[0]
        deducted = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM deposit_deductions WHERE phone=?",
            (phone,)).fetchone()[0]
        deposit_bal = round(dep - deducted, 2)

        # Cashback balance
        earned = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM cashback WHERE phone=?",
            (phone,)).fetchone()[0]
        redeemed = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM deposit_deductions WHERE phone=? AND reason LIKE 'cashback%'",
            (phone,)).fetchone()[0]
        cashback_bal = round(earned - redeemed, 2)

        # Recent transactions (last 5)
        txs = []
        for d in conn.execute(
            "SELECT amount_uah, created_at FROM deposits WHERE phone=? AND status='Approved' ORDER BY created_at DESC LIMIT 5",
            (phone,)).fetchall():
            txs.append('+{:.0f} грн — Депозит ({})'.format(d[0], (d[1] or '')[:10]))
        for c in conn.execute(
            "SELECT amount, procedure_name, created_at FROM cashback WHERE phone=? ORDER BY created_at DESC LIMIT 5",
            (phone,)).fetchall():
            txs.append('+{:.0f} грн — Кешбек 3% ({})'.format(c[0], c[1][:25] if c[1] else ''))
        for dd in conn.execute(
            "SELECT amount, reason, created_at FROM deposit_deductions WHERE phone=? ORDER BY created_at DESC LIMIT 5",
            (phone,)).fetchall():
            txs.append('-{:.0f} грн — {}'.format(dd[0], dd[1] or 'Списання'))

        conn.close()

        total = deposit_bal + cashback_bal
        text = '💰 Ваш баланс: {:.0f} грн\n\n'.format(total)
        if deposit_bal > 0:
            text += '💳 Депозит: {:.0f} грн\n'.format(deposit_bal)
        if cashback_bal > 0:
            text += '🎁 Кешбек 3%: {:.0f} грн\n'.format(cashback_bal)
        if total == 0:
            text += 'Поки що транзакцій немає.\n'

        if cashback_bal >= 500:
            text += '\n✅ Кешбек доступний для списання — зверніться до лікаря при візиті.'
        elif cashback_bal > 0:
            text += '\nКешбек доступний для списання від 500 грн (залишилось {:.0f} грн).'.format(500 - total)

        text += '\n\n📱 Поповнити баланс: https://drgomon.beauty/app/'

        if txs:
            text += '\n\nОстанні операції:\n' + '\n'.join(txs[:5])

        await update.message.reply_text(text)

    except Exception as e:
        logger.error(f'balance_command error: {e}')
        await update.message.reply_text('Помилка завантаження балансу. Спробуйте пізніше.')


async def my_services_command(update, context: ContextTypes.DEFAULT_TYPE):
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
            await update.message.reply_text(
                "Номер телефону не прив'язаний. "
                "Поділіться номером через кнопку нижче "
                "або відкрийте додаток: https://drgomon.beauty/go")
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
        from tz_utils import kyiv_now; today_str = kyiv_now().strftime('%Y-%m-%d')
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

        await update.message.reply_text(
            '\n'.join(lines))

    except Exception as e:
        logger.exception(f"Error in my_services_command: {e}")
        await update.message.reply_text(
            "Помилка при завантаженні записів. Спробуйте пізніше.")


def main():
    logger.info("Bot starting...")

    create_pid_file()

    try:
        logger.info("Validating config...")
        validate_config()
        logger.info("Config valid")

        init_db()
        logger.info("Database initialized")

    except Exception as e:
        logger.error(f"Critical initialization error: {e}")
        sys.exit(1)

    from telegram.ext import Defaults
    defaults = Defaults(parse_mode=None)
    application = Application.builder().token(TELEGRAM_TOKEN).defaults(defaults).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("app", app_command))
    application.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    application.add_handler(CommandHandler("call", call_command))
    application.add_handler(CommandHandler("contact", contact_command))
    application.add_handler(CommandHandler("map", map_command))
    application.add_handler(CommandHandler("scheme", scheme_command))
    application.add_handler(CommandHandler("channel", channel_command))
    application.add_handler(CommandHandler("restart", restart_command))
    application.add_handler(CommandHandler("test", test_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("sync", sync_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("my_services", my_services_command))
    application.add_handler(CommandHandler("services", my_services_command))
    application.add_handler(CommandHandler("monitor", monitor_command))
    application.add_handler(CommandHandler("diagnostic", diagnostic_command))
    application.add_handler(CommandHandler("logs", logs_command))

    # Sync management commands
    application.add_handler(CommandHandler("sync_status", handle_sync_status_command))
    application.add_handler(CommandHandler("sync_clean", handle_sync_clean_command))
    application.add_handler(CommandHandler("sync_full", handle_sync_full_command))
    application.add_handler(CommandHandler("sync_test", handle_sync_test_command))
    application.add_handler(CommandHandler("sync_user", handle_sync_user_command))
    application.add_handler(CommandHandler("sync_help", handle_sync_help_command))

    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(admin_callback, pattern='^(pay_start|admin_monitor|admin_diag|admin_logs|admin_sync)$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.UpdateType.CHANNEL_POST, general_text_handler))
    # media_message_handler removed -- DM messages captured by tg_business_listener.py
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST | filters.UpdateType.EDITED_CHANNEL_POST, save_channel_post))
    application.add_error_handler(error_handler)

    logger.info("All handlers added")
    logger.info("Starting polling...")
    application.run_polling()

if __name__ == '__main__':
    main()
