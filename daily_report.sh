#!/bin/bash
# ВИПРАВЛЕНА СИСТЕМА ЗВІТІВ

LOG_DIR="/home/gomoncli/zadarma"
WEBHOOK_LOG="$LOG_DIR/ivr_webhook.log"
MONITOR_LOG="$LOG_DIR/monitoring.log"
REPORT_DIR="$LOG_DIR/reports"

mkdir -p "$REPORT_DIR"

function generate_daily_report() {
    TODAY=$(date '+%Y-%m-%d')
    REPORT_FILE="$REPORT_DIR/daily_report_$TODAY.txt"
    
    echo "📋 ЩОДЕННИЙ ЗВІТ КЛІНІКИ DR. GOMON COSMETOLOGY" > "$REPORT_FILE"
    echo "📅 Дата: $TODAY" >> "$REPORT_FILE"
    echo "🕐 Згенеровано: $(date '+%Y-%m-%d %H:%M:%S')" >> "$REPORT_FILE"
    echo "==========================================" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    
    if [ -f "$WEBHOOK_LOG" ]; then
        # Статистика
        TOTAL_CALLS=$(grep "$TODAY" "$WEBHOOK_LOG" | grep "NOTIFY_START" | wc -l)
        INTERNAL_CALLS=$(grep "$TODAY" "$WEBHOOK_LOG" | grep "NOTIFY_INTERNAL" | wc -l)
        DOOR_OPENS=$(grep "$TODAY" "$WEBHOOK_LOG" | grep -E "Хвіртка відкрита|✅.*віртка" | wc -l)
        GATE_OPENS=$(grep "$TODAY" "$WEBHOOK_LOG" | grep -E "Ворота відкриті|✅.*орота" | wc -l)
        SMS_SENT=$(grep "$TODAY" "$WEBHOOK_LOG" | grep -E "SMS успішно|SMS-Fly SUCCESS" | wc -l)
        ERRORS=$(grep "$TODAY" "$WEBHOOK_LOG" | grep -E "❌|ERROR" | wc -l)
        
        echo "📞 СТАТИСТИКА ДЗВІНКІВ:" >> "$REPORT_FILE"
        echo "   Всього дзвінків: $TOTAL_CALLS" >> "$REPORT_FILE"
        echo "   Internal дзвінки: $INTERNAL_CALLS" >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"
        
        echo "🎯 ВИКОНАНІ ДІЇ:" >> "$REPORT_FILE"
        echo "   🏠 Відкриття хвіртки: $DOOR_OPENS" >> "$REPORT_FILE"
        echo "   🚪 Відкриття воріт: $GATE_OPENS" >> "$REPORT_FILE"
        echo "   📱 SMS надіслано: $SMS_SENT" >> "$REPORT_FILE"
        echo "   ❌ Помилки: $ERRORS" >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"
        
        # Системна інформація
        echo "🖥️ СИСТЕМА:" >> "$REPORT_FILE"
        echo "   Webhook URL: https://gomonclinic.com/zadarma_ivr_webhook.php" >> "$REPORT_FILE"
        echo "   Розмір логу: $(du -h "$WEBHOOK_LOG" | cut -f1)" >> "$REPORT_FILE"
        echo "   Використання диску: $(df /home | tail -1 | awk '{print $5}')" >> "$REPORT_FILE"
    fi
    
    echo "✅ Звіт збережено: $REPORT_FILE"
    send_report_to_telegram "$REPORT_FILE"
}

function send_report_to_telegram() {
    local report_file="$1"
    
    if [ -f "$report_file" ]; then
        # Створюємо коротку версію
        local today=$(date '+%Y-%m-%d')
        local total_calls=$(grep "$today" "$WEBHOOK_LOG" | grep "NOTIFY_START" | wc -l)
        local door_opens=$(grep "$today" "$WEBHOOK_LOG" | grep -E "Хвіртка відкрита|✅.*віртка" | wc -l)
        local gate_opens=$(grep "$today" "$WEBHOOK_LOG" | grep -E "Ворота відкриті|✅.*орота" | wc -l)
        local sms_sent=$(grep "$today" "$WEBHOOK_LOG" | grep -E "SMS успішно|SMS-Fly SUCCESS" | wc -l)
        local errors=$(grep "$today" "$WEBHOOK_LOG" | grep -E "❌|ERROR" | wc -l)
        
        local message="📋 ЗВІТ $today%0A📞 Дзвінки: $total_calls%0A🏠 Хвіртка: $door_opens%0A🚪 Ворота: $gate_opens%0A📱 SMS: $sms_sent%0A❌ Помилки: $errors"
        
        curl -s -X POST "https://api.telegram.org/botYOUR_TELEGRAM_BOT_TOKEN/sendMessage" \
            -d "chat_id=573368771" \
            -d "text=$message" > /dev/null 2>&1
        
        if [ $? -eq 0 ]; then
            echo "📱 Звіт надіслано в Telegram"
        else
            echo "❌ Помилка відправки в Telegram"
        fi
    fi
}

generate_daily_report
