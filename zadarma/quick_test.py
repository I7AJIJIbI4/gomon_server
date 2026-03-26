#!/usr/bin/env python3
# quick_test.py - Швидкий тест після виправлень
import logging

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_wlaunch_api():
    """Швидкий тест Wlaunch API з правильними URL"""
    print("🧪 ШВИДКИЙ ТЕСТ WLAUNCH API")
    print("=" * 40)
    
    try:
        from wlaunch_api import test_wlaunch_connection, find_client_by_phone
        
        # Тест підключення
        print("\n📡 Тестуємо підключення...")
        if test_wlaunch_connection():
            print("✅ Підключення працює!")
            
            # Тест пошуку клієнта
            print("\n🔍 Тестуємо пошук клієнта...")
            client = find_client_by_phone("380996093860")
            if client:
                print(f"✅ Клієнт знайдений: {client}")
                return True
            else:
                print("❌ Клієнт не знайдений")
                return False
        else:
            print("❌ Підключення не працює")
            return False
            
    except Exception as e:
        print(f"❌ Помилка: {e}")
        return False

def test_user_authorization():
    """Тест авторизації після синхронізації"""
    print("\n🔐 ТЕСТ АВТОРИЗАЦІЇ")
    print("=" * 40)
    
    try:
        from wlaunch_api import fetch_all_clients
        from user_db import is_authorized_user_simple
        
        # Синхронізуємо клієнтів
        print("🔄 Синхронізуємо клієнтів...")
        total = fetch_all_clients()
        print(f"📊 Синхронізовано: {total} клієнтів")
        
        # Тестуємо авторизацію viktoria_gomon
        print("\n👤 Тестуємо авторизацію...")
        is_auth = is_authorized_user_simple(827551951)
        print(f"🔐 Viktoria Gomon авторизована: {'✅ ТАК' if is_auth else '❌ НІ'}")
        
        return is_auth
        
    except Exception as e:
        print(f"❌ Помилка: {e}")
        return False

def main():
    print("🚀 ШВИДКЕ ТЕСТУВАННЯ ПІСЛЯ ВИПРАВЛЕНЬ")
    print("=" * 50)
    
    # Тест 1: WLaunch API
    wlaunch_works = test_wlaunch_api()
    
    # Тест 2: Авторизація
    auth_works = test_user_authorization()
    
    # Підсумок
    print("\n" + "=" * 50)
    print("📊 РЕЗУЛЬТАТИ:")
    print(f"📡 WLaunch API: {'✅ Працює' if wlaunch_works else '❌ Не працює'}")
    print(f"🔐 Авторизація: {'✅ Працює' if auth_works else '❌ Не працює'}")
    
    if wlaunch_works and auth_works:
        print("\n🎉 ВСЕ ПРАЦЮЄ! Основні проблеми виправлено")
        return True
    else:
        print("\n⚠️ Є проблеми, потрібне додаткове налагодження")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
