# user_db.py — ОНОВЛЕНА ВЕРСІЯ з підтримкою послуг та візитів
# Розташування: /home/gomoncli/zadarma/user_db.py
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
                    phone TEXT UNIQUE,
                    last_service TEXT DEFAULT '',
                    last_visit TEXT DEFAULT '',
                    visits_count INTEGER DEFAULT 0
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

            # Міграція: додати нові колонки якщо їх немає
            for col, col_type, default in [
                ('last_service', 'TEXT', '""'),
                ('last_visit', 'TEXT', '""'),
                ('visits_count', 'INTEGER', '0')
            ]:
                try:
                    cursor.execute('SELECT {} FROM clients LIMIT 1'.format(col))
                except sqlite3.OperationalError:
                    logger.info("🔄 Міграція: додаємо колонку {}".format(col))
                    cursor.execute('ALTER TABLE clients ADD COLUMN {} {} DEFAULT {}'.format(
                        col, col_type, default))

            conn.commit()
            conn.close()
            logger.info("✅ База даних успішно ініціалізована")
        except Exception as e:
            logger.exception("❌ Помилка ініціалізації бази даних: {}".format(e))
            raise


def normalize_phone(phone):
    normalized = ''.join(filter(str.isdigit, phone))
    logger.debug("📞 Нормалізація: '{}' -> '{}'".format(phone, normalized))
    return normalized


def add_or_update_client(client_id, first_name, last_name, phone,
                         last_service="", last_visit="", visits_count=0):
    """Додає або оновлює клієнта з інформацією про послуги та візити"""
    logger.info("👤 Клієнт: {} ({} {}), тел: {}".format(
        client_id, first_name, last_name, phone))

    with _lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            phone_norm = normalize_phone(phone)

            # Перевіряємо чи існує
            cursor.execute('SELECT phone FROM clients WHERE id = ?', (client_id,))
            existing_by_id = cursor.fetchone()

            cursor.execute('SELECT id FROM clients WHERE phone = ?', (phone_norm,))
            existing_by_phone = cursor.fetchone()

            if existing_by_id:
                cursor.execute('''
                    UPDATE clients
                    SET first_name=?, last_name=?, phone=?,
                        last_service=?, last_visit=?, visits_count=?
                    WHERE id=?
                ''', (first_name, last_name, phone_norm,
                      last_service, last_visit, visits_count, client_id))
                logger.info("✅ Оновлено клієнта {}".format(client_id))

            elif existing_by_phone:
                cursor.execute('DELETE FROM clients WHERE phone = ?', (phone_norm,))
                cursor.execute('''
                    INSERT INTO clients (id, first_name, last_name, phone,
                                        last_service, last_visit, visits_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (client_id, first_name, last_name, phone_norm,
                      last_service, last_visit, visits_count))
                logger.info("🆔 Оновлено за телефоном {}".format(phone_norm))

            else:
                cursor.execute('''
                    INSERT INTO clients (id, first_name, last_name, phone,
                                        last_service, last_visit, visits_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (client_id, first_name, last_name, phone_norm,
                      last_service, last_visit, visits_count))
                logger.info("🆕 Новий клієнт {}".format(client_id))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.exception("❌ Помилка клієнта {}: {}".format(client_id, e))
            raise


def find_client_by_phone(phone):
    """Пошук клієнта з повною інформацією (послуги, візити)"""
    logger.info("🔍 Пошук за номером: {}".format(phone))
    with _lock:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10.0)
            cursor = conn.cursor()
            phone_norm = normalize_phone(phone)
            search_pattern = '%{}%'.format(phone_norm[-9:])

            cursor.execute('SELECT COUNT(*) FROM clients')
            total_clients = cursor.fetchone()[0]
            logger.info("📊 Клієнтів в базі: {}".format(total_clients))

            if total_clients == 0:
                logger.warning("⚠️ Таблиця clients пуста!")
                conn.close()
                return None

            # Точний збіг
            cursor.execute('''
                SELECT id, first_name, last_name, phone,
                       last_service, last_visit, visits_count
                FROM clients WHERE phone = ? LIMIT 1
            ''', (phone_norm,))
            row = cursor.fetchone()

            if row:
                result = {
                    "id": row[0], "first_name": row[1], "last_name": row[2],
                    "phone": row[3],
                    "last_service": row[4] if row[4] else "",
                    "last_visit": row[5] if row[5] else "",
                    "visits_count": row[6] if row[6] else 0
                }
                logger.info("✅ Точний збіг: {}".format(result))
                conn.close()
                return result

            # Пошук за патерном
            cursor.execute('''
                SELECT id, first_name, last_name, phone,
                       last_service, last_visit, visits_count
                FROM clients WHERE phone LIKE ? LIMIT 1
            ''', (search_pattern,))
            row = cursor.fetchone()

            if row:
                result = {
                    "id": row[0], "first_name": row[1], "last_name": row[2],
                    "phone": row[3],
                    "last_service": row[4] if row[4] else "",
                    "last_visit": row[5] if row[5] else "",
                    "visits_count": row[6] if row[6] else 0
                }
                logger.info("✅ Збіг за патерном: {}".format(result))
                conn.close()
                return result

            logger.info("❌ Не знайдено: {}".format(phone))
            conn.close()
            return None

        except sqlite3.OperationalError as e:
            logger.error("❌ SQL помилка: {}".format(e))
            return None
        except Exception as e:
            logger.exception("❌ Помилка пошуку {}: {}".format(phone, e))
            return None


