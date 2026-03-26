#!/usr/bin/env python3
# Webhook процесор з ПРАВИЛЬНОЮ логікою для вашого обладнання
# ✅ ВИПРАВЛЕНО: успіх = duration == 0 + cancel (для вашого обладнання)
# ✅ Детальне логування в файл
# ✅ Python 3.6 сумісність

import sys
import json
import sqlite3
import time
import requests
from datetime import datetime

# Файл для логування
LOG_FILE = '/home/gomoncli/zadarma/webhook_processor.log'

def log_message(message):
    """Записує повідомлення в лог"""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(LOG_FILE, 'a') as f:
            f.write("[{}] {}\n".format(timestamp, message))
        print(message)  # Також виводимо в консоль
    except Exception as e:
        print("Log error: {}".format(e))

def send_telegram(chat_id, message):
    """Відправляє повідомлення в Telegram через бот API"""
    log_message("📤 Відправка Telegram повідомлення в чат {}".format(chat_id))
    try:
        # Читаємо токен з config
        with open('/home/gomoncli/zadarma/config.py', 'r') as f:
            config_content = f.read()
        
        # Знаходимо TELEGRAM_TOKEN
        import re
        token_match = re.search(r'TELEGRAM_TOKEN\s*=\s*[\'"]([^\'"]+)[\'"]', config_content)
        if not token_match:
            log_message("❌ Cannot find TELEGRAM_TOKEN in config.py")
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
            log_message("✅ Telegram повідомлення відправлено успішно")
        else:
            log_message("❌ Помилка Telegram API: {} - {}".format(
                response.status_code, response.text))
        
        return success
        
    except Exception as e:
        log_message("❌ Telegram error: {}".format(e))
        return False

def find_call_in_db(target_number, time_window=600):
    """Знаходить дзвінок в базі даних"""
    log_message("🔍 Пошук дзвінка для номеру {}".format(target_number))
    try:
        conn = sqlite3.connect('/home/gomoncli/zadarma/call_tracking.db')
        cursor = conn.cursor()
        
        current_time = int(time.time())
        time_start = current_time - time_window
        
        # Точний пошук
        cursor.execute('''
            SELECT call_id, user_id, chat_id, action_type, target_number, start_time, status
            FROM call_tracking 
            WHERE target_number = ? AND start_time > ? AND status = 'api_success'
            ORDER BY start_time DESC LIMIT 1
        ''', (target_number, time_start))
        
        result = cursor.fetchone()
        
        # Якщо не знайдено - частковий пошук
        if not result:
            normalized = target_number.lstrip('0')
            cursor.execute('''
                SELECT call_id, user_id, chat_id, action_type, target_number, start_time, status
                FROM call_tracking 
                WHERE (target_number LIKE ? OR target_number LIKE ?) 
                AND start_time > ? AND status = 'api_success'
                ORDER BY start_time DESC LIMIT 1
            ''', ('%{}%'.format(normalized), '%{}%'.format(target_number), time_start))
            result = cursor.fetchone()
        
        conn.close()
        
        if result:
            log_message("✅ Знайдено дзвінок: {}".format(result[0]))
            return {
                'call_id': result[0],
                'user_id': result[1],
                'chat_id': result[2], 
                'action_type': result[3],
                'target_number': result[4],
                'start_time': result[5],
                'status': result[6]
            }
        else:
            log_message("❌ Дзвінок не знайдено для {}".format(target_number))
        
        return None
        
    except Exception as e:
        log_message("❌ DB error: {}".format(e))
        return None

