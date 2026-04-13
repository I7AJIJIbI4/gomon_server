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
from config import WLAUNCH_API_KEY, COMPANY_ID, WLAUNCH_API_URL
from wlaunch_api import get_specialist, get_branch_id, parse_appt_time, HEADERS
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


def sync_recent_appointments(days_back=7, days_forward=90):
    """
    Синхронізує appointments за останні N днів та майбутні на M днів
    Оптимізована версія для частих запусків
    """
    logger.info(f'\U0001f504 Синхронізація appointments (назад: {days_back} днів, вперед: {days_forward} днів)')

    branch_id = get_branch_id()
    if not branch_id:
        logger.error('\u274c Не вдалося отримати branch_id')
        return 0

    url = f'{WLAUNCH_API_URL}/company/{COMPANY_ID}/branch/{branch_id}/appointment'

    end_date = datetime.utcnow() + timedelta(days=days_forward)
    start_date = datetime.utcnow() - timedelta(days=days_back)

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
            logger.error(f'\u274c Помилка на сторінці {page}: {e}')
            break

        appointments = data.get('content', [])
        if not appointments:
            break

        total_appointments += len(appointments)
        logger.info(f'\U0001f4c4 Сторінка {page + 1}, записів: {len(appointments)}')

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

            services_list_appt = appt.get('services', [])
            service_name = ', '.join(s.get('name', '') for s in services_list_appt if s.get('name'))

            # DST-correct UTC->Kyiv conversion via shared parse_appt_time
            visit_date, visit_hour, visit_minute = parse_appt_time(appt.get('start_time', ''))

            appt_status = (appt.get('status') or '').upper()
            specialist = get_specialist(appt.get('resources', []))
            duration_min = (appt.get('duration') or 0) // 60 or 60

            entry = {
                'appt_id': appt.get('id', ''),
                'date': visit_date,
                'hour': visit_hour,
                'minute': visit_minute,
                'service': service_name,
                'status': appt_status,
                'specialist': specialist,
                'duration_min': duration_min,
            }

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
                if service_name and visit_date:
                    clients_map[phone_norm]['services_history'].append(entry)

                if visit_date > clients_map[phone_norm]['last_visit']:
                    clients_map[phone_norm]['last_visit'] = visit_date
                    clients_map[phone_norm]['last_service'] = service_name

        page += 1

        total_pages = data.get('page', {}).get('total_pages', 0)
        if page >= total_pages:
            break

    # Записуємо в базу — мержимо нові записи зі старими (не перезаписуємо)
    import sqlite3
    DB_PATH = '/home/gomoncli/zadarma/users.db'
    updated = 0
    for phone_norm, c in clients_map.items():
        try:
            new_entries = c['services_history']

            # Read existing services_json from DB and merge
            conn = sqlite3.connect(DB_PATH, timeout=10)
            row = conn.execute("SELECT services_json FROM clients WHERE phone=?",
                               (phone_norm,)).fetchone()
            conn.close()

            existing = []
            if row and row[0]:
                try:
                    existing = json.loads(row[0])
                except Exception:
                    existing = []

            # Merge: index existing by appt_id, update with new data
            by_id = {}
            for e in existing:
                aid = e.get('appt_id')
                if aid:
                    by_id[aid] = e
            for e in new_entries:
                aid = e.get('appt_id')
                if aid:
                    by_id[aid] = e  # new data overwrites old for same appt
                else:
                    by_id[id(e)] = e

            merged = list(by_id.values())
            merged.sort(key=lambda x: x.get('date', ''), reverse=True)
            # Keep top 50 (enough for full history view)
            services_json = json.dumps(merged[:50], ensure_ascii=False)

            add_or_update_client(
                client_id=c['id'],
                first_name=c['first_name'],
                last_name=c['last_name'],
                phone=c['phone'],
                last_service=c['last_service'],
                last_visit=c['last_visit'],
                visits_count=max(c['visits_count'], len(merged)),
                services_json=services_json
            )
            updated += 1
        except Exception as e:
            logger.error(f'\u274c Помилка збереження {c["phone"]}: {e}')

    logger.info(f'\u2705 Оброблено {total_appointments} appointments, оновлено {updated} клієнтів')
    return updated


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--deep', action='store_true', help='Deep sync: fetch ALL history (years back)')
    args = parser.parse_args()

    try:
        if args.deep:
            # Deep sync — all appointments from 2020 to now+90 days
            logger.info('DEEP SYNC: fetching full history...')
            result = sync_recent_appointments(days_back=2000, days_forward=90)
        else:
            result = sync_recent_appointments(days_back=7, days_forward=90)
        logger.info(f'\u2705 Синхронізація завершена: {result} клієнтів оновлено')
    except Exception as e:
        logger.error(f'\u274c Помилка синхронізації: {e}', exc_info=True)
        sys.exit(1)
