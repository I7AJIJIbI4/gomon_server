#!/usr/bin/env python3
"""
Health check — monitors site, app, and API.
Sends TG alert to admin on failure.

Cron: */5 * * * * (every 5 minutes)
"""
import sys
import time
import logging
import logging.handlers
import requests

sys.path.insert(0, '/home/gomoncli/zadarma')
from config import TELEGRAM_TOKEN, ADMIN_USER_ID

LOG_FILE = '/home/gomoncli/zadarma/health_check.log'
STATE_FILE = '/tmp/health_check_state.json'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=2*1024*1024, backupCount=2),
    ]
)
logger = logging.getLogger('health_check')

CHECKS = [
    {'name': 'Сайт', 'url': 'https://drgomon.beauty/', 'expect': 200, 'contains': 'Dr. Gomon'},
    {'name': 'Додаток', 'url': 'https://drgomon.beauty/app/', 'expect': 200, 'contains': 'gomon'},
    {'name': 'API', 'url': 'https://drgomon.beauty/api/health', 'expect': 200, 'json_key': 'ok'},
    {'name': 'SW', 'url': 'https://drgomon.beauty/app/sw.js', 'expect': 200, 'contains': 'CACHE'},
]

TIMEOUT = 15


def send_tg_alert(text):
    """Send alert to admin via TG."""
    try:
        requests.post(
            'https://api.telegram.org/bot{}/sendMessage'.format(TELEGRAM_TOKEN),
            json={'chat_id': ADMIN_USER_ID, 'text': text},
            timeout=10
        )
    except Exception as e:
        logger.error('TG alert failed: {}'.format(e))


def load_state():
    """Load previous failure state."""
    import json
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    import json
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception:
        pass


def check_endpoint(check):
    """Returns (ok, error_message)."""
    name = check['name']
    url = check['url']
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={'User-Agent': 'GomonHealthCheck/1.0'})
        if r.status_code != check.get('expect', 200):
            return False, '{}: HTTP {} (очікувався {})'.format(name, r.status_code, check['expect'])
        if 'contains' in check and check['contains'] not in r.text:
            return False, '{}: відповідь не містить "{}"'.format(name, check['contains'])
        if 'json_key' in check:
            try:
                data = r.json()
                if not data.get(check['json_key']):
                    return False, '{}: JSON key "{}" = falsy'.format(name, check['json_key'])
            except Exception:
                return False, '{}: невалідний JSON'.format(name)
        return True, None
    except requests.exceptions.Timeout:
        return False, '{}: таймаут ({}с)'.format(name, TIMEOUT)
    except requests.exceptions.ConnectionError:
        return False, '{}: з\'єднання відхилено'.format(name)
    except Exception as e:
        return False, '{}: {}'.format(name, str(e)[:100])


def main():
    state = load_state()
    failures = []
    recoveries = []

    for check in CHECKS:
        name = check['name']
        ok, error = check_endpoint(check)

        was_down = state.get(name, {}).get('down', False)

        if not ok:
            failures.append(error)
            if not was_down:
                # New failure
                state[name] = {'down': True, 'since': time.strftime('%H:%M'), 'error': error}
                logger.warning('DOWN: {}'.format(error))
            else:
                # Still down — don't spam, alert every 30 min (6 checks × 5 min)
                checks_down = state[name].get('checks', 0) + 1
                state[name]['checks'] = checks_down
                if checks_down % 6 == 0:
                    failures.append('(вже {} хв)'.format(checks_down * 5))
                else:
                    failures.pop()  # Don't alert again yet
        else:
            if was_down:
                recoveries.append('{} — відновлено (було з {})'.format(name, state[name].get('since', '?')))
                logger.info('UP: {} recovered'.format(name))
            state[name] = {'down': False}

    # Send alerts
    if failures:
        text = '🔴 Dr. Gomon — проблеми:\n\n' + '\n'.join(failures)
        send_tg_alert(text)
        logger.warning('Alert sent: {}'.format(failures))

    if recoveries:
        text = '🟢 Dr. Gomon — відновлено:\n\n' + '\n'.join(recoveries)
        send_tg_alert(text)
        logger.info('Recovery alert: {}'.format(recoveries))

    save_state(state)


if __name__ == '__main__':
    main()
