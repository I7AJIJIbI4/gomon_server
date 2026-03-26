#!/bin/bash
# ШВИДКІ КОМАНДИ ДЛЯ АДМІНІСТРУВАННЯ СИСТЕМИ

function show_menu() {
    echo "🎯 СИСТЕМА УПРАВЛІННЯ КЛІНІКИ ГОМОНА"
    echo "=================================="
    echo "1. 📊 Поточний статус системи"
    echo "2. 📋 Останні логи (50 рядків)"
    echo "3. 📈 Статистика за сьогодні"
    echo "4. 🧪 Тест webhook"
    echo "5. 📱 Ручний тест SMS"
    echo "6. 🔧 Запуск обслуговування"
    echo "7. 📊 Показати звіти"
    echo "8. 🗂️ Показати архіви"
    echo "0. ❌ Вихід"
    echo "=================================="
}

function check_status() {
    echo "📊 ПОТОЧНИЙ СТАТУС СИСТЕМИ:"
    echo ""
    
    # Webhook статус
    echo "🔗 Webhook:"
    curl -s https://gomonclinic.com/zadarma_ivr_webhook.php | grep -o '"message":"[^"]*"' | cut -d'"' -f4
    
    # Розмір логу
    if [ -f "/home/gomoncli/zadarma/ivr_webhook.log" ]; then
        echo "📋 Розмір логу: $(du -h /home/gomoncli/zadarma/ivr_webhook.log | cut -f1)"
    fi
    
    # Останній дзвінок
    if [ -f "/home/gomoncli/zadarma/ivr_webhook.log" ]; then
        LAST_CALL=$(grep "NOTIFY_START" /home/gomoncli/zadarma/ivr_webhook.log | tail -1 | cut -d']' -f1 | tr -d '[')
        echo "📞 Останній дзвінок: $LAST_CALL"
    fi
    
    # Використання диску
    echo "💾 Використання диску: $(df /home | tail -1 | awk '{print $5}')"
}

function show_recent_logs() {
    echo "📋 ОСТАННІ 50 РЯДКІВ ЛОГУ:"
    echo "========================"
    tail -50 /home/gomoncli/zadarma/ivr_webhook.log
}

function daily_stats() {
    echo "📈 СТАТИСТИКА ЗА СЬОГОДНІ:"
    echo "========================="
    
    TODAY=$(date '+%Y-%m-%d')
    LOG_FILE="/home/gomoncli/zadarma/ivr_webhook.log"
    
    if [ -f "$LOG_FILE" ]; then
        TOTAL_CALLS=$(grep "$TODAY" "$LOG_FILE" | grep "NOTIFY_START" | wc -l)
        INTERNAL_CALLS=$(grep "$TODAY" "$LOG_FILE" | grep "NOTIFY_INTERNAL" | wc -l)
        DOOR_OPENS=$(grep "$TODAY" "$LOG_FILE" | grep -E "Хвіртка відкрита|✅.*віртка" | wc -l)
        GATE_OPENS=$(grep "$TODAY" "$LOG_FILE" | grep -E "Ворота відкриті|✅.*орота" | wc -l)
        SMS_SENT=$(grep "$TODAY" "$LOG_FILE" | grep -E "SMS успішно|SMS-Fly SUCCESS" | wc -l)
        ERRORS=$(grep "$TODAY" "$LOG_FILE" | grep -E "❌|ERROR" | wc -l)
        
        echo "📞 Всього дзвінків: $TOTAL_CALLS"
        echo "🎯 Internal дзвінки: $INTERNAL_CALLS"
        echo "🏠 Відкриття хвіртки: $DOOR_OPENS"
        echo "🚪 Відкриття воріт: $GATE_OPENS"
        echo "📱 SMS надіслано: $SMS_SENT"
        echo "❌ Помилки: $ERRORS"
        
        if [ "$ERRORS" -gt 0 ]; then
            echo ""
            echo "🔍 Останні помилки:"
            grep "$TODAY" "$LOG_FILE" | grep -E "❌|ERROR" | tail -3
        fi
    else
        echo "❌ Лог файл не знайдено"
    fi
}

function test_webhook() {
    echo "🧪 ТЕСТУВАННЯ WEBHOOK:"
    echo "===================="
    
    echo "📡 Тест доступності..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://gomonclinic.com/zadarma_ivr_webhook.php)
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo "✅ Webhook доступний (HTTP 200)"
        
        echo "📊 Отримання статусу..."
        curl -s https://gomonclinic.com/zadarma_ivr_webhook.php | grep -E '"status"|"message"|"version"' | sed 's/[",]//g' | sed 's/:/: /'
    else
        echo "❌ Webhook недоступний (HTTP $HTTP_CODE)"
    fi
}

function test_sms() {
    echo "📱 ТЕСТ SMS:"
    echo "==========="
    
    read -p "Введіть номер телефону для тесту (0933297777): " PHONE
    PHONE=${PHONE:-0933297777}
    
    echo "📤 Відправка тестового SMS на $PHONE..."
    
    curl -X POST "https://gomonclinic.com/zadarma_ivr_webhook.php" \
        -H "Content-Type: application/json" \
        -d "{\"event\": \"NOTIFY_INTERNAL\", \"caller_id\": \"$PHONE\", \"internal\": \"203\"}" \
        -s > /dev/null
    
    echo "✅ Тест надіслано. Перевірте логи:"
    tail -5 /home/gomoncli/zadarma/ivr_webhook.log | grep -E "SMS|CORRECT"
}

function run_maintenance() {
    echo "🔧 ЗАПУСК ОБСЛУГОВУВАННЯ:"
    echo "======================="
    ~/daily_maintenance.sh
}

function show_reports() {
    echo "📊 ДОСТУПНІ ЗВІТИ:"
    echo "================"
    ls -la /home/gomoncli/zadarma/reports/ | grep "daily_report"
    
    echo ""
    read -p "Показати останній звіт? (y/n): " SHOW
    if [ "$SHOW" = "y" ] || [ "$SHOW" = "Y" ]; then
        LATEST_REPORT=$(ls -t /home/gomoncli/zadarma/reports/daily_report_*.txt | head -1)
        if [ -f "$LATEST_REPORT" ]; then
            echo ""
            echo "📋 ОСТАННІЙ ЗВІТ:"
            cat "$LATEST_REPORT"
        fi
    fi
}

function show_archives() {
    echo "🗂️ АРХІВИ ЛОГІВ:"
    echo "==============="
    ls -lah /home/gomoncli/zadarma/archive/ 2>/dev/null || echo "Архівів поки немає"
}

# Головне меню
while true; do
    echo ""
    show_menu
    read -p "Оберіть опцію (0-8): " choice
    
    case $choice in
        1) check_status ;;
        2) show_recent_logs ;;
        3) daily_stats ;;
        4) test_webhook ;;
        5) test_sms ;;
        6) run_maintenance ;;
        7) show_reports ;;
        8) show_archives ;;
        0) echo "👋 До побачення!"; break ;;
        *) echo "❌ Невірний вибір. Спробуйте ще раз." ;;
    esac
    
    echo ""
    read -p "Натисніть Enter для продовження..."
done
