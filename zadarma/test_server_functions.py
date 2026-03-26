#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_server_functions.py - Тестування функцій на продакшн сервері

Цей скрипт тестує всі нові функції безпосередньо на сервері.
"""

import sys
import os
import sqlite3
import logging
from datetime import datetime

# Додаємо поточну директорію до шляху
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_database_connections():
    """Тестує підключення до всіх баз даних"""
    print("🧪 ТЕСТУВАННЯ ПІДКЛЮЧЕНЬ ДО БД")
    print("=" * 40)
    
    databases = [
        ('users.db', 'Основна БД користувачів'),
        ('call_tracking.db', 'БД відстеження дзвінків')
    ]
    
    results = {}
    
    for db_file, description in databases:
        try:
            if os.path.exists(db_file):
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                
                if db_file == 'users.db':
                    cursor.execute('SELECT COUNT(*) FROM clients')
                    clients_count = cursor.fetchone()[0]
                    cursor.execute('SELECT COUNT(*) FROM users')  
                    users_count = cursor.fetchone()[0]
                    print(f"✅ {description}: {clients_count} клієнтів, {users_count} користувачів")
                    results[db_file] = {'status': 'OK', 'clients': clients_count, 'users': users_count}
                    
                elif db_file == 'call_tracking.db':
                    cursor.execute('SELECT COUNT(*) FROM calls')
                    calls_count = cursor.fetchone()[0]
                    print(f"✅ {description}: {calls_count} дзвінків")
                    results[db_file] = {'status': 'OK', 'calls': calls_count}
                
                conn.close()
            else:
                print(f"⚠️  {description}: файл не існує")
                results[db_file] = {'status': 'NOT_FOUND'}
                
        except Exception as e:
            print(f"❌ {description}: помилка - {e}")
            results[db_file] = {'status': 'ERROR', 'error': str(e)}
    
    return results

def test_sync_functions():
    """Тестує нові функції синхронізації"""
    print("\n🧪 ТЕСТУВАННЯ ФУНКЦІЙ СИНХРОНІЗАЦІЇ")
    print("=" * 40)
    
    results = {}
    
    try:
        from user_db import cleanup_duplicate_phones, get_user_info
        
        # Тест очищення дублікатів
        try:
            duplicates_cleaned = cleanup_duplicate_phones()
            print(f"✅ cleanup_duplicate_phones: видалено {duplicates_cleaned} дублікатів")
            results['cleanup_duplicates'] = {'status': 'OK', 'cleaned': duplicates_cleaned}
        except Exception as e:
            print(f"❌ cleanup_duplicate_phones: {e}")
            results['cleanup_duplicates'] = {'status': 'ERROR', 'error': str(e)}
        
        # Тест отримання інформації користувача  
        try:
            test_user_id = 573368771  # Адмін
            user_info = get_user_info(test_user_id)
            if user_info:
                print(f"✅ get_user_info: інформація отримана для користувача {test_user_id}")
                results['get_user_info'] = {'status': 'OK'}
            else:
                print(f"⚠️  get_user_info: користувач {test_user_id} не знайдений")
                results['get_user_info'] = {'status': 'NOT_FOUND'}
        except Exception as e:
            print(f"❌ get_user_info: {e}")
            results['get_user_info'] = {'status': 'ERROR', 'error': str(e)}
            
    except ImportError as e:
        print(f"❌ Не вдалося імпортувати функції: {e}")
        results['import'] = {'status': 'ERROR', 'error': str(e)}
    
    return results

def test_api_connections():
    """Тестує підключення до API"""
    print("\n🧪 ТЕСТУВАННЯ API ПІДКЛЮЧЕНЬ")
    print("=" * 40)
    
    results = {}
    
    # Тест WLaunch API
    try:
        from wlaunch_api import test_wlaunch_connection
        wlaunch_ok = test_wlaunch_connection()
        if wlaunch_ok:
            print("✅ WLaunch API: підключення працює")
            results['wlaunch'] = {'status': 'OK'}
        else:
            print("❌ WLaunch API: підключення не працює")
            results['wlaunch'] = {'status': 'FAILED'}
    except Exception as e:
        print(f"❌ WLaunch API: {e}")
        results['wlaunch'] = {'status': 'ERROR', 'error': str(e)}
    
    # Тест Zadarma API
    try:
        from zadarma_api import test_zadarma_auth
        zadarma_ok = test_zadarma_auth()
        if zadarma_ok:
            print("✅ Zadarma API: підключення працює")
            results['zadarma'] = {'status': 'OK'}
        else:
            print("❌ Zadarma API: підключення не працює")
            results['zadarma'] = {'status': 'FAILED'}
    except Exception as e:
        print(f"❌ Zadarma API: {e}")
        results['zadarma'] = {'status': 'ERROR', 'error': str(e)}
    
    return results

def test_webhook_logic():
    """Тестує логіку обробки webhook"""
    print("\n🧪 ТЕСТУВАННЯ WEBHOOK ЛОГІКИ")
    print("=" * 40)
    
    results = {}
    
    # Тестові дані
    test_cases = [
        {
            'name': 'Successful call',
            'data': '{"event":"NOTIFY_END","duration":"15","disposition":"answered","caller_id":"test"}',
            'expected': True
        },
        {
            'name': 'Failed call',
            'data': '{"event":"NOTIFY_END","duration":"0","disposition":"no_answer","caller_id":"test"}',
            'expected': False
        },
        {
            'name': 'Answered call',
            'data': '{"event":"NOTIFY_END","duration":"30","disposition":"answered","caller_id":"test"}',
            'expected': True
        }
    ]
    
    for test_case in test_cases:
        try:
            # Імпортуємо функцію обробки
            from process_webhook import process_webhook_data
            import json
            
            webhook_data = json.loads(test_case['data'])
            result = process_webhook_data(webhook_data)
            
            if result == test_case['expected']:
                print(f"✅ {test_case['name']}: {'SUCCESS' if result else 'ERROR'} (правильно)")
                results[test_case['name']] = {'status': 'OK', 'result': result}
            else:
                print(f"❌ {test_case['name']}: {'SUCCESS' if result else 'ERROR'}, очікувалось {'SUCCESS' if test_case['expected'] else 'ERROR'}")
                results[test_case['name']] = {'status': 'WRONG', 'expected': test_case['expected'], 'actual': result}
                
        except Exception as e:
            print(f"❌ {test_case['name']}: помилка - {e}")
            results[test_case['name']] = {'status': 'ERROR', 'error': str(e)}
    
    return results

def test_new_bot_commands():
    """Тестує доступність нових команд бота"""
    print("\n🧪 ТЕСТУВАННЯ НОВИХ КОМАНД БОТА")
    print("=" * 40)
    
    results = {}
    
    try:
        import sync_management
        
        # Перевіряємо наявність основних функцій
        functions_to_test = [
            'handle_sync_status_command',
            'handle_sync_clean_command', 
            'handle_sync_full_command',
            'handle_sync_test_command',
            'handle_sync_user_command',
            'handle_sync_help_command'
        ]
        
        for func_name in functions_to_test:
            if hasattr(sync_management, func_name):
                print(f"✅ {func_name}: функція доступна")
                results[func_name] = {'status': 'OK'}
            else:
                print(f"❌ {func_name}: функція не знайдена")
                results[func_name] = {'status': 'NOT_FOUND'}
                
    except ImportError as e:
        print(f"❌ Не вдалося імпортувати sync_management: {e}")
        results['sync_management'] = {'status': 'IMPORT_ERROR', 'error': str(e)}
    
    return results

def create_test_report(all_results):
    """Створює детальний звіт про тестування"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    report_content = f"""
