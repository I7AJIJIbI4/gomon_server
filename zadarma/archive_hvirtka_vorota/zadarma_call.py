# zadarma_call.py - Enhanced version with call status tracking
import logging
import time
from telegram import ChatAction
from zadarma_api_webhook import make_zadarma_call_with_tracking, send_error_to_admin
from config import HVIRTKA_NUMBER, VOROTA_NUMBER

logger = logging.getLogger(__name__)

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
    """Покращений обробник команди відкриття воріт"""
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
        
        # Робимо дзвінок з відстеженням статусу
        call_result = make_zadarma_call_with_tracking(
            to_number=VOROTA_NUMBER,
            user_id=user_id,
            chat_id=chat_id,
            action_type="vorota"
        )
        
        if call_result['success']:
            # Відправляємо нове повідомлення (не редагуємо старе)
            bot.send_message(
                chat_id=chat_id,
                text="Відкриття воріт ініційовано... 🌆 Очікуйте, будь ласка, світловий сигнал.\n\n⏳ Це може зайняти до 30 секунд."
            )
            
            logger.info(f"✅ Дзвінок на ворота успішно ініційовано для користувача {user_id}")
            
            # Система відстеження автоматично відправить фінальне повідомлення
            # коли дзвінок буде скинуто або завершиться з помилкою
            
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
    """Покращений обробник команди відкриття хвіртки"""
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
        
        # Робимо дзвінок з відстеженням статусу
        call_result = make_zadarma_call_with_tracking(
            to_number=HVIRTKA_NUMBER,
            user_id=user_id,
            chat_id=chat_id,
            action_type="hvirtka"
        )
        
        if call_result['success']:
            # Відправляємо нове повідомлення (не редагуємо старе)
            bot.send_message(
                chat_id=chat_id,
                text="Відкриття хвіртки ініційовано... 📢 Очікуйте, будь-ласка, звуковий сигнал.\n\n⏳ Це може зайняти до 30 секунд."
            )
            
            logger.info(f"✅ Дзвінок на хвіртку успішно ініційовано для користувача {user_id}")
            
            # Система відстеження автоматично відправить фінальне повідомлення
            
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
    """Отримує статистику дзвінків для адміна"""
    from zadarma_api import call_tracker
    
    active_count = len(call_tracker.active_calls)
    history_count = len(call_tracker.call_history)
    
    # Аналіз останніх дзвінків
    recent_calls = call_tracker.call_history[-10:] if call_tracker.call_history else []
    
    stats = {
        'active_calls': active_count,
        'total_history': history_count,
        'recent_calls': recent_calls,
        'current_time': time.time()
    }
    
    return stats

def format_call_stats_message(stats):
    """Форматує статистику дзвінків для відправки адміну"""
    message = f"📊 <b>Статистика дзвінків</b>\n\n"
    message += f"🔄 Активних дзвінків: {stats['active_calls']}\n"
    message += f"📋 Всього в історії: {stats['total_history']}\n\n"
    
    if stats['recent_calls']:
        message += "<b>Останні 10 дзвінків:</b>\n"
        for call in stats['recent_calls']:
            action = call['action_type']
            status = call['status']
            status_emoji = {
                'success': '✅',
                'failed': '❌', 
                'timeout': '⏰',
                'answered': '⚠️'
            }.get(status, '❓')
            
            duration = call.get('end_time', time.time()) - call['start_time']
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


# === ЗАСТАРІЛІ ФУНКЦІЇ ВИДАЛЕНО ===
# Видалено функції make_zadarma_call_handler та legacy обробники
# для усунення попереджень про deprecated код та сумісності з Python 3.6
# Дата видалення: $(date +%Y-%m-%d)
