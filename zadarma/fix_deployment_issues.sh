#!/bin/bash
# fix_deployment_issues.sh - Виправляє проблеми після деплою

set -e

echo "🔧 ВИПРАВЛЕННЯ ПРОБЛЕМ ПІСЛЯ ДЕПЛОЮ"
echo "=================================="

# Кольори
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Перевірка директорії
if [ ! -f "bot.py" ]; then
    log_error "Скрипт має запускатися з директорії /home/gomoncli/zadarma"
    exit 1
fi

log_info "Поточна директорія: $(pwd)"

# 1. Виправляємо requirements.txt
log_info "1. Виправлення requirements.txt..."
if grep -q "python-telegram-bot==13.15" requirements.txt 2>/dev/null; then
    sed -i 's/python-telegram-bot==13.15/python-telegram-bot==13.12/g' requirements.txt
    log_success "requirements.txt виправлено (13.15 -> 13.12)"
else
    log_info "requirements.txt вже містить правильну версію"
fi

# 2. Встановлення правильної версії python-telegram-bot
log_info "2. Оновлення python-telegram-bot..."
pip3 install --upgrade python-telegram-bot==13.12 || {
    log_warning "Не вдалося оновити python-telegram-bot через pip3, пробуємо pip"
    pip install --upgrade python-telegram-bot==13.12 || log_warning "Встановлення python-telegram-bot пропущено"
}

# 3. Перевірка та створення process_webhook.py якщо відсутній
log_info "3. Перевірка process_webhook.py..."
if [ ! -f "process_webhook.py" ]; then
    log_warning "process_webhook.py відсутній, завантажуємо з GitHub..."
    curl -sS https://raw.githubusercontent.com/I7AJIJIbI4/zadarma/main/process_webhook.py -o process_webhook.py || {
        log_error "Не вдалося завантажити process_webhook.py"
        log_info "Створюємо базову версію..."
        cat > process_webhook.py << 'EOF'
#!/usr/bin/env python3
import sys
import json
import logging

logging.basicConfig(filename='/home/gomoncli/zadarma/webhook_processor.log', level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    if len(sys.argv) < 2:
        logger.error("No webhook data provided")
        print("ERROR")
        return 1
    
    try:
        webhook_data = json.loads(sys.argv[1])
        duration = int(webhook_data.get('duration', 0))
        disposition = webhook_data.get('disposition', '')
        
        # Improved success logic
        if duration > 0 or disposition == 'ANSWERED':
            logger.info("Call successful: duration={}, disposition={}".format(duration, disposition))
            print("SUCCESS")
            return 0
        else:
            logger.info("Call failed: duration={}, disposition={}".format(duration, disposition))
            print("ERROR")
            return 1
            
    except Exception as e:
        logger.error("Error processing webhook: {}".format(e))
        print("ERROR")
        return 1

if __name__ == "__main__":
    exit(main())
EOF
    }
    chmod +x process_webhook.py
    log_success "process_webhook.py створено та налаштовано"
else
    log_success "process_webhook.py вже існує"
fi

# 4. Налаштування прав для всіх Python файлів
log_info "4. Налаштування прав доступу..."
chmod +x *.py 2>/dev/null || true
chmod +x *.sh 2>/dev/null || true
log_success "Права доступу налаштовано"

# 5. Ініціалізація бази даних для call_tracking
log_info "5. Ініціалізація бази даних call_tracking..."
python3 -c "
import sqlite3
import os