ЗВІТ ТЕСТУВАННЯ ФУНКЦІЙ СЕРВЕРА
Дата: {timestamp}
Сервер: {os.uname().nodename if hasattr(os, 'uname') else 'Unknown'}
Директорія: {os.getcwd()}
Python версія: {sys.version}

"""
    
    for test_name, results in all_results.items():
        report_content += f"\n📋 {test_name.upper()}\n"
        report_content += "-" * 40 + "\n"
        
        success_count = 0
        total_count = 0
        
        for item_name, item_result in results.items():
            total_count += 1
            status = item_result.get('status', 'UNKNOWN')
            
            if status in ['OK', 'SUCCESS']:
                success_count += 1
                report_content += f"✅ {item_name}: {status}\n"
            elif status in ['NOT_FOUND', 'FAILED']:
                report_content += f"⚠️  {item_name}: {status}\n"
            else:
                report_content += f"❌ {item_name}: {status}\n"
                if 'error' in item_result:
                    report_content += f"   Помилка: {item_result['error']}\n"
        
        if total_count > 0:
            success_rate = (success_count / total_count) * 100
            report_content += f"\nУспішність: {success_count}/{total_count} ({success_rate:.1f}%)\n"
    
    # Загальні рекомендації
    report_content += f"""

🎯 ЗАГАЛЬНІ РЕКОМЕНДАЦІЇ:

