#!/bin/bash
# watchdog_pwa.sh — перевіряє pwa_api через HTTP, перезапускає якщо впав

API_URL="http://127.0.0.1:5001/api/prices"
DIR="/home/gomoncli/zadarma"
SCRIPT="pwa_api.py"
LOG="$DIR/pwa_api.log"
TG_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
TG_CHAT="573368771"

tg_notify() {
    curl -s -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
        -d "chat_id=${TG_CHAT}" \
        -d "text=$1" \
        -d "parse_mode=HTML" > /dev/null 2>&1
}

# Перевірка через HTTP
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API_URL")

if [ "$HTTP_CODE" = "200" ]; then
    exit 0  # все ок
fi

# ── Визначаємо контекст: ребут чи аварія ────────────────────────────────────
UPTIME_SEC=$(awk '{print int($1)}' /proc/uptime)

if [ "$UPTIME_SEC" -lt 180 ]; then
    # ── КЕЙС 1: Плановий ребут (перші 3 хв) ─────────────────────────────────
    # @reboot cron стартує API з sleep 15 — просто ще не встиг підняти сокет
    echo "$(date '+%Y-%m-%d %H:%M:%S') WATCHDOG: ребут (uptime=${UPTIME_SEC}s), чекаємо API..." >> "$LOG"
    sleep 40
    HTTP_CODE2=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API_URL")
    if [ "$HTTP_CODE2" = "200" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') WATCHDOG: API піднявся після ребуту — ок" >> "$LOG"
    else
        # Навіть після ребуту не піднявся — реальна проблема
        tg_notify "🚨 <b>pwa_api не запустився після ребуту сервера!</b>%0AUptime: ${UPTIME_SEC}s — потрібна ручна перевірка."
        echo "$(date '+%Y-%m-%d %H:%M:%S') WATCHDOG: ПОМИЛКА — не запустився після ребуту" >> "$LOG"
    fi
    exit 0
fi

# ── КЕЙС 2: Аварійне падіння під час роботи ─────────────────────────────────
echo "$(date '+%Y-%m-%d %H:%M:%S') WATCHDOG: pwa_api впав (HTTP $HTTP_CODE), перезапуск..." >> "$LOG"

pkill -f "python3 pwa_api.py" 2>/dev/null
sleep 2

cd "$DIR"
nohup /usr/bin/python3 "$SCRIPT" >> "$LOG" 2>&1 &
NEW_PID=$!
sleep 8  # Flask потребує кілька секунд на ініціалізацію

HTTP_CODE3=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API_URL")

if [ "$HTTP_CODE3" = "200" ]; then
    tg_notify "⚠️ <b>pwa_api впав і був автоматично перезапущений</b>%0APID: $NEW_PID"
    echo "$(date '+%Y-%m-%d %H:%M:%S') WATCHDOG: перезапущено після падіння, PID=$NEW_PID" >> "$LOG"
else
    tg_notify "🚨 <b>pwa_api НЕ ЗАПУСТИВСЯ після аварійного падіння!</b>%0AПотрібна ручна перевірка."
    echo "$(date '+%Y-%m-%d %H:%M:%S') WATCHDOG: ПОМИЛКА — не відповідає після перезапуску" >> "$LOG"
fi
