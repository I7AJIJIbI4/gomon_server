#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_management.py - Управління синхронізацією клієнтів

Надає команди для адміністратора для управління синхронізацією
"""

import logging
from telegram import Bot
from user_db import (
    force_full_sync, 
    cleanup_duplicate_phones, 
    sync_specific_client,
    get_user_info
)
from wlaunch_api import fetch_all_clients, test_wlaunch_connection
from config import ADMIN_USER_IDS

logger = logging.getLogger(__name__)

def handle_sync_status_command(bot, update):
    """Команда /sync_status - статус синхронізації"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Ця команда доступна тільки адміністраторам"
        )
        return
    
    try:
        import sqlite3
        from user_db import DB_PATH
        
        # Підключаємося до БД для статистики
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Загальна статистика
        cursor.execute('SELECT COUNT(*) FROM clients')
        total_clients = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        # Дублікати телефонів
        cursor.execute('''
            SELECT phone, COUNT(*) as count 
            FROM clients 
            GROUP BY phone 
            HAVING count > 1
        ''')
        duplicates = cursor.fetchall()
        
        # Останні клієнти (якщо є поле created_at)
        cursor.execute('SELECT id, first_name, last_name, phone FROM clients ORDER BY rowid DESC LIMIT 5')
        recent_clients = cursor.fetchall()
        
        conn.close()
        
        # Тестуємо WLaunch підключення
        wlaunch_status = "✅ Працює" if test_wlaunch_connection() else "❌ Не доступний"
        
        status_text = f"""📊 СТАТУС СИНХРОНІЗАЦІЇ

🏥 База даних:
  👥 Користувачів: {total_users}
  🏥 Клієнтів: {total_clients}
  🔄 Дублікатів: {len(duplicates)}

🌐 WLaunch API: {wlaunch_status}

📋 Останні клієнти:"""

        for client in recent_clients:
            status_text += f"\n  • ID:{client[0]} {client[1]} {client[2]} ({client[3]})"
        
        if duplicates:
            status_text += f"\n\n🚨 Дублікати телефонів:"
            for phone, count in duplicates[:5]:  # Показуємо перші 5
                status_text += f"\n  • {phone}: {count} записів"
        
        bot.send_message(
            chat_id=update.message.chat_id,
            text=status_text
        )
        
    except Exception as e:
        logger.exception(f"❌ Помилка в sync_status: {e}")
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Помилка отримання статусу синхронізації"
        )

def handle_sync_clean_command(bot, update):
    """Команда /sync_clean - очищення дублікатів"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Ця команда доступна тільки адміністраторам"
        )
        return
    
    try:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="🧹 Запускаю очищення дублікатів..."
        )
        
        cleaned_count = cleanup_duplicate_phones()
        
        bot.send_message(
            chat_id=update.message.chat_id,
            text=f"✅ Очищення завершено!\n🗑️ Видалено {cleaned_count} дублікатів"
        )
        
    except Exception as e:
        logger.exception(f"❌ Помилка в sync_clean: {e}")
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Помилка при очищенні дублікатів"
        )

def handle_sync_full_command(bot, update):
    """Команда /sync_full - повна синхронізація"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Ця команда доступна тільки адміністраторам"
        )
        return
    
    try:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="🔄 Запускаю ПОВНУ синхронізацію...\n⚠️ Це може зайняти кілька хвилин"
        )
        
        success = force_full_sync()
        
        if success:
            # Отримуємо статистику після синхронізації
            import sqlite3
            from user_db import DB_PATH
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM clients')
            total_clients = cursor.fetchone()[0]
            conn.close()
            
            bot.send_message(
                chat_id=update.message.chat_id,
                text=f"✅ Повна синхронізація успішна!\n📊 Загалом клієнтів: {total_clients}"
            )
        else:
            bot.send_message(
                chat_id=update.message.chat_id,
                text="❌ Повна синхронізація не вдалася\n🔧 Перевірте логи для деталей"
            )
        
    except Exception as e:
        logger.exception(f"❌ Помилка в sync_full: {e}")
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Помилка при повній синхронізації"
        )

