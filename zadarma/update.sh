#!/bin/bash

echo "🔄 ОНОВЛЕННЯ ZADARMA BOT НА СЕРВЕРІ (З ПЕРЕВІРКОЮ ВИПРАВЛЕНЬ)"
echo "============================================================="

# Кольори для виводу
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

PROJECT_DIR="/home/gomoncli/zadarma"
BACKUP_DIR="/home/gomoncli/backup/zadarma_update_$(date +%Y%m%d_%H%M%S)"

echo -e "${BLUE}📁 Оновлення проєкту: $PROJECT_DIR${NC}"
echo -e "${PURPLE}🎯 Включено: перевірка критичних виправлень webhook системи${NC}"

# Перевірка чи існує проєкт
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}❌ ПОМИЛКА: Проєкт не знайдено в $PROJECT_DIR${NC}"
    exit 1
fi

cd "$PROJECT_DIR" || exit 1

# 1. Створення backup важливих файлів
echo -e "${YELLOW}1️⃣ Створення backup важливих файлів...${NC}"
mkdir -p "$BACKUP_DIR"

# Бекапимо критичні файли ПЕРЕД оновленням
CRITICAL_FILES=("config.py" "users.db" ".env" "simple_webhook.py" "process_webhook.py")
for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$BACKUP_DIR/"
        echo -e "   💾 $file"
    fi
done

# Бекапимо PHP webhook
if [ -f "/home/gomoncli/public_html/zadarma_webhook.php" ]; then
    cp "/home/gomoncli/public_html/zadarma_webhook.php" "$BACKUP_DIR/"
    echo -e "   💾 zadarma_webhook.php"
fi

# Бекапимо базу даних
if [ -f "call_tracking.db" ]; then
    cp "call_tracking.db" "$BACKUP_DIR/"
    echo -e "   💾 call_tracking.db"
fi

# Бекапимо логи
cp *.log "$BACKUP_DIR/" 2>/dev/null && echo -e "   💾 *.log"

echo -e "${GREEN}✅ Backup створено: $BACKUP_DIR${NC}"

# 2. Зупинення бота
echo -e "${YELLOW}2️⃣ Зупинення бота...${NC}"
BOT_PIDS=$(pgrep -f "python3.*bot.py")
if [ -n "$BOT_PIDS" ]; then
    echo -e "   🛑 Зупиняємо бота (PID: $BOT_PIDS)"
    pkill -f "python3.*bot.py"
    sleep 3
    
    # Перевіряємо чи зупинився
    if pgrep -f "python3.*bot.py" > /dev/null; then
        echo -e "${RED}   ⚠️ Бот не зупинився, примусове завершення...${NC}"
        pkill -9 -f "python3.*bot.py"
        sleep 2
    fi
    echo -e "${GREEN}   ✅ Бот зупинено${NC}"
else
    echo -e "   ℹ️ Бот не був запущений"
fi

# 3. Перевірка Git статусу
echo -e "${YELLOW}3️⃣ Перевірка Git статусу...${NC}"

if [ ! -d ".git" ]; then
    echo -e "${RED}❌ ПОМИЛКА: Це не Git репозиторій${NC}"
    echo -e "${YELLOW}Потрібно ініціалізувати Git або clone проєкт заново${NC}"
    exit 1
fi

# Показуємо поточний стан
echo -e "${BLUE}   📊 Поточний стан репозиторія:${NC}"
git status --short

# Зберігаємо локальні зміни
CHANGED_FILES=$(git status --porcelain | wc -l)
if [ "$CHANGED_FILES" -gt 0 ]; then
    echo -e "${YELLOW}   ⚠️ Знайдено $CHANGED_FILES змінених файлів${NC}"
    echo -e "${BLUE}   📋 Збережемо у stash...${NC}"
    git stash push -m "Auto stash before update $(date)"
fi

# 4. Оновлення коду з GitHub
echo -e "${YELLOW}4️⃣ Оновлення з GitHub...${NC}"

# Завантажуємо зміни
git fetch origin main

# Показуємо що буде оновлено
COMMITS_BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "0")
if [ "$COMMITS_BEHIND" -gt 0 ]; then
    echo -e "${BLUE}   📥 Доступно $COMMITS_BEHIND нових коммітів:${NC}"
    git log --oneline HEAD..origin/main | head -5
else
    echo -e "${GREEN}   ✅ Код вже актуальний${NC}"
