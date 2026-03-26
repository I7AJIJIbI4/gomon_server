#!/usr/bin/env python3
# test_webhook.py - Тестування webhook обробки
import sys
import json
import logging

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_simple_webhook():
    """Тестує simple_webhook.py"""
    print("=== ТЕСТУВАННЯ SIMPLE WEBHOOK ===")
    
    # Тестові дані webhook
    test_cases = [
        {
            "name": "Успішне відкриття воріт",
            "data": {
                "event": "NOTIFY_END",
                "caller_id": "0930063585",
                "called_did": "0733103110", 
                "disposition": "cancel",
                "duration": 3
            }
        },
        {
            "name": "Успішне відкриття хвіртки",
            "data": {
                "event": "NOTIFY_END",
                "caller_id": "0637442017",
                "called_did": "0733103110",
                "disposition": "cancel", 
                "duration": 2
            }
        },
        {
            "name": "Номер зайнятий",
            "data": {
                "event": "NOTIFY_END",
                "caller_id": "0930063585",
                "called_did": "0733103110",
                "disposition": "busy",
                "duration": 0
            }
        },
        {
            "name": "Не відповідає",
            "data": {
                "event": "NOTIFY_END", 
                "caller_id": "0637442017",
                "called_did": "0733103110",
                "disposition": "no-answer",
                "duration": 0
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n🧪 Тест: {test_case['name']}")
        test_data = json.dumps(test_case['data'])
        print(f"📋 Дані: {test_data}")
        
        try:
            import subprocess
            result = subprocess.run([
                'python3', 'simple_webhook.py', test_data
            ], capture_output=True, text=True, timeout=30)
            
            print(f"🔍 Код виходу: {result.returncode}")
            if result.stdout:
                print(f"📤 Вивід: {result.stdout.strip()}")
            if result.stderr:
                print(f"❌ Помилки: {result.stderr.strip()}")
                
        except subprocess.TimeoutExpired:
            print("⏰ Таймаут виконання")
        except Exception as e:
            print(f"❌ Помилка виконання: {e}")

def create_test_call_in_db():
    """Створює тестовий дзвінок в базі для перевірки webhook"""
    print("\n=== СТВОРЕННЯ ТЕСТОВОГО ДЗВІНКА ===")
    
    try:
        import sqlite3
        import time
        
        conn = sqlite3.connect('call_tracking.db')
        cursor = conn.cursor()
        
        # Створюємо таблицю якщо не існує
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS call_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id TEXT UNIQUE,
                user_id INTEGER,
                chat_id INTEGER,
                action_type TEXT,
                target_number TEXT,
                start_time INTEGER,
                status TEXT DEFAULT 'initiated',
                pbx_call_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Додаємо тестовий дзвінок для воріт
        test_call_id = f"test_{int(time.time())}"
        cursor.execute('''
            INSERT INTO call_tracking 
            (call_id, user_id, chat_id, action_type, target_number, start_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (test_call_id, 573368771, 573368771, 'vorota', '0930063585', int(time.time()), 'api_success'))
        
        # Додаємо тестовий дзвінок для хвіртки
        test_call_id2 = f"test_hvirtka_{int(time.time())}"
        cursor.execute('''
            INSERT INTO call_tracking 
            (call_id, user_id, chat_id, action_type, target_number, start_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (test_call_id2, 573368771, 573368771, 'hvirtka', '0637442017', int(time.time()), 'api_success'))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Створено тестові дзвінки: {test_call_id}, {test_call_id2}")
        return True
        
    except Exception as e:
        print(f"❌ Помилка створення тестових дзвінків: {e}")
        return False

def check_call_tracking_db():
    """Перевіряє стан бази відстеження дзвінків"""
    print("\n=== ПЕРЕВІРКА БАЗИ ВІДСТЕЖЕННЯ ДЗВІНКІВ ===")
    
    try:
        import sqlite3
        
        conn = sqlite3.connect('call_tracking.db')
        cursor = conn.cursor()
        
        # Перевіряємо чи існує таблиця
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='call_tracking'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("❌ Таблиця call_tracking не існує")
            conn.close()
            return False
        
        # Кількість записів
        cursor.execute("SELECT COUNT(*) FROM call_tracking")
        total_calls = cursor.fetchone()[0]
        print(f"📊 Всього записів: {total_calls}")
        
        # Останні дзвінки
        cursor.execute('''
            SELECT call_id, action_type, target_number, status, created_at 
            FROM call_tracking 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        recent_calls = cursor.fetchall()
        
        print("📞 Останні дзвінки:")
        for call in recent_calls:
            print(f"  {call[0]} - {call[1]} - {call[2]} - {call[3]} - {call[4]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Помилка перевірки бази: {e}")
        return False

def main():
    print("🔧 ТЕСТУВАННЯ WEBHOOK СИСТЕМИ")
    print("=" * 50)
    
    # Перевіряємо базу відстеження
    if not check_call_tracking_db():
        print("❌ Проблеми з базою відстеження дзвінків")
    
    # Створюємо тестові дзвінки
    if create_test_call_in_db():
        print("✅ Тестові дзвінки створено")
        
        # Тестуємо webhook
        test_simple_webhook()
    else:
        print("❌ Не вдалося створити тестові дзвінки")
    
    print("\n✅ Тестування webhook завершено")

if __name__ == "__main__":
    main()
