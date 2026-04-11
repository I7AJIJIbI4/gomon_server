#!/bin/bash
# Watchdog for TG Business Bot Listener
PIDFILE="/home/gomoncli/zadarma/tg_business.pid"
SCRIPT="/home/gomoncli/zadarma/tg_business_listener.py"
LOGFILE="/home/gomoncli/zadarma/tg_business.log"

if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        exit 0
    fi
    rm -f "$PIDFILE"
fi

cd /home/gomoncli/zadarma
nohup python3 "$SCRIPT" >> /dev/null 2>&1 &
echo $! > "$PIDFILE"
echo "$(date) Started tg_business_listener PID $!" >> "$LOGFILE"
