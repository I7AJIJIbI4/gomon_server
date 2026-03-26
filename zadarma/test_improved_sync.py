#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_improved_sync.py - Тестування покращеної логіки синхронізації

Цей скрипт тестує нову логіку синхронізації клієнтів,
перевіряючи різні сценарії оновлень та дублікатів.
"""

import sys
import os
import logging
import sqlite3
import tempfile
from datetime import datetime

# Налаштування логування для тестів
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def create_test_db():
    """Створює тестову базу даних"""
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    conn = sqlite3.connect(temp_db.name)
    cursor = conn.cursor()
    
    # Створюємо таблиці
    cursor.execute('''
        CREATE TABLE clients (
            id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            phone TEXT UNIQUE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE users (
            telegram_id INTEGER PRIMARY KEY,
            phone TEXT,
            username TEXT,
            first_name TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    
    logger.info(f"📝 Створена тестова БД: {temp_db.name}")
    return temp_db.name

def normalize_phone(phone):
    """Нормалізація телефону"""
    return ''.join(filter(str.isdigit, phone))

def add_or_update_client_improved(db_path, client_id, first_name, last_name, phone):
    """Покращена версія з правильною обробкою оновлень"""
    logger.info(f"👤 Додавання/оновлення клієнта: {client_id} ({first_name} {last_name}), телефон: {phone}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        phone_norm = normalize_phone(phone)
        
        # КРОК 1: Перевіряємо, чи існує клієнт з таким ID
        cursor.execute('SELECT phone FROM clients WHERE id = ?', (client_id,))
        existing_by_id = cursor.fetchone()
        
        # КРОК 2: Перевіряємо, чи існує клієнт з таким телефоном
        cursor.execute('SELECT id, first_name, last_name FROM clients WHERE phone = ?', (phone_norm,))
        existing_by_phone = cursor.fetchone()
        
        if existing_by_id and existing_by_phone:
            # Випадок: є записи з тим же ID і з тим же телефоном
            if existing_by_id[0] == phone_norm:
                # Це той же клієнт - просто оновлюємо
                cursor.execute('''
                    UPDATE clients SET first_name=?, last_name=?, phone=? WHERE id=?
                ''', (first_name, last_name, phone_norm, client_id))
                logger.info(f"✅ Оновлено існуючого клієнта {client_id}")
            else:
                # Клієнт змінив номер - видаляємо старий запис з таким телефоном
                cursor.execute('DELETE FROM clients WHERE phone = ? AND id != ?', (phone_norm, client_id))
                cursor.execute('''
                    UPDATE clients SET first_name=?, last_name=?, phone=? WHERE id=?
                ''', (first_name, last_name, phone_norm, client_id))
                logger.info(f"🔄 Клієнт {client_id} змінив номер: {existing_by_id[0]} → {phone_norm}")
                
        elif existing_by_id:
            # Існує клієнт з таким ID, але телефон інший
            old_phone = existing_by_id[0]
            cursor.execute('''
                UPDATE clients SET first_name=?, last_name=?, phone=? WHERE id=?
            ''', (first_name, last_name, phone_norm, client_id))
            logger.info(f"📞 Клієнт {client_id} оновив телефон: {old_phone} → {phone_norm}")
            
        elif existing_by_phone:
            # Існує клієнт з таким телефоном, але ID інший
            old_id = existing_by_phone[0]
            cursor.execute('DELETE FROM clients WHERE phone = ?', (phone_norm,))
            cursor.execute('''
                INSERT INTO clients (id, first_name, last_name, phone)
                VALUES (?, ?, ?, ?)
            ''', (client_id, first_name, last_name, phone_norm))
            logger.info(f"🆔 Телефон {phone_norm} перейшов від клієнта {old_id} до {client_id}")
            
        else:
            # Новий клієнт
            cursor.execute('''
                INSERT INTO clients (id, first_name, last_name, phone)
                VALUES (?, ?, ?, ?)
            ''', (client_id, first_name, last_name, phone_norm))
            logger.info(f"🆕 Додано нового клієнта {client_id}")
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Клієнт {client_id} успішно оброблено")
        return True
        
    except Exception as e:
        logger.exception(f"❌ Помилка при обробці клієнта {client_id}: {e}")
        return False

def add_or_update_client_old(db_path, client_id, first_name, last_name, phone):
    """Стара версія для порівняння"""
    logger.info(f"👤 [СТАРА ЛОГІКА] Додавання/оновлення клієнта: {client_id}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        phone_norm = normalize_phone(phone)
        
        cursor.execute('''
            INSERT INTO clients(id, first_name, last_name, phone)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
            first_name=excluded.first_name,
            last_name=excluded.last_name,
            phone=excluded.phone
        ''', (client_id, first_name, last_name, phone_norm))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ [СТАРА ЛОГІКА] Клієнт {client_id} успішно оновлений")
        return True
        
    except Exception as e:
        logger.exception(f"❌ [СТАРА ЛОГІКА] Помилка при оновленні клієнта {client_id}: {e}")
        return False

def get_clients_info(db_path):
    """Отримує інформацію про клієнтів у базі"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, first_name, last_name, phone FROM clients ORDER BY id')
        clients = cursor.fetchall()
        
        conn.close()
        return clients
    except Exception as e:
        logger.error(f"❌ Помилка отримання клієнтів: {e}")
        return []

