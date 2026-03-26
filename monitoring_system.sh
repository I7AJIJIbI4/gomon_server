#!/bin/bash
# ВИПРАВЛЕНА СИСТЕМА МОНІТОРИНГУ

LOG_DIR="/home/gomoncli/zadarma"
WEBHOOK_LOG="$LOG_DIR/ivr_webhook.log"
MONITOR_LOG="$LOG_DIR/monitoring.log"
WEBHOOK_URL="https://gomonclinic.com/zadarma_ivr_webhook.php"

function log_monitor() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$MONITOR_LOG"
}

function check_webhook_health() {
    log_monitor "🔍 Перевірка здоров'я webhook..."
    
    # Перевірка доступності з timeout
    RESPONSE=$(curl -s -m 10 -w "%{http_code}" -o /dev/null "$WEBHOOK_URL" 2>/dev/null)
    
    if [ "$RESPONSE" = "200" ]; then
        log_monitor "✅ Webhook доступний (HTTP 200)"
        return 0
    else
        log_monitor "❌ Webhook недоступний (HTTP $RESPONSE)"
        return 1
    fi
}

function check_log_size() {
    log_monitor "📊 Перевірка розміру логів..."
    
    if [ -f "$WEBHOOK_LOG" ]; then
        SIZE=$(du -h "$WEBHOOK_LOG" | cut -f1)
        SIZE_BYTES=$(stat -c%s "$WEBHOOK_LOG")
        
        log_monitor "📋 Розмір webhook.log: $SIZE"
        
        if [ "$SIZE_BYTES" -gt 52428800 ]; then
            log_monitor "⚠️ Лог перевищує 50MB - потрібна архівація"
            return 1
        fi
    fi
    
    return 0
}

function analyze_daily_stats() {
    log_monitor "📈 Аналіз денної статистики..."
    
    if [ -f "$WEBHOOK_LOG" ]; then
        TODAY=$(date '+%Y-%m-%d')
        
        TOTAL_CALLS=$(grep "$TODAY" "$WEBHOOK_LOG" | grep "NOTIFY_START" | wc -l)
        INTERNAL_CALLS=$(grep "$TODAY" "$WEBHOOK_LOG" | grep "NOTIFY_INTERNAL" | wc -l)
        DOOR_OPENS=$(grep "$TODAY" "$WEBHOOK_LOG" | grep -E "Хвіртка відкрита|✅.*віртка" | wc -l)
        GATE_OPENS=$(grep "$TODAY" "$WEBHOOK_LOG" | grep -E "Ворота відкриті|✅.*орота" | wc -l)
        SMS_SENT=$(grep "$TODAY" "$WEBHOOK_LOG" | grep -E "SMS успішно|SMS-Fly SUCCESS" | wc -l)
        ERRORS=$(grep "$TODAY" "$WEBHOOK_LOG" | grep -E "❌|ERROR" | wc -l)
        
        log_monitor "📊 Статистика за $TODAY:"
        log_monitor "   📞 Всього дзвінків: $TOTAL_CALLS"
        log_monitor "   🎯 Internal дзвінки: $INTERNAL_CALLS"
        log_monitor "   🏠 Відкриття хвіртки: $DOOR_OPENS"
        log_monitor "   🚪 Відкриття воріт: $GATE_OPENS"
        log_monitor "   📱 SMS надіслано: $SMS_SENT"
        log_monitor "   ❌ Помилки: $ERRORS"
        
        if [ "$ERRORS" -gt 5 ]; then
            log_monitor "⚠️ УВАГА: Багато помилок за день ($ERRORS)"
        fi
    fi
}

function test_webhook_functionality() {
    log_monitor "🧪 Тестування функціональності webhook..."
    
    # Простий тест без jq
    STATUS_RESPONSE=$(curl -s -m 10 "$WEBHOOK_URL" 2>/dev/null)
    
    if echo "$STATUS_RESPONSE" | grep -q '"status":"active"'; then
        log_monitor "✅ Webhook статус: active"
    else
        log_monitor "❌ Webhook статус некоректний"
    fi
}

# Головна функція
function main_monitoring() {
    log_monitor "🚀 ПОЧАТОК ЩОДЕННОГО МОНІТОРИНГУ"
    
    check_webhook_health
    check_log_size
    analyze_daily_stats
    test_webhook_functionality
    
    log_monitor "✅ МОНІТОРИНГ ЗАВЕРШЕНО"
}

main_monitoring
