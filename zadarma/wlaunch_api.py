import json
# wlaunch_api.py — ОНОВЛЕНА ВЕРСIЯ
# Використовує /appointment endpoint для реальних клієнтів з послугами та датами
# Розташування: /home/gomoncli/zadarma/wlaunch_api.py
import requests
import logging
from datetime import datetime, timedelta
from config import WLAUNCH_API_KEY, COMPANY_ID, WLAUNCH_API_URL, WLAUNCH_API_BEARER
from user_db import add_or_update_client
from tz_utils import utc_to_kyiv

logger = logging.getLogger("wlaunch_api")

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
        if '\u0432\u0456\u043a\u0442\u043e\u0440\u0456' in name or 'viktor' in name:
            return 'victoria'
        if '\u0430\u043d\u0430\u0441\u0442\u0430\u0441\u0456' in name or 'anasta' in name:
            return 'anastasia'
    return None


def parse_appt_time(start_time_str):
    """Parse WLaunch UTC start_time string to (kyiv_date_str, kyiv_hour, kyiv_minute).
    Uses appointment's own UTC datetime for correct DST offset."""
    if not start_time_str:
        return '', None, 0
    try:
        utc_dt = datetime.strptime(start_time_str[:19], '%Y-%m-%dT%H:%M:%S')
        kyiv_dt = utc_to_kyiv(utc_dt)
        return kyiv_dt.strftime('%Y-%m-%d'), kyiv_dt.hour, kyiv_dt.minute
    except Exception:
        visit_date = start_time_str[:10]
        visit_hour = None
        visit_minute = 0
        if len(start_time_str) >= 13:
            try:
                visit_hour = int(start_time_str[11:13])
                if len(start_time_str) >= 16:
                    visit_minute = int(start_time_str[14:16])
            except Exception:
                pass
        return visit_date, visit_hour, visit_minute


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
            logger.info("\U0001f3e2 \u0424\u0456\u043b\u0456\u044f: {} ({})".format(branches[0].get("name"), branch_id))
            return branch_id
        logger.error("\u274c \u041d\u0435\u043c\u0430\u0454 \u0430\u043a\u0442\u0438\u0432\u043d\u0438\u0445 \u0444\u0456\u043b\u0456\u0439")
        return None
    except Exception as e:
        logger.error("\u274c \u041f\u043e\u043c\u0438\u043b\u043a\u0430 \u043e\u0442\u0440\u0438\u043c\u0430\u043d\u043d\u044f \u0444\u0456\u043b\u0456\u0457: {}".format(e))
        return None


def fetch_all_clients():
    """
    Синхронізація клієнтів через /appointment endpoint.
    Тягне записи за останні 3 роки, витягує клієнтів з послугами та датами.
    """
    logger.info("\U0001f504 \u041f\u043e\u0447\u0430\u0442\u043e\u043a \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0456\u0437\u0430\u0446\u0456\u0457 \u043a\u043b\u0456\u0454\u043d\u0442\u0456\u0432 \u0437 Wlaunch (appointments)...")

    branch_id = get_branch_id()
    if not branch_id:
        return 0

    url = "{}/company/{}/branch/{}/appointment".format(WLAUNCH_API_URL, COMPANY_ID, branch_id)

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=3 * 365)

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
            logger.error("\u274c \u041f\u043e\u043c\u0438\u043b\u043a\u0430 \u043d\u0430 \u0441\u0442\u043e\u0440\u0456\u043d\u0446\u0456 {}: {}".format(page, e))
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

            services_list_appt = appt.get("services", [])
            service_name = ", ".join(s.get("name", "") for s in services_list_appt if s.get("name"))

            visit_date, visit_hour, visit_minute = parse_appt_time(appt.get("start_time", ""))

            appt_status = (appt.get("status") or "").upper()
            specialist = get_specialist(appt.get("resources", []))
            duration_min = (appt.get("duration") or 0) // 60 or 60

            entry = {"appt_id": appt.get("id",""), "date": visit_date, "hour": visit_hour,
                     "service": service_name, "status": appt_status, "specialist": specialist,
                     "duration_min": duration_min}

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
                if service_name and visit_date:
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
        logger.info("\U0001f4c4 \u0421\u0442\u043e\u0440\u0456\u043d\u043a\u0430 {}/{}, \u0437\u0430\u043f\u0438\u0441\u0456\u0432: {}".format(page + 1, total_pages, len(appointments)))

        if page + 1 >= total_pages:
            break
        page += 1

    # Записуємо в базу — сортуємо і обрізаємо до 15
    total = 0
    for phone_norm, c in clients_map.items():
        try:
            c['services_history'].sort(key=lambda x: x['date'], reverse=True)
            services_json = json.dumps(c['services_history'][:15], ensure_ascii=False)
            add_or_update_client(
                client_id=c["id"],
                first_name=c["first_name"],
                last_name=c["last_name"],
                phone=c["phone"],
                last_service=c["last_service"],
                last_visit=c["last_visit"],
                visits_count=c["visits_count"],
                services_json=services_json
            )
            total += 1
        except Exception as e:
            logger.error("\u274c \u041f\u043e\u043c\u0438\u043b\u043a\u0430 \u0437\u0431\u0435\u0440\u0435\u0436\u0435\u043d\u043d\u044f {}: {}".format(c["phone"], e))

    total_visits = sum(c["visits_count"] for c in clients_map.values())
    logger.info("\u2705 \u0421\u0438\u043d\u0445\u0440\u043e\u043d\u0456\u0437\u0430\u0446\u0456\u044f: {} \u043a\u043b\u0456\u0454\u043d\u0442\u0456\u0432 \u0437 {} \u0437\u0430\u043f\u0438\u0441\u0456\u0432".format(total, total_visits))
    return total


