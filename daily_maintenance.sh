#!/bin/bash
# ВИПРАВЛЕНЕ ЩОДЕННЕ ОБСЛУГОВУВАННЯ

echo "🚀 ПОЧАТОК ЩОДЕННОГО ОБСЛУГОВУВАННЯ"
echo "🕐 $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================="

# 1. Моніторинг системи
echo "1️⃣ Запуск моніторингу..."
~/monitoring_system.sh

# 2. Архівація логів
echo "2️⃣ Архівація логів..."
~/log_archiver.sh

# 3. Генерація звітів
echo "3️⃣ Генерація звітів..."
~/daily_report.sh

# 4. Перевірка дискового простору
echo "4️⃣ Перевірка дискового простору..."
DISK_USAGE=$(df /home | tail -1 | awk '{print $5}' | sed 's/%//')
echo "💾 Використання диску: ${DISK_USAGE}%"

if [ "$DISK_USAGE" -gt 80 ]; then
    echo "⚠️ УВАГА: Диск заповнений більше ніж на 80%"
else
    echo "✅ Дисковий простір в нормі"
fi

# 5. Перевірка пакетного менеджера
echo "5️⃣ Перевірка системи..."
if command -v dnf >/dev/null 2>&1; then
    UPDATES=$(dnf check-update -q | grep -v "^$" | wc -l 2>/dev/null)
    echo "📦 Доступно оновлень (dnf): $UPDATES"
elif command -v yum >/dev/null 2>&1; then
    UPDATES=$(yum check-update --quiet | wc -l 2>/dev/null)
    echo "📦 Доступно оновлень (yum): $UPDATES"
elif command -v apt >/dev/null 2>&1; then
    UPDATES=$(apt list --upgradable 2>/dev/null | grep -v "^Listing" | wc -l)
    echo "📦 Доступно оновлень (apt): $UPDATES"
else
    echo "📦 Пакетний менеджер не визначено"
fi

# 6. Перевірка webhook
echo "6️⃣ Швидка перевірка webhook..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://gomonclinic.com/zadarma_ivr_webhook.php 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Webhook доступний"
else
    echo "❌ Webhook недоступний (HTTP: $HTTP_CODE)"
fi

echo "=================================="
echo "✅ ЩОДЕННЕ ОБСЛУГОВУВАННЯ ЗАВЕРШЕНО"
echo "🕐 $(date '+%Y-%m-%d %H:%M:%S')"
