#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_admin_in_db.py - Перевірка чи адмін є в базі клієнтів
"""

import sys
import sqlite3

# Додаємо шлях до проєкту
sys.path.append('/home/gomoncli/zadarma')

try:
    from config import ADMIN_USER_ID
    from user_db import DB_PATH, normalize_phone
    
    print("🔍 ПЕРЕВІРКА АДМІНА В БАЗІ КЛІЄНТІВ")
    print("=" * 40)
    print(f"👑 Admin User ID: {ADMIN_USER_ID}")
    
    # Підключаємося до бази
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Перевіряємо чи адмін є в таблиці users
    print(f"\n1️⃣ Перевірка в таблиці users:")
    cursor.execute('SELECT telegram_id, phone, username, first_name FROM users WHERE telegram_id = ?', (ADMIN_USER_ID,))
    admin_user = cursor.fetchone()
    
    if admin_user:
        print(f"✅ Адмін знайдений в users:")
        print(f"   ID: {admin_user[0]}")
        print(f"   Phone: {admin_user[1]}")
        print(f"   Username: {admin_user[2]}")
        print(f"   Name: {admin_user[3]}")
        
        admin_phone = normalize_phone(admin_user[1])
        print(f"   Normalized phone: {admin_phone}")
        
        # 2. Перевіряємо чи цей номер є в таблиці clients
        print(f"\n2️⃣ Перевірка номеру {admin_phone} в таблиці clients:")
        
        # Точний пошук
        cursor.execute('SELECT id, first_name, last_name, phone FROM clients WHERE phone = ?', (admin_phone,))
        exact_client = cursor.fetchone()
        
        if exact_client:
            print(f"✅ ТОЧНИЙ ЗБІГ знайдено:")
            print(f"   Client ID: {exact_client[0]}")
            print(f"   Name: {exact_client[1]} {exact_client[2]}")
            print(f"   Phone: {exact_client[3]}")
        else:
            print(f"❌ Точного збігу НЕ знайдено")
            
            # Пошук по патерну
            search_pattern = f'%{admin_phone[-9:]}%'
            print(f"   Шукаємо по патерну: {search_pattern}")
            
            cursor.execute('SELECT id, first_name, last_name, phone FROM clients WHERE phone LIKE ?', (search_pattern,))
            pattern_client = cursor.fetchone()
            
            if pattern_client:
                print(f"✅ ЗБІГ ПО ПАТЕРНУ знайдено:")
                print(f"   Client ID: {pattern_client[0]}")
                print(f"   Name: {pattern_client[1]} {pattern_client[2]}")
                print(f"   Phone: {pattern_client[3]}")
            else:
                print(f"❌ Збігу по патерну НЕ знайдено")
    else:
        print(f"❌ Адміна НЕ знайдено в таблиці users")
    
    # 3. Показуємо статистику бази
    print(f"\n3️⃣ Статистика бази даних:")
    
    cursor.execute('SELECT COUNT(*) FROM users')
    users_count = cursor.fetchone()[0]
    print(f"   👥 Користувачів в users: {users_count}")
    
    cursor.execute('SELECT COUNT(*) FROM clients')
    clients_count = cursor.fetchone()[0]
    print(f"   🏥 Клієнтів в clients: {clients_count}")
    
    # 4. Показуємо приклади номерів клієнтів
    print(f"\n4️⃣ Приклади номерів в базі клієнтів:")
    cursor.execute('SELECT phone FROM clients LIMIT 10')
    sample_phones = cursor.fetchall()
    
    if sample_phones:
        for i, phone in enumerate(sample_phones, 1):
            print(f"   {i}. {phone[0]}")
    else:
        print("   📭 Таблиця clients пуста!")
        
    # 5. Рекомендації
    print(f"\n5️⃣ РЕКОМЕНДАЦІЇ:")
    
    if admin_user and not exact_client:
        print("⚠️  Адмін є в users, але НЕ є в clients")
        print("💡 Рішення: Додати адміна до clients або покладатися на перевірку ADMIN_USER_ID")
        
        print(f"\n🛠️  Команда для додавання адміна до clients:")
        print(f"INSERT INTO clients (id, first_name, last_name, phone) VALUES")
        print(f"('{ADMIN_USER_ID}', '{admin_user[3]}', 'Admin', '{admin_phone}');")
        
    elif admin_user and exact_client:
        print("✅ Все гаразд - адмін є і в users, і в clients")
        
    conn.close()
    
except Exception as e:
    print(f"❌ Помилка: {e}")
    import traceback
    traceback.print_exc()