def find_client_by_phone(phone):
    """Пошук клієнта — спершу локальна база, потім API"""
    from user_db import find_client_by_phone as local_find
    local_result = local_find(phone)
    if local_result:
        return local_result

    logger.info("\U0001f50d \u041f\u043e\u0448\u0443\u043a {} \u0447\u0435\u0440\u0435\u0437 API...".format(phone))

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
            logger.error("\u274c \u041f\u043e\u043c\u0438\u043b\u043a\u0430 \u043f\u043e\u0448\u0443\u043a\u0443 \u0441\u0442\u043e\u0440\u0456\u043d\u043a\u0430 {}: {}".format(page, e))
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
                logger.info("\u2705 \u0417\u043d\u0430\u0439\u0434\u0435\u043d\u043e \u0432 API: {} {}".format(
                    client.get("first_name"), client.get("last_name")))
                return {
                    "id": client.get("id"),
                    "first_name": client.get("first_name", ""),
                    "last_name": client.get("last_name", ""),
                    "phone": client_phone
                }

        page += 1

    logger.info("\u274c \u041a\u043b\u0456\u0454\u043d\u0442\u0430 {} \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e".format(phone))
    return None


# Reverse map: specialist name -> WLaunch resource phone
SPECIALIST_PHONE_MAP = {v: k for k, v in RESOURCE_SPECIALIST_MAP.items()}


def find_wlaunch_client_id(phone):
    """Find WLaunch client UUID by phone. First tries /client search, then appointments."""
    normalized = ''.join(filter(str.isdigit, phone))
    if not normalized:
        return None

    # 1. Direct client search (with phone filter)
    url = "{}/company/{}/client".format(WLAUNCH_API_URL, COMPANY_ID)
    try:
        resp = requests.get(url, headers=HEADERS, params={"page": 0, "size": 50, "sort": "created,desc", "phone": normalized}, timeout=10)
        resp.raise_for_status()
        for c in resp.json().get("content", []):
            cp = ''.join(filter(str.isdigit, c.get("phone", "") or ""))
            if cp and normalized[-9:] == cp[-9:]:
                logger.info("WLaunch client found via /client: {}".format(c.get("id")))
                return c.get("id")
    except Exception as e:
        logger.warning("WLaunch /client search error: {}".format(e))

    # 2. Fallback: search through appointments
    branch_id = get_branch_id()
    if not branch_id:
        return None

    appt_url = "{}/company/{}/branch/{}/appointment".format(WLAUNCH_API_URL, COMPANY_ID, branch_id)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=365)

    for page in range(5):
        params = {
            "page": page, "size": 100, "sort": "start_time,desc",
            "start": start_date.strftime("%Y-%m-%dT00:00:00.000Z"),
            "end": end_date.strftime("%Y-%m-%dT23:59:59.999Z")
        }
        try:
            resp = requests.get(appt_url, headers=HEADERS, params=params, timeout=10)
            resp.raise_for_status()
            items = resp.json().get("content", [])
            if not items:
                break
            for appt in items:
                client = appt.get("client")
                if not client:
                    continue
                cp = ''.join(filter(str.isdigit, client.get("phone", "")))
                if normalized[-9:] == cp[-9:]:
                    return client.get("id")
        except Exception:
            break
    return None


