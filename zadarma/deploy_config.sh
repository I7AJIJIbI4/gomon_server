#!/bin/bash

echo "📋 ПЕРЕНОС config.py НА СЕРВЕР"
echo "==============================="

# Кольори
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SERVER_HOST="gomoncli@ваш-сервер.com"
PROJECT_DIR="/home/gomoncli/zadarma"

echo -e "${YELLOW}🚀 Копіювання config.py на сервер...${NC}"

# Перевірити чи існує config.py локально
if [ ! -f "config.py" ]; then
    echo "❌ config.py не знайдено локально!"
    echo "Створіть config.py з реальними даними:"
    echo "cp config.py.example config.py"
    echo "# Відредагуйте з вашими API ключами"
    exit 1
fi

echo -e "${BLUE}📤 Копіювання config.py через SCP...${NC}"

# Копіювання файлу на сервер
scp config.py "$SERVER_HOST:$PROJECT_DIR/"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ config.py успішно скопійовано!${NC}"
    
    echo -e "${YELLOW}🔄 Перезапуск бота на сервері...${NC}"
    
    # Перезапуск бота на сервері
    ssh "$SERVER_HOST" << 'EOF'
cd /home/gomoncli/zadarma

# Зупинити бота
pkill -f "python3.*bot.py"

# Перевірити конфігурацію
python3 -c "from config import validate_config; validate_config()"

if [ $? -eq 0 ]; then
    echo "✅ Конфігурація валідна"
    
    # Запустити бота
    nohup python3 bot.py > bot.log 2>&1 &
    
    sleep 3
    
    # Перевірити статус
    if pgrep -f "python3.*bot.py" > /dev/null; then
        echo "✅ Бот успішно запущений!"
        echo "PID: $(pgrep -f 'python3.*bot.py')"
    else
        echo "❌ Помилка запуску бота"
        tail -10 bot.log
    fi
else
    echo "❌ Помилка в конфігурації!"
fi
EOF

else
    echo "❌ Помилка копіювання config.py"
    echo "Перевірте SSH доступ до сервера"
fi

echo ""
echo -e "${BLUE}🔍 Для перевірки на сервері:${NC}"
echo "ssh $SERVER_HOST"
echo "cd $PROJECT_DIR"
echo "ps aux | grep bot.py"
echo "tail -f bot.log"
