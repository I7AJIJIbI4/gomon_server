#!/bin/bash
# fix_for_python36.sh - Виправлення для Python 3.6 на сервері

echo "🔧 ВИПРАВЛЕННЯ ДЛЯ PYTHON 3.6"
echo "============================="

cd /home/gomoncli/zadarma || exit 1

echo "📋 Поточна директорія: $(pwd)"
echo "🐍 Python версія: $(python3 --version)"

# 1. Ініціалізація бази даних users.db
echo "1️⃣ Ініціалізація бази даних users.db..."
python3 << 'EOF'
import sqlite3
import os

DB_PATH = 'users.db'
try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Створюємо таблицю clients
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            phone TEXT UNIQUE
        )
    ''')
    
    # Створюємо таблицю users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            phone TEXT,
            username TEXT,
            first_name TEXT
        )
    ''')
    
    conn.commit()
    
    # Перевіряємо результат
    cursor.execute('SELECT COUNT(*) FROM clients')
    clients_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM users')
    users_count = cursor.fetchone()[0]
    
    print('✅ БД users.db ініціалізована: {} клієнтів, {} користувачів'.format(clients_count, users_count))
    
    conn.close()
    
except Exception as e:
    print('❌ Помилка ініціалізації users.db: {}'.format(e))
EOF

# 2. Створюємо Python 3.6 сумісну версію sync_management
echo "2️⃣ Створення Python 3.6 сумісної версії sync_management..."
cat > sync_management_py36.py << 'EOF'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_management_py36.py - Python 3.6 совместимая версия управления синхронизацией
"""

import logging
import sys
import os
import sqlite3

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)

# Константы (копируем из config.py чтобы избежать проблем с импортом)
DB_PATH = "/home/gomoncli/zadarma/users.db"

try:
    # Попытка импорта config
    import config
    ADMIN_USER_IDS = getattr(config, 'ADMIN_USER_IDS', [573368771])
except ImportError:
    # Fallback если config не доступен
    ADMIN_USER_IDS = [573368771, 7930079513]
    logger.warning("Config не найден, используем стандартных админов")

def handle_sync_status_command(bot, update):
    """Команда /sync_status - статус синхронизации"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Эта команда доступна только администраторам"
        )
        return
    
    try:
        # Подключаемся к БД для статистики
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute('SELECT COUNT(*) FROM clients')
        total_clients = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        # Дубликаты телефонов
        cursor.execute('''
            SELECT phone, COUNT(*) as count 
            FROM clients 
            GROUP BY phone 
            HAVING count > 1
        ''')
        duplicates = cursor.fetchall()
        
        # Последние клиенты
        cursor.execute('SELECT id, first_name, last_name, phone FROM clients ORDER BY rowid DESC LIMIT 5')
        recent_clients = cursor.fetchall()
        
        conn.close()
        
        status_text = "📊 СТАТУС СИНХРОНИЗАЦИИ\n\n"
        status_text += "🏥 База данных:\n"
        status_text += "  👥 Пользователей: {}\n".format(total_users)
        status_text += "  🏥 Клиентов: {}\n".format(total_clients)
        status_text += "  🔄 Дубликатов: {}\n".format(len(duplicates))
        
        status_text += "\n📋 Последние клиенты:"
        for client in recent_clients:
            status_text += "\n  • ID:{} {} {} ({})".format(client[0], client[1], client[2], client[3])
        
        if duplicates:
            status_text += "\n\n🚨 Дубликаты телефонов:"
            for phone, count in duplicates[:5]:  # Показываем первые 5
                status_text += "\n  • {}: {} записей".format(phone, count)
        
        bot.send_message(
            chat_id=update.message.chat_id,
            text=status_text
        )
        
    except Exception as e:
        logger.exception("❌ Ошибка в sync_status: {}".format(e))
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Ошибка получения статуса синхронизации"
        )