def main():
    log_message("=" * 60)
    log_message("🔔 WEBHOOK ВИКЛИКАНО")
    
    if len(sys.argv) < 2:
        log_message("❌ Немає webhook даних")
        return
    
    try:
        # Парсимо JSON дані
        data = json.loads(sys.argv[1])
        log_message("📥 Webhook дані: {}".format(json.dumps(data, ensure_ascii=False)))
        
        # Витягуємо параметри
        event = data.get('event', '')
        caller_id = data.get('caller_id', '')
        called_did = data.get('called_did', '') 
        disposition = data.get('disposition', '')
        duration = int(data.get('duration', 0))
        
        log_message("📞 Event: {}, From: {}, To: {}, Disposition: {}, Duration: {}s".format(
            event, caller_id, called_did, disposition, duration))
        
        # Обробляємо тільки завершення дзвінків
        if event == 'NOTIFY_END':
            
            # Перевірка чи це bot callback
            clinic_numbers = ['0733103110', '733103110']
            is_from_clinic = any(clinic_num in called_did for clinic_num in clinic_numbers)
            
            log_message("🔍 Перевірка: called_did='{}', is_bot_callback={}".format(
                called_did, is_from_clinic))
            
            if not is_from_clinic:
                log_message("ℹ️ Це не bot callback - ігноруємо")
                return
            
            log_message("🤖 Детектовано bot callback")
            
            # Визначаємо пристрій по caller_id
            target_number = None
            action_name = None
            
            if '637442017' in caller_id:
                target_number = '0637442017'
                action_name = 'хвіртка'
            elif '930063585' in caller_id:
                target_number = '0930063585' 
                action_name = 'ворота'
            else:
                log_message("❓ Невідомий пристрій в caller_id: {}".format(caller_id))
                return
            
            log_message("🎯 Визначено: {} ({})".format(action_name, target_number))
            
            # Шукаємо дзвінок в базі
            call_data = find_call_in_db(target_number)
            
            if not call_data:
                log_message("❌ Дзвінок не знайдено в базі для {}".format(target_number))
                return
            
            log_message("📋 Знайдено call_id: {}".format(call_data['call_id']))
            
            # ✅ ПРАВИЛЬНА ЛОГІКА ДЛЯ ВАШОГО ОБЛАДНАННЯ
            # Ваше обладнання: cancel + duration=0 = успіх
            if disposition == 'cancel' and duration == 0:
                message = "✅ {} відчинено!".format(action_name.capitalize())
                status = 'success'
                log_message("🎉 SUCCESS: {} відкрито (cancel + duration=0)".format(action_name))
                
            elif disposition == 'cancel' and duration > 0:
                message = "⚠️ {} відкрито, але були гудки. Перевірте налаштування.".format(
                    action_name.capitalize())
                status = 'success_with_warning'
                log_message("⚠️ SUCCESS with warning: були гудки (duration={})".format(duration))
                
            elif disposition == 'busy':
                message = "❌ {} зайнятий. Спробуйте через хвилину.".format(
                    action_name.capitalize())
                status = 'busy'
                log_message("❌ BUSY: номер зайнятий")
                
            elif disposition in ['no-answer', 'noanswer']:
                message = "❌ {} не відповідає. Перевірте з'єднання.".format(
                    action_name.capitalize())
                status = 'no_answer'
                log_message("❌ NO_ANSWER: пристрій не відповідає")
                
            elif disposition == 'answered':
                message = "⚠️ {} прийняв дзвінок. Перевірте налаштування пристрою.".format(
                    action_name.capitalize())
                status = 'config_error'
                log_message("⚠️ CONFIG_ERROR: дзвінок прийнято замість скидання")
                
            else:
                message = "❌ Помилка відкриття {}: {}".format(action_name, disposition)
                status = 'failed'
                log_message("❌ FAILED: невідома помилка - {}".format(disposition))
            
            # Відправляємо повідомлення користувачу
            chat_id = call_data['chat_id']
            log_message("📤 Відправка повідомлення в чат {}: {}".format(chat_id, message))
            
            telegram_success = send_telegram(chat_id, message)
            
            if telegram_success:
                log_message("✅ Повідомлення успішно відправлено")
            else:
                log_message("❌ Не вдалося відправити повідомлення")
            
            # Оновлюємо статус в базі
            try:
                conn = sqlite3.connect('/home/gomoncli/zadarma/call_tracking.db')
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE call_tracking SET status = ? WHERE call_id = ?', 
                    (status, call_data['call_id'])
                )
                conn.commit()
                conn.close()
                log_message("📝 Статус оновлено в БД: {}".format(status))
            except Exception as e:
                log_message("❌ Помилка оновлення БД: {}".format(e))
                
        else:
            log_message("ℹ️ Ігноруємо event type: {}".format(event))
        
        log_message("✅ Webhook обробку завершено")
        log_message("=" * 60)
        
    except json.JSONDecodeError as e:
        log_message("❌ JSON ERROR: {}".format(e))
        log_message("Raw data: {}".format(sys.argv[1] if len(sys.argv) > 1 else 'None'))
    except Exception as e:
        log_message("❌ CRITICAL ERROR: {}".format(e))
        import traceback
        log_message(traceback.format_exc())

if __name__ == "__main__":
    main()