def test_scenario(name, db_path, test_func):
    """Запускає тестовий сценарій"""
    logger.info(f"🧪 ТЕСТОВИЙ СЦЕНАРІЙ: {name}")
    logger.info("=" * 50)
    
    # Очистити базу
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM clients')
    conn.commit()
    conn.close()
    
    # Запустити тест
    test_func(db_path)
    
    # Показати результат
    clients = get_clients_info(db_path)
    logger.info(f"📊 Результат тесту '{name}':")
    for client in clients:
        logger.info(f"   ID: {client[0]}, Ім'я: {client[1]} {client[2]}, Телефон: {client[3]}")
    
    logger.info(f"📊 Загалом клієнтів: {len(clients)}")
    logger.info("")
    
    return clients

def test_new_clients(db_path):
    """Тест додавання нових клієнтів"""
    add_or_update_client_improved(db_path, "1001", "Іван", "Петров", "0991234567")
    add_or_update_client_improved(db_path, "1002", "Марія", "Іванова", "0672345678")
    add_or_update_client_improved(db_path, "1003", "Олександр", "Сидоров", "0503456789")

def test_duplicate_phones(db_path):
    """Тест дублікатів телефонів"""
    add_or_update_client_improved(db_path, "1001", "Іван", "Петров", "0991234567")
    add_or_update_client_improved(db_path, "1002", "Марія", "Іванова", "0991234567")  # Той же номер!

def test_client_changed_phone(db_path):
    """Тест зміни телефону клієнта"""
    add_or_update_client_improved(db_path, "1001", "Іван", "Петров", "0991234567")
    add_or_update_client_improved(db_path, "1001", "Іван", "Петров", "0672345678")  # Новий номер

def test_phone_transfer(db_path):
    """Тест передачі номеру від одного клієнта іншому"""
    add_or_update_client_improved(db_path, "1001", "Іван", "Петров", "0991234567")
    add_or_update_client_improved(db_path, "1002", "Марія", "Іванова", "0672345678")
    
    # Тепер номер Івана переходить до Марії
    add_or_update_client_improved(db_path, "1002", "Марія", "Іванова", "0991234567")

