# wlaunch_api.py - Виправлена версія з правильними імпортами
import requests
import logging
from config import WLAUNCH_API_KEY, COMPANY_ID
from user_db import add_or_update_client

logger = logging.getLogger("wlaunch_api")

# Wlaunch API конфігурація - ВИПРАВЛЕНО за документацією
WLAUNCH_API_URL = "https://api.wlaunch.net/v1"  # Правильний домен та версія
WLAUNCH_API_BEARER = f"Bearer {WLAUNCH_API_KEY}"

HEADERS = {
    "Authorization": WLAUNCH_API_BEARER,
    "Accept": "application/json"
}

def fetch_all_clients():
    """Отримує клієнтів з Wlaunch API - ВИПРАВЛЕНО за офіційною документацією"""
    logger.info("🔄 Початок синхронізації клієнтів з Wlaunch...")
    
    try:
        # Спочатку отримуємо список філій
        logger.info("📥 Отримуємо список філій...")
        branches_url = f"{WLAUNCH_API_URL}/company/{COMPANY_ID}/branch/"
        branches_params = {
            "active": "true",
            "sort": "ordinal",
            "page": 0,
            "size": 100
        }
        
        response = requests.get(branches_url, headers=HEADERS, params=branches_params, timeout=15)
        response.raise_for_status()
        branches_data = response.json()
        
        logger.info(f"📋 Знайдено {len(branches_data.get('content', []))} філій")
        
        total_clients = 0
        
        # Обробляємо кожну філію
        for branch in branches_data.get("content", []):
            branch_id = branch.get("id")
            branch_name = branch.get("name")
            
            logger.info(f"🏢 Обробляємо філію: {branch_name} ({branch_id})")
            
            # Отримуємо клієнтів з notification_settings цієї філії
            notification_settings = branch.get("notification_settings", {})
            telegram_contacts = notification_settings.get("telegram", [])
            
            logger.info(f"📱 Знайдено {len(telegram_contacts)} Telegram контактів")
            
            # Додаємо кожен Telegram контакт як клієнта
            for contact in telegram_contacts:
                try:
                    chat_id = contact.get("chat_id")
                    phone = contact.get("phone")
                    
                    if chat_id and phone:
                        # Використовуємо chat_id як client_id
                        add_or_update_client(
                            client_id=chat_id,
                            first_name="Клієнт",  # Ім'я не передається в API
                            last_name=f"від {branch_name}",
                            phone=phone
                        )
                        total_clients += 1
                        
                        logger.info(f"✅ Додано клієнта: {chat_id} ({phone})")
                    else:
                        logger.warning(f"⚠️ Пропущено контакт без chat_id або phone: {contact}")
                        
                except Exception as e:
                    logger.error(f"❌ Помилка обробки контакту {contact}: {e}")
            
            # Також можна спробувати отримати записи (appointments) для більшої інформації
            # але це потребує додаткових параметрів часу
            
        logger.info(f"✅ Синхронізація завершена. Оброблено {total_clients} клієнтів")
        return total_clients
        
    except requests.exceptions.Timeout:
        logger.error(f"⏰ Таймаут при підключенні до Wlaunch API")
        return 0
    except requests.exceptions.RequestException as e:
        logger.error(f"🌐 Мережева помилка Wlaunch API: {e}")
        return 0
    except Exception as e:
        logger.error(f"❌ Загальна помилка синхронізації: {e}")
        return 0

def test_wlaunch_connection():
    """Тестує підключення до Wlaunch API - ВИПРАВЛЕНО"""
    try:
        logger.info("🧪 Тестування підключення до Wlaunch API...")
        
        # Тестуємо отримання списку філій
        url = f"{WLAUNCH_API_URL}/company/{COMPANY_ID}/branch/"
        params = {"page": 0, "size": 1, "active": "true"}
        
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        total_elements = data.get("page", {}).get("total_elements", 0)
        
        logger.info(f"✅ Підключення до Wlaunch працює. Загальна кількість філій: {total_elements}")
        
        # Показуємо інформацію про першу філію
        if data.get("content"):
            branch = data["content"][0]
            branch_name = branch.get("name")
            telegram_contacts = branch.get("notification_settings", {}).get("telegram", [])
            logger.info(f"🏢 Перша філія: {branch_name}, Telegram контактів: {len(telegram_contacts)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Помилка підключення до Wlaunch API: {e}")
        return False

def find_client_by_phone(phone):
    """Знаходить клієнта в Wlaunch за номером телефону - ВИПРАВЛЕНО"""
    try:
        logger.info(f"🔍 Пошук клієнта в Wlaunch за номером: {phone}")
        
        # Отримуємо список філій
        url = f"{WLAUNCH_API_URL}/company/{COMPANY_ID}/branch/"
        params = {
            "page": 0,
            "size": 100,
            "active": "true"
        }
        
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        branches = data.get("content", [])
        
        # Нормалізуємо номер для порівняння
        normalized_search = ''.join(filter(str.isdigit, phone))
        
        # Проходимо по всіх філіях
        for branch in branches:
            notification_settings = branch.get("notification_settings", {})
            telegram_contacts = notification_settings.get("telegram", [])
            
            # Перевіряємо кожен Telegram контакт
            for contact in telegram_contacts:
                contact_phone = contact.get("phone", "")
                # Нормалізуємо номер для порівняння
                normalized_contact = ''.join(filter(str.isdigit, contact_phone))
                
                # Перевіряємо часткові збіги
                if (normalized_search in normalized_contact or 
                    normalized_contact in normalized_search or
                    normalized_search[-9:] == normalized_contact[-9:]):  # Останні 9 цифр
                    
                    logger.info(f"✅ Знайдено клієнта в Wlaunch: {contact.get('chat_id')} ({contact_phone})")
                    
                    # Повертаємо в форматі схожому на старий API
                    return {
                        "id": contact.get("chat_id"),
                        "first_name": "Клієнт",
                        "last_name": f"від {branch.get('name', '')}",
                        "phone": contact_phone,
                        "branch_name": branch.get("name")
                    }
        
        logger.info(f"❌ Клієнта з номером {phone} не знайдено в Wlaunch")
        return None
        
    except Exception as e:
        logger.error(f"❌ Помилка пошуку клієнта в Wlaunch: {e}")
        return None

if __name__ == "__main__":
    # Тестування при прямому запуску
    logging.basicConfig(level=logging.INFO)
    
    if test_wlaunch_connection():
        total = fetch_all_clients()
        print(f"Синхронізовано {total} клієнтів")
    else:
        print("Помилка підключення до API")
