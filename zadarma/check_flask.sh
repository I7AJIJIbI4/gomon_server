#!/bin/bash
# check_flask.sh — перевіряє що Flask API живий, якщо ні — перезапускає.
# Також прибирає дублікати процесів pwa_api.py якщо їх більше одного.

LOGFILE="/home/gomoncli/zadarma/pwa_api.log"
PIDFILE="/home/gomoncli/zadarma/flask.pid"
TS() { date '+%Y-%m-%d %H:%M:%S'; }

start_flask() {
  cd /home/gomoncli/zadarma
  nohup /usr/bin/python3.6 pwa_api.py >> "$LOGFILE" 2>&1 &
  NEW_PID=$!
  echo $NEW_PID > "$PIDFILE"
  echo "$(TS) [watchdog] Flask запущено, PID=$NEW_PID" >> "$LOGFILE"
}

kill_duplicates() {
  # Залишаємо тільки найновіший PID (найбільший номер = запущений пізніше)
  NEWEST=$(pgrep -f "pwa_api.py" | sort -n | tail -1)
  pgrep -f "pwa_api.py" | sort -n | grep -v "^${NEWEST}$" | while read OLD; do
    echo "$(TS) [watchdog] Вбиваємо зайвий процес PID=$OLD" >> "$LOGFILE"
    kill "$OLD" 2>/dev/null
  done
  echo $NEWEST > "$PIDFILE"
}

# Перевіряємо HTTP
HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:5001/api/health)

if [ "$HTTP" = "200" ]; then
  # Живий — перевіряємо дублікати
  COUNT=$(pgrep -c -f "pwa_api.py" 2>/dev/null || echo 0)
  if [ "$COUNT" -gt 1 ]; then
    echo "$(TS) [watchdog] Знайдено $COUNT процесів pwa_api, прибираємо дублікати" >> "$LOGFILE"
    kill_duplicates
  fi
  exit 0
fi

# Не відповідає — вбиваємо всі та перезапускаємо
echo "$(TS) [watchdog] Flask не відповідає (HTTP=$HTTP), перезапуск..." >> "$LOGFILE"

pkill -f "pwa_api.py" 2>/dev/null
sleep 2

start_flask