db_path = 'call_tracking.db'
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT UNIQUE,
            caller_id TEXT,
            called_number TEXT,
            event TEXT,
            duration INTEGER,
            disposition TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_successful BOOLEAN,
            webhook_data TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS call_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT UNIQUE,
            user_id INTEGER,
            chat_id INTEGER,
            action_type TEXT,
            target_number TEXT,
            start_time INTEGER,
            status TEXT DEFAULT 'initiated'
        )
    ''')
    
    conn.commit()
    conn.close()
    print('✅ База даних call_tracking ініціалізована')
    
except Exception as e:
    print('❌ Помилка ініціалізації БД: {}'.format(e))
"

# 6. Тестування покращеної логіки
log_info "6. Тестування покращеної логіки..."

# Тест SUCCESS логіки
test_success='{"event":"NOTIFY_END","duration":"15","disposition":"answered","caller_id":"test"}'
result=$(python3 process_webhook.py "$test_success" 2>/dev/null || echo "ERROR")
if [ "$result" = "SUCCESS" ]; then
    log_success "SUCCESS логіка працює правильно"
else
    log_warning "SUCCESS логіка потребує перевірки: результат = '$result'"
fi

# Тест ERROR логіки
test_error='{"event":"NOTIFY_END","duration":"0","disposition":"no_answer","caller_id":"test"}'
result=$(python3 process_webhook.py "$test_error" 2>/dev/null || echo "ERROR")
if [ "$result" = "ERROR" ]; then
    log_success "ERROR логіка працює правильно"
else
    log_warning "ERROR логіка потребує перевірки: результат = '$result'"
fi

# 7. Перевірка роботи бота
log_info "7. Перевірка роботи бота..."
if pgrep -f "python3.*bot.py" > /dev/null; then
    bot_pid=$(pgrep -f "python3.*bot.py")
    log_success "Бот працює (PID: $bot_pid)"
    
    # Перевірка logів
    if [ -f "bot.log" ]; then
        recent_errors=$(tail -20 bot.log | grep -c "ERROR" 2>/dev/null || echo "0")
        if [ "$recent_errors" -eq 0 ]; then
            log_success "Бот працює без помилок"
        else
            log_warning "Знайдено $recent_errors помилок в останніх логах"
        fi
    fi
else
    log_warning "Бот не запущений, спробуємо перезапустити..."
    python3 bot.py & 
    sleep 2
    if pgrep -f "python3.*bot.py" > /dev/null; then
        log_success "Бот успішно перезапущено"
    else
        log_error "Не вдалося перезапустити бота"
    fi
fi

# 8. Тест нових команд синхронізації
log_info "8. Перевірка нових модулів..."
python3 -c "
try:
    import sync_management
    print('✅ sync_management модуль завантажується')
except ImportError as e:
    print('⚠️ Проблема з sync_management: {}'.format(e))
except Exception as e:
    print('❌ Помилка: {}'.format(e))

try:
    from user_db import force_full_sync, cleanup_duplicate_phones
    print('✅ Нові функції user_db доступні')
except ImportError as e:
    print('⚠️ Проблема з функціями user_db: {}'.format(e))
"

# 9. Створення файлу статусу виправлень
log_info "9. Створення звіту про виправлення..."
cat > deployment_fixes_report.txt << EOF
ЗВІТ ПРО ВИПРАВЛЕННЯ ПІСЛЯ ДЕПЛОЮ
Дата: $(date)
Сервер: $(hostname)
Директорія: $(pwd)

✅ ВИПРАВЛЕНІ ПРОБЛЕМИ:
- requirements.txt: python-telegram-bot версія виправлена на 13.12
- process_webhook.py: файл створено/оновлено з покращеною логікою
- call_tracking.db: база даних ініціалізована
- Права доступу: налаштовано для всіх файлів

📊 СТАТУС СИСТЕМИ:
- Бот PID: $(pgrep -f "python3.*bot.py" 2>/dev/null || echo "НЕ ЗАПУЩЕНИЙ")
- Python версія: $(python3 --version)
- Git коміт: $(git rev-parse --short HEAD 2>/dev/null || echo "N/A")

🧪 ТЕСТИ:
- SUCCESS логіка: $(python3 process_webhook.py '{"duration":"15","disposition":"answered"}' 2>/dev/null || echo "FAILED")
- ERROR логіка: $(python3 process_webhook.py '{"duration":"0","disposition":"no_answer"}' 2>/dev/null || echo "FAILED")

📁 ФАЙЛИ:
$(ls -la *.py | grep -E "(bot|sync|process|webhook)" || echo "Файли не знайдено")

РЕКОМЕНДАЦІЇ:
1. Протестуйте команди: /sync_status, /sync_test
2. Перевірте роботу /hvirtka та /vorota
3. Моніторьте логи: tail -f bot.log webhook_processor.log
EOF

log_success "Звіт збережено: deployment_fixes_report.txt"

echo ""
echo "🎉 ВИПРАВЛЕННЯ ЗАВЕРШЕНО!"
echo "========================"
log_info "Детальний звіт: cat deployment_fixes_report.txt"
log_info "Логи бота: tail -f bot.log"
log_info "Тест команди: надішліть /sync_status боту в Telegram"
echo ""
log_warning "РЕКОМЕНДАЦІЇ:"
echo "1. Протестуйте нові команди: /sync_status, /sync_test"
echo "2. Перевірте роботу /hvirtka та /vorota"
echo "3. Моніторьте логи перші години після виправлень"
