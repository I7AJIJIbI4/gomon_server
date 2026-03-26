#!/bin/bash
# Щоденний звіт API о 19:00

cd /home/gomoncli/zadarma

python3 -c "
from api_monitor import APIMonitor
from telegram_notifier import TelegramNotifier

# Запустити тести без сповіщень про зміни стану
monitor = APIMonitor(enable_notifications=False)
results = monitor.run_all_tests(send_notifications=False)

# Відправити щоденний звіт
notifier = TelegramNotifier()
notifier.send_daily_summary(results)

print('📊 Щоденний звіт відправлено в Telegram')
"