def create_wlaunch_client(phone, first_name, last_name=""):
    """Create a new client in WLaunch. Returns client UUID or None."""
    url = "{}/company/{}/client".format(WLAUNCH_API_URL, COMPANY_ID)
    post_headers = dict(HEADERS)
    post_headers["Content-Type"] = "application/json"
    # WLaunch expects phone with + prefix
    fmt_phone = phone if phone.startswith("+") else "+" + phone
    data = {"client": {"first_name": first_name, "last_name": last_name, "phone": fmt_phone}}
    try:
        resp = requests.post(url, headers=post_headers, json=data, timeout=10)
        if resp.status_code in (200, 201):
            cid = resp.json().get("id")
            logger.info("WLaunch client created: {} ({})".format(cid, phone))
            return cid
        logger.error("WLaunch client create failed {}: {}".format(resp.status_code, resp.text[:200]))
    except Exception as e:
        logger.error("WLaunch client create error: {}".format(e))
    return None


def get_wlaunch_resources(branch_id=None):
    """Fetch WLaunch resources (specialists) for the branch. Returns {specialist_name: resource_id}."""
    if not branch_id:
        branch_id = get_branch_id()
    if not branch_id:
        return {}
    url = "{}/company/{}/branch/{}/resource".format(WLAUNCH_API_URL, COMPANY_ID, branch_id)
    try:
        resp = requests.get(url, headers=HEADERS, params={"page": 0, "size": 50}, timeout=10)
        resp.raise_for_status()
        result = {}
        for r in resp.json().get("content", []):
            phone = ''.join(filter(str.isdigit, r.get('phone', '') or ''))
            if phone in RESOURCE_SPECIALIST_MAP:
                result[RESOURCE_SPECIALIST_MAP[phone]] = r.get("id")
            else:
                name = (r.get('name') or '').lower()
                if '\u0432\u0456\u043a\u0442\u043e\u0440\u0456' in name:
                    result['victoria'] = r.get("id")
                elif '\u0430\u043d\u0430\u0441\u0442\u0430\u0441\u0456' in name:
                    result['anastasia'] = r.get("id")
        logger.info("WLaunch resources: {}".format(result))
        return result
    except Exception as e:
        logger.error("WLaunch resources error: {}".format(e))
        return {}


def get_wlaunch_services(branch_id=None):
    """Fetch WLaunch services. Returns {service_name_lower: service_id}."""
    if not branch_id:
        branch_id = get_branch_id()
    if not branch_id:
        return {}
    url = "{}/company/{}/branch/{}/service".format(WLAUNCH_API_URL, COMPANY_ID, branch_id)
    try:
        resp = requests.get(url, headers=HEADERS, params={"page": 0, "size": 200}, timeout=10)
        resp.raise_for_status()
        result = {}
        for s in resp.json().get("content", []):
            sname = (s.get("name") or "").strip()
            if sname:
                result[sname.lower()] = {"id": s.get("id"), "name": sname}
        logger.info("WLaunch services loaded: {} items".format(len(result)))
        return result
    except Exception as e:
        logger.error("WLaunch services error: {}".format(e))
        return {}


