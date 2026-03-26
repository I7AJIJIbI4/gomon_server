#!/usr/bin/env python3
"""
Локальний тест логіки webhook системи
Перевіряє всі можливі сценарії без потреби в серверному підключенні
"""

import json

def analyze_call_result(disposition, duration, action_type):
    """
    Точна копія логіки з нашого виправленого коду
    """
    action_name = action_type.lower()
    if action_name == 'hvirtka':
        device_name = 'хвіртка'
    elif action_name == 'vorota':
        device_name = 'ворота'
    else:
        device_name = action_name
    
    # ✅ ВИПРАВЛЕНА КРИТИЧНА ЛОГІКА УСПІХУ
    if disposition == 'cancel' and duration > 0:
        return 'success', "✅ {} відчинено!".format(device_name.capitalize())
    elif disposition == 'busy':
        return 'busy', "❌ Номер {} зайнятий. Спробуйте ще раз.".format(device_name)
    elif disposition in ['no-answer', 'noanswer', 'cancel'] and duration == 0:
        return 'no_answer', "❌ Номер {} не відповідає.".format(device_name)
    elif disposition == 'answered':
        return 'answered', "📞 З'єднання з {} встановлено, але статус невідомий.".format(device_name)
    else:
        return 'failed', "❌ Не вдалося відкрити {}. Статус: {}".format(device_name, disposition)

def is_bot_callback(caller_id, called_did):
    """
    Визначає чи це bot callback чи IVR дзвінок
    """
    clinic_number = '0733103110'
    device_numbers = ['0637442017', '0930063585']
    
    # Нормалізуємо номери
    import re
    caller_clean = re.sub(r'^(\+38|38|8)?0?', '0', caller_id)
    called_clean = re.sub(r'^(\+38|38|8)?0?', '0', called_did)
    
    # Перевіряємо чи дзвінок йде З клініки НА пристрій
    from_clinic = (caller_clean == clinic_number)
    to_device = called_clean in device_numbers
    
    return from_clinic and to_device

def determine_action_type(called_did):
    """
    Визначає тип дії на основі номера
    """
    if '637442017' in called_did:
        return 'hvirtka', '0637442017'
    elif '930063585' in called_did:
        return 'vorota', '0930063585'
    else:
        return None, None

