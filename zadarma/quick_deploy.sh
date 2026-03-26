#!/bin/bash

echo "🚀 ШВИДКЕ РОЗГОРТАННЯ ZADARMA BOT З GITHUB"
echo "=========================================="

# Кольори
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR="/home/gomoncli/zadarma"

echo -e "${BLUE}📁 Переходимо до: $PROJECT_DIR${NC}"

# Перевіряємо чи існує проєкт
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}❌ ПОМИЛКА: Проєкт не знайдено в $PROJECT_DIR${NC}"
    echo -e "${YELLOW}Потрібно спочатку клонувати репозиторій${NC}"
    exit 1
fi

cd "$PROJECT_DIR" || exit 1

# Перевіряємо чи це Git репозиторій
if [ ! -d ".git" ]; then
    echo -e "${RED}❌ ПОМИЛКА: Це не Git репозиторій${NC}"
    exit 1
fi

echo -e "${YELLOW}1️⃣ Отримуємо останні зміни з GitHub...${NC}"

# Зберігаємо локальні зміни якщо є
CHANGED_FILES=$(git status --porcelain | wc -l)
if [ "$CHANGED_FILES" -gt 0 ]; then
    echo -e "${YELLOW}   📋 Зберігаємо локальні зміни...${NC}"
    git stash push -m "Auto stash before quick deploy $(date)"
fi

# Завантажуємо останні зміни
echo -e "${BLUE}   📥 git fetch origin main...${NC}"
git fetch origin main

# Показуємо що буде оновлено
COMMITS_BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "0")
if [ "$COMMITS_BEHIND" -gt 0 ]; then
    echo -e "${BLUE}   🆕 Доступно $COMMITS_BEHIND нових коммітів:${NC}"
    git log --oneline HEAD..origin/main | head -3
    
    echo -e "${YELLOW}   🔄 git pull origin main...${NC}"
    git pull origin main
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}   ✅ Код успішно оновлено${NC}"
    else
        echo -e "${RED}   ❌ ПОМИЛКА: Git pull не вдався${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}   ✅ Код вже актуальний (нових коммітів немає)${NC}"
fi

echo ""
echo -e "${YELLOW}2️⃣ Запускаємо повне оновлення системи...${NC}"

# Перевіряємо чи існує update.sh
if [ ! -f "update.sh" ]; then
    echo -e "${RED}❌ ПОМИЛКА: update.sh не знайдено${NC}"
    exit 1
fi

# Робимо update.sh виконуваним
chmod +x update.sh

echo -e "${BLUE}   🔧 Запускаємо ./update.sh...${NC}"
echo ""

# Запускаємо update.sh
./update.sh

UPDATE_EXIT_CODE=$?

echo ""
echo -e "${BLUE}📊 РЕЗУЛЬТАТ ШВИДКОГО РОЗГОРТАННЯ:${NC}"

if [ $UPDATE_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ ШВИДКЕ РОЗГОРТАННЯ УСПІШНЕ!${NC}"
    echo -e "${GREEN}   - Git pull виконано${NC}"
    echo -e "${GREEN}   - Update.sh успішно завершений${NC}"
    echo ""
    echo -e "${BLUE}🧪 ТЕСТУЙТЕ СИСТЕМУ:${NC}"
    echo -e "   📱 Telegram: /hvirtka або /vorota"
    echo -e "   📞 IVR: зателефонуйте на головний номер"
    echo -e "   📋 Логи: tail -f bot.log"
else
    echo -e "${RED}❌ ШВИДКЕ РОЗГОРТАННЯ НЕ ВДАЛОСЯ!${NC}"
    echo -e "${YELLOW}   Exit code: $UPDATE_EXIT_CODE${NC}"
    echo ""
    echo -e "${BLUE}🔍 ДІАГНОСТИКА:${NC}"
    echo -e "   📋 Перевірте логи вище"
    echo -e "   🔧 Можливо потрібне ручне втручання"
    echo -e "   📞 Або запустіть update.sh окремо"
fi

echo ""
echo -e "${BLUE}📁 Поточна директорія: $(pwd)${NC}"
echo -e "${BLUE}🤖 Bot PID: $(pgrep -f "python3.*bot.py" || echo "не знайдено")${NC}"
