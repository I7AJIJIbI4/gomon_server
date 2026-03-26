# zadarma_call_webhook.py - Версія без поллінгу, працює з webhook-ами
import logging
import time
from telegram import ChatAction

# Вибираємо правильний імпорт залежно від доступного модуля
try:
    from zadarma_api_webhook import make_zadarma_call_with_tracking, send_error_to_admin
    logger = logging.getLogger(__name__)
    logger.info("✅ Використовуємо zadarma_api_webhook (нова версія)")
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ zadarma_api_webhook недоступний, використовуємо стару версію")
    from zadarma_api import make_zadarma_call_with_tracking, send_error_to_admin

from config import HVIRTKA_NUMBER, VOROTA_NUMBER

# Rate limiting для запобігання спаму
user_last_call = {}
CALL_COOLDOWN = 10  # секунд між дзвінками

def check_rate_limit(user_id):
    """Перевіряє чи може користувач зробити дзвінок (rate limiting)"""
    current_time = time.time()
    last_call_time = user_last_call.get(user_id, 0)
    
    if current_time - last_call_time < CALL_COOLDOWN:
        remaining = CALL_COOLDOWN - (current_time - last_call_time)
        return False, remaining
    
    user_last_call[user_id] = current_time
    return True, 0

def handle_gate_command(bot, update):
    """Обробник команди відкриття воріт - WEBHOOK версія"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or "без_username"
    
    logger.info(f"🚪 /vorota викликано користувачем: {user_id} (@{username})")
    
    # 🔒 ПЕРЕВІРКА АВТОРИЗАЦІЇ
    from user_db import is_authorized_user_simple
    
    if not is_authorized_user_simple(user_id):
        bot.send_message(
            chat_id=chat_id,
            text="❌ Доступ заборонено! Спочатку авторизуйтеся через /start"
        )
        logger.warning(f"❌ НЕАВТОРИЗОВАНИЙ користувач {user_id} спробував відкрити ворота!")
        return
    
    # 🕐 ПЕРЕВІРКА RATE LIMITING
    can_call, remaining = check_rate_limit(user_id)
    if not can_call:
        bot.send_message(
            chat_id=chat_id,
            text=f"⏳ Зачекайте {int(remaining)} секунд перед наступним дзвінком"
        )
        logger.info(f"⏳ Rate limit для користувача {user_id}: залишилось {remaining:.1f} сек")
        return
    
    # Змінна для збереження повідомлення що буде оновлюватися
    status_message = None
    
    try:
        # Показуємо що бот "друкує"
        bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        
        # Відправляємо початкове повідомлення
        status_message = bot.send_message(
            chat_id=chat_id, 
            text="🔑 Підбираємо ключі…"
        )
        
        logger.info(f"📞 Ініціюємо дзвінок на ворота: {VOROTA_NUMBER}")
        
        # Робимо дзвінок з відстеженням через webhook
        call_result = make_zadarma_call_with_tracking(
            to_number=VOROTA_NUMBER,
            user_id=user_id,
            chat_id=chat_id,
            action_type="vorota"
        )
        
        if call_result['success']:
            # Оновлюємо повідомлення - дзвінок ініційовано
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message.message_id,
                text="📞 Дзвінок ініційовано... Очікуємо результат.\n\n⏳ Webhook повідомить про результат автоматично протягом 30 секунд."
            )
            
            logger.info(f"✅ Дзвінок на ворота успішно ініційовано для користувача {user_id}")
            logger.info(f"🔔 Результат буде відправлено через webhook систему")
            
            # ВАЖЛИВО: Webhook система автоматично відправить фінальне повідомлення
            # Тому тут ми НЕ відправляємо жодних додаткових повідомлень
            
        else:
            # Помилка при ініціації дзвінка
            error_msg = call_result.get('message', 'Невідома помилка')
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message.message_id,
                text=f"❌ Не вдалося ініціювати дзвінок.\n\nПомилка: {error_msg}\n\nСпробуйте ще раз або зателефонуйте нам за номером <a href=\"tel:+380733103110\">+380733103110</a>",
                parse_mode='HTML'
            )
            
            logger.warning(f"❌ Не вдалося ініціювати дзвінок на ворота для користувача {user_id}: {error_msg}")
            
            # Повідомляємо адміну про проблему
            send_error_to_admin(f"Помилка дзвінка на ворота від користувача {user_id} (@{username}): {error_msg}")
            
    except Exception as e:
        logger.exception(f"❌ Критична помилка при відкритті воріт для користувача {user_id}: {e}")
        
        # Намагаємося оновити повідомлення або відправити нове
        error_text = "❌ Сталася помилка, спробуйте, будь ласка, ще раз, або зателефонуйте нам за номером <a href=\"tel:+380733103110\">+380733103110</a>"
        
        try:
            if status_message:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_message.message_id,
                    text=error_text,
                    parse_mode='HTML'
                )
            else:
                bot.send_message(
                    chat_id=chat_id, 
                    text=error_text, 
                    parse_mode='HTML'
                )
        except:
            # Якщо навіть відправка повідомлення не працює
            logger.error("❌ Не вдалося відправити повідомлення про помилку")
        
        # Повідомляємо адміну про критичну помилку
        send_error_to_admin(f"Критична помилка в handle_gate_command від користувача {user_id}: {str(e)}")

def handle_door_command(bot, update):
    """Обробник команди відкриття хвіртки - WEBHOOK версія"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or "без_username"
    
    logger.info(f"🚪 /hvirtka викликано користувачем: {user_id} (@{username})")
    
    # 🔒 ПЕРЕВІРКА АВТОРИЗАЦІЇ
    from user_db import is_authorized_user_simple
    
    if not is_authorized_user_simple(user_id):
        bot.send_message(
            chat_id=chat_id,
            text="❌ Доступ заборонено! Спочатку авторизуйтеся через /start"
        )
        logger.warning(f"❌ НЕАВТОРИЗОВАНИЙ користувач {user_id} спробував відкрити хвіртку!")
        return
    
    # 🕐 ПЕРЕВІРКА RATE LIMITING
    can_call, remaining = check_rate_limit(user_id)
    if not can_call:
        bot.send_message(
            chat_id=chat_id,
            text=f"⏳ Зачекайте {int(remaining)} секунд перед наступним дзвінком"
        )
        logger.info(f"⏳ Rate limit для користувача {user_id}: залишилось {remaining:.1f} сек")
        return
    
    # Змінна для збереження повідомлення що буде оновлюватися
    status_message = None
    
    try:
        # Показуємо що бот "друкує"
        bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        
        # Відправляємо початкове повідомлення
        status_message = bot.send_message(
            chat_id=chat_id, 
            text="🔑 Підбираємо ключі…"
        )
        
        logger.info(f"📞 Ініціюємо дзвінок на хвіртку: {HVIRTKA_NUMBER}")
        
        # Робимо дзвінок з відстеженням через webhook
        call_result = make_zadarma_call_with_tracking(
            to_number=HVIRTKA_NUMBER,
            user_id=user_id,
            chat_id=chat_id,
            action_type="hvirtka"
        )
        
        if call_result['success']:
            # Оновлюємо повідомлення - дзвінок ініційовано
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message.message_id,
                text="📞 Дзвінок ініційовано... Очікуємо результат.\n\n⏳ Webhook повідомить про результат автоматично протягом 30 секунд."
            )
            
            logger.info(f"✅ Дзвінок на хвіртку успішно ініційовано для користувача {user_id}")
            logger.info(f"🔔 Результат буде відправлено через webhook систему")
            
            # ВАЖЛИВО: Webhook система автоматично відправить фінальне повідомлення
            
        else:
            # Помилка при ініціації дзвінка
            error_msg = call_result.get('message', 'Невідома помилка')
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message.message_id,
                text=f"❌ Не вдалося ініціювати дзвінок.\n\nПомилка: {error_msg}\n\nСпробуйте ще раз або зателефонуйте нам за номером <a href=\"tel:+380733103110\">+380733103110</a>",
                parse_mode='HTML'
            )
            
            logger.warning(f"❌ Не вдалося ініціювати дзвінок на хвіртку для користувача {user_id}: {error_msg}")
            
            # Повідомляємо адміну про проблему
            send_error_to_admin(f"Помилка дзвінка на хвіртку від користувача {user_id} (@{username}): {error_msg}")
            
    except Exception as e:
        logger.exception(f"❌ Критична помилка при відкритті хвіртки для користувача {user_id}: {e}")
        
        # Намагаємося оновити повідомлення або відправити нове
        error_text = "❌ Сталася помилка, спробуйте, будь ласка, ще раз, або зателефонуйте нам за номером <a href=\"tel:+380733103110\">+380733103110</a>"
        
        try:
            if status_message:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_message.message_id,
                    text=error_text,
                    parse_mode='HTML'
                )
            else:
                bot.send_message(
                    chat_id=chat_id, 
                    text=error_text, 
                    parse_mode='HTML'
                )
        except:
            # Якщо навіть відправка повідомлення не працює
            logger.error("❌ Не вдалося відправити повідомлення про помилку")
        
        # Повідомляємо адміну про критичну помилку
        send_error_to_admin(f"Критична помилка в handle_door_command від користувача {user_id}: {str(e)}")

