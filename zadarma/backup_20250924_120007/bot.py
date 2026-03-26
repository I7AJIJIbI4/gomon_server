# bot.py - Final version with admin functions
import os
import sys
import time
import logging
import threading
import atexit
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import ChatAction
from user_db import init_db, is_authorized_user_simple, get_user_info
from zadarma_call import handle_door_command, handle_gate_command, handle_admin_stats_command
from sync_management import (
    handle_sync_status_command, handle_sync_clean_command, handle_sync_full_command,
    handle_sync_test_command, handle_sync_user_command, handle_sync_help_command
)
from config import TELEGRAM_TOKEN, ADMIN_USER_ID, ADMIN_USER_IDS, MAP_URL, SCHEME_URL, validate_config

is_authenticated = is_authorized_user_simple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8')
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
        bot.send_message(chat_id=ADMIN_USER_ID, text=message)
        logger.info(f"📤 Повідомлення про помилку відправлено адміну: {message}")
    except Exception as e:
        logger.error(f"❌ Не вдалося відправити повідомлення адміну: {e}")

def start_command(bot, update):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    
    logger.info(f"👤 /start викликано користувачем: {user_id} (@{username}, {first_name})")
    
    try:
        if is_authenticated(user_id):
            welcome_message = (
                f"🎉 Вітаємо, {first_name}!\n\n"
                "✅ Ви авторизовані в системі Dr. Gomon Cosmetology\n\n"
                "🔓 Доступні дії:\n"
                "🚪 /hvirtka - Відкрити хвіртку\n"
                "🏠 /vorota - Відкрити ворота\n"
                "📞 /call - Зателефонувати лікарю Вікторії\n"
                "🗺️ /map - Подивитись розташування на мапі\n"
                "📋 /scheme - Схема розташування в ЖК Графський\n"
                "❓ /help - Довідка по командах\n\n"
                "💡 Швидкий доступ: Меню ☰ зліва внизу"
            )
            
            bot.send_message(chat_id=update.message.chat_id, text=welcome_message, parse_mode=None)
        else:
            unauthorized_message = (
                f"👋 Вітаємо, {first_name}!\n\n"
                "❌ Ви не авторизовані в системі\n\n"
                "📱 Для авторизації поділіться номером телефону"
            )
            
            bot.send_message(chat_id=update.message.chat_id, text=unauthorized_message, parse_mode=None)
            
            try:
                from telegram import KeyboardButton, ReplyKeyboardMarkup
                keyboard = [[KeyboardButton("📱 Поділитися номером", request_contact=True)]]
                reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
                button_message = "👇 Натисніть кнопку для авторизації:"
                
                bot.send_message(
                    chat_id=update.message.chat_id,
                    text=button_message,
                    reply_markup=reply_markup,
                    parse_mode=None
                )
            except Exception:
                fallback_message = (
                    "📱 Відправте свій номер телефону текстом\n\n"
                    "📝 Формат: +380XXXXXXXXX"
                )
                bot.send_message(chat_id=update.message.chat_id, text=fallback_message, parse_mode=None)
            
    except Exception as e:
        logger.exception(f"❌ Критична помилка в start_command: {e}")
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Технічна помилка. Зверніться до підтримки: 073-310-31-10",
            parse_mode=None
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
            parse_mode=None
        )
        
        time.sleep(2)
        
        if is_authenticated(user_id):
            authorized_message = (
                f"🎉 Вітаємо, {first_name}!\n\n"
                "✅ Ви авторизовані в системі і маєте доступ до всіх функцій Dr. Gomon Concierge\n\n"
                "🔓 Доступні дії:\n"
                "🚪 /hvirtka - відкрити хвіртку для пішого проходу\n"
                "🏠 /vorota - відкрити ворота для авто\n"
                "📞 /call - зателефонувати лікарю Вікторії\n"
                "🗺️ /map - показати розташування косметології на мапі\n"
                "📋 /scheme - схема розташування косметології в ЖК Графський\n"
                "❓ /help - довідка по командах\n\n"
                "💡 Підказка: для швидкого доступу до команд\n"
                "   натисніть кнопку \"Меню\" ☰ зліва внизу"
            )
            
            bot.send_message(chat_id=update.message.chat_id, text=authorized_message, parse_mode=None)
        else:
            denied_message = (
                "⚠️ Доступ обмежено!\n\n"
                "❌ Ваш номер не зареєстровано в системі Dr. Gomon Cosmetology\n\n"
                "📞 Для реєстрації зверніться:\n"
                "📱 +380733103110 - телефонуйте\n"
                "💬 <a href=\"https://instagram.com/dr.gomon\">Instagram</a> - пишіть в Direct\n\n"
                "🔓 Доступні функції:\n"
                "📞 /call - Зателефонувати лікарю Вікторії\n"
                "🗺️ /map - Подивитись розташування на мапі\n"
                "📋 /scheme - Схема розташування в ЖК Графський"
            )
            
            bot.send_message(chat_id=update.message.chat_id, text=denied_message, parse_mode='HTML')
            
    except Exception as e:
        logger.exception(f"❌ Помилка в contact_handler: {e}")
        from telegram import ReplyKeyboardRemove
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Виникла помилка. Спробуйте пізніше",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode=None
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
        
        bot.send_message(chat_id=update.message.chat_id, text=call_message, parse_mode=None)
        logger.info(f"📞 Телефон лікаря відправлено користувачу {user_id}")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в call_command: {e}")
        bot.send_message(chat_id=update.message.chat_id, text="❌ Помилка отримання телефону", parse_mode=None)

