#!/bin/bash
# АРХІВАЦІЯ ЛОГІВ КЛІНІКИ ГОМОНА

LOG_DIR="/home/gomoncli/zadarma"
WEBHOOK_LOG="$LOG_DIR/ivr_webhook.log"
ARCHIVE_DIR="$LOG_DIR/archive"
MONITOR_LOG="$LOG_DIR/monitoring.log"

# Створення директорії архіву
mkdir -p "$ARCHIVE_DIR"

function log_archive() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ARCHIVE: $1" >> "$MONITOR_LOG"
}

function archive_webhook_log() {
    if [ -f "$WEBHOOK_LOG" ]; then
        SIZE_BYTES=$(stat -c%s "$WEBHOOK_LOG")
        SIZE_MB=$((SIZE_BYTES / 1024 / 1024))
        
        log_archive "📊 Поточний розмір webhook.log: ${SIZE_MB}MB"
        
        # Якщо лог більше 50MB - архівуємо
        if [ "$SIZE_BYTES" -gt 52428800 ]; then
            ARCHIVE_NAME="webhook_$(date '+%Y%m%d_%H%M%S').log"
            
            log_archive "📦 Архівація логу: $ARCHIVE_NAME"
            
            # Копіюємо в архів
            cp "$WEBHOOK_LOG" "$ARCHIVE_DIR/$ARCHIVE_NAME"
            
            # Очищуємо основний лог, залишаючи заголовок
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Лог архівовано. Новий лог розпочато." > "$WEBHOOK_LOG"
            
            log_archive "✅ Лог архівовано успішно"
            
            # Стискаємо архів
            gzip "$ARCHIVE_DIR/$ARCHIVE_NAME"
            log_archive "🗜️ Архів стиснуто: ${ARCHIVE_NAME}.gz"
        else
            log_archive "✅ Архівація не потрібна (розмір: ${SIZE_MB}MB)"
        fi
    fi
}

function cleanup_old_archives() {
    log_archive "🧹 Очищення старих архівів (старіше 30 днів)..."
    
    DELETED=$(find "$ARCHIVE_DIR" -name "webhook_*.log.gz" -mtime +30 -delete -print | wc -l)
    
    if [ "$DELETED" -gt 0 ]; then
        log_archive "🗑️ Видалено $DELETED старих архівів"
    else
        log_archive "✅ Старих архівів не знайдено"
    fi
}

# Головна функція архівації
log_archive "🚀 ПОЧАТОК АРХІВАЦІЇ"
archive_webhook_log
cleanup_old_archives
log_archive "✅ АРХІВАЦІЯ ЗАВЕРШЕНА"
