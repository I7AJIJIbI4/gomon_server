#!/bin/bash
# Критичні API з Telegram сповіщеннями

cd /home/gomoncli/zadarma

python3 -c "
import sys
sys.path.append('/home/gomoncli/zadarma')
try:
    from api_monitor import APIMonitor
    
    # Тільки критичні API з увімкненими сповіщеннями
    monitor = APIMonitor(enable_notifications=True)
    monitor.test_zadarma_api()
    monitor.test_telegram_api()
    
    # Обробка сповіщень
    if monitor.notifier:
        notifications = monitor.notifier.process_api_results(monitor.results)
    
    critical_errors = sum(1 for r in monitor.results.values() if r['status'] == 'ERROR')
    exit(critical_errors)
    
except Exception as e:
    print('❌ Помилка critical_api_check:', str(e))
    exit(1)
" 2>/dev/null