def create_wlaunch_appointment(client_phone, client_name, procedure_name,
                                specialist, date_str, time_str, duration_min):
    """
    Create appointment in WLaunch CRM. Best-effort — returns (wl_appt_id, error).
    If WLaunch doesn't have the client, appointment is still created locally.

    date_str: YYYY-MM-DD (Kyiv time)
    time_str: HH:MM (Kyiv time)
    duration_min: int
    """
    from tz_utils import kyiv_offset

    branch_id = get_branch_id()
    if not branch_id:
        return None, "no_branch"

    # 1. Find or create client in WLaunch
    wl_client_id = find_wlaunch_client_id(client_phone)
    if not wl_client_id:
        # Split client_name into first/last
        parts = (client_name or '').strip().split(None, 1)
        fn = parts[0] if parts else client_phone
        ln = parts[1] if len(parts) > 1 else ''
        wl_client_id = create_wlaunch_client(client_phone, fn, ln)
    if not wl_client_id:
        logger.warning("WLaunch: client {} could not be found or created".format(client_phone))
        return None, "client_not_found"

    # 2. Convert Kyiv time to UTC
    try:
        kyiv_dt = datetime.strptime("{} {}".format(date_str, time_str), "%Y-%m-%d %H:%M")
        utc_dt = kyiv_dt - timedelta(hours=kyiv_offset(kyiv_dt))
        start_time_utc = utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    except Exception as e:
        return None, "time_parse: {}".format(e)

    # 3. Get resource ID for specialist
    resources = get_wlaunch_resources(branch_id)
    resource_id = resources.get(specialist)

    # 4. Find service ID (best match — exact, then fuzzy)
    wl_services = get_wlaunch_services(branch_id)
    proc_lower = procedure_name.lower()
    service_match = wl_services.get(proc_lower)
    if not service_match:
        # Normalize quotes for comparison
        import re as _re
        _norm = lambda s: _re.sub(r'[«»""\'`]', '', s).replace('  ', ' ').strip()
        pn = _norm(proc_lower)
        # Fuzzy: find WLaunch service that contains our name or vice versa
        for wl_name, wl_data in wl_services.items():
            wn = _norm(wl_name)
            if pn in wn or wn in pn:
                service_match = wl_data
                break
        if not service_match:
            # Category match: map our categories to WLaunch generic services
            _cat_map = {
                'ботулінотерапія': 'ботулінотерапія', '1 зона': 'ботулінотерапія',
                '2 зони': 'ботулінотерапія', '3 зони': 'ботулінотерапія',
                'full face': 'ботулінотерапія', 'ніфертіті': 'ботулінотерапія',
                'neuramis': 'контурна пластика губ', 'saypha filler': 'контурна пластика губ',
                'perfecta': 'контурна пластика губ', 'genyal': 'контурна пластика губ',
                'saypha volume': 'контурна пластика обличчя', 'neuramis volume': 'контурна пластика обличчя',
                'smart': 'smart біоревіталізація', 'vitaran': 'мезотерапія',
                'skin booster': 'мезотерапія', 'hair loss': 'мезотерапія шкіри голови',
                'kemikum': 'пілінг біоревіталізант kemikum', 'prx-t33': 'пілінг біоревіталізант prx t-33',
                'prx': 'пілінг біоревіталізант prx t-33',
                'моделювання окремої': 'drumroll окремої зони', 'моделювання всього': 'drumroll всього тіла',
                'релакс-масаж': 'drumroll всього тіла', 'пресотерапія': 'пресотерапія',
                'кисневий': 'киснева мезотерапія', 'glow skin': 'киснева мезотерапія',
                'підліткова': 'wow-чистка обличчя',
                'wow-чистка «сяяння': 'wow-чистка обличчя "сяяння"',
                'neauvia intense': 'контурна пластика губ',
                'neauvia stimulate': 'контурна пластика обличчя',
                'екзосоми': 'біорепарація шкіри екзосоми (exoxe) 2,5 ml',
                'ліполітики (тіло': 'ліполіз (ліполітики)',
                'kemikum': 'пілінг біоревіталізант kemikum',
                'азелаїновий': 'азелаїновий пілінг',
                'мигдальний': 'мигдальний пілінг',
                'пресотерапія': 'пресотерапія',
            }
            for keyword, wl_target in _cat_map.items():
                if keyword in proc_lower:
                    service_match = wl_services.get(wl_target)
                    if service_match:
                        break

    # 5. Build appointment payload (WLaunch uses snake_case)
    srs = []
    if service_match:
        srs_item = {
            "service": service_match["id"],
            "resources": [resource_id] if resource_id else [],
            "auto_selected_resources": not bool(resource_id),
            "ordinal": 1,
            "duration": duration_min * 60,
        }
        srs.append(srs_item)

    if not srs:
        logger.warning("WLaunch: no matching service for '{}', skipping WLaunch".format(procedure_name))
        return None, "service_not_found"

    appt_body = {
        "client": {"id": wl_client_id},
        "start_time": start_time_utc,
        "duration": duration_min * 60,
        "status": "CONFIRMED_BY_CLIENT",
        "source": "BO",
        "branch_id": branch_id,
        "company_id": COMPANY_ID,
        "service_resource_settings": srs,
    }

    post_headers = dict(HEADERS)
    post_headers["Content-Type"] = "application/json"

    # 6a. Calculate price (same as WLaunch dashboard does)
    try:
        price_url = "{}/client/appointment/calculate/price".format(WLAUNCH_API_URL)
        price_resp = requests.post(price_url, headers=post_headers,
                                   json={"appointment": appt_body}, timeout=10)
        if price_resp.status_code == 200:
            price_data = price_resp.json()
            appt_body["price"] = price_data.get("price", 0)
            logger.info("WLaunch price calculated: {}".format(appt_body.get("price")))
    except Exception as e:
        logger.warning("WLaunch price calc skipped: {}".format(e))

    # 6b. Create appointment
    url = "{}/company/{}/branch/{}/appointment".format(WLAUNCH_API_URL, COMPANY_ID, branch_id)
    appt_data = {"appointment": appt_body}

    try:
        resp = requests.post(url, headers=post_headers, json=appt_data,
                             params={"withDetails": "true", "withOrder": "true",
                                     "withMembership": "true", "withClientTags": "true",
                                     "skipClientBlockCheck": "false"},
                             timeout=15)
        if resp.status_code in (200, 201):
            result = resp.json()
            wl_id = result.get("id") or result.get("appointment", {}).get("id")
            logger.info("WLaunch appointment created: {} for {} on {}".format(wl_id, client_phone, date_str))
            return wl_id, None
        else:
            err = resp.text[:200]
            logger.error("WLaunch create failed {}: {}".format(resp.status_code, err))
            return None, "http_{}: {}".format(resp.status_code, err)
    except Exception as e:
        logger.error("WLaunch create error: {}".format(e))
        return None, str(e)


