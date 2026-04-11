#!/bin/bash
# check_flask.sh — перевіряє що gunicorn API живий, якщо ні — перезапускає.
# Додатково: якщо pwa_api.py змінився — graceful reload (HUP).
# Якщо рестарт не допоміг — шле TG алерт адміну.
# Cron: */2 * * * * (кожні 2 хвилини)

LOGFILE="/home/gomoncli/zadarma/pwa_api.log"
PIDFILE="/home/gomoncli/zadarma/flask.pid"
WORKDIR="/home/gomoncli/zadarma"
GUNICORN="/home/gomoncli/.local/bin/gunicorn"
RELOAD_STAMP="/home/gomoncli/zadarma/.gunicorn_reload_stamp"
TS() { date '+%Y-%m-%d %H:%M:%S'; }

# TG алерт
send_alert() {
  local msg="$1"
  cd "$WORKDIR"
  python3 -c "
import requests
from config import TELEGRAM_TOKEN, ADMIN_USER_ID
requests.post('https://api.telegram.org/bot{}/sendMessage'.format(TELEGRAM_TOKEN),
  json={'chat_id': ADMIN_USER_ID, 'text': msg}, timeout=10)
" 2>/dev/null
}

start_flask() {
  cd "$WORKDIR"
  fuser -k 5001/tcp 2>/dev/null
  sleep 1
  nohup "$GUNICORN" \
    --bind 127.0.0.1:5001 \
    --workers 2 \
    --threads 2 \
    --timeout 120 \
    --graceful-timeout 30 \
    --max-requests 5000 \
    --max-requests-jitter 500 \
    --access-logfile - \
    --error-logfile - \
    --pid "$PIDFILE" \
    pwa_api:app >> "$LOGFILE" 2>&1 &
  sleep 3
  NEW_PID=$(cat "$PIDFILE" 2>/dev/null || pgrep -f "gunicorn.*pwa_api" | head -1)
  echo "$(TS) [watchdog] gunicorn started, PID=$NEW_PID" >> "$LOGFILE"
  # Оновлюємо stamp щоб не рілоадити одразу після старту
  touch "$RELOAD_STAMP"
}

# --- 1. HTTP health check (2 спроби) ---
HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:5001/api/health 2>/dev/null)
if [ "$HTTP" != "200" ]; then
  sleep 2
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:5001/api/health 2>/dev/null)
fi

if [ "$HTTP" = "200" ]; then
  # Живий — прибираємо застарілі python3 процеси
  pkill -f "python3.*pwa_api.py" 2>/dev/null

  # --- 2. Code change detection: graceful reload ---
  MASTER_PID=$(cat "$PIDFILE" 2>/dev/null)
  if [ -n "$MASTER_PID" ] && kill -0 "$MASTER_PID" 2>/dev/null; then
    # Порівнюємо mtime pwa_api.py з reload stamp
    if [ ! -f "$RELOAD_STAMP" ]; then
      touch "$RELOAD_STAMP"
    fi
    if [ "$WORKDIR/pwa_api.py" -nt "$RELOAD_STAMP" ]; then
      echo "$(TS) [watchdog] pwa_api.py changed — sending HUP to gunicorn (PID=$MASTER_PID)" >> "$LOGFILE"
      kill -HUP "$MASTER_PID"
      touch "$RELOAD_STAMP"
      sleep 3
      # Перевіряємо що рілоад пройшов
      RCHECK=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:5001/api/health 2>/dev/null)
      if [ "$RCHECK" = "200" ]; then
        echo "$(TS) [watchdog] graceful reload OK" >> "$LOGFILE"
      else
        echo "$(TS) [watchdog] graceful reload FAILED (HTTP=$RCHECK), full restart..." >> "$LOGFILE"
        pkill -9 -f "gunicorn.*pwa_api" 2>/dev/null
        sleep 2
        start_flask
      fi
    fi
  fi
  exit 0
fi

# --- 3. Не відповідає — повний перезапуск ---
echo "$(TS) [watchdog] gunicorn down (HTTP=$HTTP), restarting..." >> "$LOGFILE"
pkill -9 -f "gunicorn.*pwa_api" 2>/dev/null
pkill -9 -f "python3.*pwa_api" 2>/dev/null
sleep 2
start_flask

# Перевіряємо чи рестарт допоміг
sleep 5
CHECK=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:5001/api/health 2>/dev/null)
if [ "$CHECK" != "200" ]; then
  echo "$(TS) [watchdog] RESTART FAILED! HTTP=$CHECK after restart" >> "$LOGFILE"
  send_alert "⚠️ API не піднявся після рестарту (HTTP=$CHECK). Потрібна ручна перевірка."
fi