def store_user(telegram_id, phone, username, first_name):
    logger.info("💾 Користувач: {} (@{}, {}), тел: {}".format(
        telegram_id, username, first_name, phone))
    with _lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            phone_norm = normalize_phone(phone)

            cursor.execute('''
                INSERT OR REPLACE INTO users (telegram_id, phone, username, first_name)
                VALUES (?, ?, ?, ?)
            ''', (telegram_id, phone_norm, username, first_name))

            search_pattern = '%{}%'.format(phone_norm[-9:])
            cursor.execute('''
                SELECT id FROM clients WHERE phone LIKE ? LIMIT 1
            ''', (search_pattern,))
            row = cursor.fetchone()

            if row:
                cursor.execute('''
                    UPDATE clients SET id = ? WHERE phone LIKE ?
                ''', (telegram_id, search_pattern))
                logger.info("✅ Оновлено ID клієнта на {}".format(telegram_id))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.exception("❌ Помилка збереження {}: {}".format(telegram_id, e))
            raise


def update_clients(clients):
    logger.info("🔄 Оновлення {} клієнтів...".format(len(clients)))
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
                last_service = client.get("last_service", "")
                last_visit = client.get("last_visit", "")
                visits_count = client.get("visits_count", 0)

                cursor.execute('''
                    INSERT INTO clients(id, first_name, last_name, phone,
                                        last_service, last_visit, visits_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        first_name=excluded.first_name,
                        last_name=excluded.last_name,
                        phone=excluded.phone,
                        last_service=excluded.last_service,
                        last_visit=excluded.last_visit,
                        visits_count=excluded.visits_count
                ''', (client_id, first_name, last_name, phone,
                      last_service, last_visit, visits_count))
                updated_count += 1

            conn.commit()
            conn.close()
            logger.info("✅ Оновлено {} клієнтів".format(updated_count))

        except Exception as e:
            logger.exception("❌ Помилка оновлення: {}".format(e))
            raise


def is_authorized_user_simple(telegram_id):
    """Спрощена авторизація"""
    logger.info("🔍 Перевірка авторизації: {}".format(telegram_id))

    try:
        from config import ADMIN_USER_IDS
        admin_list = ADMIN_USER_IDS
    except ImportError:
        from config import ADMIN_USER_ID
        admin_list = [ADMIN_USER_ID]

    if telegram_id in admin_list:
        logger.info("👑 Адмін {} - доступ дозволено".format(telegram_id))
        return True

    try:
        conn = sqlite3.connect(DB_PATH, timeout=3.0)
        cursor = conn.cursor()

        cursor.execute('SELECT phone FROM users WHERE telegram_id = ?', (telegram_id,))
        user_row = cursor.fetchone()

        if not user_row:
            conn.close()
            return False

        phone = normalize_phone(user_row[0])
        cursor.execute('SELECT id, first_name, last_name FROM clients WHERE phone = ?', (phone,))
        client_row = cursor.fetchone()
        conn.close()

        if client_row:
            logger.info("✅ Авторизовано: {} {}".format(client_row[1], client_row[2]))
            return True
        return False

    except Exception as e:
        logger.exception("❌ Помилка авторизації: {}".format(e))
        return False