def map_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"🗺️ /map викликано користувачем: {user_id}")
    
    try:
        map_message = (
            "🗺️ Розташування Dr. Gomon Cosmetology на мапі\n\n"
            "📍 Посилання: https://maps.app.goo.gl/iqNLsScEutJhVKLi7\n\n"
            "🚗 Оберіть зручний маршрут"
        )
        
        bot.send_message(chat_id=update.message.chat_id, text=map_message, parse_mode=None)
        logger.info(f"🗺️ Карта відправлена користувачу {user_id}")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в map_command: {e}")
        bot.send_message(chat_id=update.message.chat_id, text="❌ Помилка отримання карти", parse_mode=None)

def scheme_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"🧭 /scheme викликано користувачем: {user_id}")
    
    try:
        scheme_message = (
            "📋 Схема розташування в ЖК Графський\n\n"
            "🏠 Пройдіть другі ворота/хвіртку та поверніть ліворуч"
        )
        
        try:
            with open('/home/gomoncli/zadarma/enter-min.png', 'rb') as photo:
                bot.send_photo(
                    chat_id=update.message.chat_id, 
                    photo=photo,
                    caption=scheme_message,
                    parse_mode=None
                )
                logger.info(f"🧭 Схема з фото відправлена користувачу {user_id}")
        except FileNotFoundError:
            scheme_message_fallback = (
                "📋 Схема розташування в ЖК Графський\n\n"
                "🏠 Пройдіть другі ворота/хвіртку та поверніть ліворуч\n\n"
                "⚠️ Схема зображення тимчасово недоступна"
            )
            bot.send_message(
                chat_id=update.message.chat_id, 
                text=scheme_message_fallback,
                parse_mode=None
            )
            logger.warning(f"⚠️ Файл схеми не знайдено, відправлено тільки текст користувачу {user_id}")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в scheme_command: {e}")
        bot.send_message(chat_id=update.message.chat_id, text="❌ Помилка отримання схеми", parse_mode=None)

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
        
        bot.send_message(chat_id=update.message.chat_id, text=test_message, parse_mode=None)
        logger.info(f"🧪 Тест відправлено користувачу {user_id}")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в test_command: {e}")
        bot.send_message(chat_id=update.message.chat_id, text="❌ Помилка тестування")

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
        
        bot.send_message(chat_id=update.message.chat_id, text=status_text, parse_mode=None)
        logger.info(f"📊 Статус відправлено користувачу {user_id}")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в status_command: {e}")
        bot.send_message(chat_id=update.message.chat_id, text="❌ Помилка при отриманні статусу")

def restart_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"🔄 /restart викликано користувачем: {user_id}")
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id, 
            text="❌ Ця команда доступна тільки адміністратору",
            parse_mode=None
        )
        return
    
    try:
        bot.send_message(chat_id=update.message.chat_id, text="🔄 Перезапуск бота...", parse_mode=None)
        logger.info("🔄 Перезапуск бота...")
        os._exit(0)
        
    except Exception as e:
        logger.exception(f"❌ Помилка перезапуску: {e}")
        bot.send_message(chat_id=update.message.chat_id, text="❌ Помилка перезапуску", parse_mode=None)

def sync_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"🔄 /sync викликано користувачем: {user_id}")
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id, 
            text="❌ Ця команда доступна тільки адміністратору",
            parse_mode=None
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
            parse_mode=None
        )
        
        import subprocess
        subprocess.Popen(["/home/gomoncli/zadarma/sync_with_notification.sh"])
        
        logger.info(f"✅ Ручна синхронізація запущена користувачем {user_id}")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в sync_command: {e}")
        bot.send_message(
            chat_id=update.message.chat_id, 
            text="❌ Помилка при запуску ручної синхронізації",
            parse_mode=None
        )

