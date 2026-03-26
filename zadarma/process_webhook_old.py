#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_webhook.py - ВИПРАВЛЕНИЙ обробник webhook-ів для телеграм бота
Версія з покращеним алгоритмом пошуку дзвінків
"""

import sys
import json
import logging
import os
import time

# Додаємо шлях до нашого проекту
sys.path.append('/home/gomoncli/zadarma')

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/gomoncli/zadarma/webhook_processor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('webhook_processor_fixed')

def normalize_phone_number(phone):
    """Нормалізує номер телефону для порівняння"""
    if not phone:
        return ""
    
    normalized = ''.join(filter(str.isdigit, str(phone)))
    
    if normalized.startswith('380'):
        normalized = normalized[3:]
    elif normalized.startswith('38'):
        normalized = normalized[2:]
    elif normalized.startswith('0'):
        normalized = normalized[1:]
    
    return normalized

def find_tracked_call_enhanced(pbx_call_id, caller_id, call_tracker):
    """
    Покращений пошук відстежуваного дзвінка
    Використовує кілька стратегій пошуку
    """
    logger.info(f"🔍 ПОКРАЩЕНИЙ пошук дзвінка:")
    logger.info(f"   PBX ID: {pbx_call_id}")
    logger.info(f"   Caller ID: {caller_id}")
    
    current_time = time.time()
    
    # Стратегія 1: Пошук по PBX ID
    if pbx_call_id:
        try:
            call_data = call_tracker.get_call_by_pbx_id(pbx_call_id)
            if call_data:
                logger.info(f"✅ ЗНАЙДЕНО ПО PBX ID: {pbx_call_id}")
                return call_data
        except:
            pass
    
    # Стратегія 2: Аналіз номера з webhook для визначення типу дзвінка
    target_numbers = []
    action_type = None
    
    # Визначаємо тип дзвінка по caller_id
    if '637442017' in caller_id:
        target_numbers = ['0637442017', '637442017', '380637442017']
        action_type = 'hvirtka'
        logger.info("🚪 Тип: Хвіртка")
    elif '930063585' in caller_id:
        target_numbers = ['0930063585', '930063585', '380930063585']
        action_type = 'vorota'
        logger.info("🏠 Тип: Ворота")
    else:
        logger.warning(f"⚠️ Невідомий номер: {caller_id}")
        return None
    
    # Стратегія 3: Пошук по номеру та часу з розширеними інтервалами
    for target_number in target_numbers:
        for time_window in [30, 60, 120, 300, 600]:  # від 30 секунд до 10 хвилин
            try:
                if hasattr(call_tracker, 'get_call_by_target_and_time'):
                    call_data = call_tracker.get_call_by_target_and_time(target_number, time_window)
                else:
                    # Fallback метод
                    call_data = call_tracker.get_call_by_target(target_number, time_window)
                
                if call_data:
                    time_diff = current_time - call_data.get('timestamp', 0)
                    logger.info(f"✅ ЗНАЙДЕНО ПО НОМЕРУ: {target_number} (час: {time_diff:.1f}с)")
                    return call_data
            except Exception as e:
                logger.debug(f"   Помилка пошуку по {target_number}: {e}")
                continue
    
    # Стратегія 4: Пошук останнього дзвінка правильного типу
    try:
        if hasattr(call_tracker, 'get_recent_calls'):
            recent_calls = call_tracker.get_recent_calls(600)
        else:
            # Fallback
            recent_calls = []
        
        for call in recent_calls:
            if call.get('action_type') == action_type:
                time_diff = current_time - call.get('timestamp', 0)
                if time_diff < 600:  # 10 хвилин
                    logger.info(f"✅ ЗНАЙДЕНО ПО ТИПУ: {call['call_id']} (час: {time_diff:.1f}с)")
                    return call
    except Exception as e:
        logger.error(f"❌ Помилка пошуку нещодавніх дзвінків: {e}")
    
    logger.warning(f"❌ Дзвінок НЕ ЗНАЙДЕНО жодним способом")
    return None

def main():
    """Головна функція обробки webhook"""
    try:
        # Отримуємо JSON данні
        if len(sys.argv) < 2:
            logger.error("❌ Не передано JSON данні")
            print(json.dumps({"success": False, "message": "No JSON data provided"}))
            sys.exit(1)
        
        json_data = sys.argv[1]
        logger.info(f"📥 Отримано данні: {json_data}")
        
        # Парсимо JSON
        try:
            webhook_data = json.loads(json_data)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Помилка парсингу JSON: {e}")
            print(json.dumps({"success": False, "message": f"JSON parse error: {e}"}))
            sys.exit(1)
        
        event = webhook_data.get('event', '')
        pbx_call_id = webhook_data.get('pbx_call_id', '')
        caller_id = webhook_data.get('caller_id', '').replace('+', '')
        destination = webhook_data.get('destination', '')
        called_did = webhook_data.get('called_did', '')
        disposition = webhook_data.get('disposition', '')
        duration = int(webhook_data.get('duration', 0))
        
        logger.info(f"🔔 Webhook подія: {event}")
        logger.info(f"   PBX ID: {pbx_call_id}")
        logger.info(f"   Caller: {caller_id}")
        logger.info(f"   Destination: {destination}")
        logger.info(f"   Called DID: {called_did}")
        logger.info(f"   Disposition: {disposition}")
        logger.info(f"   Duration: {duration}")
        
        # Імпортуємо модуль обробки
        try:
            from zadarma_api_webhook import send_telegram_message, call_tracker
            logger.info("✅ Успішно імпортовано zadarma_api_webhook")
        except ImportError as e:
            logger.error(f"❌ Помилка імпорту zadarma_api_webhook: {e}")
            try:
                from zadarma_api import send_telegram_message, call_tracker
                logger.info("✅ Fallback: імпортовано zadarma_api")
            except ImportError:
                logger.error("❌ Не вдалося імпортувати модуль обробки")
                print(json.dumps({"success": False, "message": "Import error"}))
                sys.exit(1)
        
        # Обробляємо події
        if event == 'NOTIFY_END':
            logger.info(f"📞 Обробка завершення дзвінка")
            
            # ПОКРАЩЕНИЙ ПОШУК
            call_data = find_tracked_call_enhanced(pbx_call_id, caller_id, call_tracker)
            
            if call_data:
                logger.info(f"✅ ЗНАЙДЕНО відстежуваний дзвінок: {call_data['call_id']}")
                
                action_name = "хвіртку" if call_data['action_type'] == 'hvirtka' else "ворота"
                chat_id = call_data['chat_id']
                
                # Аналіз результату
                message = ""
                status = ""
                
                if disposition == 'cancel' and duration > 0:
                    message = f"✅ {action_name.capitalize()} відчинено!"
                    status = 'success'
                    logger.info(f"✅ УСПІХ: {action_name} відкрито")
                elif disposition == 'busy':
                    message = f"❌ Номер {action_name} зайнятий. Спробуйте ще раз через хвилину."
                    status = 'busy'
                    logger.warning(f"❌ ЗАЙНЯТО: {action_name}")
                elif disposition in ['no-answer', 'noanswer'] and duration == 0:
                    message = f"❌ Номер {action_name} не відповідає. Можливо проблеми зв'язку.\n\nСпробуйте ще раз або зателефонуйте: <a href=\"tel:+380733103110\">+380733103110</a>"
                    status = 'no_answer'
                    logger.warning(f"❌ НЕ ВІДПОВІДАЄ: {action_name}")
                elif disposition == 'answered' and duration > 0:
                    message = f"⚠️ Дзвінок для відкриття {action_name} було прийнято.\nМожливо, система не налаштована правильно.\n\nЗверніться до підтримки: <a href=\"tel:+380733103110\">+380733103110</a>"
                    status = 'answered'
                    logger.error(f"⚠️ ПРИЙНЯТО: {action_name} - потрібна перевірка")
                    
                    # Сповіщення адміна
                    try:
                        from config import ADMIN_USER_ID
                        admin_message = f"🚨 ПРОБЛЕМА: Дзвінок на {action_name} ({call_data['target_number']}) ПРИЙНЯТО замість скидання! Тривалість: {duration}s"
                        send_telegram_message(ADMIN_USER_ID, admin_message)
                    except Exception as admin_error:
                        logger.error(f"❌ Помилка сповіщення адміна: {admin_error}")
                else:
                    message = f"❌ Не вдалося відкрити {action_name}.\nСтатус: {disposition}\nТривалість: {duration}s\n\nСпробуйте ще раз або зателефонуйте: <a href=\"tel:+380733103110\">+380733103110</a>"
                    status = 'failed'
                    logger.warning(f"❌ НЕВДАЧА: {action_name} - {disposition}")
                
                # Відправляємо повідомлення користувачу
                success = send_telegram_message(chat_id, message)
                
                if success:
                    logger.info(f"📤 ПОВІДОМЛЕННЯ ВІДПРАВЛЕНО користувачу {chat_id}: {status}")
                else:
                    logger.error(f"❌ НЕ ВДАЛОСЯ відправити повідомлення користувачу {chat_id}")
                
                # Оновлюємо статус
                try:
                    call_tracker.update_call_status(call_data['call_id'], status, pbx_call_id)
                    logger.info(f"📝 Статус оновлено: {status}")
                except Exception as update_error:
                    logger.error(f"❌ Помилка оновлення статусу: {update_error}")
                
                result = {
                    "success": True, 
                    "status": status, 
                    "message": f"Notification sent to chat {chat_id}",
                    "call_id": call_data['call_id'],
                    "action": action_name
                }
                
            else:

            # Перевірити чи є pending IVR дзвінки
            ivr_call = check_pending_ivr_calls(caller_id, disposition, duration)
            if ivr_call:
                logger.info(f"📞 Знайдено pending IVR дзвінок: {ivr_call["call_id"]}")
                message, status = process_ivr_webhook_result(ivr_call, disposition, duration)
                logger.info(f"📋 IVR результат: {message}")
                print(json.dumps({"success": True, "message": message, "call_id": ivr_call["call_id"], "status": status}))
                return

                logger.warning(f"ℹ️ Дзвінок {pbx_call_id} ({caller_id}) НЕ ВІДСТЕЖУЄТЬСЯ")
                
                # Діагностична інформація
                logger.info("🔍 ДІАГНОСТИКА:")
                logger.info(f"   Нормалізований caller: {normalize_phone_number(caller_id)}")
                
                try:
                    if hasattr(call_tracker, 'get_recent_calls'):
                        recent_calls = call_tracker.get_recent_calls(300)
                        logger.info(f"   Активних дзвінків: {len(recent_calls)}")
                        for call in recent_calls:
                            age = time.time() - call.get('timestamp', 0)
                            logger.info(f"     - {call['call_id']}: {call['target_number']} ({age:.0f}с)")
                except Exception as diag_error:
                    logger.error(f"   Помилка діагностики: {diag_error}")
                
                result = {"success": True, "message": "Call not tracked by our system"}
                
        elif event == 'NOTIFY_START':
            logger.info(f"📞 START: PBX {pbx_call_id}, Caller: {caller_id}")
            result = {"success": True, "message": "Start event logged"}
            
        elif event == 'NOTIFY_INTERNAL':
            internal = webhook_data.get('internal', '')
            logger.info(f"📞 INTERNAL: {caller_id} -> {internal}")
            result = {"success": True, "message": "Internal call logged"}
            
        else:
            logger.info(f"ℹ️ Подія {event} ігнорується")
            result = {"success": True, "message": f"Event {event} ignored"}
        
        # Повертаємо результат
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)
        
    except Exception as e:
        logger.exception(f"❌ КРИТИЧНА ПОМИЛКА: {e}")
        print(json.dumps({"success": False, "message": str(e)}, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
import json
import os
import time

def check_pending_ivr_calls(caller_id, disposition, duration):
    """Перевіряє чи є pending IVR дзвінки для цього номера"""
    pending_file = '/tmp/pending_ivr_calls.json'
    
    if not os.path.exists(pending_file):
        return None
    
    try:
        with open(pending_file, 'r') as f:
            data = json.load(f)
    except:
        return None
    
    # Нормалізуємо номер
    normalized_caller = caller_id.replace('+', '').replace('380', '0')
    
    # Шукаємо pending дзвінок для цього номера
    for call in data:
        if (call['target_number'] == normalized_caller and 
            call['status'] == 'pending' and
            (time.time() - call['timestamp']) <= 120):  # 2 хвилини
            
            return call
    
    return None

def update_ivr_call_status(call_id, status):
    """Оновлює статус IVR дзвінка"""
    pending_file = '/tmp/pending_ivr_calls.json'
    
    if not os.path.exists(pending_file):
        return False
    
    try:
        with open(pending_file, 'r') as f:
            data = json.load(f)
        
        for call in data:
            if call['call_id'] == call_id:
                call['status'] = status
                call['completed_at'] = int(time.time())
                break
        
        with open(pending_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        return True
    except:
        return False

def process_ivr_webhook_result(call_data, disposition, duration):
    """Обробляє результат IVR webhook і повертає повідомлення для логу"""
    action_name = call_data['action_type']
    call_id = call_data['call_id']
    
    if disposition == 'cancel' and duration > 0:
        message = f"✅ {action_name.capitalize()} відкрито!"
        status = 'success'
        update_ivr_call_status(call_id, 'success')
    elif disposition == 'busy':
        message = f"❌ {action_name.capitalize()}: номер зайнятий"
        status = 'busy'
        update_ivr_call_status(call_id, 'busy')
    elif disposition in ['no-answer', 'noanswer'] and duration == 0:
        message = f"❌ {action_name.capitalize()}: номер не відповідає"
        status = 'no_answer' 
        update_ivr_call_status(call_id, 'no_answer')
    elif disposition == 'answered' and duration > 0:
        message = f"⚠️ {action_name.capitalize()}: дзвінок прийнято (потрібна перевірка)"
        status = 'answered'
        update_ivr_call_status(call_id, 'answered')
    else:
        message = f"❌ {action_name.capitalize()}: невдача ({disposition})"
        status = 'failed'
        update_ivr_call_status(call_id, 'failed')
    
    return message, status

# ВИПРАВЛЕННЯ 2025-08-06: Змінено логіку успішності дзвінків
# Успіх тепер = duration > 0 (були гудки) AND disposition = 'cancel' (скинули)
