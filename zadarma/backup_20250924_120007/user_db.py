# user_db.py - Enhanced version with logging
import sqlite3
import threading
import logging

logger = logging.getLogger(__name__)

DB_PATH = "/home/gomoncli/zadarma/users.db"
_lock = threading.Lock()

def init_db():
    logger.info("🔄 Ініціалізація бази даних...")
    with _lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS clients (
                    id TEXT PRIMARY KEY,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT UNIQUE
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    phone TEXT,
                    username TEXT,
                    first_name TEXT
                )
            ''')
            conn.commit()
            conn.close()
            logger.info("✅ База даних успішно ініціалізована")
        except Exception as e:
            logger.exception(f"❌ Помилка ініціалізації бази даних: {e}")
            raise

def normalize_phone(phone):
    normalized = ''.join(filter(str.isdigit, phone))
    logger.debug(f"📞 Нормалізація номеру: '{phone}' → '{normalized}'")
    return normalized

def add_or_update_client(client_id, first_name, last_name, phone):
    """Покращена версія з правильною обробкою оновлень"""
    logger.info(f"👤 Додавання/оновлення клієнта: {client_id} ({first_name} {last_name}), телефон: {phone}")
    
    with _lock:
        try:
            conn = sqlite3.connect(DB_PATH)
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
            
        except Exception as e:
            logger.exception(f"❌ Помилка при обробці клієнта {client_id}: {e}")
            raise

def find_client_by_phone(phone):
    logger.info(f"🔍 Пошук клієнта за номером: {phone}")
    with _lock:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10.0)  # Додаємо таймаут
            cursor = conn.cursor()
            phone_norm = normalize_phone(phone)
            search_pattern = f'%{phone_norm[-9:]}%'
            logger.info(f"🔍 Нормалізований номер: {phone_norm}")
            logger.info(f"🔍 Шукаємо за патерном: {search_pattern}")
            
            # Спочатку подивимося, скільки взагалі клієнтів в базі
            cursor.execute('SELECT COUNT(*) FROM clients')
            total_clients = cursor.fetchone()[0]
            logger.info(f"📊 Загальна кількість клієнтів в базі: {total_clients}")
            
            if total_clients == 0:
                logger.warning("⚠️  Таблиця clients пуста!")
                conn.close()
                return None
            
            # Перевіримо, чи є точний збіг
            logger.info(f"🔍 Шукаємо точний збіг для: {phone_norm}")
            cursor.execute('''
                SELECT id, first_name, last_name, phone FROM clients
                WHERE phone = ?
                LIMIT 1
            ''', (phone_norm,))
            exact_match = cursor.fetchone()
            
            if exact_match:
                result = {
                    "id": exact_match[0],
                    "first_name": exact_match[1],
                    "last_name": exact_match[2],
                    "phone": exact_match[3]
                }
                logger.info(f"✅ Знайдено точний збіг: {result}")
                conn.close()
                return result
            
            # Якщо точного збігу немає, шукаємо за патерном
            logger.info(f"🔍 Точного збігу немає, шукаємо за патерном: {search_pattern}")
            cursor.execute('''
                SELECT id, first_name, last_name, phone FROM clients
                WHERE phone LIKE ?
                LIMIT 1
            ''', (search_pattern,))
            row = cursor.fetchone()
            
            if row:
                result = {
                    "id": row[0],
                    "first_name": row[1],
                    "last_name": row[2],
                    "phone": row[3]
                }
                logger.info(f"✅ Знайдено клієнта за патерном: {result}")
                conn.close()
                return result
            else:
                # Покажемо приклади номерів для діагностики
                cursor.execute('SELECT phone FROM clients LIMIT 5')
                sample_phones = cursor.fetchall()
                logger.info(f"📋 Приклади номерів в базі: {[p[0] for p in sample_phones]}")
                
                logger.info(f"❌ Клієнта за номером {phone} (патерн {search_pattern}) не знайдено")
                conn.close()
                return None
                
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Помилка SQL операції: {e}")
            if 'database is locked' in str(e):
                logger.error("🔒 База даних заблокована! Можливо, іде синхронізація.")
            return None
        except Exception as e:
            logger.exception(f"❌ Помилка пошуку клієнта за номером {phone}: {e}")
            return None

def store_user(telegram_id, phone, username, first_name):
    logger.info(f"💾 Збереження користувача: {telegram_id} (@{username}, {first_name}), телефон: {phone}")
    with _lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            phone_norm = normalize_phone(phone)

            # зберігаємо в таблицю users
            cursor.execute('''
                INSERT OR REPLACE INTO users (telegram_id, phone, username, first_name)
                VALUES (?, ?, ?, ?)
            ''', (telegram_id, phone_norm, username, first_name))
            logger.info(f"✅ Користувач {telegram_id} збережений в таблицю users")

            # шукаємо відповідного клієнта
            search_pattern = f'%{phone_norm[-9:]}%'
            cursor.execute('''
                SELECT id FROM clients WHERE phone LIKE ?
                LIMIT 1
            ''', (search_pattern,))
            row = cursor.fetchone()

            # якщо знайдено — оновлюємо telegram_id як id клієнта
            if row:
                client_id = telegram_id
                cursor.execute('''
                    UPDATE clients
                    SET id = ?
                    WHERE phone LIKE ?
                ''', (client_id, search_pattern))
                logger.info(f"✅ Оновлено ID клієнта на {client_id} для номеру {phone}")
            else:
                logger.info(f"ℹ️  Клієнта з номером {phone} не знайдено в базі")

            conn.commit()
            conn.close()
            logger.info(f"✅ Користувач {telegram_id} успішно збережений")
            
        except Exception as e:
            logger.exception(f"❌ Помилка збереження користувача {telegram_id}: {e}")
            raise

def update_clients(clients):
    logger.info(f"🔄 Оновлення {len(clients)} клієнтів...")
    with _lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            updated_count = 0
            
            for client in clients:
                client_id = client.get("id")
                first_name = client.get("first_name", "")
                last_name = client.get("last_name", "")
                phone = normalize_phone(client.get("phone", ""))
                
                cursor.execute('''
                    INSERT INTO clients(id, first_name, last_name, phone)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        first_name=excluded.first_name,
                        last_name=excluded.last_name,
                        phone=excluded.phone
                ''', (client_id, first_name, last_name, phone))
                updated_count += 1
                
            conn.commit()
            conn.close()
            logger.info(f"✅ Оновлено {updated_count} клієнтів")
            
        except Exception as e:
            logger.exception(f"❌ Помилка оновлення клієнтів: {e}")
            raise

def is_authorized_user_simple(telegram_id):
    """Спрощена версія авторизації без складних пошуків"""
    logger.info(f"🔍 Спрощена перевірка авторизації для користувача: {telegram_id}")
    
    # КРИТИЧНО: Перевірка адмінів в першу чергу!
    try:
        from config import ADMIN_USER_IDS
        admin_list = ADMIN_USER_IDS
    except ImportError:
        # Fallback для старої конфігурації
        from config import ADMIN_USER_ID
        admin_list = [ADMIN_USER_ID]
    
    if telegram_id in admin_list:
        logger.info(f"👑 Користувач {telegram_id} є АДМІНОМ - доступ дозволено")
        return True
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=3.0)
        cursor = conn.cursor()
        
        # Отримуємо телефон користувача
        cursor.execute('SELECT phone FROM users WHERE telegram_id = ?', (telegram_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            logger.info(f"❌ Користувача {telegram_id} не знайдено")
            conn.close()
            return False
            
        phone = normalize_phone(user_row[0])
        logger.info(f"✅ Телефон користувача: {phone}")
        
        # Шукаємо точний збіг телефону
        cursor.execute('SELECT id, first_name, last_name FROM clients WHERE phone = ?', (phone,))
        client_row = cursor.fetchone()
        
        conn.close()
        
        if client_row:
            logger.info(f"✅ Знайдено клієнта: {client_row[1]} {client_row[2]}")
            return True
        else:
            logger.info(f"❌ Клієнта з номером {phone} не знайдено")
            return False
            
    except Exception as e:
        logger.exception(f"❌ Помилка авторизації: {e}")
        return False

def is_authorized_user(telegram_id):
    """Основна функція авторизації з fallback"""
    try:
        # Спочатку пробуємо спрощений метод
        return is_authorized_user_simple(telegram_id)
    except Exception as e:
        logger.error(f"❌ Помилка в основній авторизації: {e}")
        return False

# Додаткова функція для діагностики
def get_user_info(telegram_id):
    """Отримує повну інформацію про користувача для діагностики"""
    logger.info(f"ℹ️  Отримання інформації про користувача: {telegram_id}")
    
    with _lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Інформація з таблиці users
            cursor.execute('''
                SELECT telegram_id, phone, username, first_name FROM users 
                WHERE telegram_id = ?
            ''', (telegram_id,))
            user_row = cursor.fetchone()
            
            # Загальна кількість клієнтів
            cursor.execute('SELECT COUNT(*) FROM clients')
            clients_count = cursor.fetchone()[0]
            
            # Загальна кількість користувачів
            cursor.execute('SELECT COUNT(*) FROM users')
            users_count = cursor.fetchone()[0]
            
            conn.close()
            
            info = {
                "user_in_db": user_row is not None,
                "user_data": user_row,
                "clients_count": clients_count,
                "users_count": users_count
            }
            
            logger.info(f"ℹ️  Інформація про користувача {telegram_id}: {info}")
            return info
            
        except Exception as e:
            logger.exception(f"❌ Помилка отримання інформації про користувача {telegram_id}: {e}")
            return None

def add_test_client(telegram_id, phone):
    """Додає тестового клієнта для діагностики"""
    logger.info(f"🧪 Додавання тестового клієнта: {telegram_id}, {phone}")
    
    try:
        # Отримуємо інформацію про користувача
        with _lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT first_name, username FROM users WHERE telegram_id = ?
            ''', (telegram_id,))
            user_row = cursor.fetchone()
            
            if user_row:
                first_name = user_row[0]
                username = user_row[1]
                
                # Додаємо як клієнта
                phone_norm = normalize_phone(phone)
                cursor.execute('''
                    INSERT OR REPLACE INTO clients (id, first_name, last_name, phone)
                    VALUES (?, ?, ?, ?)
                ''', (telegram_id, first_name, f"Test_{username}", phone_norm))
                
                conn.commit()
                logger.info(f"✅ Тестовий клієнт {telegram_id} додано")
            else:
                logger.warning(f"⚠️  Користувача {telegram_id} не знайдено в таблиці users")
                
            conn.close()
            
    except Exception as e:
        logger.exception(f"❌ Помилка додавання тестового клієнта: {e}")
        raise