def handle_sync_test_command(bot, update):
    """Команда /sync_test - тестування підключення до API"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Ця команда доступна тільки адміністраторам"
        )
        return
    
    try:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="🧪 Тестування підключень до API..."
        )
        
        # Тестуємо WLaunch
        wlaunch_ok = test_wlaunch_connection()
        
        # Тестуємо Zadarma
        try:
            from zadarma_api import test_zadarma_auth
            zadarma_ok = test_zadarma_auth()
        except:
            zadarma_ok = False
        
        # Тестуємо базу даних
        try:
            import sqlite3
            from user_db import DB_PATH
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM clients')
            clients_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM users')
            users_count = cursor.fetchone()[0]
            conn.close()
            db_ok = True
        except Exception as e:
            db_ok = False
            clients_count = 0
            users_count = 0
        
        test_result = f"""🧪 РЕЗУЛЬТАТ ТЕСТУВАННЯ:

🌐 WLaunch API: {'✅ OK' if wlaunch_ok else '❌ Помилка'}
📞 Zadarma API: {'✅ OK' if zadarma_ok else '❌ Помилка'}
💾 База даних: {'✅ OK' if db_ok else '❌ Помилка'}

📊 Статистика БД:
  🏥 Клієнтів: {clients_count}
  👥 Користувачів: {users_count}
"""

        bot.send_message(
            chat_id=update.message.chat_id,
            text=test_result
        )
        
    except Exception as e:
        logger.exception(f"❌ Помилка в sync_test: {e}")
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Помилка при тестуванні API"
        )

def handle_sync_user_command(bot, update):
    """Команда /sync_user <user_id> - синхронізація конкретного користувача"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Ця команда доступна тільки адміністраторам"
        )
        return
    
    try:
        message_text = update.message.text.strip()
        parts = message_text.split()
        
        if len(parts) != 2:
            bot.send_message(
                chat_id=update.message.chat_id,
                text="❓ Використання: /sync_user <telegram_id>\nПриклад: /sync_user 123456789"
            )
            return
        
        target_user_id = int(parts[1])
        
        bot.send_message(
            chat_id=update.message.chat_id,
            text=f"🔍 Синхронізація користувача {target_user_id}..."
        )
        
        # Отримуємо інформацію про користувача
        user_info = get_user_info(target_user_id)
        
        if not user_info or not user_info.get('user_data'):
            bot.send_message(
                chat_id=update.message.chat_id,
                text=f"❌ Користувач {target_user_id} не знайдений в базі"
            )
            return
        
        phone = user_info['user_data'][1]
        
        # Спробуємо синхронізувати
        success = sync_specific_client(target_user_id, phone)
        
        if success:
            bot.send_message(
                chat_id=update.message.chat_id,
                text=f"✅ Користувач {target_user_id} ({phone}) синхронізовано"
            )
        else:
            bot.send_message(
                chat_id=update.message.chat_id,
                text=f"❌ Не вдалося синхронізувати користувача {target_user_id}"
            )
        
    except ValueError:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Некоректний формат ID користувача"
        )
    except Exception as e:
        logger.exception(f"❌ Помилка в sync_user: {e}")
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Помилка при синхронізації користувача"
        )

def handle_sync_help_command(bot, update):
    """Команда /sync_help - довідка по командах синхронізації"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Ця команда доступна тільки адміністраторам"
        )
        return
    
    help_text = """🔄 КОМАНДИ СИНХРОНІЗАЦІЇ

📊 /sync_status - поточний статус синхронізації
🧹 /sync_clean - очистити дублікати телефонів
🔄 /sync_full - повна синхронізація (ОБЕРЕЖНО!)
🧪 /sync_test - тестувати підключення до API
👤 /sync_user <ID> - синхронізувати конкретного користувача
❓ /sync_help - ця довідка

⚠️ УВАГА:
• Повна синхронізація (/sync_full) видаляє всі існуючі дані
• Завжди робіть резервну копію перед повною синхронізацією
• При проблемах перевіряйте логи

📞 ПІДТРИМКА: +380733103110"""

    bot.send_message(
        chat_id=update.message.chat_id,
        text=help_text
    )
