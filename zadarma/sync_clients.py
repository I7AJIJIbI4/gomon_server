# sync_clients.py - Unified version with logging
import requests
import logging
import os
from datetime import datetime, timedelta
from user_db import update_clients, add_or_update_client
from config import COMPANY_ID, WLAUNCH_API_KEY, ADMIN_USER_ID, TELEGRAM_TOKEN

logger = logging.getLogger(__name__)

API_BASE = "https://api.wlaunch.net/v1"
FIRST_SYNC_FLAG_FILE = "/home/gomoncli/zadarma/.first_sync_done"

def get_clients(created_start=None, created_end=None, page=0, size=1000):
    """Отримує клієнтів з API з можливістю пагінації"""
    headers = {
        "Authorization": f"Bearer {WLAUNCH_API_KEY}",
        "Accept": "application/json"
    }
    params = {
        "sort": "created,desc",
        "page": page,
        "size": size,
    }
    
    if created_start and created_end:
        params["createdStart"] = created_start
        params["createdEnd"] = created_end
        
    logger.info(f"🌐 Запит до API: page={page}, size={size}, period={created_start} to {created_end}")
    
    try:
        response = requests.get(f"{API_BASE}/company/{COMPANY_ID}/client", headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        content = data.get("content", [])
        page_info = data.get("page", {})
        total_pages = page_info.get("total_pages", 1)
        current_page = page_info.get("number", 0)
        
        logger.info(f"✅ Отримано {len(content)} клієнтів (сторінка {current_page + 1}/{total_pages})")
        
        return {
            "content": content,
            "total_pages": total_pages,
            "current_page": current_page,
            "total_elements": page_info.get("total_elements", 0)
        }
        
    except Exception as e:
        logger.exception(f"❌ Помилка API запиту: {e}")
        send_admin_error(f"❌ Не вдалося отримати клієнтів з wlaunch: {e}")
        return {"content": [], "total_pages": 0, "current_page": 0, "total_elements": 0}

def fetch_all_clients_first_time():
    """Завантажує всіх клієнтів при першому запуску"""
    logger.info("🔄 Перший запуск: завантаження всіх клієнтів...")
    
    result = {"status": "ok", "count": 0, "clients": [], "errors": []}
    
    try:
        page = 0
        size = 100
        
        while True:
            api_result = get_clients(page=page, size=size)
            clients = api_result["content"]
            total_pages = api_result["total_pages"]
            
            if not clients:
                break
                
            for client in clients:
                try:
                    first_name = client.get("first_name") or ""
                    last_name = client.get("last_name") or ""
                    add_or_update_client(
                        client_id=client.get("id"),
                        first_name=first_name,
                        last_name=last_name,
                        phone=client.get("phone") or ""
                    )
                    result["count"] += 1
                    name = f"{first_name} {last_name}".strip()
                    if name:
                        result["clients"].append(name)
                except Exception as e:
                    logger.error(f"❌ Помилка додавання клієнта {client.get('id')}: {e}")
                    result["errors"].append(str(e))
            
            logger.info(f"📥 Оброблено {len(clients)} клієнтів на сторінці {page + 1}/{total_pages}")
            
            page += 1
            if page >= total_pages:
                break
        
        with open(FIRST_SYNC_FLAG_FILE, 'w') as f:
            f.write(datetime.now().isoformat())
            
        if result["errors"]:
            result["status"] = "warning"
        
        logger.info(f"✅ Перший синк завершено: завантажено {result['count']} клієнтів")
        send_admin_error(f"✅ Перший синк завершено: завантажено {result['count']} клієнтів")
        
    except Exception as e:
        logger.exception(f"❌ Помилка при першому синку: {e}")
        send_admin_error(f"❌ Помилка при першому синку: {e}")
        result["status"] = "error"
        result["errors"].append(str(e))
    
    return result

def fetch_recent_clients():
    """Завантажує клієнтів за останню добу"""
    logger.info("🔄 Оновлення клієнтів за останню добу...")
    
    result = {"status": "ok", "count": 0, "clients": [], "errors": []}
    
    try:
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        created_start = yesterday.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        created_end = now.strftime('%Y-%m-%dT%H:%M:%S.999Z')
        
        logger.info(f"📅 Період: {created_start} - {created_end}")
        
        page = 0
        
        while True:
            api_result = get_clients(created_start, created_end, page=page, size=100)
            clients = api_result["content"]
            total_pages = api_result["total_pages"]
            
            if not clients:
                break
                
            for client in clients:
                try:
                    first_name = client.get("first_name") or ""
                    last_name = client.get("last_name") or ""
                    add_or_update_client(
                        client_id=client.get("id"),
                        first_name=first_name,
                        last_name=last_name,
                        phone=client.get("phone") or ""
                    )
                    result["count"] += 1
                    name = f"{first_name} {last_name}".strip()
                    if name:
                        result["clients"].append(name)
                except Exception as e:
                    logger.error(f"❌ Помилка оновлення клієнта {client.get('id')}: {e}")
                    result["errors"].append(str(e))
            
            page += 1
            if page >= total_pages:
                break
        
        if result["errors"]:
            result["status"] = "warning"
        
        if result["count"] > 0:
            logger.info(f"✅ Оновлено {result['count']} клієнтів за останню добу")
            send_admin_error(f"✅ Оновлено {result['count']} клієнтів за останню добу")
        else:
            logger.info("ℹ️  Нових клієнтів за останню добу не знайдено")
            
    except Exception as e:
        logger.exception(f"❌ Помилка оновлення клієнтів: {e}")
        send_admin_error(f"❌ Помилка оновлення клієнтів: {e}")
        result["status"] = "error"
        result["errors"].append(str(e))
    
    return result

def is_first_sync_done():
    """Перевіряє, чи виконувався перший синк"""
    return os.path.exists(FIRST_SYNC_FLAG_FILE)

def send_admin_error(message):
    """Відправляє повідомлення адміну"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": ADMIN_USER_ID, "text": message}
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"📤 Повідомлення адміну відправлено: {message}")
        else:
            logger.error(f"❌ Помилка відправки адміну (код {response.status_code})")
    except Exception as e:
        logger.error(f"❌ Помилка надсилання повідомлення адміну: {e}")

def sync_clients():
    """Основна функція синхронізації"""
    logger.info("🔄 Запуск синхронізації клієнтів...")
    
    try:
        if not is_first_sync_done():
            logger.info("🆕 Перший запуск - завантажуємо всіх клієнтів")
            result = fetch_all_clients_first_time()
        else:
            logger.info("🔄 Звичайне оновлення - завантажуємо нових клієнтів")
            result = fetch_recent_clients()
            
        logger.info("✅ Синхронізація завершена")
        return result
        
    except Exception as e:
        logger.exception(f"❌ Критична помилка синхронізації: {e}")
        send_admin_error(f"❌ Критична помилка синхронізації: {e}")
        return {"status": "error", "count": 0, "clients": [], "errors": [str(e)]}

def force_full_sync():
    """Примусова повна синхронізація (для тестування)"""
    logger.info("🔄 Примусова повна синхронізація...")
    
    if os.path.exists(FIRST_SYNC_FLAG_FILE):
        os.remove(FIRST_SYNC_FLAG_FILE)
        logger.info("🗑️  Видалено флаг першого синку")
    
    return sync_clients()

if __name__ == "__main__":
    sync_clients()
