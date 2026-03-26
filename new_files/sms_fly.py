# sms_fly.py — Відправка SMS через SMSFly (простий API)
# Розташування: /home/gomoncli/zadarma/sms_fly.py
import requests
import logging

logger = logging.getLogger("sms_fly")

SMS_FLY_URL = "http://sms-fly.com/api/api.php"
SMS_FLY_LOGIN = "380933297777"
SMS_FLY_PASSWORD = "pJYAWmZpWOvUozqAUvsTaBjxTpu9oJEk"


def normalize_phone_for_sms(phone):
    """Нормалізує номер до формату 380XXXXXXXXX"""
    digits = ''.join(filter(str.isdigit, phone))
    if digits.startswith('0') and len(digits) == 10:
        return '38' + digits
    if digits.startswith('380') and len(digits) == 12:
        return digits
    if digits.startswith('80') and len(digits) == 11:
        return '3' + digits
    return digits


def send_sms(to, message):
    """Відправляє SMS через SMSFly. Повертає True/False."""
    sms_phone = normalize_phone_for_sms(to)

    if not sms_phone or len(sms_phone) != 12:
        logger.error("❌ SMS: невалідний номер: {} -> {}".format(to, sms_phone))
        return False

    try:
        data = {
            'login': SMS_FLY_LOGIN,
            'password': SMS_FLY_PASSWORD,
            'message': message,
            'recipients': sms_phone,
            'format': 'json'
        }

        response = requests.post(SMS_FLY_URL, data=data, timeout=30)
        logger.info("📱 SMS -> {}: HTTP {}".format(sms_phone, response.status_code))

        if response.status_code == 200:
            result = response.json()
            if result.get('result') == 'ok':
                logger.info("✅ SMS відправлено: {}".format(sms_phone))
                return True
            else:
                error = result.get('error', 'невідомо')
                logger.error("❌ SMS помилка: {}".format(error))
                return False

        logger.error("❌ SMS HTTP {}".format(response.status_code))
        return False

    except Exception as e:
        logger.error("❌ SMS виняток: {}".format(e))
        return False
