#!/usr/bin/env python3
# Покращений простий webhook процесор з логуванням
import sys
import json
import sqlite3
import time
import requests
import logging

# Налаштування webhook логування
logging.basicConfig(
    filename='/home/gomoncli/zadarma/webhook_processor.log',
    level=logging.INFO,
    format='%(asctime)s - webhook_processor - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def send_telegram(chat_id, message):
    """Відправляє повідомлення в Telegram через бот API"""
    logger.info(f"📤 Відправка Telegram повідомлення в чат {chat_id}")
    try:
        # Читаємо токен з config
        with open('config.py', 'r') as f:
            config_content = f.read()
        
        # Знаходимо TELEGRAM_TOKEN
        import re
        token_match = re.search(r'TELEGRAM_TOKEN\s*=\s*[\'"]([^\'"]+)[\'"]', config_content)
        if not token_match:
            logger.error("❌ Cannot find TELEGRAM_TOKEN in config.py")
            return False
            
        token = token_match.group(1)
        
        # Telegram API URL
        url = "https://api.telegram.org/bot{}/sendMessage".format(token)
        data = {
            "chat_id": chat_id, 
            "text": message, 
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, data=data, timeout=10)
        success = response.status_code == 200
        if success:
            logger.info("✅ Telegram повідомлення відправлено")
        else:
            logger.error(f"❌ Помилка Telegram API: {response.status_code}")
        return success
        
    except Exception as e:
        logger.error(f"❌ Telegram error: {e}")
        return False

def find_call_in_db(target_number, time_window=600):
    """Знаходить дзвінок в базі даних з покращеним пошуком"""
    logger.info(f"🔍 Пошук дзвінка для номеру {target_number}")
    try:
        conn = sqlite3.connect('call_tracking.db')
        cursor = conn.cursor()
        
        current_time = int(time.time())
        time_start = current_time - time_window
        
        # Спочатку точний пошук
        cursor.execute('''
            SELECT call_id, user_id, chat_id, action_type, target_number, start_time, status
            FROM call_tracking 
            WHERE target_number = ? AND start_time > ? AND status IN ('api_success', 'no_answer')
            ORDER BY start_time DESC LIMIT 1
        ''', (target_number, time_start))
        
        result = cursor.fetchone()
        
        if result:
            logger.info(f"✅ Знайдено дзвінок: {result[0]}")
        else:
            logger.info(f"❌ Дзвінок для {target_number} не знайдено")
        
        conn.close()
        
        if result:
            return {
                'call_id': result[0],
                'user_id': result[1],
                'chat_id': result[2], 
                'action_type': result[3],
                'target_number': result[4],
                'start_time': result[5],
                'status': result[6]
            }
        return None
        
    except Exception as e:
        logger.error(f"❌ DB error: {e}")
        return None

def main():
    logger.info("🔔 Webhook викликано")
    
    if len(sys.argv) < 2:
        logger.error("❌ Немає webhook даних")
        return
    
    try:
        # Парсимо JSON дані
        data = json.loads(sys.argv[1])
        logger.info(f"📥 Отримано: {data}")
        
        # Витягуємо основні параметри
        event = data.get('event', '')
        caller_id = data.get('caller_id', '')
        called_did = data.get('called_did', '') 
        disposition = data.get('disposition', '')
        duration = int(data.get('duration', 0))
        
        logger.info(f"📞 Event: {event}, From: {caller_id}, To: {called_did}, Status: {disposition}, Duration: {duration}")
        
        # Обробляємо тільки завершення дзвінків
        if event == 'NOTIFY_END':
            # Визначення типу дзвінка
            target_number = None
            action_name = None
            
            # Перевіряємо чи це callback від бота
            clinic_numbers = ['0733103110', '733103110']
            is_from_clinic = any(clinic_num in called_did for clinic_num in clinic_numbers)
            
            if is_from_clinic:
                logger.info("🤖 Детектовано bot callback")
                
                # Визначаємо пристрій
                if '637442017' in caller_id:
                    target_number = '0637442017'
                    action_name = 'хвіртка'
                elif '930063585' in caller_id:
                    target_number = '0930063585' 
                    action_name = 'ворота'
                
                if target_number and action_name:
                    logger.info(f"🎯 Target: {target_number}, Action: {action_name}")
                    
                    # Шукаємо дзвінок в базі
                    call_data = find_call_in_db(target_number)
                    
                    if call_data:
                        logger.info(f"📋 Знайдено call: {call_data['call_id']}")
                        
                        # ПРАВИЛЬНА ЛОГІКА УСПІХУ
                        if disposition == 'cancel' and duration == 0:
                            message = f"✅ {action_name.capitalize()} відчинено!"
                            status = 'success'
                            logger.info("🎉 SUCCESS: Відкрито успішно!")
                        elif disposition == 'busy':
                            message = f"❌ {action_name.capitalize()} зайняті. Спробуйте ще раз через хвилину."
                            status = 'busy'
                            logger.warning("⚠️ BUSY: Номер зайнятий")
                        elif disposition == 'cancel' and duration > 0:
                            message = f"❌ Технічна проблема з {action_name}. Спробуйте ще раз."
                            status = 'technical_error'
                            logger.warning("⚠️ TECH_ERROR: Були гудки, потім скинули")
                        elif disposition == 'answered':
                            message = f"⚠️ Технічна проблема з налаштуванням {action_name}. Зверніться до підтримки."
                            status = 'config_error'
                            logger.error("❌ CONFIG_ERROR: Дзвінок прийняли замість скидання")
                        else:
                            message = f"❌ Не вдалося відкрити {action_name}. Спробуйте ще раз."
                            status = 'failed'
                            logger.warning(f"❌ FAILED: {disposition}")
                        
                        # Відправляємо результат користувачу
                        chat_id = call_data['chat_id']
                        success = send_telegram(chat_id, message)
                        
                        if success:
                            logger.info(f"✅ Повідомлення відправлено в чат {chat_id}")
                        else:
                            logger.error(f"❌ Не вдалося відправити в чат {chat_id}")
                        
                        # Оновлюємо статус в базі
                        try:
                            conn = sqlite3.connect('call_tracking.db')
                            cursor = conn.cursor()
                            cursor.execute('UPDATE call_tracking SET status = ? WHERE call_id = ?', 
                                         (status, call_data['call_id']))
                            conn.commit()
                            conn.close()
                            logger.info(f"📝 Статус оновлено: {status}")
                        except Exception as e:
                            logger.error(f"❌ DB update error: {e}")
                    else:
                        logger.warning(f"❌ Call not found for {target_number}")
                else:
                    logger.info(f"❓ Unknown device in caller_id: {caller_id}")
            else:
                logger.info(f"ℹ️ Not a bot callback - called_did: {called_did}")
        else:
            logger.info(f"ℹ️ Ignoring event type: {event}")
        
        logger.info("✅ Webhook обробку завершено")
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON ERROR: {e}")
    except Exception as e:
        logger.error(f"❌ ERROR: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