def force_full_sync():
    """Примусова повна синхронізація з очищенням застарілих даних"""
    logger.info("🔄 ПРИМУСОВА ПОВНА СИНХРОНІЗАЦІЯ")
    
    try:
        # Крок 1: Створюємо резервну таблицю
        with _lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Створюємо backup поточних клієнтів
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS clients_backup AS 
                SELECT * FROM clients WHERE 1=0
            ''')
            cursor.execute('DELETE FROM clients_backup')
            cursor.execute('INSERT INTO clients_backup SELECT * FROM clients')
            
            # Очищуємо поточну таблицю
            cursor.execute('DELETE FROM clients')
            conn.commit()
            conn.close()
            
            logger.info("🗑️ Стара таблиця clients очищена, створено backup")
        
        # Крок 2: Завантажуємо свіжі дані
        from wlaunch_api import fetch_all_clients
        new_count = fetch_all_clients()
        
        # Крок 3: Перевіряємо результат
        with _lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM clients')
            current_count = cursor.fetchone()[0]
            conn.close()
        
        if current_count > 0:
            logger.info(f"✅ Повна синхронізація успішна: {current_count} клієнтів")
            # Видаляємо backup
            with _lock:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute('DROP TABLE clients_backup')
                conn.commit()
                conn.close()
            return True
        else:
            # Щось пішло не так - відновлюємо з backup
            logger.error("❌ Синхронізація не вдалася, відновлюємо з backup")
            with _lock:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM clients')
                cursor.execute('INSERT INTO clients SELECT * FROM clients_backup')
                cursor.execute('DROP TABLE clients_backup')
                conn.commit()
                conn.close()
            return False
            
    except Exception as e:
        logger.exception(f"❌ Критична помилка повної синхронізації: {e}")
        return False

def cleanup_duplicate_phones():
    """Очищення дублікатів номерів телефонів"""
    logger.info("🧹 Очищення дублікатів номерів")
    
    with _lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Знаходимо дублікати
            cursor.execute('''
                SELECT phone, COUNT(*) as count 
                FROM clients 
                GROUP BY phone 
                HAVING count > 1
            ''')
            
            duplicates = cursor.fetchall()
            cleaned_count = 0
            
            for phone, count in duplicates:
                logger.info(f"📞 Знайдено {count} дублікатів для номера {phone}")
                
                # Залишаємо запис з найменшим rowid (найстарший)
                cursor.execute('''
                    DELETE FROM clients 
                    WHERE phone = ? AND rowid NOT IN (
                        SELECT MIN(rowid) FROM clients WHERE phone = ?
                    )
                ''', (phone, phone))
                
                cleaned_count += cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Видалено {cleaned_count} дублікатів")
            return cleaned_count
            
        except Exception as e:
            logger.exception(f"❌ Помилка очищення дублікатів: {e}")
            return 0

def sync_specific_client(client_id, phone):
    """Синхронізує конкретного клієнта з WLaunch API"""
    logger.info(f"🎯 Синхронізація конкретного клієнта: {client_id}, телефон: {phone}")
    
    try:
        from wlaunch_api import find_client_by_phone
        
        # Шукаємо в WLaunch
        wlaunch_data = find_client_by_phone(phone)
        
        if wlaunch_data:
            # Оновлюємо в локальній базі
            add_or_update_client(
                client_id=wlaunch_data.get('id', client_id),
                first_name=wlaunch_data.get('first_name', ''),
                last_name=wlaunch_data.get('last_name', ''),
                phone=wlaunch_data.get('phone', phone)
            )
            logger.info(f"✅ Клієнт {client_id} синхронізовано з WLaunch")
            return True
        else:
            logger.warning(f"⚠️ Клієнт з номером {phone} не знайдено в WLaunch")
            return False
            
    except Exception as e:
        logger.exception(f"❌ Помилка синхронізації клієнта {client_id}: {e}")
        return False