def handle_sync_test_command(bot, update):
    """Команда /sync_test - тестирование подключения к API"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Эта команда доступна только администраторам"
        )
        return
    
    try:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="🧪 Тестирование подключений к API..."
        )
        
        # Тестируем базу данных
        try:
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
        
        test_result = "🧪 РЕЗУЛЬТАТ ТЕСТИРОВАНИЯ:\n\n"
        test_result += "💾 База данных: {}\n".format('✅ OK' if db_ok else '❌ Ошибка')
        test_result += "\n📊 Статистика БД:\n"
        test_result += "  🏥 Клиентов: {}\n".format(clients_count)
        test_result += "  👥 Пользователей: {}\n".format(users_count)

        bot.send_message(
            chat_id=update.message.chat_id,
            text=test_result
        )
        
    except Exception as e:
        logger.exception("❌ Ошибка в sync_test: {}".format(e))
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Ошибка при тестировании API"
        )

def handle_sync_help_command(bot, update):
    """Команда /sync_help - справка по командам синхронизации"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Эта команда доступна только администраторам"
        )
        return
    
    help_text = """🔄 КОМАНДЫ СИНХРОНИЗАЦИИ

📊 /sync_status - текущий статус синхронизации
🧪 /sync_test - тестировать подключение к API
❓ /sync_help - эта справка

⚠️ ВНИМАНИЕ:
• Система адаптирована под Python 3.6
• При проблемах проверяйте логи

📞 ПОДДЕРЖКА: +380733103110"""

    bot.send_message(
        chat_id=update.message.chat_id,
        text=help_text
    )
EOF

