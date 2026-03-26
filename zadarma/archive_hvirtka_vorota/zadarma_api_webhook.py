# zadarma_api_webhook.py - Версія без поллінгу, працює з webhook-ами
import logging
import hashlib
import hmac
import base64
import requests
import json
import time
import sqlite3
import os
from urllib.parse import urlencode
from collections import OrderedDict
from datetime import datetime
from config import (
    ZADARMA_API_KEY,
    ZADARMA_API_SECRET,
    ZADARMA_MAIN_PHONE,
    ADMIN_USER_ID,
    TELEGRAM_TOKEN,
    format_phone_for_zadarma,
    validate_phone_number
)

logger = logging.getLogger(__name__)

class ZadarmaAPI:
    def __init__(self, key, secret, is_sandbox=False):
        self.key = key
        self.secret = secret
        self.is_sandbox = is_sandbox
        self.__url_api = 'https://api.zadarma.com'
        if is_sandbox:
            self.__url_api = 'https://api-sandbox.zadarma.com'

    def call(self, method, params={}, request_type='GET', format='json', is_auth=True):
        """
        Function for send API request - точна копія з GitHub
        """
        logger.info(f"📡 Zadarma API call: {method}, params: {params}")
        
        request_type = request_type.upper()
        if request_type not in ['GET', 'POST', 'PUT', 'DELETE']:
            request_type = 'GET'
        
        params['format'] = format
        auth_str = None
        
        # Сортуємо параметри та створюємо query string
        params_string = urlencode(OrderedDict(sorted(params.items())))
        logger.info(f"🔐 Params string: {params_string}")

        if is_auth:
            auth_str = self.__get_auth_string_for_header(method, params_string)
            logger.info(f"🔐 Auth header: {auth_str}")

        url = self.__url_api + method
        logger.info(f"🌐 Request URL: {url}")

        try:
            if request_type == 'GET':
                if params_string:
                    url += '?' + params_string
                result = requests.get(url, headers={'Authorization': auth_str}, timeout=10)
            elif request_type == 'POST':
                result = requests.post(url, headers={'Authorization': auth_str}, data=params, timeout=10)
            elif request_type == 'PUT':
                result = requests.put(url, headers={'Authorization': auth_str}, data=params, timeout=10)
            elif request_type == 'DELETE':
                result = requests.delete(url, headers={'Authorization': auth_str}, data=params, timeout=10)

            logger.info(f"📡 Response status: {result.status_code}")
            logger.info(f"📡 Response: {result.text}")
            
            return result
            
        except requests.exceptions.Timeout:
            logger.error("❌ Таймаут запиту до Zadarma API")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Помилка запиту до Zadarma API: {e}")
            raise

    def __get_auth_string_for_header(self, method, params_string):
        """
        Офіційний алгоритм авторизації з GitHub
        """
        # Крок 1: створюємо рядок для підпису
        data = method + params_string + hashlib.md5(params_string.encode('utf8')).hexdigest()
        logger.debug(f"🔐 String to sign: {data}")
        
        # Крок 2: HMAC SHA1
        hmac_h = hmac.new(self.secret.encode('utf8'), data.encode('utf8'), hashlib.sha1)
        
        # Крок 3: ВАЖЛИВО! Спочатку hexdigest, потім base64
        hex_digest = hmac_h.hexdigest()
        logger.debug(f"🔐 HMAC hex digest: {hex_digest}")
        
        bts = bytes(hex_digest, 'utf8')
        signature = base64.b64encode(bts).decode()
        logger.debug(f"🔐 Final signature: {signature}")
        
        # Крок 4: форуємо заголовок авторизації
        auth = self.key + ':' + signature
        return auth

# Глобальний екземпляр API
zadarma_api = ZadarmaAPI(ZADARMA_API_KEY, ZADARMA_API_SECRET)