def test_complex_scenario(db_path):
    """Складний сценарій з багатьма змінами"""
    # Початкові дані
    add_or_update_client_improved(db_path, "1001", "Іван", "Петров", "0991234567")
    add_or_update_client_improved(db_path, "1002", "Марія", "Іванова", "0672345678")
    add_or_update_client_improved(db_path, "1003", "Олександр", "Сидоров", "0503456789")
    
    # Іван змінює номер
    add_or_update_client_improved(db_path, "1001", "Іван", "Петров", "0631111111")
    
    # Новий клієнт отримує старий номер Івана
    add_or_update_client_improved(db_path, "1004", "Петро", "Коваль", "0991234567")
    
    # Марія оновлює дані
    add_or_update_client_improved(db_path, "1002", "Марія", "Іванова-Петрова", "0672345678")

def compare_old_vs_new_logic(db_path_old, db_path_new):
    """Порівнюємо стару та нову логіку"""
    logger.info("🆚 ПОРІВНЯННЯ СТАРОЇ ТА НОВОЇ ЛОГІКИ")
    logger.info("=" * 50)
    
    test_data = [
        ("1001", "Іван", "Петров", "0991234567"),
        ("1002", "Марія", "Іванова", "0672345678"),
        ("1001", "Іван", "Петров", "0631111111"),  # Зміна номеру
        ("1003", "Новий", "Клієнт", "0991234567"),  # Повторний номер
    ]
    
    # Стара логіка
    for client_data in test_data:
        add_or_update_client_old(db_path_old, *client_data)
    
    # Нова логіка
    for client_data in test_data:
        add_or_update_client_improved(db_path_new, *client_data)
    
    # Порівнюємо результати
    old_clients = get_clients_info(db_path_old)
    new_clients = get_clients_info(db_path_new)
    
    logger.info(f"📊 СТАРА ЛОГІКА - {len(old_clients)} клієнтів:")
    for client in old_clients:
        logger.info(f"   ID: {client[0]}, Ім'я: {client[1]} {client[2]}, Телефон: {client[3]}")
    
    logger.info(f"📊 НОВА ЛОГІКА - {len(new_clients)} клієнтів:")
    for client in new_clients:
        logger.info(f"   ID: {client[0]}, Ім'я: {client[1]} {client[2]}, Телефон: {client[3]}")
    
    # Перевіряємо дублікати телефонів
    old_phones = [client[3] for client in old_clients]
    new_phones = [client[3] for client in new_clients]
    
    old_duplicates = len(old_phones) - len(set(old_phones))
    new_duplicates = len(new_phones) - len(set(new_phones))
    
    logger.info(f"📊 Дублікати телефонів:")
    logger.info(f"   Стара логіка: {old_duplicates}")
    logger.info(f"   Нова логіка: {new_duplicates}")

def main():
    """Основна функція тестування"""
    logger.info("🚀 ЗАПУСК ТЕСТУВАННЯ ПОКРАЩЕНОЇ СИНХРОНІЗАЦІЇ")
    logger.info(f"⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    # Створюємо тестові БД
    test_db = create_test_db()
    old_db = create_test_db()
    new_db = create_test_db()
    
    try:
        # Тестові сценарії для нової логіки
        test_scenario("Додавання нових клієнтів", test_db, test_new_clients)
        test_scenario("Дублікати телефонів", test_db, test_duplicate_phones)
        test_scenario("Зміна телефону клієнта", test_db, test_client_changed_phone)
        test_scenario("Передача номеру між клієнтами", test_db, test_phone_transfer)
        test_scenario("Складний сценарій", test_db, test_complex_scenario)
        
        # Порівняння старої та нової логіки
        compare_old_vs_new_logic(old_db, new_db)
        
        logger.info("✅ ВСІ ТЕСТИ ЗАВЕРШЕНО УСПІШНО")
        
    except Exception as e:
        logger.exception(f"❌ Помилка в тестах: {e}")
    finally:
        # Видаляємо тестові файли
        for db_file in [test_db, old_db, new_db]:
            try:
                os.unlink(db_file)
                logger.info(f"🗑️ Видалено тестову БД: {db_file}")
            except:
                pass

if __name__ == "__main__":
    main()
