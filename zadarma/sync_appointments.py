#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Синхронізація appointments - оптимізована версія
Синхронізує тільки актуальні та майбутні записи
"""
import sys
import json
import logging
from datetime import datetime, timedelta

sys.path.insert(0, '/home/gomoncli/zadarma')
from user_db import add_or_update_client
from config import WLAUNCH_API_KEY, COMPANY_ID
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/home/gomoncli/zadarma/sync_appointments.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WLAUNCH_API_URL = 'https://api.wlaunch.net/v1'

# Маппінг телефону ресурсу → ім'я спеціаліста
RESOURCE_SPECIALIST_MAP = {
    '380996093860': 'victoria',
    '380685129121': 'anastasia',
}

def get_specialist(resources):
    """Витягує ім'я спеціаліста з поля resources апоінтменту."""
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
HEADERS = {
    'Authorization': f'Bearer {WLAUNCH_API_KEY}',
    'Accept': 'application/json'
}


def get_branch_id():
    """Отримує ID першої активної філії"""
    try:
        url = f'{WLAUNCH_API_URL}/company/{COMPANY_ID}/branch/'
        params = {'active': 'true', 'sort': 'ordinal', 'page': 0, 'size': 1}
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        branches = data.get('content', [])
        if branches:
            return branches[0]['id']
        return None
    except Exception as e:
        logger.error(f'Помилка отримання branch_id: {e}')
        return None


def sync_recent_appointments(days_back=7, days_forward=90):
    """
    Синхронізує appointments за останні N днів та майбутні на M днів
    Оптимізована версія для частих запусків
    """
    logger.info(f'🔄 Синхронізація appointments (назад: {days_back} днів, вперед: {days_forward} днів)')
    
    branch_id = get_branch_id()
    if not branch_id:
        logger.error('❌ Не вдалося отримати branch_id')
        return 0

    url = f'{WLAUNCH_API_URL}/company/{COMPANY_ID}/branch/{branch_id}/appointment'
    
    # Період: від days_back днів назад до days_forward днів вперед
    end_date = datetime.utcnow() + timedelta(days=days_forward)
    start_date = datetime.utcnow() - timedelta(days=days_back)
    
    # Збираємо клієнтів: phone -> {дані}
    clients_map = {}
    page = 0
    max_pages = 50
    total_appointments = 0

    while page < max_pages:
        params = {
            'sort': 'start_time,desc',
            'page': page,
            'size': 100,
            'start': start_date.strftime('%Y-%m-%dT00:00:00.000Z'),
            'end': end_date.strftime('%Y-%m-%dT23:59:59.999Z')
        }

        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f'❌ Помилка на сторінці {page}: {e}')
            break

        appointments = data.get('content', [])
        if not appointments:
            break

        total_appointments += len(appointments)
        logger.info(f'📄 Сторінка {page + 1}, записів: {len(appointments)}')

        for appt in appointments:
            client = appt.get('client')
            if not client:
                continue

            phone = client.get('phone', '')
            if not phone:
                continue

            phone_norm = ''.join(filter(str.isdigit, phone))
            if not phone_norm:
                continue

            client_id = client.get('id', phone_norm)
            first_name = client.get('first_name', '')
            last_name = client.get('last_name', '')

            # Витягуємо послугу
            services_list_appt = appt.get('services', [])
            service_name = ', '.join(s.get('name', '') for s in services_list_appt if s.get('name'))

            # Дата, година та статус запису
            visit_date = ''
            visit_hour = None
            start_time = appt.get('start_time', '')
            if start_time:
                try:
                    visit_date = start_time[:10]
                    if len(start_time) >= 13:
                        visit_hour = int(start_time[11:13])
                except Exception:
                    pass

            appt_status = (appt.get('status') or '').upper()
            specialist = get_specialist(appt.get('resources', []))

            entry = {
                'appt_id': appt.get('id', ''),
                'date': visit_date,
                'hour': visit_hour,
                'service': service_name,
                'status': appt_status,
                'specialist': specialist,
            }

            # Оновлюємо або додаємо
            if phone_norm not in clients_map:
                clients_map[phone_norm] = {
                    'id': client_id,
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone': phone_norm,
                    'last_service': service_name,
                    'last_visit': visit_date,
                    'visits_count': 1,
                    'services_history': [entry] if service_name and visit_date else []
                }
            else:
                clients_map[phone_norm]['visits_count'] += 1
                if not clients_map[phone_norm]['first_name'] and first_name:
                    clients_map[phone_norm]['first_name'] = first_name
                if not clients_map[phone_norm]['last_name'] and last_name:
                    clients_map[phone_norm]['last_name'] = last_name
                if service_name and visit_date and len(clients_map[phone_norm]['services_history']) < 10:
                    clients_map[phone_norm]['services_history'].append(entry)

                # Оновлюємо last_visit якщо цей запис новіший
                if visit_date > clients_map[phone_norm]['last_visit']:
                    clients_map[phone_norm]['last_visit'] = visit_date
                    clients_map[phone_norm]['last_service'] = service_name

        page += 1
        
        # Якщо це остання сторінка
        total_pages = data.get('page', {}).get('total_pages', 0)
        if page >= total_pages:
            break

    # Записуємо в базу
    updated = 0
    for phone_norm, c in clients_map.items():
        try:
            # Сортуємо історію по даті (новіші першими) та беремо топ-5
            c['services_history'].sort(key=lambda x: x['date'], reverse=True)
            services_json = json.dumps(c['services_history'][:5], ensure_ascii=False)
            
            add_or_update_client(
                client_id=c['id'],
                first_name=c['first_name'],
                last_name=c['last_name'],
                phone=c['phone'],
                last_service=c['last_service'],
                last_visit=c['last_visit'],
                visits_count=c['visits_count'],
                services_json=services_json
            )
            updated += 1
        except Exception as e:
            logger.error(f'❌ Помилка збереження {c["phone"]}: {e}')

    logger.info(f'✅ Оброблено {total_appointments} appointments, оновлено {updated} клієнтів')
    return updated


if __name__ == '__main__':
    try:
        result = sync_recent_appointments(days_back=7, days_forward=90)
        logger.info(f'✅ Синхронізація завершена: {result} клієнтів оновлено')
    except Exception as e:
        logger.error(f'❌ Помилка синхронізації: {e}', exc_info=True)
        sys.exit(1)