# Додаткові функції для адміністрування

def get_call_stats_for_admin():
    """Отримує статистику дзвінків для адміна з бази даних"""
    try:
        from zadarma_api_webhook import call_tracker
        import sqlite3
        
        # Підключаємося до бази даних відстеження
        conn = sqlite3.connect(call_tracker.db_path)
        cursor = conn.cursor()
        
        # Отримуємо статистику
        cursor.execute('''
            SELECT 
                COUNT(*) as total_calls,
                COUNT(CASE WHEN status = 'initiated' THEN 1 END) as active_calls,
                COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_calls,
                COUNT(CASE WHEN status IN ('busy', 'no_answer', 'failed') THEN 1 END) as failed_calls
            FROM call_tracking 
            WHERE start_time > ?
        ''', (int(time.time()) - 24*3600,))  # За останні 24 години
        
        stats_row = cursor.fetchone()
        
        # Отримуємо останні дзвінки
        cursor.execute('''
            SELECT call_id, action_type, status, start_time, user_id
            FROM call_tracking 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        
        recent_calls = cursor.fetchall()
        conn.close()
        
        stats = {
            'total_calls': stats_row[0] if stats_row else 0,
            'active_calls': stats_row[1] if stats_row else 0,
            'successful_calls': stats_row[2] if stats_row else 0,
            'failed_calls': stats_row[3] if stats_row else 0,
            'recent_calls': recent_calls,
            'current_time': time.time()
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Помилка отримання статистики: {e}")
        # Fallback до старої версії
        try:
            from zadarma_api import call_tracker
            active_count = len(getattr(call_tracker, 'active_calls', {}))
            history_count = len(getattr(call_tracker, 'call_history', []))
            recent_calls = getattr(call_tracker, 'call_history', [])[-10:]
            
            return {
                'active_calls': active_count,
                'total_calls': history_count,
                'successful_calls': 0,
                'failed_calls': 0,
                'recent_calls': recent_calls,
                'current_time': time.time()
            }
        except:
            return {
                'active_calls': 0,
                'total_calls': 0,
                'successful_calls': 0,
                'failed_calls': 0,
                'recent_calls': [],
                'current_time': time.time()
            }

def format_call_stats_message(stats):
    """Форматує статистику дзвінків для відправки адміну"""
    message = f"📊 <b>Статистика дзвінків (24 години)</b>\n\n"
    message += f"📈 Всього дзвінків: {stats['total_calls']}\n"
    message += f"🔄 Активних: {stats['active_calls']}\n"
    message += f"✅ Успішних: {stats['successful_calls']}\n"
    message += f"❌ Невдалих: {stats['failed_calls']}\n\n"
    
    if stats['recent_calls']:
        message += "<b>Останні 10 дзвінків:</b>\n"
        for call in stats['recent_calls']:
            if isinstance(call, tuple):
                # З нової бази даних
                call_id, action_type, status, start_time, user_id = call
                status_emoji = {
                    'success': '✅',
                    'failed': '❌', 
                    'busy': '📵',
                    'no_answer': '🔇',
                    'timeout': '⏰',
                    'answered': '⚠️',
                    'initiated': '🔄'
                }.get(status, '❓')
                
                time_ago = int(time.time() - start_time)
                if time_ago < 60:
                    time_str = f"{time_ago}с тому"
                elif time_ago < 3600:
                    time_str = f"{time_ago//60}хв тому"
                else:
                    time_str = f"{time_ago//3600}год тому"
                
                message += f"{status_emoji} {action_type} - {status} ({time_str})\n"
            else:
                # Зі старої системи
                action = call.get('action_type', 'unknown')
                status = call.get('status', 'unknown')
                status_emoji = {
                    'success': '✅',
                    'failed': '❌', 
                    'timeout': '⏰',
                    'answered': '⚠️'
                }.get(status, '❓')
                
                duration = call.get('end_time', time.time()) - call.get('start_time', time.time())
                message += f"{status_emoji} {action} - {status} ({duration:.1f}s)\n"
    else:
        message += "Немає недавніх дзвінків"
    
    return message

# Функція для додавання в головний бот як адмін команда
def handle_admin_stats_command(bot, update):
    """Команда для отримання статистики (тільки для адміна)"""
    user_id = update.effective_user.id
    from config import ADMIN_USER_ID
    
    if user_id != ADMIN_USER_ID:
        bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Ця команда доступна тільки адміністратору"
        )
        return
    
    try:
        stats = get_call_stats_for_admin()
        message = format_call_stats_message(stats)
        
        bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.exception(f"❌ Помилка отримання статистики: {e}")
        bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Помилка отримання статистики"
        )

# Для сумісності зі старим кодом (deprecated)
def make_zadarma_call_handler(target_number, label):
    """Застаріла функція для сумісності"""
    logger.warning(f"⚠️ Використовується застаріла функція make_zadarma_call_handler для {label}")
    
    def handler(bot, update):
        user_id = update.message.chat_id
        logger.info(f"🔑 Викликано {label} для користувача {user_id} (застарілий метод)")
        
        # Перенаправляємо на нові функції
        if "ворота" in label.lower() or "gate" in label.lower():
            handle_gate_command(bot, update)
        elif "хвіртка" in label.lower() or "door" in label.lower():
            handle_door_command(bot, update)
        else:
            bot.send_message(
                chat_id=user_id, 
                text="❌ Невідомий тип дзвінка. Зверніться до підтримки."
            )
            
    return handler

# Застарілі хендлери (залишаємо для сумісності)
handle_gate_command_legacy = make_zadarma_call_handler(VOROTA_NUMBER, "Ворота")
handle_door_command_legacy = make_zadarma_call_handler(HVIRTKA_NUMBER, "Хвіртку")