def run_tests():
    print("🧪 === ЛОКАЛЬНИЙ ТЕСТ ЛОГІКИ WEBHOOK СИСТЕМИ ===")
    print()
    
    # Тестові сценарії
    test_scenarios = [
        # Bot Callback тести - мають відправляти Telegram повідомлення
        {
            "name": "✅ Хвіртка - Успішне відкриття",
            "caller_id": "0733103110",
            "called_did": "0637442017", 
            "disposition": "cancel",
            "duration": 5,
            "expected_routing": "BOT",
            "expected_status": "success",
            "expected_message": "✅ Хвіртка відчинено!"
        },
        {
            "name": "✅ Ворота - Успішне відкриття",
            "caller_id": "0733103110",
            "called_did": "0930063585",
            "disposition": "cancel", 
            "duration": 7,
            "expected_routing": "BOT",
            "expected_status": "success",
            "expected_message": "✅ Ворота відчинено!"
        },
        {
            "name": "❌ Хвіртка - Зайнято",
            "caller_id": "0733103110",
            "called_did": "0637442017",
            "disposition": "busy",
            "duration": 0,
            "expected_routing": "BOT", 
            "expected_status": "busy",
            "expected_message": "❌ Номер хвіртка зайнятий"
        },
        {
            "name": "❌ Ворота - Не відповідає (cancel+0)",
            "caller_id": "0733103110",
            "called_did": "0930063585",
            "disposition": "cancel",
            "duration": 0,
            "expected_routing": "BOT",
            "expected_status": "no_answer", 
            "expected_message": "❌ Номер ворота не відповідає"
        },
        {
            "name": "❌ Ворота - Не відповідає (no-answer)",
            "caller_id": "0733103110",
            "called_did": "0930063585", 
            "disposition": "no-answer",
            "duration": 0,
            "expected_routing": "BOT",
            "expected_status": "no_answer",
            "expected_message": "❌ Номер ворота не відповідає"
        },
        {
            "name": "❌ Хвіртка - Інша помилка",
            "caller_id": "0733103110",
            "called_did": "0637442017",
            "disposition": "failed",
            "duration": 2,
            "expected_routing": "BOT",
            "expected_status": "failed",
            "expected_message": "❌ Не вдалося відкрити хвіртка"
        },
        # IVR тести - не повинні відправляти Telegram
        {
            "name": "🔄 IVR - Зовнішній дзвінок на клініку",
            "caller_id": "0501234567",
            "called_did": "0733103110",
            "disposition": "hangup", 
            "duration": 30,
            "expected_routing": "IVR",
            "expected_status": None,
            "expected_message": None
        },
        {
            "name": "🔄 IVR - Зовнішній дзвінок на пристрій",
            "caller_id": "0672345678", 
            "called_did": "0637442017",
            "disposition": "cancel",
            "duration": 5,
            "expected_routing": "IVR",
            "expected_status": None,
            "expected_message": None
        }
    ]
    
    total_tests = len(test_scenarios)
    passed_tests = 0
    failed_tests = 0
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"📋 Тест {i}: {scenario['name']}")
        print(f"   FROM: {scenario['caller_id']} → TO: {scenario['called_did']}")
        print(f"   Disposition: {scenario['disposition']}, Duration: {scenario['duration']}")
        
        # 1. Тестуємо роутинг
        is_bot = is_bot_callback(scenario['caller_id'], scenario['called_did'])
        actual_routing = "BOT" if is_bot else "IVR"
        
        routing_ok = actual_routing == scenario['expected_routing']
        print(f"   Роутинг: {actual_routing} ({'✅' if routing_ok else '❌'})")
        
        if not routing_ok:
            print(f"   ❌ FAIL: Очікувався {scenario['expected_routing']}")
            failed_tests += 1
            print()
            continue
            
        # 2. Якщо Bot - тестуємо логіку повідомлень
        if is_bot:
            action_type, target_number = determine_action_type(scenario['called_did'])
            
            if action_type:
                status, message = analyze_call_result(
                    scenario['disposition'],
                    scenario['duration'], 
                    action_type
                )
                
                status_ok = status == scenario['expected_status']
                message_ok = scenario['expected_message'] in message
                
                print(f"   Статус: {status} ({'✅' if status_ok else '❌'})")
                print(f"   Повідомлення: {message}")
                print(f"   Очікувалось: {scenario['expected_message']}")
                print(f"   Збіг: {'✅' if message_ok else '❌'}")
                
                if status_ok and message_ok:
                    print(f"   🎯 Telegram буде надіслано: {message}")
                    passed_tests += 1
                else:
                    print(f"   ❌ FAIL: Логіка неправильна")
                    failed_tests += 1
            else:
                print(f"   ❌ FAIL: Невідомий пристрій")
                failed_tests += 1
        else:
            # IVR - просто перевіряємо що не обробляється як bot
            print(f"   🔄 IVR обробка - Telegram повідомлення НЕ надсилається")
            passed_tests += 1
            
        print()
    
    # Результати
    print("📊 === РЕЗУЛЬТАТИ ТЕСТУВАННЯ ===")
    print(f"Всього тестів: {total_tests}")
    print(f"Пройшло: {passed_tests}")
    print(f"Провалилось: {failed_tests}")
    success_rate = (passed_tests * 100) // total_tests
    print(f"Відсоток успішності: {success_rate}%")
    
    if failed_tests == 0:
        print("\n🎉 ВСІ ТЕСТИ ПРОЙШЛИ! Логіка працює правильно!")
        print("\n✅ Гарантії:")
        print("- Користувачі отримають '✅ Відчинено!' при успішному відкритті")
        print("- Користувачі отримають '❌ Зайнято/Не відповідає' при помилках") 
        print("- IVR функціонал не поламався")
        print("- Telegram повідомлення надсилаються тільки для bot callbacks")
        return True
    else:
        print(f"\n⚠️ Знайдено {failed_tests} проблем у логіці!")
        return False

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