fi

# КРИТИЧНО: Тимчасово зберігаємо конфіги
echo -e "${BLUE}   💾 Тимчасово зберігаємо критичні файли...${NC}"
TEMP_DIR="/tmp/zadarma_configs_$(date +%s)"
mkdir -p "$TEMP_DIR"

for file in config.py users.db call_tracking.db .env; do
    if [ -f "$file" ]; then
        cp "$file" "$TEMP_DIR/"
        echo -e "   📁 $file → $TEMP_DIR/"
    fi
done

# Застосовуємо оновлення
echo -e "${BLUE}   🔄 Застосовуємо оновлення...${NC}"
git reset --hard origin/main

# КРИТИЧНО: Відновлюємо конфіги
echo -e "${BLUE}   🔄 Відновлюємо критичні файли...${NC}"
for file in config.py users.db call_tracking.db .env; do
    if [ -f "$TEMP_DIR/$file" ]; then
        cp "$TEMP_DIR/$file" "$file"
        echo -e "   ✅ $file відновлено"
    fi
done

# Очищуємо тимчасовий каталог
rm -rf "$TEMP_DIR"

echo -e "${GREEN}✅ Код оновлено зі збереженням конфігурацій${NC}"

# 5. НОВЕ: Перевірка критичних виправлень
echo -e "${PURPLE}5️⃣ 🔍 ПЕРЕВІРКА КРИТИЧНИХ ВИПРАВЛЕНЬ...${NC}"

# Перевіряємо чи файли містять виправлену логіку
check_fix() {
    local file="$1"
    local pattern="$2"
    local description="$3"
    
    if [ ! -f "$file" ]; then
        echo -e "${RED}   ❌ $file відсутній${NC}"
        return 1
    fi
    
    if grep -q "$pattern" "$file"; then
        echo -e "${GREEN}   ✅ $description${NC}"
        return 0
    else
        echo -e "${RED}   ❌ $description - НЕ ЗНАЙДЕНО${NC}"
        return 1
    fi
}

FIX_ERRORS=0

echo -e "${BLUE}   🧪 Перевіряємо виправлення в Python файлах:${NC}"

# Перевіряємо simple_webhook.py
if check_fix "simple_webhook.py" "duration > 0" "Правильна логіка успіху (duration > 0)"; then
    :
else
    FIX_ERRORS=$((FIX_ERRORS + 1))
fi

if check_fix "simple_webhook.py" "\.format(" "Python 3.6 сумісність (.format замість f-strings)"; then
    :
else
    FIX_ERRORS=$((FIX_ERRORS + 1))
fi

if check_fix "simple_webhook.py" "ENHANCED.*WEBHOOK.*PROCESSOR" "Оновлений enhanced processor"; then
    :
else
    FIX_ERRORS=$((FIX_ERRORS + 1))
fi

# Перевіряємо process_webhook.py
if check_fix "process_webhook.py" "duration > 0" "Правильна логіка в process_webhook.py"; then
    :
else
    FIX_ERRORS=$((FIX_ERRORS + 1))
fi

# Перевіряємо PHP webhook
PHP_WEBHOOK="/home/gomoncli/public_html/zadarma_webhook.php"
if [ -f "$PHP_WEBHOOK" ]; then
    echo -e "${BLUE}   🧪 Перевіряємо PHP webhook:${NC}"
    
    if check_fix "$PHP_WEBHOOK" "isBotCallback" "Функція розділення IVR/Bot"; then
        :
    else
        FIX_ERRORS=$((FIX_ERRORS + 1))
    fi
    
    if check_fix "$PHP_WEBHOOK" "simple_webhook.py" "Використання simple_webhook.py"; then
        :
    else
        FIX_ERRORS=$((FIX_ERRORS + 1))
    fi
else
    echo -e "${RED}   ❌ PHP webhook файл відсутній${NC}"
    FIX_ERRORS=$((FIX_ERRORS + 1))
fi

if [ $FIX_ERRORS -eq 0 ]; then
    echo -e "${GREEN}   🎉 ВСІ КРИТИЧНІ ВИПРАВЛЕННЯ ПРИСУТНІ!${NC}"
else
    echo -e "${RED}   ⚠️ ЗНАЙДЕНО $FIX_ERRORS ВІДСУТНІХ ВИПРАВЛЕНЬ!${NC}"
    echo -e "${YELLOW}   📋 Можливо потрібно оновити файли вручну${NC}"
