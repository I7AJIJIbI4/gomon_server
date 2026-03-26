#!/usr/bin/env python3
import sys
import json
import sqlite3
import time
import requests
import logging

# Налаштування логування
logging.basicConfig(
    filename='/home/gomoncli/zadarma/webhook_processor.log',
    level=logging.INFO,
    format='%(asctime)s - webhook_processor - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("🔔 Webhook викликано")
    
    if len(sys.argv) < 2:
        logger.error("❌ Немає даних webhook")
        return
    
    try:
        data = json.loads(sys.argv[1])
        event = data.get('event', '')
        caller_id = data.get('caller_id', '')
        disposition = data.get('disposition', '')
        
        logger.info(f"📞 Обробка {event}: {caller_id} -> {disposition}")
        
        # Тут ваш існуючий код з simple_webhook.py
        # Але з додаванням логування для ключових моментів
        
        logger.info("✅ Webhook оброблено успішно")
        
    except Exception as e:
        logger.error(f"❌ Помилка webhook: {e}")

if __name__ == "__main__":
    main()