def help_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"❓ /help викликано користувачем: {user_id}")
    
    try:
        if user_id in ADMIN_USER_IDS:
            help_message = (
                "🤖 ДОВІДКА ДЛЯ АДМІНІСТРАТОРА\n\n"
                "👥 КОРИСТУВАЦЬКІ КОМАНДИ:\n"
                "🚪 /hvirtka - Відкрити хвіртку\n"
                "🏠 /vorota - Відкрити ворота\n"
                "📞 /call - зателефонувати лікарю Вікторії\n"
                "🗺️ /map - подивитись розташування на мапі\n"
                "📋 /scheme - схема розташування в ЖК Графський\n"
                "🧪 /test - Тест роботи бота\n"
                "📊 /status - Статус користувача\n\n"
                "👑 АДМІНІСТРАТИВНІ КОМАНДИ:\n"
                "📈 /stats - Загальна статистика дзвінків\n"
                "📊 /monitor - Моніторинг всіх API сервісів\n"
                "🔧 /diagnostic - Системна діагностика\n"
                "📋 /logs - Останні записи логів\n"
                "🔄 /sync - Ручна синхронізація клієнтів\n"
                "📊 /sync_status - Статус синхронізації\n"
                "🧹 /sync_clean - Очистити дублікати\n"
                "🔄 /sync_full - Повна синхронізація\n"
                "🧪 /sync_test - Тест API підключень\n"
                "👤 /sync_user - Синхронізувати користувача\n"
                "❓ /sync_help - Довідка по синхронізації\n"
                "🔄 /restart - Перезапуск бота\n"
                "❓ /help - Ця довідка\n\n"
                "📱 КОНТАКТИ ПІДТРИМКИ:\n"
                "+380733103110"
            )
        elif is_authenticated(user_id):
            help_message = (
                "🤖 ДОВІДКА ПО КОМАНДАХ\n\n"
                "🔓 ДОСТУПНІ ДІЇ:\n"
                "🚪 /hvirtka - відкрити хвіртку для проходу\n"
                "🏠 /vorota - відкрити ворота для авто\n"
                "📞 /call - зателефонувати лікарю Вікторії\n"
                "🗺️ /map - подивитись розташування на мапі\n"
                "📋 /scheme - схема розташування в ЖК Графський\n\n"
                "ℹ️ ІНФОРМАЦІЙНІ:\n"
                "🧪 /test - Перевірити роботу бота\n"
                "📊 /status - Ваш статус в системі\n"
                "❓ /help - Ця довідка\n\n"
                "💡 ПІДКАЗКИ:\n"
                "• Використовуйте меню для швидкого доступу\n"
                "• При проблемах з відкриттям спробуйте ще раз\n"
                "• Для підтримки дзвоніть: +380733103110"
            )
        else:
            help_message = (
                "🤖 ДОВІДКА\n\n"
                "❌ Ви не авторизовані в системі\n\n"
                "📱 Для авторизації:\n"
                "1. Натисніть /start\n"
                "2. Поділіться номером телефону\n"
                "3. Дочекайтеся підтвердження доступу\n\n"
                "🔓 ДОСТУПНІ КОМАНДИ:\n"
                "📞 /call - зателефонувати лікарю Вікторії\n"
                "🗺️ /map - подивитись розташування на мапі\n"
                "📋 /scheme - схема розташування в ЖК Графський\n"
                "❓ /help - Ця довідка\n\n"
                "📞 ДЛЯ РЕЄСТРАЦІЇ ЗВЕРНІТЬСЯ:\n"
                "+380733103110 - телефонуйте\n"
                "💬 Instagram: @dr.gomon - пишіть в Direct"
            )
        
        bot.send_message(
            chat_id=update.message.chat_id,
            text=help_message,
            parse_mode=None
        )
        logger.info(f"❓ Довідка відправлена користувачу {user_id}")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в help_command: {e}")
        simple_help = (
            "🤖 ДОВІДКА\n\n"
            "Основні команди:\n"
            "/hvirtka - Відкрити хвіртку\n"
            "/vorota - Відкрити ворота\n"
            "/call - Телефон лікаря\n"
            "/map - Карта\n"
            "/scheme - Схема\n\n"
            "Техпідтримка: +380733103110"
        )
        bot.send_message(chat_id=update.message.chat_id, text=simple_help)

def monitor_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"📊 /monitor викликано користувачем: {user_id}")
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Ця команда доступна тільки адміністратору"
        )
        return
    
    try:
        import os
        bot.send_message(
            chat_id=update.message.chat_id,
            text="📊 Запускаю API моніторинг..."
        )
        
        # Запустити api_monitor.py та зберегти результат у файл
        os.system("cd /home/gomoncli/zadarma && python3 api_monitor.py > /tmp/monitor_result.txt 2>&1")
        
        # Прочитати результат
        try:
            with open("/tmp/monitor_result.txt", "r", encoding="utf-8") as f:
                output = f.read()
            if len(output) > 3900:
                output = output[:3900] + "\n\n... (обрізано)"
            bot.send_message(
                chat_id=update.message.chat_id,
                text=f"📊 МОНІТОРИНГ API:\n\n{output}"
            )
        except Exception as e:
            bot.send_message(
                chat_id=update.message.chat_id,
                text=f"❌ Помилка читання результату: {e}"
            )
        
        logger.info(f"📊 Моніторинг API відправлено адміну")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в monitor_command: {e}")
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Помилка моніторингу API"
        )

