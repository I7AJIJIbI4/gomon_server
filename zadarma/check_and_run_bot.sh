#!/bin/bash
# ============================================================================
# ZADARMA BOT - Покращений скрипт запуску та моніторингу
# ============================================================================

# === КОНФІГУРАЦІЯ ===
LOCKFILE="/tmp/zadarma_bot.lock"
BOT_DIR="/home/gomoncli/zadarma"
BOT_SCRIPT="bot.py"
PIDFILE="$BOT_DIR/bot.pid"
LOGFILE="$BOT_DIR/bot_cron.log"
BOT_LOGFILE="$BOT_DIR/bot.log"
PYTHON_EXEC="/usr/bin/python3"
MAX_WAIT_TIME=10
RESTART_COOLDOWN=30

# === КОЛЬОРИ ДЛЯ ВИВОДУ ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# === ФУНКЦІЇ ЛОГУВАННЯ ===
log_message() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $message" >> "$LOGFILE"
    if [[ -t 1 ]]; then
        echo -e "${BLUE}[$timestamp]${NC} $message"
    fi
}

log_error() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] ERROR: $message" >> "$LOGFILE"
    if [[ -t 1 ]]; then
        echo -e "${RED}[$timestamp] ERROR:${NC} $message" >&2
    fi
}

log_success() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] SUCCESS: $message" >> "$LOGFILE"
    if [[ -t 1 ]]; then
        echo -e "${GREEN}[$timestamp] SUCCESS:${NC} $message"
    fi
}

log_warning() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] WARNING: $message" >> "$LOGFILE"
    if [[ -t 1 ]]; then
        echo -e "${YELLOW}[$timestamp] WARNING:${NC} $message"
    fi
}

# === ФУНКЦІЯ ПЕРЕВІРКИ ЗАЛЕЖНОСТЕЙ ===
check_dependencies() {
    local missing_deps=()
    
    # Перевірка Python
    if ! command -v "$PYTHON_EXEC" &> /dev/null; then
        missing_deps+=("python3")
    fi
    
    # Перевірка flock
    if ! command -v flock &> /dev/null; then
        missing_deps+=("util-linux (flock)")
    fi
    
    # Перевірка основних файлів
    if [[ ! -f "$BOT_DIR/$BOT_SCRIPT" ]]; then
        missing_deps+=("$BOT_SCRIPT")
    fi
    
    if [[ ! -f "$BOT_DIR/config.py" ]]; then
        missing_deps+=("config.py")
    fi
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Відсутні залежності: ${missing_deps[*]}"
        return 1
    fi
    
    return 0
}

# === ФУНКЦІЯ ОЧИЩЕННЯ РЕСУРСІВ ===
cleanup() {
    if [[ -n "$LOCK_FD" ]]; then
        exec {LOCK_FD}>&-
    fi
}

trap cleanup EXIT

# === БЛОКУВАННЯ ОДНОЧАСНОГО ЗАПУСКУ ===
acquire_lock() {
    exec {LOCK_FD}>"$LOCKFILE"
    if ! flock -n $LOCK_FD; then
        log_warning "Скрипт вже запущений (файл блокування: $LOCKFILE)"
        exit 1
    fi
    echo $$ > "$LOCKFILE"
}

