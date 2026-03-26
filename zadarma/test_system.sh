#!/bin/bash
# Комплексний тест всієї системи webhook
# Перевіряє IVR, Bot callbacks, та всі статуси Telegram повідомлень

echo "🧪 === КОМПЛЕКСНИЙ ТЕСТ WEBHOOK СИСТЕМИ ==="
echo "Дата: $(date)"
echo

# Кольори для виводу
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Лічильники
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Функція тестування
test_webhook() {
    local test_name="$1"
    local webhook_data="$2"
    local expected_routing="$3"
    local expected_status="$4"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    echo -e "${BLUE}📋 Тест $TOTAL_TESTS: $test_name${NC}"
    echo "   Дані: $webhook_data"
    echo "   Очікується: $expected_routing → $expected_status"
    
    # Відправляємо POST запит на webhook
    response=$(curl -s -X POST https://gomonclinic.com/zadarma_webhook.php \
        -d "$webhook_data" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo "   Відповідь: $response"
        
        # Перевіряємо роутинг
        if [[ "$expected_routing" == "BOT" ]]; then
            if [[ "$response" == *"bot_processed"* ]]; then
                echo -e "   ✅ ${GREEN}Роутинг: PASS (Bot)${NC}"
                
                # Перевіряємо статус в відповіді бота
                if [[ "$response" == *"$expected_status"* ]]; then
                    echo -e "   ✅ ${GREEN}Статус: PASS${NC}"
                    PASSED_TESTS=$((PASSED_TESTS + 1))
                else
                    echo -e "   ❌ ${RED}Статус: FAIL (не знайдено '$expected_status')${NC}"
                    FAILED_TESTS=$((FAILED_TESTS + 1))
                fi
            else
                echo -e "   ❌ ${RED}Роутинг: FAIL (очікувався Bot)${NC}"
                FAILED_TESTS=$((FAILED_TESTS + 1))
            fi
        else
            # IVR тест
            if [[ "$response" == *"ivr_say"* || "$response" == *"status\":\"ok"* ]]; then
                echo -e "   ✅ ${GREEN}Роутинг: PASS (IVR)${NC}"
                PASSED_TESTS=$((PASSED_TESTS + 1))
            else
                echo -e "   ❌ ${RED}Роутинг: FAIL (очікувався IVR)${NC}"
                FAILED_TESTS=$((FAILED_TESTS + 1))
            fi
        fi
    else
        echo -e "   ❌ ${RED}NETWORK ERROR${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    
    echo
}

# Функція тестування Python скрипта
test_python_script() {
    local test_name="$1"
    local webhook_data="$2"
    local expected_status="$3"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    echo -e "${BLUE}🐍 Python тест $TOTAL_TESTS: $test_name${NC}"
    echo "   Команда: python3 simple_webhook.py '$webhook_data'"
    
    # Тестуємо Python скрипт напряму
    result=$(cd /home/gomoncli/zadarma && python3 simple_webhook.py "$webhook_data" 2>&1)
    
    if [ $? -eq 0 ]; then
        echo "   Результат: $result"
        
        if [[ "$result" == *"$expected_status"* ]]; then
            echo -e "   ✅ ${GREEN}PASS${NC}"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo -e "   ❌ ${RED}FAIL (не знайдено '$expected_status')${NC}"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo -e "   ❌ ${RED}Python ERROR: $result${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    
    echo
}

echo "🔄 === ТЕСТИ BOT CALLBACKS (Telegram повідомлення) ==="

# Тест 1: Успішне відкриття хвіртки
test_webhook "Хвіртка - Успіх" \
    "event=NOTIFY_END&caller_id=0733103110&called_did=0637442017&disposition=cancel&duration=5" \
    "BOT" "✅ Хвіртка відчинено!"

# Тест 2: Успішне відкриття воріт  
test_webhook "Ворота - Успіх" \
    "event=NOTIFY_END&caller_id=0733103110&called_did=0930063585&disposition=cancel&duration=7" \
    "BOT" "✅ Ворота відчинено!"

# Тест 3: Хвіртка зайнята
test_webhook "Хвіртка - Зайнято" \
    "event=NOTIFY_END&caller_id=0733103110&called_did=0637442017&disposition=busy&duration=0" \
    "BOT" "❌ Номер хвіртка зайнятий"

# Тест 4: Ворота не відповідають
test_webhook "Ворота - Не відповідає" \
    "event=NOTIFY_END&caller_id=0733103110&called_did=0930063585&disposition=cancel&duration=0" \
    "BOT" "❌ Номер ворота не відповідає"

# Тест 5: Ворота не відповідають (no-answer)
test_webhook "Ворота - No Answer" \
    "event=NOTIFY_END&caller_id=0733103110&called_did=0930063585&disposition=no-answer&duration=0" \
    "BOT" "❌ Номер ворота не відповідає"

# Тест 6: Хвіртка - інша помилка
test_webhook "Хвіртка - Помилка" \
    "event=NOTIFY_END&caller_id=0733103110&called_did=0637442017&disposition=failed&duration=2" \
    "BOT" "❌ Не вдалося відкрити хвіртка"

echo "🔄 === ТЕСТИ IVR (не повинні ламатися) ==="

# Тест 7: IVR Start - зовнішній дзвінок
test_webhook "IVR - Початок дзвінка" \
    "event=NOTIFY_START&caller_id=0501234567&called_did=0733103110" \
    "IVR" "ivr_say"

# Тест 8: IVR Response - вибір воріт
test_webhook "IVR - Вибір воріт" \
    "event=NOTIFY_IVR&caller_id=0501234567&called_did=0733103110&wait_dtmf[digits]=1" \
    "IVR" "ворота"

# Тест 9: IVR Response - вибір хвіртки
test_webhook "IVR - Вибір хвіртки" \
    "event=NOTIFY_IVR&caller_id=0501234567&called_did=0733103110&wait_dtmf[digits]=2" \
    "IVR" "хвіртка"

# Тест 10: IVR End
test_webhook "IVR - Завершення" \
    "event=NOTIFY_END&caller_id=0501234567&called_did=0733103110&disposition=hangup&duration=30" \
    "IVR" "ok"

echo "🔄 === ПРЯМІ ТЕСТИ PYTHON СКРИПТА ==="

# Тест Python скрипта напряму (без PHP)
test_python_script "Python - Хвіртка успіх" \
    '{"event":"NOTIFY_END","caller_id":"0733103110","called_did":"0637442017","disposition":"cancel","duration":"5"}' \
    "✅ Хвіртка відчинено!"

test_python_script "Python - Ворота зайнято" \
    '{"event":"NOTIFY_END","caller_id":"0733103110","called_did":"0930063585","disposition":"busy","duration":"0"}' \
    "❌ Номер ворота зайнятий"

test_python_script "Python - Хвіртка не відповідає" \
    '{"event":"NOTIFY_END","caller_id":"0733103110","called_did":"0637442017","disposition":"cancel","duration":"0"}' \
    "❌ Номер хвіртка не відповідає"

echo "📊 === РЕЗУЛЬТАТИ ТЕСТУВАННЯ ==="
echo -e "Всього тестів: ${BLUE}$TOTAL_TESTS${NC}"
echo -e "Пройшло: ${GREEN}$PASSED_TESTS${NC}"  
echo -e "Провалилось: ${RED}$FAILED_TESTS${NC}"

SUCCESS_RATE=$((PASSED_TESTS * 100 / TOTAL_TESTS))
echo -e "Відсоток успішності: ${YELLOW}$SUCCESS_RATE%${NC}"

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "\n🎉 ${GREEN}ВСІ ТЕСТИ ПРОЙШЛИ! Система працює ідеально!${NC}"
    exit 0
else
    echo -e "\n⚠️  ${YELLOW}Знайдено $FAILED_TESTS проблем. Перевірте логи вище.${NC}"
    exit 1
fi
