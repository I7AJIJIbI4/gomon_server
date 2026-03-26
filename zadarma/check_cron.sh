LOCKFILE=/tmp/zadarma_bot.lock
BOT_DIR="/home/gomoncli/zadarma"
BOT_SCRIPT="bot.py"
PIDFILE="$BOT_DIR/bot.pid"
LOGFILE="$BOT_DIR/bot_cron.log"
PYTHON_EXEC="/usr/bin/python3"

# Функція логування
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') — $1" >> "$LOGFILE"
}

# === Блокування через flock ===
exec 200>"$LOCKFILE"
flock -n 200 || {
    log_message "Скрипт вже запущений (lock)"
    exit 1
}

# === Перевірка PID файлу ===
if [ -f "$PIDFILE" ]; then
    BOT_PID=$(cat "$PIDFILE")
    
    # Перевіряємо чи існує процес з таким PID
    if kill -0 "$BOT_PID" 2>/dev/null; then
        # Перевіряємо чи це справді наш бот
        if ps -p "$BOT_PID" -o cmd= | grep -q "$BOT_SCRIPT"; then
            log_message "Бот працює (PID: $BOT_PID)"
            exit 0
        else
            log_message "PID $BOT_PID не відповідає боту, видаляємо PID файл"
            rm -f "$PIDFILE"
        fi
    else
        log_message "Процес з PID $BOT_PID не існує, видаляємо PID файл"
        rm -f "$PIDFILE"
    fi
fi

# === Додаткова перевірка через pgrep ===
EXISTING_PID=$(pgrep -f "python.*$BOT_SCRIPT")
if [ -n "$EXISTING_PID" ]; then
    log_message "Знайдено працюючий бот (PID: $EXISTING_PID), оновлюємо PID файл"
    echo "$EXISTING_PID" > "$PIDFILE"
    exit 0
fi

# === Запуск бота ===
log_message "Запускаю бота..."
cd "$BOT_DIR"

# Запускаємо бота і записуємо PID
$PYTHON_EXEC "$BOT_SCRIPT" >> "$BOT_DIR/bot.log" 2>&1 &
BOT_PID=$!

# Записуємо PID у файл
echo "$BOT_PID" > "$PIDFILE"
log_message "Бот запущено з PID: $BOT_PID"

# Перевіряємо що бот справді запустився
sleep 3
if kill -0 "$BOT_PID" 2>/dev/null; then
    log_message "Бот успішно запущений та працює"
else
    log_message "Помилка: бот не запустився"
    rm -f "$PIDFILE"
    exit 1
fi
EOF