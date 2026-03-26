#!/bin/bash
# fix_bot_syntax.sh - Швидке виправлення синтаксису bot.py

echo "🔧 ВИПРАВЛЕННЯ СИНТАКСИСУ BOT.PY"
echo "================================"

cd /home/gomoncli/zadarma || exit 1

# Знайдемо та виправимо проблему з відступами
echo "🔍 Пошук проблеми в bot.py..."

# Створимо backup
cp bot.py bot.py.syntax_backup.$(date +%Y%m%d_%H%M%S)

# Видаляємо рядки, які ми додавали, і додамо їх правильно
echo "📝 Видалення проблемних рядків..."

# Видаляємо наші додавання з кінця файлу
sed -i '/# Python 3.6 sync functions/,$d' bot.py

# Тепер додаємо правильно в кінець файлу
echo "📝 Додавання правильного імпорту..."
cat >> bot.py << 'EOF'

# Python 3.6 compatible sync functions
try:
    from sync_stubs import (
        handle_sync_status_command, handle_sync_test_command, handle_sync_help_command,
        handle_sync_clean_command, handle_sync_full_command, handle_sync_user_command
    )
    print("✅ Завантажено sync_stubs для Python 3.6")
except ImportError as e:
    print("❌ Помилка завантаження sync_stubs: {}".format(e))
    
    # Мінімальні заглушки
    def handle_sync_status_command(bot, update):
        bot.send_message(chat_id=update.message.chat_id, text="❌ Модуль синхронізації недоступний")
    
    def handle_sync_clean_command(bot, update):
        bot.send_message(chat_id=update.message.chat_id, text="❌ Модуль синхронізації недоступний")
        
    def handle_sync_full_command(bot, update):
        bot.send_message(chat_id=update.message.chat_id, text="❌ Модуль синхронізації недоступний")
        
    def handle_sync_test_command(bot, update):
        bot.send_message(chat_id=update.message.chat_id, text="❌ Модуль синхронізації недоступний")
        
    def handle_sync_user_command(bot, update):
        bot.send_message(chat_id=update.message.chat_id, text="❌ Модуль синхронізації недоступний")
        
    def handle_sync_help_command(bot, update):
        bot.send_message(chat_id=update.message.chat_id, text="❌ Модуль синхронізації недоступний")
EOF

echo "🧪 Тестування синтаксису..."
if python3 -m py_compile bot.py; then
    echo "✅ bot.py синтаксис виправлено"
    
    # Перезапускаємо бота
    echo "🔄 Перезапуск бота..."
    pkill -f "python3.*bot.py" 2>/dev/null || true
    sleep 2
    
    # Запускаємо бота з логуванням
    nohup python3 bot.py > bot_restart.log 2>&1 &
    sleep 3
    
    if pgrep -f "python3.*bot.py" > /dev/null; then
        bot_pid=$(pgrep -f "python3.*bot.py")
        echo "✅ Бот перезапущено успішно (PID: $bot_pid)"
        
        # Показуємо статус запуску
        if [ -f "bot_restart.log" ]; then
            echo "📋 Лог запуску:"
            tail -10 bot_restart.log
        fi
    else
        echo "❌ Не вдалося перезапустити бота"
        echo "📋 Лог помилок:"
        [ -f "bot_restart.log" ] && cat bot_restart.log
    fi
else
    echo "❌ Синтаксичні помилки все ще присутні"
    python3 -m py_compile bot.py
fi

echo ""
echo "📊 ПОТОЧНИЙ СТАТУС:"
if pgrep -f "python3.*bot.py" > /dev/null; then
    echo "🤖 Бот: ✅ Працює (PID: $(pgrep -f 'python3.*bot.py'))"
else
    echo "🤖 Бот: ❌ Не працює"
fi

echo ""
echo "🧪 НАСТУПНІ КРОКИ:"
echo "1. Перевірте в Telegram: /sync_status"
echo "2. Якщо не працює: cat bot_restart.log"
echo "3. Для повернення: cp bot.py.syntax_backup.* bot.py"