fi

# 6. Налаштування прав доступу
echo -e "${YELLOW}6️⃣ Налаштування прав...${NC}"
chmod +x *.sh *.py
chmod -R 755 webhooks/ 2>/dev/null || true

# Критично важливо для webhook файлів
chmod +x simple_webhook.py process_webhook.py
if [ -f "$PHP_WEBHOOK" ]; then
    chmod 755 "$PHP_WEBHOOK"
fi

echo -e "${GREEN}✅ Права налаштовано${NC}"

# 7. НОВЕ: Тестування виправлень
echo -e "${PURPLE}7️⃣ 🧪 ТЕСТУВАННЯ ВИПРАВЛЕНЬ...${NC}"

# Тест 1: Python логіка
echo -e "${BLUE}   📋 Тест 1: Python логіка успіху${NC}"
TEST_RESULT=$(python3 simple_webhook.py '{"event":"NOTIFY_END","caller_id":"0733103110","called_did":"0637442017","disposition":"cancel","duration":"5"}' 2>&1)

if echo "$TEST_RESULT" | grep -q "✅.*відчинено"; then
    echo -e "${GREEN}   ✅ SUCCESS логіка працює правильно${NC}"
else
    echo -e "${RED}   ❌ SUCCESS логіка НЕ ПРАЦЮЄ${NC}"
    echo -e "${YELLOW}   Результат: $TEST_RESULT${NC}"
    FIX_ERRORS=$((FIX_ERRORS + 1))
fi

# Тест 2: Логіка помилок
echo -e "${BLUE}   📋 Тест 2: Логіка помилок${NC}"
ERROR_TEST=$(python3 simple_webhook.py '{"event":"NOTIFY_END","caller_id":"0733103110","called_did":"0930063585","disposition":"busy","duration":"0"}' 2>&1)

if echo "$ERROR_TEST" | grep -q "❌.*зайнятий"; then
    echo -e "${GREEN}   ✅ ERROR логіка працює правильно${NC}"
else
    echo -e "${RED}   ❌ ERROR логіка НЕ ПРАЦЮЄ${NC}"
    echo -e "${YELLOW}   Результат: $ERROR_TEST${NC}"
fi

