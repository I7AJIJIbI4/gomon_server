#!/bin/bash
# Скрипт синхронізації з Telegram повідомленням

LOG_FILE="/var/log/gomon/sync.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$DATE] 🔄 Запуск синхронізації з повідомленням..." >> $LOG_FILE

cd /opt/gomon/app/zadarma/

/opt/gomon/venv/bin/python3 -c "
import sys
sys.path.append('/opt/gomon/app/zadarma')

from sync_clients import sync_clients
from config import TELEGRAM_TOKEN, ADMIN_USER_ID
import requests
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    data = {
        'chat_id': ADMIN_USER_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            logger.info('📱 Telegram повідомлення відправлено')
            return True
        else:
            logger.error(f'❌ Помилка Telegram API: {response.status_code}')
            return False
    except Exception as e:
        logger.error(f'❌ Помилка відправки Telegram: {e}')
        return False

try:
    logger.info('🔄 Запуск синхронізації клієнтів...')
    
    result = sync_clients()
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    status = result.get('status', 'error')
    count = result.get('count', 0)
    clients = result.get('clients', [])
    errors = result.get('errors', [])

    if status == 'ok':
        if count > 0:
            clients_text = ''
            for name in clients[:10]:
                clients_text += f'\n👤 {name}'
            if len(clients) > 10:
                clients_text += f'\n... та ще {len(clients) - 10}'
            message = f'''📊 <b>ЗВІТ СИНХРОНІЗАЦІЇ КЛІЄНТІВ</b>

🕐 Час: {now}
✅ Статус: Завершено успішно
🔄 Тип: Автоматичне оновлення
📥 Нових клієнтів: {count}
<b>Клієнти:</b>{clients_text}'''
        else:
            message = f'''📊 <b>ЗВІТ СИНХРОНІЗАЦІЇ КЛІЄНТІВ</b>

🕐 Час: {now}
✅ Статус: Завершено успішно
🔄 Тип: Автоматичне оновлення
ℹ️ Нових клієнтів за добу немає'''

    elif status == 'warning':
        errors_text = ''
        for err in errors[:5]:
            errors_text += f'\n⚠️ {err}'
        clients_text = ''
        if count > 0:
            for name in clients[:5]:
                clients_text += f'\n👤 {name}'
            if len(clients) > 5:
                clients_text += f'\n... та ще {len(clients) - 5}'
        message = f'''📊 <b>ЗВІТ СИНХРОНІЗАЦІЇ КЛІЄНТІВ</b>

🕐 Час: {now}
⚠️ Статус: Завершено з помилками ({len(errors)})
🔄 Тип: Автоматичне оновлення
📥 Оброблено клієнтів: {count}'''
        if clients_text:
            message += f'\n<b>Клієнти:</b>{clients_text}'
        if errors_text:
            message += f'\n\n<b>Помилки:</b>{errors_text}'

    else:
        err_detail = errors[0] if errors else 'невідома помилка'
        message = f'''📊 <b>ПОМИЛКА СИНХРОНІЗАЦІЇ</b>

🕐 Час: {now}
❌ Статус: Помилка
🔧 Деталі: {err_detail}

🛠️ Потрібна перевірка системи'''

    send_telegram_message(message)
    logger.info('✅ Синхронізація та повідомлення завершено')
    
except Exception as e:
    logger.error(f'❌ Помилка синхронізації: {e}')
    
    error_message = f'''📊 <b>ПОМИЛКА СИНХРОНІЗАЦІЇ</b>
    
🕐 Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
❌ Статус: Помилка
🔧 Деталі: {str(e)}

🛠️ Потрібна перевірка системи'''
    
    send_telegram_message(error_message)
" >> $LOG_FILE 2>&1

echo "[$DATE] ✅ Синхронізація завершена" >> $LOG_FILE
