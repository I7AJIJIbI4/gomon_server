import json
# wlaunch_api.py — ОНОВЛЕНА ВЕРСІЯ
# Використовує /appointment endpoint для реальних клієнтів з послугами та датами
# Розташування: /home/gomoncli/zadarma/wlaunch_api.py
import requests
import logging
from datetime import datetime, timedelta
from config import WLAUNCH_API_KEY, COMPANY_ID
from user_db import add_or_update_client

logger = logging.getLogger("wlaunch_api")

WLAUNCH_API_URL = "https://api.wlaunch.net/v1"

RESOURCE_SPECIALIST_MAP = {
    '380996093860': 'victoria',
    '380685129121': 'anastasia',
}

def get_specialist(resources):
    for r in (resources or []):
        phone = ''.join(filter(str.isdigit, r.get('phone', '') or ''))
        if phone in RESOURCE_SPECIALIST_MAP:
            return RESOURCE_SPECIALIST_MAP[phone]
        name = (r.get('name') or '').lower()
        if 'вікторі' in name or 'viktor' in name:
            return 'victoria'
        if 'анастасі' in name or 'anasta' in name:
            return 'anastasia'
    return None
WLAUNCH_API_BEARER = "Bearer {}".format(WLAUNCH_API_KEY)

HEADERS = {
    "Authorization": WLAUNCH_API_BEARER,
    "Accept": "application/json"
}


def get_branch_id():
    """Отримує ID першої активної філії"""
    try:
        url = "{}/company/{}/branch/".format(WLAUNCH_API_URL, COMPANY_ID)
        params = {"active": "true", "sort": "ordinal", "page": 0, "size": 1}
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        branches = data.get("content", [])
        if branches:
            branch_id = branches[0]["id"]
            logger.info("🏢 Філія: {} ({})".format(branches[0].get("name"), branch_id))
            return branch_id
        logger.error("❌ Немає активних філій")
        return None
    except Exception as e:
        logger.error("❌ Помилка отримання філії: {}".format(e))
        return None


def fetch_all_clients():
    """
    Синхронізація клієнтів через /appointment endpoint.
    Тягне записи за останні 3 роки, витягує клієнтів з послугами та датами.
    """
    logger.info("🔄 Початок синхронізації клієнтів з Wlaunch (appointments)...")

    branch_id = get_branch_id()
    if not branch_id:
        return 0

    url = "{}/company/{}/branch/{}/appointment".format(WLAUNCH_API_URL, COMPANY_ID, branch_id)

    # Записи за останні 3 роки
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=3 * 365)

    # Збираємо клієнтів: phone -> {дані}
    clients_map = {}
    page = 0
    max_pages = 50

    while page < max_pages:
        params = {
            "sort": "start_time,desc",
            "page": page,
            "size": 100,
            "start": start_date.strftime("%Y-%m-%dT00:00:00.000Z"),
            "end": end_date.strftime("%Y-%m-%dT23:59:59.999Z")
        }

        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error("❌ Помилка на сторінці {}: {}".format(page, e))
            break

        appointments = data.get("content", [])
        if not appointments:
            break

        for appt in appointments:
            client = appt.get("client")
            if not client:
                continue

            phone = client.get("phone", "")
            if not phone:
                continue

            phone_norm = ''.join(filter(str.isdigit, phone))
            if not phone_norm:
                continue

            client_id = client.get("id", phone_norm)
            first_name = client.get("first_name", "")
            last_name = client.get("last_name", "")

            # Витягуємо послугу
            services_list_appt = appt.get("services", [])
            service_name = ", ".join(s.get("name", "") for s in services_list_appt if s.get("name"))

            # Дата, година та статус запису
            visit_date = ""
            visit_hour = None  # година запису — для SMS нагадування в той самий час
            start_time = appt.get("start_time", "")
            if start_time:
                try:
                    visit_date = start_time[:10]  # YYYY-MM-DD
                    if len(start_time) >= 13:
                        visit_hour = int(start_time[11:13])  # година (0-23), UTC
                except Exception:
                    pass

            # Статус апоінтменту з wlaunch (CONFIRMED, DONE, CANCELLED, NO_SHOW тощо)
            appt_status = (appt.get("status") or "").upper()
            specialist = get_specialist(appt.get("resources", []))

            duration_min = (appt.get("duration") or 0) // 60 or 60
            entry = {"appt_id": appt.get("id",""), "date": visit_date, "hour": visit_hour,
                     "service": service_name, "status": appt_status, "specialist": specialist,
                     "duration_min": duration_min}

            # Оновлюємо або додаємо
            if phone_norm not in clients_map:
                clients_map[phone_norm] = {
                    "id": client_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone": phone_norm,
                    "last_service": service_name,
                    "last_visit": visit_date,
                    "visits_count": 1,
                    "services_history": [entry] if service_name and visit_date else []
                }
            else:
                clients_map[phone_norm]["visits_count"] += 1
                if not clients_map[phone_norm]["first_name"] and first_name:
                    clients_map[phone_norm]["first_name"] = first_name
                if not clients_map[phone_norm]["last_name"] and last_name:
                    clients_map[phone_norm]["last_name"] = last_name
                if service_name and visit_date and len(clients_map[phone_norm]["services_history"]) < 5:
                    updated = False
                    for existing in clients_map[phone_norm]["services_history"]:
                        if existing.get("date") == visit_date and existing.get("service") == service_name:
                            existing["status"] = appt_status
                            existing["specialist"] = specialist
                            updated = True
                            break
                    if not updated:
                        clients_map[phone_norm]["services_history"].append(entry)

        total_pages = data.get("page", {}).get("total_pages", 1)
        logger.info("📄 Сторінка {}/{}, записів: {}".format(page + 1, total_pages, len(appointments)))

        if page + 1 >= total_pages:
            break
        page += 1

    # Записуємо в базу
    total = 0
    for phone_norm, c in clients_map.items():
        try:
            add_or_update_client(
                client_id=c["id"],
                first_name=c["first_name"],
                last_name=c["last_name"],
                phone=c["phone"],
                last_service=c["last_service"],
                last_visit=c["last_visit"],
                visits_count=c["visits_count"],
                services_json=json.dumps(c.get("services_history", []), ensure_ascii=False)
            )
            total += 1
        except Exception as e:
            logger.error("❌ Помилка збереження {}: {}".format(c["phone"], e))

    total_visits = sum(c["visits_count"] for c in clients_map.values())
    logger.info("✅ Синхронізація: {} клієнтів з {} записів".format(total, total_visits))
    return total