1. КРИТИЧНО ВАЖЛИВО:
   - Перевірте роботу бота: ps aux | grep bot.py
   - Протестуйте команди: /sync_status, /hvirtka, /vorota
   - Моніторьте логи: tail -f bot.log

2. МОНІТОРИНГ:
   - Перевіряйте логи webhook_processor.log
   - Стежте за помилками в bot.log
   - Контролюйте розмір баз даних

3. ПІДТРИМКА:
   - При проблемах звертайтеся: +380733103110
   - Backup файли знаходяться в /home/gomoncli/backup/
   - Документація: SYNC_IMPROVEMENTS.md

СТАТУС СИСТЕМИ: {"🟢 ГОТОВА ДО РОБОТИ" if success_rate > 80 else "🟡 ПОТРЕБУЄ УВАГИ" if success_rate > 50 else "🔴 КРИТИЧНІ ПРОБЛЕМИ"}
"""
    
    # Зберігаємо звіт
    report_file = f"server_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"\n📄 Детальний звіт збережено: {report_file}")
    except Exception as e:
        print(f"⚠️  Не вдалося зберегти звіт: {e}")
    
    return report_content

def main():
    """Головна функція тестування"""
    print("🚀 ЗАПУСК КОМПЛЕКСНОГО ТЕСТУВАННЯ СЕРВЕРА")
    print("=" * 50)
    print(f"Час початку: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Директорія: {os.getcwd()}")
    print()
    
    # Виконуємо всі тести
    all_results = {}
    
    try:
        all_results['database_connections'] = test_database_connections()
        all_results['sync_functions'] = test_sync_functions()
        all_results['api_connections'] = test_api_connections()
        all_results['webhook_logic'] = test_webhook_logic()
        all_results['bot_commands'] = test_new_bot_commands()
        
    except Exception as e:
        print(f"❌ Критична помилка під час тестування: {e}")
        return 1
    
    # Створюємо звіт
    report = create_test_report(all_results)
    
    # Підсумок
    print("\n" + "=" * 50)
    print("🎉 ТЕСТУВАННЯ ЗАВЕРШЕНО!")
    print("=" * 50)
    
    # Підрахунок загальної успішності
    total_success = 0
    total_tests = 0
    
    for results in all_results.values():
        for result in results.values():
            total_tests += 1
            if result.get('status') in ['OK', 'SUCCESS']:
                total_success += 1
    
    if total_tests > 0:
        overall_success = (total_success / total_tests) * 100
        print(f"📊 ЗАГАЛЬНА УСПІШНІСТЬ: {total_success}/{total_tests} ({overall_success:.1f}%)")
        
        if overall_success >= 90:
            print("🟢 СИСТЕМА ПОВНІСТЮ ГОТОВА ДО РОБОТИ")
            return 0
        elif overall_success >= 70:
            print("🟡 СИСТЕМА ПРАЦЮЄ, АЛЕ ПОТРЕБУЄ УВАГИ")
            return 0
        else:
            print("🔴 ВИЯВЛЕНО КРИТИЧНІ ПРОБЛЕМИ")
            return 1
    else:
        print("❌ НЕ ВДАЛОСЯ ВИКОНАТИ ЖОДНОГО ТЕСТУ")
        return 1

if __name__ == "__main__":
    exit(main())
