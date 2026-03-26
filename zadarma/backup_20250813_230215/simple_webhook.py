#!/usr/bin/env python3
# Покращений простий webhook процесор - ОСТАТОЧНО ВИПРАВЛЕНА ВЕРСІЯ
# ✅ КРИТИЧНА ВИПРАВЛЕНА ЛОГІКА: cancel завжди означає успіх
# ✅ ВИПРАВЛЕНО: шукаємо пристрої в caller_id замість called_did
# ✅ ВИПРАВЛЕНО: правильні повідомлення про помилки
# ✅ Python 3.6 сумісність
# ✅ Покращена діагностика
# ✅ Telegram API працює

import sys
import json
import sqlite3
import time
import requests

def send_telegram(chat_id, message):
    """Відправляє повідомлення в Telegram через бот API"""
    try:
        # Читаємо токен з config
        with open('config.py', 'r') as f:
            config_content = f.read()
        
        # Знаходимо TELEGRAM_TOKEN
        import re
        token_match = re.search(r'TELEGRAM_TOKEN\s*=\s*[\'"]([^\'"]+)[\'"]', config_content)
        if not token_match:
            print("ERROR: Cannot find TELEGRAM_TOKEN in config.py")
            return False
            
        token = token_match.group(1)
        
        # Telegram API URL (без f-strings для Python 3.6)
        url = "https://api.telegram.org/bot{}/sendMessage".format(token)
        data = {
            "chat_id": chat_id, 
            "text": message, 
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, data=data, timeout=10)
        print("Telegram: {} - {}".format(response.status_code, response.text))
        return response.status_code == 200
        
    except Exception as e:
        print("Telegram error: {}".format(e))
        return False

def find_call_in_db(target_number, time_window=600):  # Збільшено до 10 хвилин
    """Знаходить дзвінок в базі даних з покращеним пошуком"""
    try:
        conn = sqlite3.connect('call_tracking.db')
        cursor = conn.cursor()
        
        current_time = int(time.time())
        time_start = current_time - time_window
        
        print("DB SEARCH: Looking for target '{}' in last {} seconds".format(target_number, time_window))
        
        # Спочатку точний пошук по target_number
        cursor.execute('''
            SELECT call_id, user_id, chat_id, action_type, target_number, start_time, status
            FROM call_tracking 
            WHERE target_number = ? AND start_time > ? AND status IN ('api_success', 'no_answer')
            ORDER BY start_time DESC LIMIT 1
        ''', (target_number, time_start))
        
        result = cursor.fetchone()
        
        if result:
            print("EXACT MATCH found: {}".format(result[0]))
        else:
            print("No exact match, trying partial search...")
            # Якщо не знайдено - пробуємо по частковим номерам
            normalized = target_number.lstrip('0')
            cursor.execute('''
                SELECT call_id, user_id, chat_id, action_type, target_number, start_time, status
                FROM call_tracking 
                WHERE (target_number LIKE ? OR target_number LIKE ?) 
                AND start_time > ? AND status IN ('api_success', 'no_answer')
                ORDER BY start_time DESC LIMIT 1
            ''', ('%{}%'.format(normalized), '%{}%'.format(target_number), time_start))
            result = cursor.fetchone()
            
            if result:
                print("PARTIAL MATCH found: {}".format(result[0]))
        
        # Якщо все ще не знайдено - показуємо що є в базі
        if not result:
            print("DEBUG: Recent calls in DB:")
            cursor.execute('''
                SELECT call_id, action_type, target_number, status, start_time
                FROM call_tracking 
                WHERE start_time > ?
                ORDER BY start_time DESC LIMIT 3
            ''', (time_start,))
            recent = cursor.fetchall()
            for r in recent:
                age = current_time - r[4]
                print("  {} - {} - {} - {} ({}s ago)".format(r[0], r[1], r[2], r[3], age))
        
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
        print("DB error: {}".format(e))
        return None

def show_recent_calls_diagnostic():
    """Діагностична функція - показує останні дзвінки"""
    try:
        conn = sqlite3.connect('call_tracking.db')
        cursor = conn.cursor()
        cursor.execute('SELECT call_id, action_type, target_number, status FROM call_tracking ORDER BY created_at DESC LIMIT 5')
        recent = cursor.fetchall()
        conn.close()
        print("RECENT CALLS:")
        for r in recent:
            print("  {} - {} - {} - {}".format(r[0], r[1], r[2], r[3]))
    except Exception as e:
        print("DIAGNOSTIC ERROR: {}".format(e))

