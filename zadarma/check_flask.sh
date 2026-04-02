#!/bin/bash
# check_flask.sh — перевіряє що gunicorn API живий, якщо ні — перезапускає.
# Cron: */5 * * * * (кожні 5 хв) + @reboot
# Gunicorn: 2 workers, timeout 120s, auto-restart workers, preload app

LOGFILE="/home/gomoncli/zadarma/pwa_api.log"
PIDFILE="/home/gomoncli/zadarma/flask.pid"
WORKDIR="/home/gomoncli/zadarma"
TS() { date '+%Y-%m-%d %H:%M:%S'; }

start_flask() {
  cd "$WORKDIR"
  # Вбиваємо все що залишилось на порті
  fuser -k 5001/tcp 2>/dev/null
  sleep 1
  nohup gunicorn \
    --bind 127.0.0.1:5001 \
    --workers 2 \
    --threads 2 \
    --timeout 120 \
    --graceful-timeout 30 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile - \
    --pid "$PIDFILE" \
    pwa_api:app >> "$LOGFILE" 2>&1 &
  sleep 3
  NEW_PID=$(cat "$PIDFILE" 2>/dev/null || pgrep -f "gunicorn.*pwa_api" | head -1)
  echo "$(TS) [watchdog] gunicorn started, PID=$NEW_PID" >> "$LOGFILE"
}

# Перевіряємо HTTP — 2 спроби з інтервалом
HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:5001/api/health 2>/dev/null)
if [ "$HTTP" != "200" ]; then
  sleep 2
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:5001/api/health 2>/dev/null)
fi

if [ "$HTTP" = "200" ]; then
  # Живий — прибираємо старі python3 процеси якщо є
  pkill -f "python3.*pwa_api.py" 2>/dev/null
  exit 0
fi

# Не відповідає — перезапуск
echo "$(TS) [watchdog] gunicorn down (HTTP=$HTTP), restarting..." >> "$LOGFILE"
pkill -9 -f "gunicorn.*pwa_api" 2>/dev/null
pkill -9 -f "python3.*pwa_api" 2>/dev/null
sleep 2
start_flask
