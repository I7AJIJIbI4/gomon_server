#!/bin/bash
# check_flask.sh — перевіряє що Flask API живий, якщо ні — перезапускає

LOGFILE="/home/gomoncli/zadarma/pwa_api.log"
PIDFILE="/home/gomoncli/zadarma/flask.pid"

start_flask() {
  cd /home/gomoncli/zadarma
  nohup /usr/bin/python3.6 pwa_api.py >> "$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
  echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] Flask запущено, PID=$!" >> "$LOGFILE"
}

# Перевіряємо HTTP
HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:5001/api/health)

if [ "$HTTP" = "200" ]; then
  exit 0
fi

# Не відповідає — вбиваємо старий процес (якщо є) і перезапускаємо
echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] Flask не відповідає (HTTP=$HTTP), перезапуск..." >> "$LOGFILE"

if [ -f "$PIDFILE" ]; then
  OLD_PID=$(cat "$PIDFILE")
  kill "$OLD_PID" 2>/dev/null
fi

# Також kill будь-який процес на порту 5001
pkill -f "pwa_api.py" 2>/dev/null
sleep 2

start_flask