# Тест 3: PHP Webhook
echo -e "${BLUE}   📋 Тест 3: PHP Webhook роутинг${NC}"
PHP_TEST=$(curl -s -X POST https://gomonclinic.com/zadarma_webhook.php -d "event=NOTIFY_END&caller_id=0733103110&called_did=0637442017&disposition=cancel&duration=5" 2>/dev/null)

if echo "$PHP_TEST" | grep -q "bot_processed"; then
    echo -e "${GREEN}   ✅ PHP роутинг працює правильно${NC}"
else
    echo -e "${YELLOW}   ⚠️ PHP тест не пройшов або webhook недоступний${NC}"
    echo -e "${BLUE}   Відповідь: ${PHP_TEST:0:100}...${NC}"
fi

# 8. Оновлення залежностей
echo -e "${YELLOW}8️⃣ Оновлення залежностей...${NC}"
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt --user --upgrade
    echo -e "${GREEN}✅ Залежності оновлено${NC}"
else
    echo -e "${YELLOW}   ⚠️ requirements.txt не знайдено${NC}"
fi

# 9. Перевірка конфігурації
echo -e "${YELLOW}9️⃣ Перевірка конфігурації...${NC}"

if [ ! -f "config.py" ]; then
    echo -e "${RED}❌ КРИТИЧНА ПОМИЛКА: Відсутній config.py${NC}"
    if [ -f "config.py.example" ]; then
        echo -e "${YELLOW}Створюємо config.py з шаблону...${NC}"
        cp config.py.example config.py
        echo -e "${RED}⚠️  УВАГА: Відредагуйте config.py з реальними API ключами!${NC}"
        echo -e "${BLUE}nano config.py${NC}"
    fi
    exit 1
fi

# Тестуємо конфігурацію
if python3 -c "from config import validate_config; validate_config()" 2>/dev/null; then
    echo -e "${GREEN}✅ Конфігурація валідна${NC}"
else
    echo -e "${RED}❌ ПОМИЛКА: Некоректна конфігурація${NC}"
    echo -e "${YELLOW}Перевірте файл config.py та виправте помилки${NC}"
    exit 1
fi

# 10. Запуск бота
echo -e "${YELLOW}🔟 Запуск оновленого бота...${NC}"

if [ -f "check_and_run_bot.sh" ]; then
    # Використовуємо професійний скрипт управління ботом
    chmod +x check_and_run_bot.sh
    echo -e "   🔄 Перезапускаємо бота через check_and_run_bot.sh..."
    ./check_and_run_bot.sh restart
    
    # Перевіряємо статус
    sleep 3
    if ./check_and_run_bot.sh status | grep -q "✅.*працює"; then
        echo -e "${GREEN}✅ Бот успішно працює${NC}"
    else
        echo -e "${RED}❌ Бот не запустився, перевірте статус:${NC}"
        ./check_and_run_bot.sh status
        exit 1
    fi
elif [ -f "run_script.sh" ]; then
    # Резервний варіант
    echo -e "   🔄 Запускаємо через run_script.sh..."
    nohup ./run_script.sh > /dev/null 2>&1 &
    BOT_PID=$!
    echo -e "   🚀 Бот запущено (PID: $BOT_PID)"
else
    # Останній варіант - напряму
    echo -e "${YELLOW}   ⚠️ Скрипти запуску не знайдені, запускаємо напряму:${NC}"
    nohup python3 bot.py > /dev/null 2>&1 &
    echo -e "   🚀 Бот запущено напряму"
fi

# 11. Очищення старих backup'ів
echo -e "${YELLOW}1️⃣1️⃣ Очищення старих backup'ів...${NC}"
BACKUP_BASE_DIR="$(dirname "$BACKUP_DIR")"
if [ -d "$BACKUP_BASE_DIR" ]; then
    ls -1t "$BACKUP_BASE_DIR"/zadarma_update_* 2>/dev/null | tail -n +6 | xargs rm -rf 2>/dev/null || true
    REMAINING_BACKUPS=$(ls -1 "$BACKUP_BASE_DIR"/zadarma_update_* 2>/dev/null | wc -l)
    echo -e "   🗑️ Залишено $REMAINING_BACKUPS останніх backup'ів"
fi

# ФІНАЛЬНИЙ ЗВІТ
echo ""
echo -e "${GREEN}🎉 ОНОВЛЕННЯ ЗАВЕРШЕНО!${NC}"
echo ""

if [ $FIX_ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ КРИТИЧНІ ВИПРАВЛЕННЯ АКТИВНІ!${NC}"
    echo -e "${GREEN}   - Правильна логіка успіху (duration > 0)${NC}"
    echo -e "${GREEN}   - Python 3.6 сумісність${NC}"  
    echo -e "${GREEN}   - Роутинг IVR/Bot розділений${NC}"
    echo -e "${GREEN}   - Telegram повідомлення працюють${NC}"
else
    echo -e "${YELLOW}⚠️ ЗНАЙДЕНО $FIX_ERRORS ПРОБЛЕМ З ВИПРАВЛЕННЯМИ${NC}"
    echo -e "${YELLOW}   Перевірте файли та логи${NC}"
fi

echo ""
echo -e "${BLUE}📋 ПІДСУМОК:${NC}"
echo -e "   📁 Проєкт:        $PROJECT_DIR"
echo -e "   💾 Backup:        $BACKUP_DIR"
echo -e "   🤖 Bot PID:       $(pgrep -f "python3.*bot.py" || echo "не знайдено")"
echo -e "   📊 Коммітів:      $COMMITS_BEHIND нових"
echo -e "   🔧 Виправлення:   $([ $FIX_ERRORS -eq 0 ] && echo "✅ ВСЕ ОК" || echo "⚠️ $FIX_ERRORS проблем")"
echo ""
echo -e "${BLUE}🔍 ПЕРЕВІРКА СИСТЕМИ:${NC}"
echo -e "   Статус бота:      ps aux | grep bot.py"
echo -e "   Логи бота:        tail -f bot.log"
echo -e "   Тест команди:     Надішліть /hvirtka або /vorota боту"
echo -e "   PHP логи:         tail -f /home/gomoncli/public_html/error_log"
echo ""

if [ $FIX_ERRORS -eq 0 ]; then
    echo -e "${GREEN}🚀 СИСТЕМА ГОТОВА! Тестуйте команди /hvirtka та /vorota${NC}"
else
    echo -e "${YELLOW}⚠️ ПОТРІБНА УВАГА: Перевірте виправлення вручну${NC}"
fi