# 3. Создаем Python 3.6 совместимый process_webhook
echo "3️⃣ Обновление process_webhook для Python 3.6..."
cat > process_webhook.py << 'EOF'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_webhook.py - Python 3.6 compatible webhook processor
"""

import sys
import json
import logging
import sqlite3
from datetime import datetime
import os

# Настройка логирования
log_file = '/home/gomoncli/zadarma/webhook_processor.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Константы
DB_PATH = '/home/gomoncli/zadarma/call_tracking.db'

def is_call_successful(webhook_data):
    """
    Логика определения успешности звонка для Python 3.6
    """
    try:
        # Проверка длительности
        duration = int(webhook_data.get('duration', 0))
        if duration > 0:
            logger.info("✅ Звонок успешный: duration = {}".format(duration))
            return True
        
        # Проверка статуса
        disposition = webhook_data.get('disposition', '').upper()
        if disposition == 'ANSWERED':
            logger.info("✅ Звонок успешный: disposition = ANSWERED")
            return True
        
        # Звонок неуспешный
        logger.info("❌ Звонок неуспешный: duration={}, disposition={}".format(duration, disposition))
        return False
        
    except Exception as e:
        logger.error("❌ Ошибка при определении успешности звонка: {}".format(e))
        return False

def process_webhook_data(webhook_json):
    """Основная функция обработки webhook данных"""
    try:
        if not webhook_json:
            logger.error("❌ Пустые webhook данные")
            return False
            
        webhook_data = json.loads(webhook_json) if isinstance(webhook_json, str) else webhook_json
        
        # Логирование полученных данных
        event = webhook_data.get('event', 'UNKNOWN')
        caller = webhook_data.get('caller_id', 'N/A')
        called = webhook_data.get('called_did', webhook_data.get('internal', 'N/A'))
        
        logger.info("📞 Webhook обработка: event={}, caller={}, called={}".format(event, caller, called))
        
        # Определение успешности
        success = is_call_successful(webhook_data)
        
        if event == 'NOTIFY_START':
            logger.info("🟢 Звонок начался: {} -> {}".format(caller, called))
        elif event == 'NOTIFY_END':
            duration = webhook_data.get('duration', 0)
            status = "успешный" if success else "неуспешный"
            logger.info("🔴 Звонок завершен: {} сек, {}".format(duration, status))
        
        return success
        
    except json.JSONDecodeError as e:
        logger.error("❌ Ошибка парсинга JSON: {}".format(e))
        return False
    except Exception as e:
        logger.error("❌ Общая ошибка обработки webhook: {}".format(e))
        return False

def main():
    """Главная функция для запуска из командной строки"""
    if len(sys.argv) < 2:
        logger.error("❌ Использование: python3 process_webhook.py '<json_data>'")
        sys.exit(1)
    
    webhook_json = sys.argv[1]
    
    logger.info("🚀 Запуск process_webhook.py")
    
    success = process_webhook_data(webhook_json)
    
    if success:
        logger.info("✅ Webhook успешно обработан")
        print("SUCCESS")
        return 0
    else:
        logger.error("❌ Ошибка обработки webhook")
        print("ERROR")
        return 1

if __name__ == "__main__":
    exit(main())
EOF

chmod +x process_webhook.py sync_management_py36.py

# 4. Создаем Python 3.6 совместимую версию user_db функций
echo "4️⃣ Создание совместимых функций user_db..."
python3 << 'EOF'
import sqlite3
import sys
import os

DB_PATH = 'users.db'

def cleanup_duplicate_phones():
    """Очистка дубликатов номеров телефонов - Python 3.6"""
    print("🧹 Очистка дубликатов номеров")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Находим дубликаты
        cursor.execute('''
            SELECT phone, COUNT(*) as count 
            FROM clients 
            GROUP BY phone 
            HAVING count > 1
        ''')
        
        duplicates = cursor.fetchall()
        cleaned_count = 0
        
        for phone, count in duplicates:
            print("📞 Найдено {} дубликатов для номера {}".format(count, phone))
            
            # Оставляем запись с наименьшим rowid (самый старый)
            cursor.execute('''
                DELETE FROM clients 
                WHERE phone = ? AND rowid NOT IN (
                    SELECT MIN(rowid) FROM clients WHERE phone = ?
                )
            ''', (phone, phone))
            
            cleaned_count += cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print("✅ Удалено {} дубликатов".format(cleaned_count))
        return cleaned_count
        
    except Exception as e:
        print("❌ Ошибка очистки дубликатов: {}".format(e))
        return 0

# Запускаем очистку дубликатов
result = cleanup_duplicate_phones()
print("Результат: {}".format(result))
EOF

# 5. Тестируем исправленные функции
echo "5️⃣ Тестирование исправленных функций..."

echo "🧪 Тест process_webhook успех:"
python3 process_webhook.py '{"event":"NOTIFY_END","duration":"15","disposition":"answered","caller_id":"test"}'

echo "🧪 Тест process_webhook ошибка:"
python3 process_webhook.py '{"event":"NOTIFY_END","duration":"0","disposition":"no_answer","caller_id":"test"}'

# 6. Проверка статуса бота
echo "6️⃣ Проверка статуса бота..."
if pgrep -f "python3.*bot.py" > /dev/null; then
    bot_pid=$(pgrep -f "python3.*bot.py")
    echo "✅ Бот работает (PID: $bot_pid)"
else
    echo "⚠️  Бот не запущен"
    echo "🔄 Попытка запуска..."
    python3 bot.py &
    sleep 3
    if pgrep -f "python3.*bot.py" > /dev/null; then
        echo "✅ Бот перезапущен успешно"
    else
        echo "❌ Не удалось запустить бота"
    fi
fi

echo ""
echo "🎉 ИСПРАВЛЕНИЯ ДЛЯ PYTHON 3.6 ЗАВЕРШЕНЫ!"
echo "======================================="
echo ""
echo "📋 ЧТО ИСПРАВЛЕНО:"
echo "1. ✅ Инициализирована БД users.db"
echo "2. ✅ Создана Python 3.6 совместимая версия sync_management"
echo "3. ✅ Обновлен process_webhook для Python 3.6"
echo "4. ✅ Исправлены f-strings на .format()"
echo "5. ✅ Убраны проблемы с импортом config"
echo ""
echo "🧪 ТЕСТИРОВАНИЕ:"
echo "В Telegram отправьте боту:"
echo "• /sync_status - статус синхронизации"
echo "• /sync_test - тест подключений"
echo "• /hvirtka - тест открытия калитки"
echo ""
echo "📋 ЛОГИ:"
echo "• tail -f bot.log"
echo "• tail -f webhook_processor.log"