class CallTracker:
    """Клас для відстеження дзвінків через SQLite базу даних"""
    
    def __init__(self):
        self.db_path = "/home/gomoncli/zadarma/call_tracking.db"
        self.init_db()
        
    def init_db(self):
        """Ініціалізує базу даних для відстеження дзвінків"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
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
            
            conn.commit()
            conn.close()
            logger.info("✅ База даних для відстеження дзвінків ініціалізована")
            
        except Exception as e:
            logger.error(f"❌ Помилка ініціалізації бази даних: {e}")
    
    def register_call(self, call_id, user_id, chat_id, action_type, target_number):
        """Реєструє новий дзвінок для відстеження"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO call_tracking 
                (call_id, user_id, chat_id, action_type, target_number, start_time, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (call_id, user_id, chat_id, action_type, target_number, int(time.time()), 'initiated'))
            
            conn.commit()
            conn.close()
            
            logger.info(f"📋 Зареєстровано дзвінок для відстеження: {call_id}")
            
        except Exception as e:
            logger.error(f"❌ Помилка реєстрації дзвінка: {e}")
    
    def update_call_status(self, call_id, status, pbx_call_id=None):
        """Оновлює статус дзвінка"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if pbx_call_id:
                cursor.execute('''
                    UPDATE call_tracking 
                    SET status = ?, pbx_call_id = ?
                    WHERE call_id = ?
                ''', (status, pbx_call_id, call_id))
            else:
                cursor.execute('''
                    UPDATE call_tracking 
                    SET status = ?
                    WHERE call_id = ?
                ''', (status, call_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"📝 Оновлено статус дзвінка {call_id}: {status}")
            
        except Exception as e:
            logger.error(f"❌ Помилка оновлення статусу дзвінка: {e}")
    
    def get_call_by_pbx_id(self, pbx_call_id):
        """Отримує дані дзвінка по PBX call ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT call_id, user_id, chat_id, action_type, target_number, start_time, status
                FROM call_tracking 
                WHERE pbx_call_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            ''', (pbx_call_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'call_id': result[0],
                    'user_id': result[1], 
                    'chat_id': result[2],
                    'action_type': result[3],
                    'target_number': result[4],
                    'start_time': result[5],
                    'status': result[6]
                }
            return None
            
        except Exception as e:
            logger.error(f"❌ Помилка отримання дзвінка по PBX ID: {e}")
            return None

    def get_call_by_target_and_time(self, target_number, start_time_window=60):
        """Отримує дані дзвінка по номеру телефону і часовому вікну"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            current_time = int(time.time())
            time_start = current_time - start_time_window
            
            query = "SELECT call_id, user_id, chat_id, action_type, target_number, start_time, status FROM call_tracking WHERE target_number = ? AND start_time > ? AND status = 'api_success' ORDER BY start_time DESC LIMIT 1"
            cursor.execute(query, (target_number, time_start))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'call_id': result[0],
                    'user_id': result[1], 
                    'chat_id': result[2],
                    'action_type': result[3],
                    'target_number': result[4],
                    'start_time': result[5],
                    'status': result[6]
                }
            return None
            
        except Exception as e:
            logger.error(f"❌ Помилка отримання дзвінка по номеру і часу: {e}")
            return None
    
    def cleanup_old_calls(self, hours=24):
        """Очищує старі записи дзвінків"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = int(time.time()) - (hours * 3600)
            
            cursor.execute('''
                DELETE FROM call_tracking 
                WHERE start_time < ?
            ''', (cutoff_time,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                logger.info(f"🧹 Очищено {deleted_count} старих записів дзвінків")
                
        except Exception as e:
            logger.error(f"❌ Помилка очищення старих дзвінків: {e}")

# Глобальний трекер
call_tracker = CallTracker()
    # Додайте ці методи в клас CallTracker в файлі zadarma_api_webhook.py

def get_recent_calls(self, time_window_seconds=300):
    """
    Отримує всі дзвінки за останній період
    
    Args:
        time_window_seconds: Вікно часу в секундах (за замовчуванням 5 хвилин)
    
    Returns:
        list: Список дзвінків
    """
    try:
        current_time = time.time()
        cutoff_time = current_time - time_window_seconds
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT call_id, chat_id, target_number, action_type, timestamp, status, pbx_call_id
            FROM call_tracking 
            WHERE timestamp > ?
            ORDER BY timestamp DESC
        """, (cutoff_time,))
        
        calls = []
        for row in cursor.fetchall():
            calls.append({
                'call_id': row[0],
                'chat_id': row[1], 
                'target_number': row[2],
                'action_type': row[3],
                'timestamp': row[4],
                'status': row[5],
                'pbx_call_id': row[6]
            })
        
        return calls
        
    except Exception as e:
        logger.error(f"❌ Помилка отримання нещодавніх дзвінків: {e}")
        return []

def get_call_by_target_and_time(self, target_number, time_window_seconds=120):
    """
    Покращена функція пошуку дзвінка по номеру та часу
    
    Args:
        target_number: Цільовий номер телефону
        time_window_seconds: Вікно часу для пошуку
    
    Returns:
        dict або None: Дані дзвінка
    """
    try:
        current_time = time.time()
        cutoff_time = current_time - time_window_seconds
        
        cursor = self.conn.cursor()
        
        # Шукаємо по точній відповідності
        cursor.execute("""
            SELECT call_id, chat_id, target_number, action_type, timestamp, status, pbx_call_id
            FROM call_tracking 
            WHERE target_number = ? AND timestamp > ? AND status IN ('pending', 'api_success')
            ORDER BY timestamp DESC
            LIMIT 1
        """, (target_number, cutoff_time))
        
        row = cursor.fetchone()
        if row:
            return {
                'call_id': row[0],
                'chat_id': row[1],
                'target_number': row[2], 
                'action_type': row[3],
                'timestamp': row[4],
                'status': row[5],
                'pbx_call_id': row[6]
            }
        
        # Якщо не знайдено точної відповідності, шукаємо по частковій
        # Нормалізуємо номер для пошуку
        normalized_target = target_number.lstrip('0').lstrip('38')
        
        cursor.execute("""
            SELECT call_id, chat_id, target_number, action_type, timestamp, status, pbx_call_id
            FROM call_tracking 
            WHERE (target_number LIKE ? OR target_number LIKE ?) 
            AND timestamp > ? AND status IN ('pending', 'api_success')
            ORDER BY timestamp DESC
            LIMIT 1
        """, (f'%{normalized_target}', f'%{target_number}%', cutoff_time))
        
        row = cursor.fetchone()
        if row:
            return {
                'call_id': row[0],
                'chat_id': row[1],
                'target_number': row[2],
                'action_type': row[3], 
                'timestamp': row[4],
                'status': row[5],
                'pbx_call_id': row[6]
            }
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Помилка пошуку дзвінка по номеру {target_number}: {e}")
        return None

def send_telegram_message(chat_id, message):
    """Відправляє повідомлення в Telegram з HTML форматуванням та retry логікою"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    # Спробуємо 3 рази з паузами
    for attempt in range(3):
        try:
            response = requests.post(url, data=payload, timeout=15)
            if response.status_code == 200:
                logger.info(f"📤 Повідомлення відправлено в чат {chat_id}")
                return True
            else:
                logger.warning(f"⚠️ Помилка відправки (спроба {attempt + 1}): код {response.status_code}")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.warning(f"⚠️ Мережева помилка відправки (спроба {attempt + 1}): {e}")
            if attempt < 2:  # Пауза тільки між спробами
                time.sleep(2)
        except Exception as e:
            logger.error(f"❌ Критична помилка надсилання повідомлення: {e}")
            break
    
    logger.error(f"❌ Не вдалося відправити повідомлення після 3 спроб")
    return False

def send_error_to_admin(message):
    """Відправляє повідомлення про помилку адміну"""
    send_telegram_message(ADMIN_USER_ID, f"🔧 ADMIN: {message}")

def make_zadarma_call_with_tracking(to_number: str, user_id: int, chat_id: int, action_type: str) -> dict:
    """
    Робить callback дзвінок через API з реєстрацією в базі для відстеження через webhook
    
    Args:
        to_number: номер для дзвінка
        user_id: ID користувача Telegram
        chat_id: ID чату для повідомлень  
        action_type: 'hvirtka' або 'vorota'
        
    Returns:
        dict: результат з полями success, call_id, message
    """
    logger.info(f"📞 Робимо дзвінок з відстеженням на номер: {to_number}")
    
    # Валідація номеру
    if not validate_phone_number(to_number):
        error_msg = f"Неправильний формат номеру: {to_number}"
        logger.error(f"❌ {error_msg}")
        return {"success": False, "message": error_msg}
    
    # Форматуємо номер призначення
    formatted_to = format_phone_for_zadarma(to_number)
    logger.info(f"📞 Відформатований номер TO: {formatted_to}")
    
    # Використовуємо основний номер
    from_number = ZADARMA_MAIN_PHONE
    logger.info(f"📞 Використовуємо FROM номер: {from_number}")
    
    try:
        params = {
            "from": from_number,
            "to": formatted_to,
        }
        
        # Генеруємо унікальний ID для відстеження
        call_id = f"{user_id}_{int(time.time())}"
        
        # Реєструємо дзвінок в базі ДО запиту API
        call_tracker.register_call(call_id, user_id, chat_id, action_type, formatted_to)
        
        # Робимо API запит
        response = zadarma_api.call('/v1/request/callback/', params, 'GET')
        
        # Парсимо відповідь
        try:
            result = json.loads(response.text)
        except json.JSONDecodeError:
            error_msg = f"Некоректна відповідь API: {response.text}"
            logger.error(f"❌ {error_msg}")
            # Оновлюємо статус в базі
            call_tracker.update_call_status(call_id, 'failed')
            return {"success": False, "message": error_msg}
        
        logger.info("🔍 CRITICAL: Before status check")
        logger.info("🔍 CRITICAL: result type: " + str(type(result)))
        logger.info("🔍 CRITICAL: result content: " + str(result))
        status_val = result.get("status")
        logger.info("🔍 CRITICAL: status value: " + str(status_val))
        if result.get("status") == "success":
            logger.info(f"✅ Успішний запит дзвінка з {from_number} на {formatted_to}")
            logger.info(f"📋 Повна відповідь: {result}")
            logger.info('🔍 DEBUG: Before API time processing')
            
            # Отримуємо time з відповіді API (якщо є)
            api_time = result.get('time')
            if api_time:
                # Можемо використати цей час для кращого відстеження
                logger.info(f"📅 API час: {api_time}")
            
            # Оновлюємо статус в базі
            logger.info('🔍 DEBUG: Before update_call_status')
            call_tracker.update_call_status(call_id, 'api_success')
            logger.info('🔍 DEBUG: After update_call_status')
            
            return {
                "success": True, 
                "call_id": call_id,
                "message": "Дзвінок ініційовано, очікуємо результат через webhook..."
            }
        else:
            error_msg = result.get("message", "Невідома помилка API")
            logger.warning(f"❌ Помилка API дзвінка: {error_msg}")
            # Оновлюємо статус в базі
            call_tracker.update_call_status(call_id, 'api_failed')
            return {"success": False, "message": error_msg}
            
    except Exception as e:
        error_msg = f"Помилка виклику API: {str(e)}"
        logger.exception(f"❌ {error_msg}")
        # Оновлюємо статус в базі, якщо call_id вже створено
        try:
            call_tracker.update_call_status(call_id, 'exception')
        except:
            pass
        return {"success": False, "message": error_msg}

def process_webhook_call_status(webhook_data):
    """
    Обробляє webhook події від Zadarma про статус дзвінків
    Викликається з webhook PHP скрипта
    """
    try:
        event = webhook_data.get('event', '')
        pbx_call_id = webhook_data.get('pbx_call_id', '')
        disposition = webhook_data.get('disposition', '')
        duration = int(webhook_data.get('duration', 0))
        
        logger.info(f"🔔 Webhook подія: {event}, PBX ID: {pbx_call_id}, Disposition: {disposition}")
        
        if event == 'NOTIFY_END':
            # Спочатку шукаємо по PBX ID
            call_data = call_tracker.get_call_by_pbx_id(pbx_call_id)
            
            # Якщо не знайдено, шукаємо по номеру телефону і часу
            if not call_data:
                # Визначаємо номер телефону з webhook даних
                caller_id = webhook_data.get('caller_id', '')
                called_did = webhook_data.get('called_did', '')
                
                # Нормалізуємо номери  
                target_number = None
                if '0637442017' in caller_id or '0637442017' in called_did:
                    target_number = '0637442017'
                elif '0930063585' in caller_id or '0930063585' in called_did:
                    target_number = '0930063585'
                
                if target_number:
                    call_data = call_tracker.get_call_by_target_and_time(target_number, 120)
                    if call_data:
                        logger.info(f"📞 Знайдено дзвінок по номеру {target_number}: {call_data['call_id']}")
            
            if call_data:
                logger.info(f"📞 Знайдено відстежуваний дзвінок: {call_data['call_id']}")
                
                action_name = "хвіртку" if call_data['action_type'] == 'hvirtka' else "ворота"
                chat_id = call_data['chat_id']
                
                # Аналізуємо результат дзвінка
                if disposition == 'cancel' and duration > 0:
                    # ✅ УСПІХ: Дзвінок скинуто після гудків
                    if action_name == 'хвіртку':
                        message = "✅ Хвіртка відчинена!"
                    elif action_name == 'ворота':
                        message = "✅ Ворота відчинено!"
                    else:
                        message = f"✅ {action_name.capitalize()} відчинено"
                    status = 'success'
                    logger.info(f"✅ SUCCESS: {action_name} відкрито успішно")
                    
                elif disposition == 'busy':
                    # ❌ ЗАЙНЯТО  
                    message = f"❌ Номер {action_name} зайнятий. Спробуйте ще раз через хвилину."
                    status = 'busy'
                    logger.warning(f"❌ BUSY: {action_name} зайнято")
                    
                elif disposition in ['cancel', 'no-answer'] and duration == 0:
                    # ❌ НЕ ВІДПОВІДАЄ
                    message = f"❌ Номер {action_name} не відповідає. Можливо проблеми зв'язку.\n\nСпробуйте ще раз або зателефонуйте нам за номером <a href=\"tel:+380733103110\">+380733103110</a>"
                    status = 'no_answer'
                    logger.warning(f"❌ NO_ANSWER: {action_name} не відповідає")
                    
                elif disposition == 'answered':
                    # ⚠️ ПРОБЛЕМА: Дзвінок прийняли замість скидання
                    message = f"⚠️ Дзвінок для відкриття {action_name} було прийнято.\nМожливо, система не налаштована правильно.\n\nЗверніться до підтримки: <a href=\"tel:+380733103110\">+380733103110</a>"
                    status = 'answered'
                    logger.error(f"⚠️ ANSWERED: Проблема налаштування - дзвінок на {action_name} прийнято")
                    
                    # Сповіщаємо адміна про проблему
                    send_error_to_admin(f"🚨 ПРОБЛЕМА: Дзвінок на {action_name} ({call_data['target_number']}) було ПРИЙНЯТО замість скидання! Перевірте налаштування.")
                    
                else:
                    # ❌ ІНША ПОМИЛКА
                    message = f"❌ Не вдалося відкрити {action_name}. Причина: {disposition}\n\nСпробуйте ще раз або зателефонуйте нам за номером <a href=\"tel:+380733103110\">+380733103110</a>"
                    status = 'failed'
                    logger.warning(f"❌ FAILED: {action_name} - {disposition}")
                
                # Відправляємо результат користувачу
                send_telegram_message(chat_id, message)
                
                # Оновлюємо статус в базі
                call_tracker.update_call_status(call_data['call_id'], status, pbx_call_id)
                
                logger.info(f"📤 Результат відправлено користувачу: {status}")
                
                return {"success": True, "status": status, "message": message}
            else:
                logger.info(f"ℹ️ Дзвінок {pbx_call_id} не відстежується нашою системою")
                
        elif event == 'NOTIFY_START':
            # Для початку дзвінка можемо оновити PBX call ID якщо знаходимо відповідний дзвінок
            # Поки що просто логуємо
            logger.info(f"📞 START: PBX ID {pbx_call_id}")
        
        return {"success": True, "message": "Webhook processed"}
        
    except Exception as e:
        logger.exception(f"❌ Помилка обробки webhook: {e}")
        return {"success": False, "message": str(e)}

# Функції для сумісності зі старим кодом
def make_zadarma_call(to_number: str) -> bool:
    """
    Стара функція для зворотної сумісності
    Робить дзвінок без відстеження статусу
    """
    result = make_zadarma_call_with_tracking(to_number, 0, 0, "legacy")
    return result["success"]

# Функції для тестування та діагностики
def test_zadarma_auth():
    """Тестуємо базову авторизацію"""
    logger.info("🧪 Тестування авторизації з офіційним API...")
    
    try:
        response = zadarma_api.call('/v1/info/balance/', {}, 'GET')
        result = json.loads(response.text)
        
        if result.get("status") == "success":
            balance = result.get("balance", "невідомо")
            currency = result.get("currency", "")
            logger.info(f"✅ Авторизація працює. Баланс: {balance} {currency}")
            return True
        else:
            logger.error(f"❌ Авторизація не працює: {result}")
            return False
            
    except Exception as e:
        logger.exception(f"❌ Помилка тестування авторизації: {e}")
        return False

def get_call_statistics(hours=24):
    """Отримує статистику дзвінків за останні години"""
    try:
        end_time = time.time()
        start_time = end_time - (hours * 3600)
        
        params = {
            'start': int(start_time),
            'end': int(end_time)
        }
        
        response = zadarma_api.call('/v1/statistics/', params, 'GET')
        result = json.loads(response.text)
        
        if result.get("status") == "success":
            calls = result.get('calls', [])
            logger.info(f"📊 Отримано статистику: {len(calls)} дзвінків за {hours} годин")
            return calls
        else:
            logger.error(f"❌ Помилка отримання статистики: {result}")
            return []
            
    except Exception as e:
        logger.exception(f"❌ Помилка отримання статистики дзвінків: {e}")
        return []

def cleanup_old_calls():
    """Очищає стару історію дзвінків"""
    call_tracker.cleanup_old_calls(24)  # Очищаємо дзвінки старше 24 годин

# Запуск очищення кожні 6 годин
def start_cleanup_scheduler():
    """Запускає періодичне очищення"""
    import threading
    
    def cleanup_loop():
        while True:
            time.sleep(6 * 3600)  # 6 годин
            cleanup_old_calls()
    
    thread = threading.Thread(target=cleanup_loop)
    thread.daemon = True
    thread.start()
    logger.info("🔄 Запущено автоочищення історії дзвінків")

# Ініціалізація при імпорті
if __name__ != "__main__":
    start_cleanup_scheduler()
def get_call_statistics(days=7):
    """
    Отримує статистику дзвінків за вказаний період
    """
    try:
        import time
        current_time = time.time()
        cutoff_time = current_time - (days * 24 * 3600)
        
        cursor = call_tracker.conn.cursor()
        
        cursor.execute("""
            SELECT 
                status,
                action_type,
                COUNT(*) as count
            FROM call_tracking 
            WHERE timestamp > ?
            GROUP BY status, action_type
            ORDER BY count DESC
        """, (cutoff_time,))
        
        stats = {
            'total_calls': 0,
            'success_rate': 0,
            'by_status': {},
            'by_action': {'hvirtka': 0, 'vorota': 0},
            'period_days': days
        }
        
        for row in cursor.fetchall():
            status, action_type, count = row
            stats['total_calls'] += count
            
            if status not in stats['by_status']:
                stats['by_status'][status] = 0
            stats['by_status'][status] += count
            
            if action_type in stats['by_action']:
                stats['by_action'][action_type] += count
        
        success_count = stats['by_status'].get('success', 0)
        if stats['total_calls'] > 0:
            stats['success_rate'] = round((success_count / stats['total_calls']) * 100, 1)
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Помилка отримання статистики: {e}")
        return None

# ВИПРАВЛЕННЯ 2025-08-06: Змінено логіку успішності дзвінків
# Успіх тепер = duration > 0 (були гудки) AND disposition = 'cancel' (скинули)
