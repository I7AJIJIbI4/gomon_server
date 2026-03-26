#!/usr/bin/env python3
# test_sync.py - Тестування синхронізації з Wlaunch
import sys
import logging
import sqlite3

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_database():
    """Тестує стан бази даних"""
    print("=== ТЕСТУВАННЯ БАЗИ ДАНИХ ===")
    
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        
        # Перевіряємо таблиці
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"📋 Таблиці: {[t[0] for t in tables]}")
        
        # Кількість користувачів
        cursor.execute("SELECT COUNT(*) FROM users")
        users_count = cursor.fetchone()[0]
        print(f"👥 Користувачів: {users_count}")
        
        # Кількість клієнтів
        cursor.execute("SELECT COUNT(*) FROM clients")
        clients_count = cursor.fetchone()[0]
        print(f"🏥 Клієнтів: {clients_count}")
        
        # Показуємо останніх користувачів
        cursor.execute("SELECT telegram_id, username, first_name, phone FROM users ORDER BY telegram_id DESC LIMIT 3")
        recent_users = cursor.fetchall()
        print(f"\n📱 Останні користувачі:")
        for user in recent_users:
            print(f"  ID: {user[0]}, @{user[1]}, {user[2]}, 📞{user[3]}")
        
        # Показуємо останніх клієнтів
        cursor.execute("SELECT id, first_name, last_name, phone FROM clients ORDER BY id DESC LIMIT 5")
        recent_clients = cursor.fetchall()
        print(f"\n🏥 Останні клієнти:")
        for client in recent_clients:
            print(f"  ID: {client[0]}, {client[1]} {client[2]}, 📞{client[3]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Помилка бази даних: {e}")
        return False

def test_wlaunch_sync():
    """Тестує синхронізацію з Wlaunch"""
    print("\n=== ТЕСТУВАННЯ WLAUNCH СИНХРОНІЗАЦІЇ ===")
    
    try:
        from wlaunch_api import test_wlaunch_connection, fetch_all_clients, find_client_by_phone
        
        # Тестуємо підключення
        if not test_wlaunch_connection():
            print("❌ Не вдалося підключитися до Wlaunch API")
            return False
        
        # Пробуємо знайти конкретного клієнта
        test_phone = "380996093860"  # Номер з логів
        print(f"\n🔍 Шукаємо клієнта з номером {test_phone} в Wlaunch...")
        
        wlaunch_client = find_client_by_phone(test_phone)
        if wlaunch_client:
            print(f"✅ Знайдено в Wlaunch: {wlaunch_client.get('first_name')} {wlaunch_client.get('last_name')}")
            print(f"   ID: {wlaunch_client.get('id')}")
            print(f"   Телефон: {wlaunch_client.get('phone')}")
        else:
            print(f"❌ Клієнта з номером {test_phone} не знайдено в Wlaunch")
        
        return True
        
    except ImportError as e:
        print(f"❌ Помилка імпорту: {e}")
        return False
    except Exception as e:
        print(f"❌ Помилка тестування Wlaunch: {e}")
        return False

def test_user_authorization():
    """Тестує авторизацію користувача"""
    print("\n=== ТЕСТУВАННЯ АВТОРИЗАЦІЇ ===")
    
    try:
        from user_db import is_authorized_user_simple, find_client_by_phone
        
        # Тестуємо користувача з логів
        test_user_id = 827551951  # viktoria_gomon
        test_phone = "380996093860"
        
        print(f"🔍 Тестуємо авторизацію користувача {test_user_id}...")
        
        # Перевіряємо авторизацію
        is_auth = is_authorized_user_simple(test_user_id)
        print(f"🔐 Авторизований: {'✅ Так' if is_auth else '❌ Ні'}")
        
        # Шукаємо клієнта за телефоном
        client = find_client_by_phone(test_phone)
        if client:
            print(f"✅ Клієнт знайдений: {client['first_name']} {client['last_name']}")
        else:
            print(f"❌ Клієнт з номером {test_phone} не знайдений в локальній базі")
        
        return True
        
    except Exception as e:
        print(f"❌ Помилка тестування авторизації: {e}")
        return False

def manual_sync():
    """Запускає ручну синхронізацію"""
    print("\n=== РУЧНА СИНХРОНІЗАЦІЯ ===")
    
    try:
        from wlaunch_api import fetch_all_clients
        
        print("🔄 Запускаємо синхронізацію...")
        total = fetch_all_clients()
        print(f"✅ Синхронізовано {total} клієнтів")
        
        return True
        
    except Exception as e:
        print(f"❌ Помилка синхронізації: {e}")
        return False

def main():
    print("🔧 КОМПЛЕКСНИЙ ТЕСТ СИСТЕМИ")
    print("=" * 50)
    
    # Тестуємо базу даних
    if not test_database():
        print("❌ Критична помилка бази даних")
        return
    
    # Тестуємо Wlaunch
    if not test_wlaunch_sync():
        print("❌ Проблеми з Wlaunch API")
    
    # Тестуємо авторизацію
    if not test_user_authorization():
        print("❌ Проблеми з авторизацією")
    
    # Пропонуємо ручну синхронізацію
    print("\n" + "=" * 50)
    choice = input("🔄 Запустити ручну синхронізацію? (y/N): ")
    if choice.lower() in ['y', 'yes', 'так']:
        manual_sync()
        
        # Перетестуємо після синхронізації
        print("\n🔄 ПОВТОРНЕ ТЕСТУВАННЯ ПІСЛЯ СИНХРОНІЗАЦІЇ")
        test_user_authorization()
    
    print("\n✅ Тестування завершено")

if __name__ == "__main__":
    main()
