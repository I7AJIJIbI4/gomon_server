#!/bin/bash
# ШВИДКА ПЕРЕВІРКА ВСІХ API

echo "🌐 ПЕРЕВІРКА API СЕРВІСІВ $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================="

cd /home/gomoncli/zadarma

if [ -f "api_monitor.py" ]; then
    python3 api_monitor.py
else
    echo "❌ api_monitor.py не знайдено"
    exit 1
fi
