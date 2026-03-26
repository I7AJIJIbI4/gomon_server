# push_sender.py — Web Push відправка та управління підписками
import json
import logging
import sqlite3
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')  # suppress Python 3.6 deprecation warnings

logger = logging.getLogger('push_sender')

DB_PATH          = '/home/gomoncli/zadarma/users.db'
VAPID_PRIVATE_KEY = '/home/gomoncli/zadarma/vapid_private.pem'
VAPID_CLAIMS     = {'sub': 'mailto:admin@gomonclinic.com'}


def init_push_tables():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        'CREATE TABLE IF NOT EXISTS push_subscriptions ('
        '    id           INTEGER PRIMARY KEY AUTOINCREMENT,'
        '    phone        TEXT NOT NULL,'
        '    endpoint     TEXT NOT NULL,'
        '    subscription TEXT NOT NULL,'
        '    created_at   TEXT NOT NULL,'
        '    active       INTEGER DEFAULT 1,'
        '    UNIQUE(phone, endpoint)'
        ')'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS push_log ('
        '    id        INTEGER PRIMARY KEY AUTOINCREMENT,'
        '    phone     TEXT NOT NULL,'
        '    type      TEXT NOT NULL,'
        '    reference TEXT NOT NULL,'
        '    title     TEXT,'
        '    sent_at   TEXT NOT NULL,'
        '    status    TEXT DEFAULT "sent"'
        ')'
    )
    conn.commit()
    conn.close()


def save_subscription(phone, subscription_json_str):
    """Зберігає або оновлює push-підписку."""
    try:
        sub = json.loads(subscription_json_str)
        endpoint = sub.get('endpoint', '')
        if not endpoint:
            return False
    except Exception:
        return False

    conn = sqlite3.connect(DB_PATH)
    try:
        # ON CONFLICT не підтримується в SQLite 3.6 з upsert, використовуємо INSERT OR REPLACE
        conn.execute(
            'INSERT OR REPLACE INTO push_subscriptions '
            '(phone, endpoint, subscription, created_at, active) VALUES (?,?,?,?,1)',
            (phone, endpoint, subscription_json_str, datetime.now().isoformat())
        )
        conn.commit()
        logger.info('Push subscription saved: {}'.format(phone))
        return True
    except Exception as e:
        logger.error('save_subscription error: {}'.format(e))
        return False
    finally:
        conn.close()


def remove_subscription(phone, endpoint=None):
    """Деактивує підписку (або всі підписки клієнта)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        if endpoint:
            conn.execute(
                'UPDATE push_subscriptions SET active=0 WHERE phone=? AND endpoint=?',
                (phone, endpoint)
            )
        else:
            conn.execute('UPDATE push_subscriptions SET active=0 WHERE phone=?', (phone,))
        conn.commit()
    finally:
        conn.close()


def get_subscriptions(phone):
    """Повертає список активних підписок для телефону."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'SELECT subscription FROM push_subscriptions WHERE phone=? AND active=1',
        (phone,)
    )
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]


def _deactivate_endpoint(endpoint):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('UPDATE push_subscriptions SET active=0 WHERE endpoint=?', (endpoint,))
    conn.commit()
    conn.close()


def send_push(subscription_json_str, title, body, url='/app/', tag='gomon'):
    """
    Відправляє одне Web Push повідомлення.
    Повертає True при успіху, False при помилці.
    410/404 — автоматично деактивує підписку.
    """
    from pywebpush import webpush, WebPushException

    try:
        sub = json.loads(subscription_json_str)
        payload = json.dumps({
            'title': title,
            'body':  body,
            'url':   url,
            'tag':   tag,
        })
        webpush(
            subscription_info=sub,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
            headers={'urgency': 'high', 'TTL': '86400'},
        )
        return True
    except WebPushException as e:
        err = str(e)
        if '410' in err or '404' in err:
            endpoint = json.loads(subscription_json_str).get('endpoint', '')
            logger.warning('Subscription gone, deactivating: {}...'.format(endpoint[:50]))
            _deactivate_endpoint(endpoint)
        else:
            logger.error('WebPushException: {}'.format(e))
        return False
    except Exception as e:
        logger.error('send_push error: {}'.format(e))
        return False


def send_push_to_phone(phone, title, body, url='/app/', tag='gomon'):
    """
    Відправляє push всім активним підпискам клієнта.
    Повертає True якщо хоча б одна успішна.
    """
    subs = get_subscriptions(phone)
    if not subs:
        return False
    results = [send_push(s, title, body, url, tag) for s in subs]
    return any(results)


def is_push_already_sent(phone, push_type, reference):
    """Чи вже відправляли цей push (тип + reference = uniq ключ)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'SELECT id FROM push_log '
        'WHERE phone=? AND type=? AND reference=? AND status != "failed"',
        (phone, push_type, reference)
    )
    row = c.fetchone()
    conn.close()
    return row is not None


def log_push(phone, push_type, reference, title, status='sent'):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            'INSERT INTO push_log (phone, type, reference, title, sent_at, status) '
            'VALUES (?,?,?,?,?,?)',
            (phone, push_type, reference, title, datetime.now().isoformat(), status)
        )
        conn.commit()
    except Exception as e:
        logger.error('log_push error: {}'.format(e))
    finally:
        conn.close()


if __name__ == '__main__':
    import logging as _l
    _l.basicConfig(level=_l.INFO)
    init_push_tables()
    print('push_sender: tables initialized')
