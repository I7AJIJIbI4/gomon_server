# sms_fly.py — Відправка SMS через SMSFly API v2
# Розташування: /home/gomoncli/zadarma/sms_fly.py
import requests
import logging
from config import SMS_FLY_LOGIN, SMS_FLY_PASSWORD, SMS_FLY_SENDER

logger = logging.getLogger('sms_fly')

SMS_FLY_URL = 'https://sms-fly.ua/api/v2/api.php'


def normalize_phone_for_sms(phone):
    digits = ''.join(filter(str.isdigit, phone))
    if digits.startswith('0') and len(digits) == 10:
        return '38' + digits
    if digits.startswith('380') and len(digits) == 12:
        return digits
    if digits.startswith('80') and len(digits) == 11:
        return '3' + digits
    return digits


def send_sms(to, message):
    sms_phone = normalize_phone_for_sms(to)

    if not sms_phone or len(sms_phone) != 12:
        logger.error('❌ SMS: невалідний номер: {} -> {}'.format(to, sms_phone))
        return False

    try:
        payload = {
            'auth': {'key': SMS_FLY_PASSWORD},
            'action': 'SENDMESSAGE',
            'data': {
                'recipient': sms_phone,
                'channels': ['sms'],
                'sms': {
                    'source': SMS_FLY_SENDER,
                    'text': message,
                    'start_time': 'AUTO'
                }
            }
        }

        response = requests.post(
            SMS_FLY_URL,
            json=payload,
            headers={'Content-Type': 'application/json; charset=utf-8'},
            timeout=30
        )
        logger.info('📱 SMS -> {}: HTTP {}'.format(sms_phone, response.status_code))

        if response.status_code == 200:
            result = response.json()
            if result.get('success') == 1:
                logger.info('✅ SMS відправлено: {}'.format(sms_phone))
                return True
            else:
                error = result.get('error', {}).get('description', str(result))
                logger.error('❌ SMS помилка: {}'.format(error))
                return False

        logger.error('❌ SMS HTTP {}'.format(response.status_code))
        return False

    except Exception as e:
        logger.error('❌ SMS виняток: {}'.format(e))
        return False