# === ФУНКЦІЯ ПЕРЕВІРКИ СТАТУСУ ПРОЦЕСУ ===
is_process_running() {
    local pid="$1"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

is_bot_process() {
    local pid="$1"
    [[ -n "$pid" ]] && ps -p "$pid" -o cmd= 2>/dev/null | grep -q "$BOT_SCRIPT"
}

# === ФУНКЦІЯ ПОШУКУ АКТИВНИХ ПРОЦЕСІВ БОТА ===
find_bot_processes() {
    pgrep -f "python.*$BOT_SCRIPT" 2>/dev/null
}

# === ФУНКЦІЯ ЗУПИНКИ ПРОЦЕСУ ===
stop_process() {
    local pid="$1"
    local timeout="${2:-10}"
    
    if ! is_process_running "$pid"; then
        return 0
    fi
    
    log_message "Зупиняю процес $pid..."
    
    # Спробувати SIGTERM
    kill "$pid" 2>/dev/null
    
    # Чекати завершення
    local count=0
    while [[ $count -lt $timeout ]] && is_process_running "$pid"; do
        sleep 1
        ((count++))
    done
    
    # Якщо не завершився, використати SIGKILL
    if is_process_running "$pid"; then
        log_warning "Процес $pid не відповідає на SIGTERM, використовую SIGKILL"
        kill -9 "$pid" 2>/dev/null
        sleep 1
    fi
    
    if is_process_running "$pid"; then
        log_error "Не вдалося зупинити процес $pid"
        return 1
    fi
    
    log_success "Процес $pid успішно зупинено"
    return 0
}

# === ФУНКЦІЯ ОЧИЩЕННЯ PID ФАЙЛУ ===
cleanup_pidfile() {
    if [[ -f "$PIDFILE" ]]; then
        local stored_pid=$(cat "$PIDFILE" 2>/dev/null)
        if [[ -n "$stored_pid" ]]; then
            if ! is_process_running "$stored_pid" || ! is_bot_process "$stored_pid"; then
                log_message "Видаляю застарілий PID файл (PID: $stored_pid)"
                rm -f "$PIDFILE"
            fi
        else
            log_message "Видаляю порожній PID файл"
            rm -f "$PIDFILE"
        fi
    fi
}

# === ФУНКЦІЯ ПЕРЕВІРКИ РОБОТИ БОТА ===
check_bot_status() {
    cleanup_pidfile
    
    # Перевірка через PID файл
    if [[ -f "$PIDFILE" ]]; then
        local stored_pid=$(cat "$PIDFILE" 2>/dev/null)
        if [[ -n "$stored_pid" ]] && is_process_running "$stored_pid" && is_bot_process "$stored_pid"; then
            log_success "Бот працює (PID: $stored_pid)"
            return 0
        fi
    fi
    
    # Додаткова перевірка через pgrep
    local running_pids=($(find_bot_processes))
    if [[ ${#running_pids[@]} -gt 0 ]]; then
        local main_pid="${running_pids[0]}"
        log_message "Знайдено активний процес бота (PID: $main_pid), оновлюю PID файл"
        echo "$main_pid" > "$PIDFILE"
        
        # Якщо знайдено кілька процесів, зупинити зайві
        if [[ ${#running_pids[@]} -gt 1 ]]; then
            log_warning "Знайдено ${#running_pids[@]} процесів бота, зупиняю зайві"
            for pid in "${running_pids[@]:1}"; do
                stop_process "$pid"
            done
        fi
        
        return 0
    fi
    
    return 1
}

# === ФУНКЦІЯ ЗАПУСКУ БОТА ===
start_bot() {
    log_message "Запускаю бота в $BOT_DIR..."
    
    # Перехід в робочу директорію
    if ! cd "$BOT_DIR"; then
        log_error "Не вдалося перейти в директорію $BOT_DIR"
        return 1
    fi
    
    # Перевірка Python скрипта
    if ! "$PYTHON_EXEC" -m py_compile "$BOT_SCRIPT"; then
        log_error "Синтаксична помилка в $BOT_SCRIPT"
        return 1
    fi
    
    # Запуск бота
    "$PYTHON_EXEC" "$BOT_SCRIPT" >> "$BOT_LOGFILE" 2>&1 &
    local bot_pid=$!
    
    # Збереження PID
    echo "$bot_pid" > "$PIDFILE"
    log_message "Бот запущено з PID: $bot_pid"
    
    # Перевірка успішного запуску
    local wait_count=0
    while [[ $wait_count -lt $MAX_WAIT_TIME ]]; do
        if is_process_running "$bot_pid" && is_bot_process "$bot_pid"; then
            log_success "Бот успішно запущений та працює (PID: $bot_pid)"
            
            # Додаткова перевірка логу на помилки
            if [[ -f "$BOT_LOGFILE" ]]; then
                local recent_errors=$(tail -20 "$BOT_LOGFILE" | grep -i "error\|exception\|traceback" | wc -l)
                if [[ $recent_errors -gt 0 ]]; then
                    log_warning "Виявлено $recent_errors помилок в останніх логах"
                fi
            fi
            
            return 0
        fi
        
        sleep 1
        ((wait_count++))
    done
    
    log_error "Бот не запустився протягом $MAX_WAIT_TIME секунд"
    rm -f "$PIDFILE"
    
    # Показати останні рядки логу для діагностики
    if [[ -f "$BOT_LOGFILE" ]]; then
        log_error "Останні записи логу:"
        tail -5 "$BOT_LOGFILE" | while read -r line; do
            log_error "  $line"
        done
    fi
    
    return 1
}

# === ФУНКЦІЯ ПЕРЕЗАПУСКУ БОТА ===
restart_bot() {
    log_message "Перезапуск бота..."
    
    # Знайти та зупинити всі процеси бота
    local running_pids=($(find_bot_processes))
    for pid in "${running_pids[@]}"; do
        stop_process "$pid"
    done
    
    # Очистити PID файл
    rm -f "$PIDFILE"
    
    # Невелика пауза перед запуском
    sleep 2
    
    # Запустити бота
    start_bot
}

# === ФУНКЦІЯ ПОКАЗУ СТАТУСУ ===
show_status() {
    echo "=== СТАТУС ZADARMA BOT ==="
    echo "Робоча директорія: $BOT_DIR"
    echo "Python скрипт: $BOT_SCRIPT"
    echo "PID файл: $PIDFILE"
    echo "Лог файл: $LOGFILE"
    echo "Лог бота: $BOT_LOGFILE"
    echo ""
    
    if check_bot_status; then
        local stored_pid=$(cat "$PIDFILE" 2>/dev/null)
        echo -e "${GREEN}✅ Бот працює (PID: $stored_pid)${NC}"
        
        # Показати інформацію про процес
        if [[ -n "$stored_pid" ]]; then
            echo "Інформація про процес:"
            ps -p "$stored_pid" -o pid,ppid,start,etime,cmd 2>/dev/null || echo "Не вдалося отримати інформацію про процес"
        fi
    else
        echo -e "${RED}❌ Бот не працює${NC}"
    fi
    
    # Показати останні записи логу
    if [[ -f "$LOGFILE" ]]; then
        echo ""
        echo "Останні записи логу:"
        tail -5 "$LOGFILE"
    fi
}

# === ФУНКЦІЯ ПОКАЗУ ДОПОМОГИ ===
show_help() {
    cat << EOF
Використання: $0 [КОМАНДА]

КОМАНДИ:
    start       Запустити бота (якщо не працює)
    stop        Зупинити бота
    restart     Перезапустити бота
    status      Показати статус бота
    check       Перевірити та запустити бота при необхідності (за замовчуванням)
    help        Показати цю довідку

ПРИКЛАДИ:
    $0              # Перевірити та запустити бота
    $0 start        # Запустити бота
    $0 restart      # Перезапустити бота
    $0 status       # Показати статус

ФАЙЛИ:
    $PIDFILE      # PID файл
    $LOGFILE      # Лог скрипта
    $BOT_LOGFILE     # Лог бота
EOF
}

# === ГОЛОВНА ФУНКЦІЯ ===
main() {
    local command="${1:-check}"
    
    # Перевірка залежностей
    if ! check_dependencies; then
        exit 1
    fi
    
    # Створення директорій та файлів
    mkdir -p "$(dirname "$LOGFILE")"
    touch "$LOGFILE"
    
    case "$command" in
        "start")
            acquire_lock
            if check_bot_status; then
                log_message "Бот вже працює"
                exit 0
            else
                if start_bot; then
                    exit 0
                else
                    exit 1
                fi
            fi
            ;;
        "stop")
            acquire_lock
            local running_pids=($(find_bot_processes))
            if [[ ${#running_pids[@]} -eq 0 ]]; then
                log_message "Бот не працює"
                rm -f "$PIDFILE"
                exit 0
            fi
            
            for pid in "${running_pids[@]}"; do
                stop_process "$pid"
            done
            rm -f "$PIDFILE"
            log_success "Бот зупинено"
            ;;
        "restart")
            acquire_lock
            restart_bot
            ;;
        "status")
            show_status
            ;;
        "check")
            acquire_lock
            if ! check_bot_status; then
                log_message "Бот не працює, запускаю..."
                if start_bot; then
                    exit 0
                else
                    exit 1
                fi
            fi
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            echo "Невідома команда: $command"
            echo "Використайте '$0 help' для довідки"
            exit 1
            ;;
    esac
}

# === ЗАПУСК СКРИПТА ===
main "$@"