def find_client_by_phone(phone):
    """Пошук клієнта — спершу локальна база, потім API"""
    from user_db import find_client_by_phone as local_find
    local_result = local_find(phone)
    if local_result:
        return local_result

    logger.info("🔍 Пошук {} через API...".format(phone))

    branch_id = get_branch_id()
    if not branch_id:
        return None

    url = "{}/company/{}/branch/{}/appointment".format(WLAUNCH_API_URL, COMPANY_ID, branch_id)
    normalized_search = ''.join(filter(str.isdigit, phone))

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=3 * 365)

    page = 0
    while page < 10:
        params = {
            "page": page,
            "size": 100,
            "sort": "start_time,desc",
            "start": start_date.strftime("%Y-%m-%dT00:00:00.000Z"),
            "end": end_date.strftime("%Y-%m-%dT23:59:59.999Z")
        }

        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error("❌ Помилка пошуку сторінка {}: {}".format(page, e))
            break

        appointments = data.get("content", [])
        if not appointments:
            break

        for appt in appointments:
            client = appt.get("client")
            if not client:
                continue
            client_phone = ''.join(filter(str.isdigit, client.get("phone", "")))
            if (normalized_search in client_phone or
                    client_phone in normalized_search or
                    normalized_search[-9:] == client_phone[-9:]):
                logger.info("✅ Знайдено в API: {} {}".format(
                    client.get("first_name"), client.get("last_name")))
                return {
                    "id": client.get("id"),
                    "first_name": client.get("first_name", ""),
                    "last_name": client.get("last_name", ""),
                    "phone": client_phone
                }

        page += 1

    logger.info("❌ Клієнта {} не знайдено".format(phone))
    return None


def test_wlaunch_connection():
    """Тестує підключення"""
    try:
        logger.info("🧪 Тестування Wlaunch API...")
        url = "{}/company/{}/branch/".format(WLAUNCH_API_URL, COMPANY_ID)
        params = {"page": 0, "size": 1, "active": "true"}
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        total = data.get("page", {}).get("total_elements", 0)
        logger.info("✅ Підключення працює. Філій: {}".format(total))

        branch_id = get_branch_id()
        if branch_id:
            appt_url = "{}/company/{}/branch/{}/appointment".format(
                WLAUNCH_API_URL, COMPANY_ID, branch_id)
            appt_params = {"page": 0, "size": 1, "sort": "start_time,desc"}
            appt_resp = requests.get(appt_url, headers=HEADERS, params=appt_params, timeout=10)
            appt_resp.raise_for_status()
            appt_data = appt_resp.json()
            appt_total = appt_data.get("page", {}).get("total_elements", 0)
            logger.info("📋 Записів в системі: {}".format(appt_total))

        return True
    except Exception as e:
        logger.error("❌ Помилка підключення: {}".format(e))
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if test_wlaunch_connection():
        total = fetch_all_clients()
        print("Синхронізовано {} клієнтів".format(total))
    else:
        print("Помилка підключення до API")