def main():
    print("=== ENHANCED SIMPLE WEBHOOK PROCESSOR ===")
    
    if len(sys.argv) < 2:
        print("ERROR: No webhook data provided")
        print("Usage: python3 simple_webhook.py '{\"event\":\"NOTIFY_END\",\"caller_id\":\"...\", ...}'")
        return
    
    try:
        # Парсимо JSON дані
        data = json.loads(sys.argv[1])
        print("Received data: {}".format(data))
        
        # Витягуємо основні параметри
        event = data.get('event', '')
        caller_id = data.get('caller_id', '')
        called_did = data.get('called_did', '') 
        disposition = data.get('disposition', '')
        duration = int(data.get('duration', 0))
        
        print("Event: {}, From: {}, To: {}".format(event, caller_id, called_did))
        print("Disposition: {}, Duration: {}".format(disposition, duration))
        
        # Обробляємо тільки завершення дзвінків
        if event == 'NOTIFY_END':
            # Покращене визначення типу дзвінка
            target_number = None
            action_name = None
            
            print("DIAGNOSTIC: Checking caller_id: '{}'".format(caller_id))
            
            # ВИПРАВЛЕНА ЛОГІКА: В callback дзвінках FROM=клініка, TO=пристрій
            # Але в webhook CALLER_ID=пристрій, CALLED_DID=клініка (зворотний порядок!)
            
            # Спочатку перевіряємо called_did (має бути номер клініки)
            clinic_numbers = ['0733103110', '733103110']
            is_from_clinic = any(clinic_num in called_did for clinic_num in clinic_numbers)
            
            if is_from_clinic:
                # Це callback дзвінок від нашого бота
                print("DETECTED: Bot callback call")
                
                # Пристрій буде в caller_id
                if '637442017' in caller_id:
                    target_number = '0637442017'
                    action_name = 'хвіртка'
                    print("DETECTED: Хвіртка")
                elif '930063585' in caller_id:
                    target_number = '0930063585' 
                    action_name = 'ворота'
                    print("DETECTED: Ворота")
                else:
                    # Додатковий пошук по частковим номерам
                    possible_devices = [
                        ('637442017', '0637442017', 'хвіртка'),
                        ('930063585', '0930063585', 'ворота')
                    ]
                    
                    for partial, full, name in possible_devices:
                        if partial in caller_id:
                            target_number = full
                            action_name = name
                            print("DETECTED by partial: {} -> {}".format(partial, name))
                            break
                    
                    if not target_number:
                        print("UNKNOWN DEVICE in caller_id: '{}'".format(caller_id))
                        return
            else:
                # Це не callback дзвінок від бота - ігноруємо
                print("NOT a bot callback - called_did: '{}'".format(called_did))
                return
            
            print("Target: {}, Action: {}".format(target_number, action_name))
            
            # Шукаємо дзвінок в базі
            call_data = find_call_in_db(target_number)
            
            if call_data:
                print("Found call: {}".format(call_data['call_id']))
                
                # ✅ ВИПРАВЛЕНА ЛОГІКА УСПІХУ - cancel завжди означає успіх
                if disposition == 'cancel':
                    message = "✅ {} відчинено!".format(action_name.capitalize())
                    status = 'success'
                    print("SUCCESS: Call was cancelled - gate/door opened!")
                elif disposition == 'busy':
                    message = "❌ {} зайняті/відчиняються. Спробуйте ще раз через хвилину.".format(action_name.capitalize())
                    status = 'busy'
                elif disposition in ['no-answer', 'noanswer']:
                    message = "❌ {} вже відчинено/відчиняються, або сталася технічна помилка. Спробуйте ще раз.".format(action_name.capitalize())
                    status = 'no_answer'
                else:
                    message = "❌ Не вдалося відкрити {}. Статус: {}. Спробуйте ще раз.".format(action_name, disposition)
                    status = 'failed'
                
                print("Result: {} - {}".format(status, message))
                
                # Відправляємо повідомлення користувачу
                chat_id = call_data['chat_id']
                success = send_telegram(chat_id, message)
                
                if success:
                    print("✅ Message sent successfully to chat {}!".format(chat_id))
                else:
                    print("❌ Failed to send message to chat {}".format(chat_id))
                
                # Оновлюємо статус в базі
                try:
                    conn = sqlite3.connect('call_tracking.db')
                    cursor = conn.cursor()
                    cursor.execute('UPDATE call_tracking SET status = ? WHERE call_id = ?', 
                                 (status, call_data['call_id']))
                    conn.commit()
                    conn.close()
                    print("✅ Status updated in DB: {}".format(status))
                except Exception as e:
                    print("DB update error: {}".format(e))
                
            else:
                print("❌ Call not found for {}".format(target_number))
                # Діагностика - покажемо останні записи
                show_recent_calls_diagnostic()
        else:
            print("INFO: Ignoring event type: {}".format(event))
        
        print("=== WEBHOOK PROCESSING COMPLETE ===")
        
    except json.JSONDecodeError as e:
        print("JSON ERROR: {}".format(e))
        print("Received data: {}".format(sys.argv[1] if len(sys.argv) > 1 else 'None'))
    except Exception as e:
        print("ERROR: {}".format(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()