
# ============================================
# ЧАСТИНА 6: МОНІТОРИНГ API СЕРВІСІВ
# ============================================

log_message "🌐 МОНІТОРИНГ API СЕРВІСІВ"
log_message "========================="

cd "$ZADARMA_DIR"

# 6.1 Запуск тестування API
log_message "1️⃣ Тестування всіх API сервісів..."
if python3 api_monitor.py > /tmp/api_test_output.txt 2>&1; then
    API_EXIT_CODE=$?
    log_message "✅ API тестування завершено (код: $API_EXIT_CODE)"
    
    # Логуємо результати
    while IFS= read -r line; do
        log_message "   $line"
    done < /tmp/api_test_output.txt
    
    # Якщо є помилки API - додаємо до лічільника помилок
    if [ "$API_EXIT_CODE" -gt 0 ]; then
        ERROR_COUNT=$((ERROR_COUNT + API_EXIT_CODE))
        log_message "⚠️ Виявлено $API_EXIT_CODE проблем з API"
    fi
else
    log_message "❌ Помилка запуску API тестування"
    ERROR_COUNT=$((ERROR_COUNT + 5))
fi

# 6.2 Перевірка специфічних API параметрів
log_message "2️⃣ Додаткові перевірки API..."

# Zadarma баланс (якщо API працює)
if python3 -c "from zadarma_api import test_zadarma_auth; exit(0 if test_zadarma_auth() else 1)" 2>/dev/null; then
    log_message "✅ Zadarma API доступний"
else
    log_message "❌ Zadarma API недоступний"
fi

# WLaunch підключення
WLAUNCH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://wlaunch.wlapi.net/api/v1/companies" \
    -H "Authorization: Bearer $(python3 -c "from config import WLAUNCH_API_KEY; print(WLAUNCH_API_KEY)" 2>/dev/null)" 2>/dev/null || echo "000")

if [ "$WLAUNCH_STATUS" = "200" ]; then
    log_message "✅ WLaunch API доступний (HTTP: $WLAUNCH_STATUS)"
else
    log_message "❌ WLaunch API недоступний (HTTP: $WLAUNCH_STATUS)"
fi

rm -f /tmp/api_test_output.txt