def test_wlaunch_connection():
    """Тестує підключення"""
    try:
        logger.info("\U0001f9ea \u0422\u0435\u0441\u0442\u0443\u0432\u0430\u043d\u043d\u044f Wlaunch API...")
        url = "{}/company/{}/branch/".format(WLAUNCH_API_URL, COMPANY_ID)
        params = {"page": 0, "size": 1, "active": "true"}
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        total = data.get("page", {}).get("total_elements", 0)
        logger.info("\u2705 \u041f\u0456\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u043d\u044f \u043f\u0440\u0430\u0446\u044e\u0454. \u0424\u0456\u043b\u0456\u0439: {}".format(total))

        branch_id = get_branch_id()
        if branch_id:
            appt_url = "{}/company/{}/branch/{}/appointment".format(
                WLAUNCH_API_URL, COMPANY_ID, branch_id)
            appt_params = {"page": 0, "size": 1, "sort": "start_time,desc"}
            appt_resp = requests.get(appt_url, headers=HEADERS, params=appt_params, timeout=10)
            appt_resp.raise_for_status()
            appt_data = appt_resp.json()
            appt_total = appt_data.get("page", {}).get("total_elements", 0)
            logger.info("\U0001f4cb \u0417\u0430\u043f\u0438\u0441\u0456\u0432 \u0432 \u0441\u0438\u0441\u0442\u0435\u043c\u0456: {}".format(appt_total))

        return True
    except Exception as e:
        logger.error("\u274c \u041f\u043e\u043c\u0438\u043b\u043a\u0430 \u043f\u0456\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u043d\u044f: {}".format(e))
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if test_wlaunch_connection():
        total = fetch_all_clients()
        print("\u0421\u0438\u043d\u0445\u0440\u043e\u043d\u0456\u0437\u043e\u0432\u0430\u043d\u043e {} \u043a\u043b\u0456\u0454\u043d\u0442\u0456\u0432".format(total))
    else:
        print("\u041f\u043e\u043c\u0438\u043b\u043a\u0430 \u043f\u0456\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u043d\u044f \u0434\u043e API")
