#!/usr/bin/env python3
# pwa_api.py — Flask API для Dr. Gomon PWA
# Розташування: /home/gomoncli/zadarma/pwa_api.py
# Запуск: python3 pwa_api.py

import sqlite3
import random
import string
import time
import json
import logging
import os
import sys
from functools import wraps
from datetime import datetime

from typing import Optional
from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS

sys.path.append('/home/gomoncli/zadarma')
try:
    from sms_fly import send_sms
except ImportError:
    def send_sms(to, msg):
        logging.warning(f"sms_fly не знайдено: {to}")
        return False

app = Flask(__name__)
CORS(app, origins=['https://gomonclinic.com', 'https://www.gomonclinic.com'])

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('pwa_api')

# ── CONFIG ──
DB_PATH      = '/home/gomoncli/zadarma/users.db'
FEED_DB      = '/home/gomoncli/zadarma/feed.db'
from config import TELEGRAM_TOKEN as TG_TOKEN

def init_feed_db():
    conn = sqlite3.connect(FEED_DB)
    conn.execute(
        'CREATE TABLE IF NOT EXISTS posts ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT,'
        'tg_msg_id INTEGER UNIQUE,'
        'text TEXT,'
        'date INTEGER,'
        'media_type TEXT,'
        'file_id TEXT,'
        "created_at TEXT DEFAULT (datetime('now'))"
        ')'
    )
    conn.commit()
    conn.close()

init_feed_db()

OTP_DB       = '/home/gomoncli/zadarma/otp_sessions.db'
PRICES_PATH  = '/home/gomoncli/private_data/prices.json'
PWA_DIR      = '/home/gomoncli/public_html/app'
OTP_TTL      = 300    # 5 хв
SESSION_TTL  = 30 * 86400  # 30 днів

