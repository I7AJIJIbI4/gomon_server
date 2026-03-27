#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Webhook handler для Wlaunch API - оновлення записів клієнтів в реальному часі
"""
import sys
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

sys.path.insert(0, '/home/gomoncli/zadarma')
from user_db import add_or_update_client
import requests
from config import WLAUNCH_API_KEY, COMPANY_ID

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/home/gomoncli/zadarma/wlaunch_webhook.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WLAUNCH_API_URL = 'https://api.wlaunch.net/v1'
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


def fetch_client_appointments(client_phone):
    """Отримує всі appointments для клієнта"""
    branch_id = get_branch_id()
    if not branch_id:
        return []
    
    url = f'{WLAUNCH_API_URL}/company/{COMPANY_ID}/branch/{branch_id}/appointment'
    
    # Шукаємо appointments за останні 3 роки
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=3 * 365)
    
    params = {
        'sort': 'start_time,desc',
        'page': 0,
        'size': 100,
        'start': start_date.strftime('%Y-%m-%dT00:00:00.000Z'),
        'end': end_date.strftime('%Y-%m-%dT23:59:59.999Z')
    }
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        appointments = data.get('content', [])
        
        # Фільтруємо тільки цього клієнта
        phone_norm = ''.join(filter(str.isdigit, client_phone))
        client_appointments = []
        
        for appt in appointments:
            client = appt.get('client', {})
            appt_phone = ''.join(filter(str.isdigit, client.get('phone', '')))
            
            if appt_phone == phone_norm:
                services_list = appt.get('services', [])
                service_name = ', '.join(s.get('name', '') for s in services_list if s.get('name'))
                
                start_time = appt.get('start_time', '')
                visit_date = ''
                visit_hour = None
                
                if start_time:
                    try:
                        visit_date = start_time[:10]
                        if len(start_time) >= 13:
                            visit_hour = int(start_time[11:13])
                    except Exception:
                        pass
                
                appt_status = (appt.get('status') or '').upper()
                
                client_appointments.append({
                    'appt_id': appt.get('id', ''),
                    'date': visit_date,
                    'hour': visit_hour,
                    'service': service_name,
                    'status': appt_status
                })
        
        # Сортуємо по даті (новіші першими), беремо топ-5
        client_appointments.sort(key=lambda x: x['date'], reverse=True)
        return client_appointments[:5]
        
    except Exception as e:
        logger.error(f'Помилка отримання appointments: {e}')
        return []


def sync_client_from_appointment(appointment_data):
    """Синхронізує клієнта на основі даних appointment"""
    try:
        client = appointment_data.get('client')
        if not client:
            logger.warning('Немає даних клієнта в appointment')
            return False
        
        phone = client.get('phone', '')
        if not phone:
            logger.warning('Немає номера телефону')
            return False
        
        phone_norm = ''.join(filter(str.isdigit, phone))
        client_id = client.get('id', phone_norm)
        first_name = client.get('first_name', '')
        last_name = client.get('last_name', '')
        
        # Отримуємо всі appointments клієнта
        appointments = fetch_client_appointments(phone)
        
        if not appointments:
            logger.warning(f'Не знайдено appointments для {phone}')
            return False
        
        # Визначаємо останній візит та послугу
        last_visit = appointments[0]['date']
        last_service = appointments[0]['service']
        visits_count = len(appointments)
        
        # Оновлюємо клієнта в БД
        add_or_update_client(
            client_id=client_id,
            first_name=first_name,
            last_name=last_name,
            phone=phone_norm,
            last_service=last_service,
            last_visit=last_visit,
            visits_count=visits_count,
            services_json=json.dumps(appointments, ensure_ascii=False)
        )
        
        logger.info(f'✅ Оновлено клієнта {first_name} {last_name} ({phone_norm}), записів: {len(appointments)}')
        return True
        
    except Exception as e:
        logger.error(f'Помилка синхронізації: {e}', exc_info=True)
        return False


@app.route('/webhook/wlaunch', methods=['POST'])
def wlaunch_webhook():
    """Обробник webhook від Wlaunch"""
    try:
        data = request.get_json()
        logger.info(f'📥 Отримано webhook: {json.dumps(data, ensure_ascii=False)[:500]}')
        
        event_type = data.get('type')
        event_data = data.get('data', {})
        
        # Обробляємо події appointments
        if event_type in ['APPOINTMENT_CREATED', 'APPOINTMENT_UPDATED', 'APPOINTMENT_DELETED', 'APPOINTMENT_CANCELLED']:
            appointment = event_data.get('appointment', event_data)
            
            if sync_client_from_appointment(appointment):
                logger.info(f'✅ {event_type} - клієнт оновлений')
                return jsonify({'status': 'ok', 'message': 'Client synced'}), 200
            else:
                logger.warning(f'⚠️ {event_type} - не вдалось оновити')
                return jsonify({'status': 'error', 'message': 'Sync failed'}), 200
        
        logger.info(f'ℹ️ Невідома подія: {event_type}')
        return jsonify({'status': 'ok', 'message': 'Event ignored'}), 200
        
    except Exception as e:
        logger.error(f'❌ Помилка обробки webhook: {e}', exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/webhook/wlaunch/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'wlaunch_webhook'}), 200


if __name__ == '__main__':
    logger.info('🚀 Запуск Wlaunch webhook server на порту 5003')
    app.run(host='0.0.0.0', port=5003, debug=False)