def is_authorized_user(telegram_id):
    try:
        return is_authorized_user_simple(telegram_id)
    except Exception as e:
        logger.error("❌ Помилка авторизації: {}".format(e))
        return False


def get_user_info(telegram_id):
    """Діагностична інформація про користувача"""
    with _lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute('SELECT telegram_id, phone, username, first_name FROM users WHERE telegram_id = ?',
                           (telegram_id,))
            user_row = cursor.fetchone()

            cursor.execute('SELECT COUNT(*) FROM clients')
            clients_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM users')
            users_count = cursor.fetchone()[0]

            conn.close()
            return {
                "user_in_db": user_row is not None,
                "user_data": user_row,
                "clients_count": clients_count,
                "users_count": users_count
            }
        except Exception as e:
            logger.exception("❌ Помилка: {}".format(e))
            return None


def force_full_sync():
    """Примусова повна синхронізація"""
    logger.info("🔄 ПРИМУСОВА ПОВНА СИНХРОНІЗАЦІЯ")
    try:
        with _lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('CREATE TABLE IF NOT EXISTS clients_backup AS SELECT * FROM clients WHERE 1=0')
            cursor.execute('DELETE FROM clients_backup')
            cursor.execute('INSERT INTO clients_backup SELECT * FROM clients')
            cursor.execute('DELETE FROM clients')
            conn.commit()
            conn.close()

        from wlaunch_api import fetch_all_clients
        new_count = fetch_all_clients()

        with _lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM clients')
            current_count = cursor.fetchone()[0]
            conn.close()

        if current_count > 0:
            logger.info("✅ Синхронізація: {} клієнтів".format(current_count))
            with _lock:
                conn = sqlite3.connect(DB_PATH)
                conn.execute('DROP TABLE IF EXISTS clients_backup')
                conn.commit()
                conn.close()
            return True
        else:
            logger.error("❌ Синхронізація пуста, відновлюємо backup")
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
        logger.exception("❌ Критична помилка: {}".format(e))
        return False


def sync_specific_client(client_id, phone):
    """Синхронізує конкретного клієнта з WLaunch API (використовується sync_management.py)"""
    logger.info("🎯 Синхронізація клієнта: {}, тел: {}".format(client_id, phone))
    try:
        from wlaunch_api import find_client_by_phone
        wlaunch_data = find_client_by_phone(phone)
        if wlaunch_data:
            add_or_update_client(
                client_id=wlaunch_data.get('id', client_id),
                first_name=wlaunch_data.get('first_name', ''),
                last_name=wlaunch_data.get('last_name', ''),
                phone=wlaunch_data.get('phone', phone),
                last_service=wlaunch_data.get('last_service', ''),
                last_visit=wlaunch_data.get('last_visit', ''),
                visits_count=wlaunch_data.get('visits_count', 0)
            )
            logger.info("✅ Клієнт {} синхронізовано".format(client_id))
            return True
        else:
            logger.warning("⚠️ Клієнта {} не знайдено в WLaunch".format(phone))
            return False
    except Exception as e:
        logger.exception("❌ Помилка синхронізації {}: {}".format(client_id, e))
        return False


def cleanup_duplicate_phones():
    """Очищення дублікатів"""
    logger.info("🧹 Очищення дублікатів")
    with _lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT phone, COUNT(*) as count FROM clients
                GROUP BY phone HAVING count > 1
            ''')
            duplicates = cursor.fetchall()
            cleaned_count = 0

            for phone, count in duplicates:
                cursor.execute('''
                    DELETE FROM clients
                    WHERE phone = ? AND rowid NOT IN (
                        SELECT MIN(rowid) FROM clients WHERE phone = ?
                    )
                ''', (phone, phone))
                cleaned_count += cursor.rowcount

            conn.commit()
            conn.close()
            logger.info("✅ Видалено {} дублікатів".format(cleaned_count))
            return cleaned_count
        except Exception as e:
            logger.exception("❌ Помилка: {}".format(e))
            return 0
