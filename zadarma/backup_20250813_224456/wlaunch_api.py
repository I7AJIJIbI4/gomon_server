# wlaunch_api.py - Виправлена версія з правильними імпортами
import requests
import logging
from config import WLAUNCH_API_KEY, COMPANY_ID
from user_db import add_or_update_client

logger = logging.getLogger("wlaunch_api")

# Wlaunch API конфігурація
WLAUNCH_API_URL = "https://api.wlaunch.com/api/v2"
WLAUNCH_API_BEARER = f"Bearer {WLAUNCH_API_KEY}"

HEADERS = {
    "Authorization": WLAUNCH_API_BEARER,
    "Accept": "application/json"
}

def fetch_all_clients():
    """Отримує всіх клієнтів з Wlaunch API"""
    logger.info("🔄 Початок синхронізації клієнтів з Wlaunch...")
    
    page = 0
    size = 100
    total_pages = 1
    total_clients = 0
    
    while page < total_pages:
        url = f"{WLAUNCH_API_URL}/company/{COMPANY_ID}/client"
        params = {
            "page": page,
            "size": size,
            "sort": "created,desc"
        }
        
        try:
            logger.info(f"📥 Завантажуємо сторінку {page + 1}...")
            response = requests.get(url, headers=HEADERS, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            total_pages = data.get("page", {}).get("total_pages", 1)
            clients = data.get("content", [])
            
            logger.info(f"📋 Знайдено {len(clients)} клієнтів на сторінці {page + 1}")
            
            for client in clients:
                try:
                    client_id = client.get("id")
                    first_name = client.get("first_name") or ""
                    last_name = client.get("last_name") or ""
                    phone = client.get("phone") or ""
                    
                    if client_id and phone:
                        add_or_update_client(
                            client_id=client_id,
                            first_name=first_name,
                            last_name=last_name,
                            phone=phone
                        )
                        total_clients += 1
                        
                        if total_clients % 50 == 0:
                            logger.info(f"✅ Оброблено {total_clients} клієнтів...")
                    else:
                        logger.warning(f"⚠️ Пропущено клієнта без ID або телефону: {client}")
                        
                except Exception as e:
                    logger.error(f"❌ Помилка обробки клієнта {client.get('id', 'Unknown')}: {e}")
                    
            page += 1
            
        except requests.exceptions.Timeout:
            logger.error(f"⏰ Таймаут при завантаженні сторінки {page + 1}")
            break
        except requests.exceptions.RequestException as e:
            logger.error(f"🌐 Мережева помилка на сторінці {page + 1}: {e}")
            break
        except Exception as e:
            logger.error(f"❌ Загальна помилка завантаження клієнтів на сторінці {page + 1}: {e}")
            break
            
    logger.info(f"✅ Синхронізація завершена. Оброблено {total_clients} клієнтів")
    return total_clients

def test_wlaunch_connection():
    """Тестує підключення до Wlaunch API"""
    try:
        logger.info("🧪 Тестування підключення до Wlaunch API...")
        
        url = f"{WLAUNCH_API_URL}/company/{COMPANY_ID}/client"
        params = {"page": 0, "size": 1}
        
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        total_elements = data.get("page", {}).get("total_elements", 0)
        
        logger.info(f"✅ Підключення до Wlaunch працює. Загальна кількість клієнтів: {total_elements}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Помилка підключення до Wlaunch API: {e}")
        return False

def find_client_by_phone(phone):
    """Знаходить клієнта в Wlaunch за номером телефону"""
    try:
        logger.info(f"🔍 Пошук клієнта в Wlaunch за номером: {phone}")
        
        url = f"{WLAUNCH_API_URL}/company/{COMPANY_ID}/client"
        params = {
            "page": 0,
            "size": 100,
            "search": phone
        }
        
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        clients = data.get("content", [])
        
        for client in clients:
            client_phone = client.get("phone", "")
            # Нормалізуємо номери для порівняння
            normalized_search = ''.join(filter(str.isdigit, phone))
            normalized_client = ''.join(filter(str.isdigit, client_phone))
            
            if normalized_search in normalized_client or normalized_client in normalized_search:
                logger.info(f"✅ Знайдено клієнта в Wlaunch: {client.get('first_name')} {client.get('last_name')}")
                return client
        
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