def diagnostic_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"🔧 /diagnostic викликано користувачем: {user_id}")
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Ця команда доступна тільки адміністратору"
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
                                     stderr=subprocess.PIPE)
            if df_result.returncode == 0:
                lines = df_result.stdout.decode('utf-8').strip().split('\n')
                if len(lines) > 1:
                    diagnostic_info.append("💾 ДИСК:")
                    diagnostic_info.append(f"   {lines[1]}")
        except:
            pass
        
        # Процеси Python
        try:
            ps_result = subprocess.run(['ps', 'aux'], 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE)
            if ps_result.returncode == 0:
                ps_output = ps_result.stdout.decode('utf-8')
                python_procs = [line for line in ps_output.split('\n') if 'python' in line and 'zadarma' in line]
                diagnostic_info.append("🐍 PYTHON ПРОЦЕСИ:")
                for proc in python_procs[:3]:  # Показати тільки перші 3
                    parts = proc.split()
                    if len(parts) > 10:
                        diagnostic_info.append(f"   PID:{parts[1]} CPU:{parts[2]}% MEM:{parts[3]}%")
        except:
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
        except:
            diagnostic_info.append("⚠️ Не вдалося прочитати лог")
        
        output = '\n'.join(diagnostic_info)
        if len(output) > 4000:
            output = output[:3900] + "\n\n... (обрізано)"
        
        bot.send_message(
            chat_id=update.message.chat_id,
            text=output
        )
        logger.info(f"🔧 Діагностика відправлена адміну")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в diagnostic_command: {e}")
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Помилка при виконанні діагностики"
        )

def logs_command(bot, update):
    user_id = update.effective_user.id
    logger.info(f"📋 /logs викликано користувачем: {user_id}")
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Ця команда доступна тільки адміністратору"
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
        except:
            pass
        
        output = '\n'.join(logs_info)
        if len(output) > 4000:
            output = output[:3900] + "\n\n... (обрізано)"
        
        bot.send_message(
            chat_id=update.message.chat_id,
            text=output
        )
        logger.info(f"📋 Логи відправлені адміну")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в logs_command: {e}")
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Помилка при читанні логів"
        )

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
                    parse_mode=None
                )
        except:
            pass
    
    send_error_to_admin(bot, f"❌ Критична помилка: {error}")

def main():
    logger.info("🚀 Бот запускається...")
    
    create_pid_file()
    
    try:
        logger.info("⚙️ Перевіряємо конфігурацію...")
        validate_config()
        logger.info("✅ Конфігурація валідна")
        
        init_db()
        logger.info("✅ База даних ініціалізована")
        
        logger.info("📞 Тестуємо підключення до Zadarma API...")
        from zadarma_api import test_zadarma_auth
        if test_zadarma_auth():
            logger.info("✅ Zadarma API підключено")
        else:
            logger.warning("⚠️ Проблеми з Zadarma API, але продовжуємо запуск")
            
    except Exception as e:
        logger.error(f"❌ Критична помилка ініціалізації: {e}")
        sys.exit(1)

    updater = Updater(TELEGRAM_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start_command))
    dp.add_handler(MessageHandler(Filters.contact, contact_handler))
    dp.add_handler(CommandHandler("call", call_command))
    dp.add_handler(CommandHandler("map", map_command))
    dp.add_handler(CommandHandler("scheme", scheme_command))
    dp.add_handler(CommandHandler("restart", restart_command))
    dp.add_handler(CommandHandler("test", test_command))
    dp.add_handler(CommandHandler("status", status_command))
    dp.add_handler(CommandHandler("sync", sync_command))
    dp.add_handler(CommandHandler("hvirtka", handle_door_command))
    dp.add_handler(CommandHandler("vorota", handle_gate_command))
    dp.add_handler(CommandHandler("stats", handle_admin_stats_command))
    dp.add_handler(CommandHandler("help", help_command))
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
    
    dp.add_error_handler(error_handler)
    
    logger.info("✅ Всі обробники додані")
    logger.info("✅ Стартуємо polling...")
    updater.start_polling()
    
    logger.info("🤖 Бот успішно запущений та чекає на повідомлення...")
    logger.info("ℹ️  Для зупинки натисніть Ctrl+C")
    
    updater.idle()

if __name__ == '__main__':
    main()