# ── OTP / SESSION DB ──
def init_otp_db():
    conn = sqlite3.connect(OTP_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS otp_codes (
        phone      TEXT PRIMARY KEY,
        code       TEXT NOT NULL,
        expires_at INTEGER NOT NULL,
        attempts   INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        token      TEXT PRIMARY KEY,
        phone      TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL
    )''')
    conn.commit()
    conn.close()

init_otp_db()

def init_leads_db():
    conn = sqlite3.connect(OTP_DB)
    conn.execute('''CREATE TABLE IF NOT EXISTS leads (
        phone      TEXT PRIMARY KEY,
        name       TEXT,
        procedure  TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        source     TEXT DEFAULT 'app'
    )''')
    conn.commit()
    conn.close()

init_leads_db()

def save_lead(phone: str, procedure: str, source: str = 'app'):
    """Зберігає потенційного клієнта якщо він ще не в clients."""
    if get_client(phone):
        return
    try:
        conn = sqlite3.connect(OTP_DB)
        conn.execute(
            'INSERT OR REPLACE INTO leads (phone, procedure, source) VALUES (?,?,?)',
            (phone, procedure, source)
        )
        conn.commit()
        conn.close()
        logger.info('lead saved: {}'.format(phone))
    except Exception as e:
        logger.warning('save_lead error: {}'.format(e))

# ── HELPERS ──

ADMIN_PHONE = '380733103110'

def norm_phone(phone: str) -> str:
    """Нормалізує до формату 380XXXXXXXXX"""
    d = ''.join(filter(str.isdigit, phone))
    if d.startswith('380') and len(d) == 12:
        return d
    if d.startswith('0') and len(d) == 10:
        return '38' + d
    if d.startswith('80') and len(d) == 11:
        return '3' + d
    return d

def gen_token(n=40):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))

def get_client(phone: str) -> Optional[dict]:
    """
    Шукає клієнта в clients таблиці за номером.
    Таблиця: id, first_name, last_name, phone, last_service,
             last_visit, visits_count, services_json
    """
    normalized = norm_phone(phone)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Шукаємо за точним збігом, потім за хвостом номера
    c.execute('''SELECT id, first_name, last_name, phone,
                        last_service, last_visit, visits_count, services_json
                 FROM clients
                 WHERE phone = ? OR phone = ?
                 LIMIT 1''', (normalized, phone))
    row = c.fetchone()
    if not row:
        # Fuzzy: останні 9 цифр
        tail = normalized[-9:] if len(normalized) >= 9 else normalized
        c.execute('''SELECT id, first_name, last_name, phone,
                            last_service, last_visit, visits_count, services_json
                     FROM clients WHERE phone LIKE ? LIMIT 1''', (f'%{tail}',))
        row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def parse_services(client: dict) -> list:
    """
    Парсить services_json клієнта.
    Формат в базі: [{"date": "2025-09-24", "service": "WOW-чистка обличчя"}, ...]
    Повертає відсортований список (новіші першими) з доданим полем status.
    """
    raw = client.get('services_json') or '[]'
    try:
        items = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        items = []

    today_str = datetime.now().strftime('%Y-%m-%d')
    result = []
    for item in items:
        if item.get('status') == 'CANCELLED':
            continue
        date_str = item.get('date', '')
        hour     = item.get('hour')
        result.append({
            'service': item.get('service', ''),
            'date':    date_str,
            'appt_id': item.get('appt_id', ''),
            'time':    '{:02d}:00'.format(hour) if hour is not None else '',
            # Якщо дата сьогодні або в майбутньому — "upcoming", інакше — "done"
            'status':  'upcoming' if date_str >= today_str else 'done',
        })

    # Сортуємо: upcoming вперед, потім по даті спадання
    result.sort(key=lambda x: (x['status'] != 'upcoming', x['date']), reverse=False)
    result.sort(key=lambda x: x['date'], reverse=True)
    # Upcoming — на початку
    upcoming = [x for x in result if x['status'] == 'upcoming']
    done     = [x for x in result if x['status'] == 'done']
    return upcoming + done

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
        if not token:
            return jsonify({'error': 'unauthorized'}), 401
        conn = sqlite3.connect(OTP_DB)
        c = conn.cursor()
        now = int(time.time())
        c.execute('SELECT phone FROM sessions WHERE token=? AND expires_at>?',
                  (token, now))
        row = c.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': 'session_expired'}), 401
        # sliding window — продовжуємо сесію при кожному запиті
        c.execute('UPDATE sessions SET expires_at=? WHERE token=?',
                  (now + SESSION_TTL, token))
        conn.commit()
        conn.close()
        request.user_phone = row[0]
        return f(*args, **kwargs)
    return wrapper

# ── AUTH ──

@app.route('/api/auth/send-otp', methods=['POST'])
def send_otp():
    data  = request.get_json() or {}
    phone = norm_phone(data.get('phone', ''))
    if len(phone) < 11:
        return jsonify({'error': 'invalid_phone'}), 400

    # Не клієнт → гостьовий режим (без OTP)
    if not get_client(phone) and phone != ADMIN_PHONE:
        save_lead(phone, '', 'app_guest')
        logger.info(f"Guest mode (not a client): {phone}")
        return jsonify({'ok': True, 'guest': True})

    code    = ''.join(random.choices(string.digits, k=4))
    expires = int(time.time()) + OTP_TTL

    conn = sqlite3.connect(OTP_DB)
    conn.execute('INSERT OR REPLACE INTO otp_codes VALUES (?,?,?,0)',
                 (phone, code, expires))
    conn.commit()
    conn.close()

    msg = (f"Ваш код — {code}. Дійсний 5 хвилин."
           f"\n\n@www.gomonclinic.com #{code}")
    ok  = send_sms(phone, msg)
    if not ok:
        time.sleep(2)
        logger.warning(f"SMS retry для {phone}")
        ok = send_sms(phone, msg)

    if ok:
        logger.info(f"OTP відправлено: {phone}")
        return jsonify({'ok': True})
    else:
        logger.warning(f"SMS fail для {phone}")
        return jsonify({'error': 'sms_failed'}), 500

@app.route('/api/auth/verify', methods=['POST'])
def verify_otp():
    data  = request.get_json() or {}
    phone = norm_phone(data.get('phone', ''))
    code  = str(data.get('code', '')).strip()

    conn = sqlite3.connect(OTP_DB)
    c    = conn.cursor()
    c.execute('SELECT code, expires_at, attempts FROM otp_codes WHERE phone=?', (phone,))
    row = c.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': 'code_not_found'}), 400

    stored_code, expires_at, attempts = row

    if attempts >= 5:
        conn.close()
        return jsonify({'error': 'too_many_attempts'}), 429

    if int(time.time()) > expires_at:
        c.execute('DELETE FROM otp_codes WHERE phone=?', (phone,))
        conn.commit()
        conn.close()
        return jsonify({'error': 'code_expired'}), 400

    if code != stored_code:
        c.execute('UPDATE otp_codes SET attempts=attempts+1 WHERE phone=?', (phone,))
        conn.commit()
        conn.close()
        return jsonify({'error': 'wrong_code'}), 400

    # ✅ Успіх
    c.execute('DELETE FROM otp_codes WHERE phone=?', (phone,))
    token = gen_token()
    now   = int(time.time())
    c.execute('INSERT INTO sessions VALUES (?,?,?,?)',
              (token, phone, now, now + SESSION_TTL))
    conn.commit()
    conn.close()

    client = get_client(phone)
    logger.info(f"Login: {phone} → {'знайдений' if client else 'новий'}")

    return jsonify({
        'ok':    True,
        'token': token,
        'client': _client_payload(client, phone),
    })

# ── ME ──

@app.route('/api/me', methods=['GET'])
@require_auth
def get_me():
    client = get_client(request.user_phone)
    if not client:
        return jsonify({'error': 'not_found'}), 404
    return jsonify(_client_payload(client, request.user_phone))

@app.route('/api/me/appointments', methods=['GET'])
@require_auth
def get_my_appointments():
    """
    Повертає список записів клієнта з services_json.
    Кожен запис: { service, date, status }
    """
    client = get_client(request.user_phone)
    if not client:
        return jsonify({'appointments': []})

    appointments = parse_services(client)
    return jsonify({'appointments': appointments})

# ── PRICES ──

@app.route('/api/prices', methods=['GET'])
def get_prices():
    """Повертає prices.json напряму з диску (оновлюється з сайтом)"""
    try:
        with open(PRICES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Нормалізуємо до [{cat, items:[{name,price}]}] для фронтенду
        if isinstance(data, dict):
            raw = []
            for k in sorted(data.keys(), key=lambda x: int(x) if x.isdigit() else 0):
                val = data[k]
                if isinstance(val, list):
                    raw.extend(val)
                else:
                    raw.append(val)
            data = raw
        result = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            cat_name = entry.get('title') or entry.get('cat') or entry.get('name') or ''
            rows = entry.get('rows') or entry.get('items') or entry.get('services') or []
            items = []
            for row in rows:
                if isinstance(row, list):
                    name  = row[0] if len(row) > 0 else ''
                    price = row[2] if len(row) > 2 else ''
                    items.append({'name': name, 'price': price})
                elif isinstance(row, dict):
                    items.append({
                        'name':  row.get('name') or row.get('service') or '',
                        'price': row.get('price') or row.get('cost') or ''
                    })
            if items:
                result.append({'cat': cat_name, 'items': items})
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({'error': 'prices_not_found'}), 404
    except json.JSONDecodeError:
        return jsonify({'error': 'prices_invalid_json'}), 500

# ── HEALTH ──

@app.route('/api/health', methods=['GET'])
def health():
    # Перевіряємо доступність бази
    try:
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute('SELECT COUNT(*) FROM clients').fetchone()[0]
        conn.close()
        db_ok = True
    except Exception:
        count = 0
        db_ok = False

    return jsonify({
        'ok':      True,
        'ts':      int(time.time()),
        'db':      db_ok,
        'clients': count,
    })


# -- NEWS FEED --

@app.route('/api/feed', methods=['GET'])
def get_feed():
    try:
        conn = sqlite3.connect(FEED_DB)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            'SELECT id, tg_msg_id, text, date, media_type, file_id FROM posts ORDER BY date DESC LIMIT 30'
        ).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception:
        return jsonify([])

@app.route('/api/feed/media/<fid>')
def feed_media(fid):
    import urllib.request
    try:
        url = 'https://api.telegram.org/bot' + TG_TOKEN + '/getFile?file_id=' + fid
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        if not data.get('ok'):
            return jsonify({'error': 'not found'}), 404
        fp = data['result']['file_path']
        return redirect('https://api.telegram.org/file/bot' + TG_TOKEN + '/' + fp)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── PWA STATIC FILES ──

@app.route('/app/', defaults={'path': ''})
@app.route('/app/<path:path>')
def serve_pwa(path):
    if path and os.path.exists(os.path.join(PWA_DIR, path)):
        return send_from_directory(PWA_DIR, path)
    return send_from_directory(PWA_DIR, 'index.html')

# ── INTERNAL ──

def _client_payload(client: Optional[dict], phone: str) -> dict:
    """Формує уніфікований об'єкт клієнта для відповіді"""
    if not client:
        return {
            'name':         'Клієнт',
            'last_name':    '',
            'phone':        phone,
            'wlaunch_id':   None,
            'last_service': '',
            'last_visit':   '',
            'visits_count': 0,
        'is_admin':     norm_phone(phone) == ADMIN_PHONE,
        }
    return {
        'name':         client.get('first_name') or 'Клієнт',
        'last_name':    client.get('last_name') or '',
        'phone':        client.get('phone') or phone,
        'wlaunch_id':   str(client.get('id') or ''),
        'last_service': client.get('last_service') or '',
        'last_visit':   client.get('last_visit') or '',
        'visits_count': client.get('visits_count') or 0,
        'is_admin':     (client.get('phone') or phone) == ADMIN_PHONE or norm_phone(phone) == ADMIN_PHONE,
    }




# ── ADMIN ──────────────────────────────────────────────────────────────────

def require_admin(f):
    """Декоратор: тільки для адміна"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        token = auth.replace('Bearer ', '').strip()
        if not token:
            return jsonify({'error': 'unauthorized'}), 401
        conn = sqlite3.connect(OTP_DB)
        c = conn.cursor()
        c.execute('SELECT phone FROM sessions WHERE token=? AND expires_at>?', (token, int(time.time())))
        row = c.fetchone()
        conn.close()
        if not row or norm_phone(row[0]) != ADMIN_PHONE:
            return jsonify({'error': 'forbidden'}), 403
        return f(*args, **kwargs)
    return decorated

@app.route('/api/admin/stats', methods=['GET'])
@require_admin
def admin_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM clients")
    total_clients = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM push_subscriptions WHERE active=1")
    push_subs = c.fetchone()[0]

    # Записи за останні 30 днів
    from datetime import datetime, timedelta
    since = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    c.execute("""
        SELECT COUNT(*) FROM (
            SELECT json_each.value FROM clients, json_each(clients.services_json)
            WHERE json_extract(json_each.value, '$.date') >= ?
        )
    """, (since,))
    visits_month = c.fetchone()[0]

    # Останні 10 відвідувань
    c.execute("""
        SELECT c.first_name, c.last_name, c.phone,
               json_extract(s.value, '$.date') as date,
               json_extract(s.value, '$.service') as service
        FROM clients c, json_each(c.services_json) s
        WHERE json_extract(s.value, '$.date') IS NOT NULL
        ORDER BY json_extract(s.value, '$.date') DESC
        LIMIT 10
    """)
    recent = [dict(r) for r in c.fetchall()]
    conn.close()

    return jsonify({
        'total_clients': total_clients,
        'total_users':   total_users,
        'push_subs':     push_subs,
        'visits_month':  visits_month,
        'recent':        recent,
    })

@app.route('/api/admin/appointments', methods=['GET'])
@require_admin
def admin_appointments():
    """Всі записи всіх клієнтів, відсортовані за датою"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT c.first_name, c.last_name, c.phone,
               json_extract(s.value, '$.date')    as date,
               json_extract(s.value, '$.service') as service,
               json_extract(s.value, '$.status')  as status
        FROM clients c, json_each(c.services_json) s
        WHERE json_extract(s.value, '$.date') IS NOT NULL
        ORDER BY json_extract(s.value, '$.date') DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({'appointments': rows})


# ── ADMIN DETAIL LISTS ──────────────────────────────────────────────────────

def _build_price_lookup():
    """Flat dict {service_name_lower: price_str} from prices.json"""
    lookup = {}
    try:
        import json as _json
        data = _json.load(open(PRICES_PATH))
        cats = data.values() if isinstance(data, dict) else data
        for cat in cats:
            items = cat if isinstance(cat, list) else [cat]
            for item in items:
                rows = item.get('rows', []) if isinstance(item, dict) else []
                for row in rows:
                    if isinstance(row, list) and len(row) >= 3:
                        name  = (row[0] or '').strip()
                        price = (row[2] or '').strip()
                        if name:
                            lookup[name.lower()] = price
                    elif isinstance(row, dict):
                        name  = (row.get('name') or '').strip()
                        price = (row.get('price') or row.get('cost') or '').strip()
                        if name:
                            lookup[name.lower()] = price
    except Exception:
        pass
    return lookup

def _client_appts(services_json_str):
    try:
        items = json.loads(services_json_str or '[]')
    except Exception:
        items = []
    result = []
    for it in items:
        result.append({
            'service': it.get('service', ''),
            'date':    it.get('date', ''),
            'hour':    it.get('hour'),
            'status':  it.get('status', ''),
            'appt_id': it.get('appt_id', ''),
        })
    result.sort(key=lambda x: x['date'], reverse=True)
    return result

@app.route('/api/admin/clients-list', methods=['GET'])
@require_admin
def admin_clients_list():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT phone, first_name, last_name, last_service,
                        last_visit, visits_count, services_json
                 FROM clients ORDER BY last_visit DESC""")
    rows = c.fetchall()
    conn.close()
    result = []
    for r in rows:
        name = ((r['first_name'] or '') + ' ' + (r['last_name'] or '')).strip()
        result.append({
            'phone':        r['phone'],
            'name':         name or r['phone'],
            'last_service': r['last_service'] or '',
            'last_visit':   r['last_visit'] or '',
            'visits_count': r['visits_count'] or 0,
            'appointments': _client_appts(r['services_json']),
        })
    return jsonify({'clients': result})

@app.route('/api/admin/users-list', methods=['GET'])
@require_admin
def admin_users_list():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT u.phone, u.first_name,
                        cl.first_name as cl_first, cl.last_name as cl_last,
                        cl.last_service, cl.last_visit, cl.services_json
                 FROM users u
                 LEFT JOIN clients cl ON cl.phone = u.phone
                 ORDER BY cl.last_visit DESC""")
    rows = c.fetchall()
    conn.close()
    result = []
    for r in rows:
        name = ((r['cl_first'] or '') + ' ' + (r['cl_last'] or '')).strip()
        if not name:
            name = r['first_name'] or r['phone']
        result.append({
            'phone':        r['phone'],
            'name':         name,
            'last_service': r['last_service'] or '',
            'last_visit':   r['last_visit'] or '',
            'appointments': _client_appts(r['services_json']),
        })
    return jsonify({'clients': result})

@app.route('/api/admin/push-list', methods=['GET'])
@require_admin
def admin_push_list():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT ps.phone,
                        cl.first_name, cl.last_name,
                        cl.last_service, cl.last_visit, cl.services_json
                 FROM push_subscriptions ps
                 LEFT JOIN clients cl ON cl.phone = ps.phone
                 WHERE ps.active = 1
                 GROUP BY ps.phone
                 ORDER BY cl.last_visit DESC""")
    rows = c.fetchall()
    conn.close()
    result = []
    for r in rows:
        name = ((r['first_name'] or '') + ' ' + (r['last_name'] or '')).strip()
        result.append({
            'phone':        r['phone'],
            'name':         name or r['phone'],
            'last_service': r['last_service'] or '',
            'last_visit':   r['last_visit'] or '',
            'appointments': _client_appts(r['services_json']),
        })
    return jsonify({'clients': result})

@app.route('/api/admin/month-visits', methods=['GET'])
@require_admin
def admin_month_visits():
    from datetime import datetime
    since = datetime.now().strftime('%Y-%m') + '-01'
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT phone, first_name, last_name, services_json
                 FROM clients""")
    rows = c.fetchall()
    conn.close()
    price_lookup = _build_price_lookup()
    visits = []
    for r in rows:
        name = ((r['first_name'] or '') + ' ' + (r['last_name'] or '')).strip() or r['phone']
        try:
            items = json.loads(r['services_json'] or '[]')
        except Exception:
            items = []
        for it in items:
            date = it.get('date', '')
            if date >= since:
                service = it.get('service', '')
                price = price_lookup.get(service.lower(), '')
                visits.append({
                    'client':  name,
                    'phone':   r['phone'],
                    'service': service,
                    'date':    date,
                    'hour':    it.get('hour'),
                    'price':   price,
                })
    visits.sort(key=lambda x: x['date'], reverse=True)
    return jsonify({'visits': visits})

@app.route('/api/admin/sync', methods=['POST'])
@require_admin
def admin_sync():
    """Запускає синхронізацію з Wlaunch"""
    import subprocess
    try:
        r1 = subprocess.run(
            ['python3', '/home/gomoncli/zadarma/sync_clients.py'],
            capture_output=True, text=True, timeout=60,
            cwd='/home/gomoncli/zadarma'
        )
        r2 = subprocess.run(
            ['python3', '/home/gomoncli/zadarma/sync_appointments.py'],
            capture_output=True, text=True, timeout=120,
            cwd='/home/gomoncli/zadarma'
        )
        return jsonify({
            'ok':     True,
            'stdout': (r1.stdout + r2.stdout)[-800:],
            'stderr': (r1.stderr + r2.stderr)[-300:],
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ── PUSH NOTIFICATIONS ──

try:
    from push_sender import (
        init_push_tables, save_subscription, remove_subscription,
        get_subscriptions, send_push_to_phone
    )
    init_push_tables()
    _push_ok = True
except Exception as _push_err:
    logger.warning('push_sender unavailable: {}'.format(_push_err))
    _push_ok = False

with open('/home/gomoncli/zadarma/vapid_public.txt') as _f:
    VAPID_PUBLIC_KEY = _f.read().strip()


@app.route('/api/push/vapid-key', methods=['GET'])
def push_vapid_key():
    return jsonify({'publicKey': VAPID_PUBLIC_KEY})


@app.route('/api/push/subscribe', methods=['POST'])
@require_auth
def push_subscribe():
    if not _push_ok:
        return jsonify({'error': 'push_unavailable'}), 503
    data = request.get_json() or {}
    sub = data.get('subscription')
    if not sub:
        return jsonify({'error': 'no_subscription'}), 400
    phone = request.user_phone
    import json as _json
    ok = save_subscription(phone, _json.dumps(sub) if isinstance(sub, dict) else sub)
    logger.info('push subscribe: {} ok={}'.format(phone, ok))
    return jsonify({'ok': ok})


@app.route('/api/push/unsubscribe', methods=['POST'])
@require_auth
def push_unsubscribe():
    if not _push_ok:
        return jsonify({'ok': True})
    data = request.get_json() or {}
    endpoint = (data.get('subscription') or {}).get('endpoint') if isinstance(data.get('subscription'), dict) else None
    remove_subscription(request.user_phone, endpoint)
    return jsonify({'ok': True})


@app.route('/api/push/status', methods=['GET'])
@require_auth
def push_status():
    subs = get_subscriptions(request.user_phone) if _push_ok else []
    return jsonify({'subscribed': len(subs) > 0, 'count': len(subs)})


@app.route('/api/push/procedure-reminder', methods=['POST'])
@require_auth
def push_procedure_reminder():
    """Надсилає push + SMS нагадування про підібрану процедуру якщо юзер не записався"""
    data = request.get_json(silent=True) or {}
    procedure = (data.get('procedure') or '').strip()
    if not procedure:
        return jsonify({'error': 'no_procedure'}), 400

    push_ok = False
    if _push_ok:
        title = '\U0001f338 Ваша процедура чекає'
        body  = 'AI підібрав для вас {}. Запишіться до лікаря — це займе хвилину \U0001f48c'.format(procedure)
        push_ok = send_push_to_phone(request.user_phone, title, body, url='https://ig.me/m/dr.gomon', tag='procedure-reminder')
        logger.info('procedure-reminder push: {} ok={}'.format(request.user_phone, push_ok))

    # SMS — незалежно від push
    sms_text = (
        '\U0001f338 Dr.Gomon: AI підібрав для вас — {}.\n'
        'Запишіться зручним способом:\n'
        '\U0001f4f1 Instagram: instagram.com/dr.gomon\n'
        '\U0001f4de +38 073 310 31 10'
    ).format(procedure)
    sms_ok = send_sms(request.user_phone, sms_text)
    if not sms_ok:
        sms_ok = send_sms(request.user_phone, sms_text)  # 1 retry
    logger.info('procedure-reminder sms: {} ok={}'.format(request.user_phone, sms_ok))

    # Якщо не клієнт — зберегти як потенційного клієнта
    save_lead(request.user_phone, procedure)

    return jsonify({'ok': push_ok or sms_ok})


@app.route('/api/sms/procedure-reminder', methods=['POST'])
def sms_procedure_reminder_guest():
    """SMS-нагадування для гостьового юзера (не авторизований, тільки телефон)."""
    data = request.get_json(silent=True) or {}
    phone = norm_phone((data.get('phone') or '').strip())
    procedure = (data.get('procedure') or '').strip()

    if len(phone) < 11 or not procedure:
        return jsonify({'error': 'invalid_params'}), 400

    # Захист від зловживань: тільки якщо телефон є в leads (юзер проходив через додаток)
    conn = sqlite3.connect(OTP_DB)
    c = conn.cursor()
    c.execute("SELECT phone FROM leads WHERE phone=? AND created_at >= datetime('now','-3 hours')", (phone,))
    row = c.fetchone()
    conn.close()
    if not row:
        logger.warning('sms/procedure-reminder: phone not in recent leads: {}'.format(phone))
        return jsonify({'error': 'not_eligible'}), 403

    sms_text = (
        '\U0001f338 Dr.Gomon: AI підібрав для вас — {}.\n'
        'Запишіться зручним способом:\n'
        '\U0001f4f1 Instagram: instagram.com/dr.gomon\n'
        '\U0001f4de +38 073 310 31 10'
    ).format(procedure)
    ok = send_sms(phone, sms_text)
    if not ok:
        ok = send_sms(phone, sms_text)
    logger.info('guest procedure-reminder sms: {} ok={}'.format(phone, ok))

    # Оновлюємо процедуру в leads
    try:
        conn = sqlite3.connect(OTP_DB)
        conn.execute('UPDATE leads SET procedure=? WHERE phone=?', (procedure, phone))
        conn.commit()
        conn.close()
    except Exception:
        pass

    return jsonify({'ok': ok})


# ── CANCEL APPOINTMENT ──

def _find_wlaunch_appt_id(phone, date_str, service):
    """Шукає ID запису в WLaunch за телефоном і датою"""
    import requests as _req
    from config import WLAUNCH_API_KEY, COMPANY_ID
    headers = {
        "Authorization": "Bearer " + WLAUNCH_API_KEY,
        "Accept": "application/json"
    }
    base = "https://api.wlaunch.net/v1"
    # Отримуємо branch_id
    try:
        br = _req.get(base + "/company/" + COMPANY_ID + "/branch/",
                      headers=headers, params={"active": "true", "page": 0, "size": 1}, timeout=8)
        br.raise_for_status()
        branches = br.json().get("content", [])
        if not branches:
            return None
        branch_id = branches[0]["id"]
    except Exception as e:
        logger.error("cancel: branch error: {}".format(e))
        return None

    phone_digits = ''.join(filter(str.isdigit, phone))
    url = "{}/company/{}/branch/{}/appointment".format(base, COMPANY_ID, branch_id)
    params = {
        "sort": "start_time,desc", "page": 0, "size": 100,
        "start": date_str + "T00:00:00.000Z",
        "end":   date_str + "T23:59:59.999Z"
    }
    try:
        resp = _req.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        for appt in resp.json().get("content", []):
            client = appt.get("client") or {}
            cp = ''.join(filter(str.isdigit, client.get("phone", "")))
            if phone_digits[-9:] == cp[-9:]:
                svcs = ", ".join(s.get("name", "") for s in appt.get("services", []) if s.get("name"))
                if not service or service == svcs:
                    return appt.get("id")
    except Exception as e:
        logger.error("cancel: search error: {}".format(e))
    return None


def _cancel_wlaunch_appt(appt_id):
    """Скасовує запис у WLaunch через POST {"appointment": {"id": ..., "status": "CANCELLED"}}"""
    import requests as _req
    from config import WLAUNCH_API_KEY, COMPANY_ID
    headers = {
        "Authorization": "Bearer " + WLAUNCH_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    base = "https://api.wlaunch.net/v1"
    try:
        br = _req.get(base + "/company/" + COMPANY_ID + "/branch/",
                      headers=headers, params={"active": "true", "page": 0, "size": 1}, timeout=8)
        br.raise_for_status()
        branches = br.json().get("content", [])
        if not branches:
            return False, "no_branch"
        branch_id = branches[0]["id"]
    except Exception as e:
        return False, "branch: " + str(e)

    url = "{}/company/{}/branch/{}/appointment/{}".format(base, COMPANY_ID, branch_id, appt_id)
    try:
        resp = _req.post(url, headers=headers,
                         json={"appointment": {"id": appt_id, "status": "CANCELLED"}},
                         timeout=10)
        resp.raise_for_status()
        return True, None
    except Exception as e:
        logger.error("cancel wlaunch: {} {}".format(e, getattr(e, 'response', None) and e.response.text))
        return False, str(e)


def _update_local_appt_cancelled(phone, date_str, service):
    """Позначає запис як CANCELLED в services_json в БД"""
    client = get_client(phone)
    if not client:
        return
    raw = client.get('services_json') or '[]'
    try:
        items = json.loads(raw)
    except Exception:
        return
    changed = False
    for item in items:
        if item.get('date') == date_str and (not service or item.get('service') == service):
            item['status'] = 'CANCELLED'
            changed = True
            break
    if changed:
        import sqlite3 as _sq
        conn = _sq.connect(DB_PATH)
        conn.execute("UPDATE clients SET services_json=? WHERE phone=? OR phone=?",
                     (json.dumps(items, ensure_ascii=False), phone, norm_phone(phone)))
        conn.commit()
        conn.close()


def _tg_notify_cancel(name, phone, date_str, service):
    """Telegram notification to admin about cancellation"""
    import requests as _req
    from config import TELEGRAM_TOKEN, ADMIN_USER_IDS
    lines = [
        "Скасування запису",
        "Клієнт: " + (name or phone),
        "Телефон: " + phone,
        "Дата: " + date_str,
        "Послуга: " + (service or "-"),
    ]
    text = "\n".join(lines)
    for chat_id in ADMIN_USER_IDS:
        try:
            _req.post(
                "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_TOKEN),
                json={"chat_id": chat_id, "text": text},
                timeout=8
            )
        except Exception:
            pass


@app.route('/api/me/appointments/cancel', methods=['POST'])
@require_auth
def cancel_my_appointment():
    """Скасовує майбутній запис клієнта"""
    data    = request.get_json() or {}
    date    = data.get('date', '').strip()
    service = data.get('service', '').strip()
    appt_id = data.get('appt_id', '').strip()

    if not date:
        return jsonify({'error': 'missing_date'}), 400

    phone = request.user_phone

    # Знаходимо WLaunch ID якщо не переданий
    if not appt_id:
        appt_id = _find_wlaunch_appt_id(phone, date, service)
        if not appt_id:
            return jsonify({'error': 'appointment_not_found'}), 404

    # Скасовуємо в WLaunch
    ok, err = _cancel_wlaunch_appt(appt_id)
    if not ok:
        logger.error("cancel failed for {}: {}".format(phone, err))
        return jsonify({'error': 'cancel_failed', 'detail': err}), 502

    # Оновлюємо локальну БД
    _update_local_appt_cancelled(phone, date, service)

    logger.info("Cancelled appointment: {} {} {}".format(phone, date, service))
    return jsonify({'ok': True})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=False)
