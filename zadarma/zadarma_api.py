# zadarma_api.py - Enhanced version with call status tracking
import logging
import hashlib
import hmac
import base64
import requests
import json
import time
import threading
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
        
        # Крок 4: формуємо заголовок авторизації
        auth = self.key + ':' + signature
        return auth

# Глобальний екземпляр API
zadarma_api = ZadarmaAPI(ZADARMA_API_KEY, ZADARMA_API_SECRET)

def send_telegram_message(chat_id, message):
    """Відправляє повідомлення в Telegram з HTML форматуванням"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"📤 Повідомлення відправлено в чат {chat_id}")
        else:
            logger.error(f"❌ Помилка відправки повідомлення (код {response.status_code})")
    except Exception as e:
        logger.error(f"❌ Помилка надсилання повідомлення: {e}")

def send_error_to_admin(message):
    """Відправляє повідомлення про помилку адміну"""
    send_telegram_message(ADMIN_USER_ID, f"🔧 ADMIN: {message}")

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

