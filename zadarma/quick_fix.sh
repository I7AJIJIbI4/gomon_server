#!/bin/bash
# quick_fix.sh - Швидке виправлення проблем після деплою

echo "⚡ ШВИДКЕ ВИПРАВЛЕННЯ ПРОБЛЕМ"
echo "============================"

# Перехід до правильної директорії
cd /home/gomoncli/zadarma || exit 1

# 1. Виправляємо requirements.txt
echo "🔧 Виправляємо requirements.txt..."
sed -i 's/python-telegram-bot==13.15/python-telegram-bot==13.12/g' requirements.txt 2>/dev/null || true

# 2. Встановлюємо правильну версію
echo "📦 Встановлюємо python-telegram-bot==13.12..."
pip3 install --upgrade python-telegram-bot==13.12 --quiet

# 3. Оновлюємо код з GitHub
echo "📥 Оновлюємо код з GitHub..."
git stash push -m "Quick fix stash" 2>/dev/null
git pull origin main --quiet
git stash pop 2>/dev/null || true

# 4. Налаштовуємо права
echo "🔐 Налаштовуємо права..."
chmod +x *.py *.sh 2>/dev/null

# 5. Перезапускаємо бота
echo "🔄 Перезапускаємо бота..."
pkill -f "python3.*bot.py" 2>/dev/null
sleep 2
python3 bot.py &

# 6. Перевіряємо статус
sleep 3
if pgrep -f "python3.*bot.py" > /dev/null; then
    BOT_PID=$(pgrep -f "python3.*bot.py")
    echo "✅ Бот перезапущено успішно (PID: $BOT_PID)"
else
    echo "❌ Бот не запущено"
fi

# 7. Швидкий тест
echo "🧪 Швидкий тест..."
if [ -f "process_webhook.py" ]; then
    echo "✅ process_webhook.py знайдено"
else
    echo "⚠️  process_webhook.py відсутній"
fi

if [ -f "sync_management.py" ]; then
    echo "✅ sync_management.py знайдено"
else
    echo "⚠️  sync_management.py відсутній"
fi

echo ""
echo "🎯 РЕКОМЕНДАЦІЇ:"
echo "1. Протестуйте: /sync_status в Telegram"
echo "2. Перевірте: /hvirtka та /vorota"
echo "3. Моніторьте: tail -f bot.log"
echo ""
echo "✅ Швидке виправлення завершено!"
