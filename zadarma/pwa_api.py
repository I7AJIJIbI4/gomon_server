#!/usr/bin/env python3
# pwa_api.py — Flask API для Dr. Gomon PWA
# Розташування: /home/gomoncli/zadarma/pwa_api.py
# Запуск: python3 pwa_api.py

import sqlite3
import random
import string
import secrets
import time
import json
import logging
import os
import sys
from functools import wraps
from datetime import datetime, timedelta

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

# ── Startup: перевірка що notifier.py імпортується без помилок ──
try:
    import notifier as _notifier_check  # noqa
    logger.info('notifier.py OK')
except Exception as _ne:
    logger.error('notifier.py FAILED TO IMPORT: %s', _ne)

# ── CONFIG ──
DB_PATH      = '/home/gomoncli/zadarma/users.db'
FEED_DB      = '/home/gomoncli/zadarma/feed.db'
from config import TELEGRAM_TOKEN as TG_TOKEN, ANTHROPIC_KEY
try:
    from config import PIN_AUTH as _PIN_AUTH_CFG
    _PIN_AUTH_OVERRIDE = _PIN_AUTH_CFG
except (ImportError, AttributeError):
    _PIN_AUTH_OVERRIDE = None

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

def init_appointments_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS manual_appointments (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        client_phone TEXT NOT NULL,
        client_name  TEXT,
        procedure_name TEXT NOT NULL,
        specialist   TEXT NOT NULL,
        date         TEXT NOT NULL,
        time         TEXT NOT NULL,
        status       TEXT DEFAULT 'CONFIRMED',
        notes        TEXT,
        wlaunch_id   TEXT,
        created_at   TEXT DEFAULT (datetime('now')),
        created_by   TEXT
    )''')
    # Add duration column if missing (existing installs)
    try:
        conn.execute('ALTER TABLE manual_appointments ADD COLUMN duration INTEGER DEFAULT 60')
        conn.commit()
    except Exception:
        pass  # column already exists
    conn.commit()
    conn.close()

init_appointments_db()


def _time_to_min(t):
    """Convert 'HH:MM' string to minutes since midnight."""
    try:
        h, m = map(int, (t or '00:00').split(':'))
        return h * 60 + m
    except Exception:
        return 0


def _check_overlap(conn, specialist, date, new_start, new_end, exclude_id=None):
    """Return True if specialist already has a non-cancelled appointment overlapping [new_start, new_end) on date."""
    # Check manual_appointments
    q = "SELECT time, duration FROM manual_appointments WHERE specialist=? AND date=? AND status!='CANCELLED'"
    params = [specialist, date]
    if exclude_id is not None:
        q += ' AND id != ?'
        params.append(exclude_id)
    for row in conn.execute(q, params).fetchall():
        s = _time_to_min(row[0] or '00:00')
        e = s + (row[1] or 60)
        if new_start < e and s < new_end:
            return True
    # Check WLaunch appointments from services_json
    for row in conn.execute('SELECT services_json FROM clients').fetchall():
        try:
            items = json.loads(row[0] or '[]')
        except Exception:
            items = []
        for it in items:
            if it.get('date') != date or it.get('specialist') != specialist:
                continue
            if (it.get('status') or '').upper() == 'CANCELLED':
                continue
            hour = it.get('hour')
            if hour is None:
                continue
            s = hour * 60
            e = s + (it.get('duration_min') or 60)
            if new_start < e and s < new_end:
                return True
    return False

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

# ── ADMIN ROLES ──
ADMIN_ROLES = {
    '380733103110': 'superadmin',
    '380996093860': 'full',
    '380685129121': 'specialist',
    '16452040153':  'specialist',   # test account (Anastasia role, no appointments)
}
SPECIALIST_MAP = {
    '380996093860': 'victoria',
    '380685129121': 'anastasia',
    '16452040153':  'anastasia',    # test account mirrors Anastasia
}
# Phones that authenticate via fixed PIN instead of SMS OTP (loaded from config.py)
PIN_AUTH = _PIN_AUTH_OVERRIDE if _PIN_AUTH_OVERRIDE is not None else {}
ADMIN_PHONE = '380733103110'  # backward compat

def get_admin_role(phone: str):
    """Returns (role, specialist) or (None, None)."""
    p = norm_phone(phone)
    return ADMIN_ROLES.get(p), SPECIALIST_MAP.get(p)

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
    return secrets.token_urlsafe(n)

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
            'specialist': item.get('specialist', ''),
            'duration_min': item.get('duration_min', 60),
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

_otp_rate = {}  # phone -> (count, first_request_ts)
OTP_RATE_LIMIT = 3  # max OTPs per hour
OTP_RATE_WINDOW = 3600  # 1 hour
_magic_tokens = {}  # magic_token -> (phone, expires_at)

@app.route('/api/auth/send-otp', methods=['POST'])
def send_otp():
    data  = request.get_json() or {}
    phone = norm_phone(data.get('phone', ''))
    if len(phone) < 11:
        return jsonify({'error': 'invalid_phone'}), 400

    # Rate limit: max 3 OTPs per phone per hour
    now_ts = int(time.time())
    rate = _otp_rate.get(phone, (0, now_ts))
    if now_ts - rate[1] < OTP_RATE_WINDOW:
        if rate[0] >= OTP_RATE_LIMIT:
            return jsonify({'error': 'rate_limited'}), 429
        _otp_rate[phone] = (rate[0] + 1, rate[1])
    else:
        _otp_rate[phone] = (1, now_ts)

    # Не клієнт → гостьовий режим (без OTP)
    if not get_client(phone) and phone not in ADMIN_ROLES:
        save_lead(phone, '', 'app_guest')
        logger.info(f"Guest mode (not a client): {phone}")
        return jsonify({'ok': True, 'guest': True})

    # PIN-авторизація — не надсилаємо SMS, просто підтверджуємо що код прийнятий
    if phone in PIN_AUTH:
        return jsonify({'ok': True})

    code    = ''.join(random.choices(string.digits, k=4))
    expires = int(time.time()) + OTP_TTL

    conn = sqlite3.connect(OTP_DB)
    conn.execute('INSERT OR REPLACE INTO otp_codes VALUES (?,?,?,0)',
                 (phone, code, expires))
    conn.commit()
    conn.close()

    # TG-first з magic link, SMS/Viber fallback з WebOTP
    magic = secrets.token_urlsafe(32)
    _magic_tokens[magic] = (phone, expires)
    magic_link = 'https://www.gomonclinic.com/app/?magic={}'.format(magic)

    tg_text  = 'Ваш код для входу в Dr. Gomon — {code}.\n\nАбо натисніть для автоматичного входу:\n{link}'.format(
        code=code, link=magic_link)
    sms_text = (f"Ваш код — {code}. Дійсний 5 хвилин."
                f"\n\n@www.gomonclinic.com #{code}")

    ok = False
    channel = 'sms'
    try:
        from notifier import _get_tg_id, _send_tg
        tg_id = _get_tg_id(phone)
        if tg_id:
            ok = _send_tg(tg_id, tg_text)
            if ok:
                channel = 'tg'
    except Exception as _e:
        logger.warning(f"TG OTP attempt failed for {phone}: {_e}")

    if not ok:
        ok = send_sms(phone, sms_text)
        if not ok:
            logger.warning(f"SMS fail (без retry): {phone}")

    if ok:
        logger.info(f"OTP відправлено ({channel}): {phone}")
        return jsonify({'ok': True})
    else:
        logger.warning(f"OTP fail (всі канали): {phone}")
        return jsonify({'error': 'sms_failed'}), 500

@app.route('/api/auth/magic', methods=['POST'])
def verify_magic():
    """Magic link auto-login — одноразовий токен з TG повідомлення."""
    data = request.get_json() or {}
    magic = (data.get('token') or '').strip()
    if not magic or magic not in _magic_tokens:
        return jsonify({'error': 'invalid_token'}), 400

    phone, expires_at = _magic_tokens.pop(magic)  # одноразовий — видаляємо

    if int(time.time()) > expires_at:
        return jsonify({'error': 'token_expired'}), 400

    # Видаляємо OTP (вже не потрібен)
    conn = sqlite3.connect(OTP_DB)
    conn.execute('DELETE FROM otp_codes WHERE phone=?', (phone,))
    # Створюємо сесію
    token = gen_token()
    now = int(time.time())
    conn.execute('INSERT INTO sessions VALUES (?,?,?,?)',
                 (token, phone, now, now + SESSION_TTL))
    conn.commit()
    conn.close()

    client = get_client(phone)
    logger.info('Magic link login: {}'.format(phone))

    return jsonify({
        'ok':    True,
        'token': token,
        'client': _client_payload(client, phone),
    })


@app.route('/api/auth/verify', methods=['POST'])
def verify_otp():
    data  = request.get_json() or {}
    phone = norm_phone(data.get('phone', ''))
    code  = str(data.get('code', '')).strip()

    # PIN bypass — перевіряємо фіксований PIN замість OTP
    if phone in PIN_AUTH:
        if code != PIN_AUTH[phone]:
            return jsonify({'error': 'wrong_code'}), 400
        token = gen_token()
        now   = int(time.time())
        conn  = sqlite3.connect(OTP_DB)
        conn.execute('INSERT INTO sessions VALUES (?,?,?,?)',
                     (token, phone, now, now + SESSION_TTL))
        conn.commit()
        conn.close()
        client = get_client(phone)
        logger.info(f"PIN login: {phone}")
        return jsonify({'ok': True, 'token': token, 'client': _client_payload(client, phone)})

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
    """Записи клієнта: WLaunch (services_json) + manual_appointments."""
    phone = request.user_phone
    client = get_client(phone)
    appointments = parse_services(client) if client else []

    # Додаємо manual appointments
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        normalized = norm_phone(phone)
        rows = conn.execute(
            '''SELECT procedure_name, date, time, status, id, specialist, duration
               FROM manual_appointments
               WHERE client_phone=? AND status != 'CANCELLED'
               ORDER BY date DESC''',
            (normalized,)
        ).fetchall()
        conn.close()
        today_str = datetime.now().strftime('%Y-%m-%d')
        for r in rows:
            appt_status = 'upcoming' if r['date'] >= today_str else 'done'
            appointments.append({
                'service': r['procedure_name'],
                'date':    r['date'],
                'time':    r['time'] or '',
                'appt_id': 'manual_{}'.format(r['id']),
                'specialist': r['specialist'] if 'specialist' in r.keys() else '',
                'duration_min': r['duration'] if 'duration' in r.keys() else 60,
                'status':  appt_status,
            })
    except Exception as e:
        logger.warning('manual_appointments merge error: {}'.format(e))

    # Пересортовуємо: upcoming вперед
    upcoming = [x for x in appointments if x.get('status') == 'upcoming']
    done     = [x for x in appointments if x.get('status') != 'upcoming']
    upcoming.sort(key=lambda x: x['date'])
    done.sort(key=lambda x: x['date'], reverse=True)
    return jsonify({'appointments': upcoming + done})

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
    try:
        import requests as _req
        from config import TELEGRAM_TOKEN as TG_TOKEN_LOCAL
        r = _req.get('https://api.telegram.org/bot{}/getFile'.format(TG_TOKEN_LOCAL),
                      params={'file_id': fid}, timeout=5)
        fp = r.json().get('result', {}).get('file_path', '')
        if not fp:
            return '', 404
        media = _req.get('https://api.telegram.org/file/bot{}/{}'.format(TG_TOKEN_LOCAL, fp), timeout=15)
        if media.status_code != 200:
            return '', 502
        from flask import Response
        content_type = media.headers.get('Content-Type', 'application/octet-stream')
        return Response(media.content, content_type=content_type,
                        headers={'Cache-Control': 'public, max-age=86400'})
    except Exception:
        return '', 502

# ── PWA STATIC FILES ──

@app.route('/app/', defaults={'path': ''})
@app.route('/app/<path:path>')
def serve_pwa(path):
    if path and '..' not in path and os.path.exists(os.path.join(PWA_DIR, path)):
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
        'is_admin':     norm_phone(phone) in ADMIN_ROLES,
        'admin_role':   ADMIN_ROLES.get(norm_phone(phone)),
        'specialist':   SPECIALIST_MAP.get(norm_phone(phone)),
        }
    p = norm_phone(phone)
    return {
        'name':         client.get('first_name') or 'Клієнт',
        'last_name':    client.get('last_name') or '',
        'phone':        client.get('phone') or phone,
        'wlaunch_id':   str(client.get('id') or ''),
        'last_service': client.get('last_service') or '',
        'last_visit':   client.get('last_visit') or '',
        'visits_count': client.get('visits_count') or 0,
        'is_admin':     p in ADMIN_ROLES,
        'admin_role':   ADMIN_ROLES.get(p),
        'specialist':   SPECIALIST_MAP.get(p),
    }




# ── ADMIN ──────────────────────────────────────────────────────────────────

def _get_session_phone(token: str):
    """Returns phone from token or None."""
    conn = sqlite3.connect(OTP_DB)
    c = conn.cursor()
    c.execute('SELECT phone FROM sessions WHERE token=? AND expires_at>?', (token, int(time.time())))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def require_admin(f):
    """Декоратор: superadmin, full і specialist."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
        if not token:
            return jsonify({'error': 'unauthorized'}), 401
        phone = _get_session_phone(token)
        if not phone or norm_phone(phone) not in ADMIN_ROLES:
            return jsonify({'error': 'forbidden'}), 403
        request.admin_phone = norm_phone(phone)
        request.admin_role, request.admin_specialist = get_admin_role(phone)
        return f(*args, **kwargs)
    return decorated

def require_full_admin(f):
    """Декоратор: тільки superadmin і full (редагування цін/процедур)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
        if not token:
            return jsonify({'error': 'unauthorized'}), 401
        phone = _get_session_phone(token)
        role = ADMIN_ROLES.get(norm_phone(phone or ''))
        if role not in ('superadmin', 'full'):
            return jsonify({'error': 'forbidden'}), 403
        request.admin_phone = norm_phone(phone)
        request.admin_role = role
        request.admin_specialist = SPECIALIST_MAP.get(norm_phone(phone))
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

    c.execute("SELECT COUNT(*) FROM push_subscriptions WHERE active=1")
    push_subs = c.fetchone()[0]

    # Записи за останні 30 днів
    from datetime import datetime, timedelta
    since = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if request.admin_role == 'specialist':
        spec = request.admin_specialist
        c.execute("""
            SELECT COUNT(*) FROM (
                SELECT json_each.value FROM clients, json_each(clients.services_json)
                WHERE json_extract(json_each.value, '$.date') >= ?
                  AND json_extract(json_each.value, '$.specialist') = ?
            )
        """, (since, spec))
    else:
        c.execute("""
            SELECT COUNT(*) FROM (
                SELECT json_each.value FROM clients, json_each(clients.services_json)
                WHERE json_extract(json_each.value, '$.date') >= ?
            )
        """, (since,))
    visits_month = c.fetchone()[0]

    # Останні 10 відвідувань
    today_str = datetime.now().strftime('%Y-%m-%d')
    if request.admin_role == 'specialist':
        spec = request.admin_specialist
        c.execute("""
            SELECT c.first_name, c.last_name, c.phone,
                   json_extract(s.value, '$.date') as date,
                   json_extract(s.value, '$.service') as service,
                   json_extract(s.value, '$.hour') as hour
            FROM clients c, json_each(c.services_json) s
            WHERE json_extract(s.value, '$.date') IS NOT NULL
              AND json_extract(s.value, '$.date') >= ?
              AND json_extract(s.value, '$.specialist') = ?
              AND IFNULL(json_extract(s.value, '$.status'),'') != 'CANCELLED'
            ORDER BY json_extract(s.value, '$.date') ASC
            LIMIT 10
        """, (today_str, spec))
    else:
        c.execute("""
            SELECT c.first_name, c.last_name, c.phone,
                   json_extract(s.value, '$.date') as date,
                   json_extract(s.value, '$.service') as service,
                   json_extract(s.value, '$.hour') as hour
            FROM clients c, json_each(c.services_json) s
            WHERE json_extract(s.value, '$.date') IS NOT NULL
              AND json_extract(s.value, '$.date') >= ?
              AND IFNULL(json_extract(s.value, '$.status'),'') != 'CANCELLED'
            ORDER BY json_extract(s.value, '$.date') ASC
            LIMIT 10
        """, (today_str,))
    recent = [dict(r) for r in c.fetchall()]
    conn.close()

    # PWA юзери з otp_sessions.db
    pwa_users = 0
    try:
        otp_conn = sqlite3.connect(OTP_DB)
        pwa_users = otp_conn.execute('SELECT COUNT(DISTINCT phone) FROM sessions').fetchone()[0]
        otp_conn.close()
    except Exception:
        pass

    return jsonify({
        'total_clients': total_clients,
        'pwa_users':     pwa_users,
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
            if not isinstance(cat, dict):
                continue
            items = cat.get('items', [])
            for item in items:
                if not isinstance(item, dict):
                    continue
                name  = (item.get('name') or '').strip()
                price = (item.get('price') or '').strip()
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
    # PWA users = phones that have authenticated via OTP (otp_sessions.db)
    try:
        otp_conn = sqlite3.connect(OTP_DB)
        otp_phones = [r[0] for r in otp_conn.execute(
            'SELECT DISTINCT phone FROM sessions ORDER BY created_at DESC'
        ).fetchall()]
        otp_conn.close()
    except Exception:
        otp_phones = []

    if not otp_phones:
        return jsonify({'clients': []})

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    placeholders = ','.join('?' * len(otp_phones))
    rows = conn.execute(
        """SELECT phone, first_name, last_name, last_service, last_visit, services_json
           FROM clients WHERE phone IN ({})""".format(placeholders),
        otp_phones
    ).fetchall()
    conn.close()

    client_map = {r['phone']: r for r in rows}
    result = []
    for phone in otp_phones:
        r = client_map.get(phone)
        if r:
            name = ((r['first_name'] or '') + ' ' + (r['last_name'] or '')).strip() or phone
            result.append({
                'phone':        phone,
                'name':         name,
                'last_service': r['last_service'] or '',
                'last_visit':   r['last_visit'] or '',
                'appointments': _client_appts(r['services_json']),
            })
        else:
            result.append({
                'phone':        phone,
                'name':         phone,
                'last_service': '',
                'last_visit':   '',
                'appointments': [],
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
    from_date = request.args.get('from', '')
    to_date   = request.args.get('to', '')
    since = from_date if from_date else datetime.now().strftime('%Y-%m') + '-01'
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
            if date < since:
                continue
            if to_date and date > to_date:
                continue
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
        logger.error('admin_sync error: {}'.format(e))
        return jsonify({'ok': False, 'error': 'sync_failed'}), 500

# ── ADMIN NEW ENDPOINTS ──────────────────────────────────────────────────────

@app.route('/api/admin/role', methods=['GET'])
@require_admin
def admin_role():
    return jsonify({'role': request.admin_role, 'specialist': request.admin_specialist})

@app.route('/api/admin/calendar/appointments', methods=['GET'])
@require_admin
def admin_cal_get():
    """Список записів: manual_appointments + WLaunch (services_json), фільтр по даті."""
    from_date = request.args.get('from', '')
    to_date   = request.args.get('to', '')
    result = []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 1. Manual appointments
    # Specialist бачить свої записи повністю + чужі як "Зайнято" (без деталей)
    query = "SELECT * FROM manual_appointments WHERE status != 'CANCELLED'"
    params = []
    if from_date:
        query += ' AND date >= ?'
        params.append(from_date)
    if to_date:
        query += ' AND date <= ?'
        params.append(to_date)
    query += ' ORDER BY date ASC, time ASC'
    for r in conn.execute(query, params).fetchall():
        row_dict = dict(r)
        row_dict['duration_min'] = r['duration'] if r['duration'] else 60
        if request.admin_role == 'specialist' and row_dict.get('specialist') != request.admin_specialist:
            row_dict['client_name'] = ''
            row_dict['client_phone'] = ''
            row_dict['procedure_name'] = 'Зайнято'
            row_dict['notes'] = ''
            row_dict['busy'] = True
        result.append(row_dict)

    # 2. WLaunch appointments from services_json
    rows = conn.execute(
        'SELECT phone, first_name, last_name, services_json FROM clients'
    ).fetchall()
    for row in rows:
        try:
            items = json.loads(row['services_json'] or '[]')
        except Exception:
            items = []
        for it in items:
            d = it.get('date', '')
            if not d:
                continue
            status = (it.get('status') or '').upper()
            if status == 'CANCELLED':
                continue
            if from_date and d < from_date:
                continue
            if to_date and d > to_date:
                continue
            specialist = it.get('specialist')
            hour = it.get('hour')
            time_str = '{:02d}:00'.format(hour) if hour is not None else ''
            name = ((row['first_name'] or '') + ' ' + (row['last_name'] or '')).strip()
            is_other_spec = request.admin_role == 'specialist' and specialist != request.admin_specialist
            result.append({
                'id': 'wl_{}'.format(it.get('appt_id', '')),
                'client_phone': '' if is_other_spec else row['phone'],
                'client_name':  '' if is_other_spec else (name or row['phone']),
                'procedure_name': 'Зайнято' if is_other_spec else it.get('service', ''),
                'specialist': specialist,
                'date': d,
                'time': time_str,
                'status': status or 'CONFIRMED',
                'notes': '',
                'busy': True if is_other_spec else False,
                'source': 'wlaunch',
                'duration_min': it.get('duration_min') or 60,
            })

    conn.close()
    result.sort(key=lambda x: (x['date'], x['time'] or ''))
    return jsonify({'appointments': result})


# Безстрокові ключі для Google Calendar підписки (не протухають, можна відкликати)
ICS_KEYS = {
    'rtsqIeZt6zJICZOIHOQW545DYI3sRxajum-oGL3EEnw': {'phone': '380733103110', 'role': 'superadmin', 'specialist': ''},
    '3zIZzKlBoW37t_-T7zjmhQTDunK9bQUVde3JiQGg4rk': {'phone': '380996093860', 'role': 'full',       'specialist': 'victoria'},
    'z_eszoPbMUFTt_TKiGUkI6ZOkaZGu4P7YfT8-yJLX8k': {'phone': '380685129121', 'role': 'specialist',  'specialist': 'anastasia'},
}

@app.route('/api/admin/calendar.ics')
def admin_calendar_ics():
    """
    iCalendar feed — підписка в Google Calendar.
    Auth: ?key= (безстроковий) або ?token= (сесійний) або Authorization header.

    URL для Google Calendar:
      superadmin: /api/admin/calendar.ics?key=rtsqIeZt6zJICZOIHOQW545DYI3sRxajum-oGL3EEnw
      victoria:   /api/admin/calendar.ics?key=3zIZzKlBoW37t_-T7zjmhQTDunK9bQUVde3JiQGg4rk
      anastasia:  /api/admin/calendar.ics?key=z_eszoPbMUFTt_TKiGUkI6ZOkaZGu4P7YfT8-yJLX8k
    """
    # 1. Безстроковий ключ (для Google Calendar)
    ics_key = request.args.get('key', '')
    if ics_key and ics_key in ICS_KEYS:
        info = ICS_KEYS[ics_key]
        ics_phone = info['phone']
        ics_role = info['role']
        ics_specialist = info['specialist']
    else:
        # 2. Сесійний token (fallback)
        ics_token = request.args.get('token', '')
        if not ics_token:
            auth_h = request.headers.get('Authorization', '')
            if auth_h.startswith('Bearer '):
                ics_token = auth_h[7:]
        if not ics_token:
            return 'Unauthorized', 401
        otp_conn = sqlite3.connect(OTP_DB)
        sess = otp_conn.execute('SELECT phone, expires_at FROM sessions WHERE token=?', (ics_token,)).fetchone()
        otp_conn.close()
        if not sess or sess[1] < int(time.time()):
            return 'Unauthorized', 401
        ics_phone = sess[0]
        ics_role = ADMIN_ROLES.get(ics_phone)
        if not ics_role:
            return 'Forbidden', 403
        ics_specialist = SPECIALIST_MAP.get(ics_phone, '')
    ics_specialist = SPECIALIST_MAP.get(ics_phone, '')

    from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    to_date   = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    appts = []

    # Manual appointments
    for r in conn.execute(
        "SELECT id, client_phone, client_name, procedure_name, specialist, date, time, duration, notes, status "
        "FROM manual_appointments WHERE status != 'CANCELLED' AND date >= ? AND date <= ? ORDER BY date",
        (from_date, to_date)
    ).fetchall():
        if ics_role == 'specialist' and r['specialist'] != ics_specialist:
            continue
        appts.append(dict(r))

    # WLaunch
    for row in conn.execute('SELECT phone, first_name, last_name, services_json FROM clients').fetchall():
        try:
            items = json.loads(row['services_json'] or '[]')
        except Exception:
            continue
        for it in items:
            d = it.get('date', '')
            if not d or d < from_date or d > to_date:
                continue
            status = (it.get('status') or '').upper()
            if status == 'CANCELLED':
                continue
            spec = it.get('specialist', '')
            if ics_role == 'specialist' and spec != ics_specialist:
                continue
            hour = it.get('hour')
            name = ((row['first_name'] or '') + ' ' + (row['last_name'] or '')).strip()
            appts.append({
                'id': 'wl_{}'.format(it.get('appt_id', '')),
                'client_name': name,
                'client_phone': row['phone'],
                'procedure_name': it.get('service', ''),
                'specialist': spec,
                'date': d,
                'time': '{:02d}:00'.format(hour) if hour is not None else '09:00',
                'duration': it.get('duration_min') or 60,
                'notes': '',
                'status': status,
            })
    conn.close()

    # Build iCalendar
    spec_names = {'victoria': 'Вікторія', 'anastasia': 'Анастасія'}
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//GomonClinic//PWA//UK',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'X-WR-CALNAME:Dr. Gomon Cosmetology',
        'X-WR-TIMEZONE:Europe/Kyiv',
    ]
    for a in appts:
        uid = 'gomon-{}-{}@gomonclinic.com'.format(a.get('id', ''), a['date'])
        t = a.get('time', '09:00') or '09:00'
        h, m = int(t[:2]), int(t[3:5]) if len(t) >= 5 else 0
        dur = int(a.get('duration') or 60)
        dtstart = '{}T{:02d}{:02d}00'.format(a['date'].replace('-', ''), h, m)
        eh, em = divmod(h * 60 + m + dur, 60)
        dtend = '{}T{:02d}{:02d}00'.format(a['date'].replace('-', ''), eh, em)
        summary = '{} — {}'.format(a.get('procedure_name', ''), a.get('client_name', ''))
        spec = spec_names.get(a.get('specialist', ''), a.get('specialist', ''))
        desc = 'Клієнт: {}\\nТелефон: {}\\nСпеціаліст: {}\\nСтатус: {}'.format(
            a.get('client_name', ''), (a.get('client_phone', '') or '').replace('380', '0', 1),
            spec, a.get('status', ''))
        if a.get('notes'):
            desc += '\\nНотатки: {}'.format(a['notes'])
        lines.extend([
            'BEGIN:VEVENT',
            'UID:{}'.format(uid),
            'DTSTART;TZID=Europe/Kyiv:{}'.format(dtstart),
            'DTEND;TZID=Europe/Kyiv:{}'.format(dtend),
            'SUMMARY:{}'.format(summary.replace(',', '\\,')),
            'DESCRIPTION:{}'.format(desc.replace(',', '\\,')),
            'LOCATION:Dr. Gomon Cosmetology\\, БЦ Галерея\\, 6 поверх',
            'STATUS:CONFIRMED',
            'END:VEVENT',
        ])
    lines.append('END:VCALENDAR')

    from flask import Response
    return Response(
        '\r\n'.join(lines),
        content_type='text/calendar; charset=utf-8',
        headers={'Content-Disposition': 'inline; filename="gomon-calendar.ics"'}
    )


@app.route('/api/admin/calendar/appointments', methods=['POST'])
@require_admin
def admin_cal_create():
    """Створити новий запис."""
    d = request.get_json() or {}
    client_phone   = norm_phone(d.get('client_phone', ''))
    client_name    = (d.get('client_name', '') or '').strip()
    procedure_name = (d.get('procedure_name', '') or '').strip()
    specialist     = (d.get('specialist', '') or '').strip()
    date           = (d.get('date', '') or '').strip()
    appt_time      = (d.get('time', '') or '').strip()
    notes          = (d.get('notes', '') or '').strip()
    duration       = int(d.get('duration', 60) or 60)
    if duration < 15 or duration > 480:
        duration = 60

    if not procedure_name or not specialist or not date or not appt_time:
        return jsonify({'error': 'missing_fields'}), 400

    import re
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        return jsonify({'error': 'invalid_date'}), 400
    if not re.match(r'^\d{2}:\d{2}$', appt_time):
        return jsonify({'error': 'invalid_time'}), 400
    if specialist not in ('victoria', 'anastasia', ''):
        return jsonify({'error': 'invalid_specialist'}), 400

    # Specialist може записувати тільки до себе
    if request.admin_role == 'specialist' and specialist != request.admin_specialist:
        return jsonify({'error': 'forbidden'}), 403

    # Validate end time doesn't exceed 21:00
    start_min = int(appt_time[:2]) * 60 + int(appt_time[3:5])
    end_min = start_min + duration
    if end_min > 21 * 60:
        return jsonify({'error': 'too_late', 'detail': 'Запис не може закінчуватись пізніше 21:00'}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.execute('BEGIN IMMEDIATE')
    new_start = _time_to_min(appt_time)
    new_end   = new_start + duration
    if _check_overlap(conn, specialist, date, new_start, new_end):
        conn.rollback()
        conn.close()
        return jsonify({'error': 'conflict'}), 409

    c = conn.cursor()
    c.execute(
        '''INSERT INTO manual_appointments
           (client_phone, client_name, procedure_name, specialist, date, time, duration, notes, created_by)
           VALUES (?,?,?,?,?,?,?,?,?)''',
        (client_phone, client_name, procedure_name, specialist, date, appt_time, duration, notes, request.admin_phone)
    )
    new_id = c.lastrowid
    conn.commit()
    conn.close()

    # Підтвердження запису клієнту
    if client_phone:
        try:
            from notifier import send_appt_confirm
            send_appt_confirm({
                'id':             new_id,
                'client_phone':   client_phone,
                'client_name':    client_name,
                'procedure_name': procedure_name,
                'specialist':     specialist,
                'date':           date,
                'time':           appt_time,
                'duration_min':   duration,
            })
        except Exception as _e:
            logger.error('notifier confirm error: {}'.format(_e))

    return jsonify({'ok': True, 'id': new_id})

@app.route('/api/admin/calendar/appointments/<int:appt_id>', methods=['PUT'])
@require_admin
def admin_cal_update(appt_id):
    d = request.get_json() or {}
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT * FROM manual_appointments WHERE id=?', (appt_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'not_found'}), 404
    if request.admin_role == 'specialist' and row['specialist'] != request.admin_specialist:
        conn.close()
        return jsonify({'error': 'forbidden'}), 403
    fields = ['procedure_name', 'specialist', 'date', 'time', 'status', 'notes', 'client_name', 'client_phone', 'duration']
    updates, params = [], []
    for f in fields:
        if f in d:
            updates.append('{} = ?'.format(f))
            params.append(d[f])
    if not updates:
        conn.close()
        return jsonify({'ok': True})

    # Overlap check only when time/date/specialist/duration is being changed
    time_related = {'specialist', 'date', 'time', 'duration'}
    if time_related.intersection(set(d.keys())):
        eff_specialist = d.get('specialist', row['specialist'])
        eff_date       = d.get('date',       row['date'])
        eff_time       = d.get('time',       row['time'])
        eff_duration   = int(d.get('duration', row['duration'] or 60) or 60)
        new_start = _time_to_min(eff_time)
        new_end   = new_start + eff_duration
        if _check_overlap(conn, eff_specialist, eff_date, new_start, new_end, exclude_id=appt_id):
            conn.close()
            return jsonify({'error': 'conflict'}), 409

    params.append(appt_id)
    conn.execute('UPDATE manual_appointments SET {} WHERE id=?'.format(', '.join(updates)), params)
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/admin/calendar/appointments/<int:appt_id>', methods=['DELETE'])
@require_admin
def admin_cal_delete(appt_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT * FROM manual_appointments WHERE id=?', (appt_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'not_found'}), 404
    if request.admin_role == 'specialist' and row['specialist'] != request.admin_specialist:
        conn.close()
        return jsonify({'error': 'forbidden'}), 403
    conn.execute("UPDATE manual_appointments SET status='CANCELLED' WHERE id=?", (appt_id,))
    conn.commit()
    conn.close()

    # Сповіщення клієнту + спеціалісту про скасування
    try:
        from notifier import send_cancellation
        send_cancellation({
            'id':             appt_id,
            'client_phone':   row['client_phone'],
            'client_name':    row['client_name'],
            'procedure_name': row['procedure_name'],
            'specialist':     row['specialist'],
            'date':           row['date'],
            'time':           row['time'],
            'duration_min':   row['duration'] or 60,
        })
    except Exception as _e:
        logger.error('notifier cancel error: {}'.format(_e))

    return jsonify({'ok': True})

@app.route('/api/admin/clients/add', methods=['POST'])
@require_admin
def admin_client_add():
    """Додати нового клієнта вручну."""
    d = request.get_json() or {}
    first_name = (d.get('first_name', '') or '').strip()
    last_name  = (d.get('last_name', '') or '').strip()
    phone      = norm_phone(d.get('phone', ''))
    if not first_name or len(phone) < 11:
        return jsonify({'error': 'missing_fields'}), 400
    existing = get_client(phone)
    if existing:
        return jsonify({'ok': True, 'existing': True, 'client': {
            'phone': existing['phone'],
            'name': ((existing.get('first_name') or '') + ' ' + (existing.get('last_name') or '')).strip()
        }})
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            '''INSERT OR IGNORE INTO clients
               (id, first_name, last_name, phone, last_service, last_visit, visits_count, services_json)
               VALUES (?,?,?,?,?,?,?,?)''',
            (phone, first_name, last_name, phone, '', '', 0, '[]')
        )
        conn.commit()
    except Exception as e:
        logger.error('admin_client_add error: {}'.format(e))
        conn.close()
        return jsonify({'error': 'db_error'}), 500
    conn.close()
    return jsonify({'ok': True, 'existing': False})

# ═══════════════════════════════════════════════════════════════════════════════
# ФОТО-АЛЬБОМИ КЛІЄНТІВ — ЗАКОМЕНТОВАНО, ГОТОВО ДО АКТИВАЦІЇ
#
# Концепція:
#   Спеціалісти ведуть shared Google Photos / iCloud альбом для кожного клієнта.
#   В БД зберігається тільки ПОСИЛАННЯ на альбом (не файли).
#   В адмін-додатку — кнопка "Фото" що відкриває альбом у браузері.
#   Без upload на сервер, без thumbnails, без зайвого навантаження.
#
# Формат альбому (рекомендація):
#   - Google Photos: створити shared album → "Отримати посилання" → зберегти URL
#     URL формат: https://photos.google.com/share/...
#     Плюси: автобекап, необмежений простір, зручний UI
#   - iCloud: створити shared album → скопіювати посилання
#     URL формат: https://www.icloud.com/sharedalbum/...
#     Плюси: нативний на iPhone, автосинк
#   - Будь-яке інше: Dropbox, OneDrive — головне URL
#
# Структура папок в альбомі (рекомендація):
#   Назва альбому: "{Ім'я Прізвище} — {Телефон}"
#   Фото всередині: підписувати датою процедури (Google Photos дозволяє)
#   Порада: використовувати один Google-акаунт клініки для всіх альбомів
#
# Таблиця: client_albums (phone → album_url)
# API: GET/PUT для збереження і отримання URL альбому
# UI: кнопка "📷 Фото" в action sheet запису + в картці клієнта
# ═══════════════════════════════════════════════════════════════════════════════
#
# def _init_albums_table():
#     conn = sqlite3.connect(DB_PATH)
#     conn.execute('''
#         CREATE TABLE IF NOT EXISTS client_albums (
#             phone       TEXT PRIMARY KEY,
#             album_url   TEXT NOT NULL,
#             album_type  TEXT DEFAULT 'google',  -- 'google', 'icloud', 'other'
#             updated_by  TEXT,
#             updated_at  TEXT DEFAULT (datetime('now'))
#         )
#     ''')
#     conn.commit()
#     conn.close()
#
# _init_albums_table()
#
#
# @app.route('/api/admin/album/<phone>', methods=['GET'])
# @require_admin
# def admin_album_get(phone):
#     """Отримати URL фото-альбому клієнта."""
#     phone = norm_phone(phone)
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     row = conn.execute('SELECT * FROM client_albums WHERE phone=?', (phone,)).fetchone()
#     conn.close()
#     if not row:
#         return jsonify({'album': None})
#     return jsonify({'album': dict(row)})
#
#
# @app.route('/api/admin/album/<phone>', methods=['PUT'])
# @require_admin
# def admin_album_set(phone):
#     """Зберегти/оновити URL фото-альбому клієнта."""
#     phone = norm_phone(phone)
#     d = request.get_json() or {}
#     url = (d.get('album_url') or '').strip()
#     album_type = d.get('album_type', 'google')
#     if not url:
#         return jsonify({'error': 'empty_url'}), 400
#     if album_type not in ('google', 'icloud', 'other'):
#         album_type = 'other'
#     conn = sqlite3.connect(DB_PATH)
#     conn.execute(
#         '''INSERT INTO client_albums (phone, album_url, album_type, updated_by, updated_at)
#            VALUES (?,?,?,?,datetime('now'))
#            ON CONFLICT(phone) DO UPDATE SET
#              album_url=excluded.album_url,
#              album_type=excluded.album_type,
#              updated_by=excluded.updated_by,
#              updated_at=excluded.updated_at''',
#         (phone, url, album_type, request.admin_phone)
#     )
#     conn.commit()
#     conn.close()
#     return jsonify({'ok': True})
#
#
# @app.route('/api/admin/album/<phone>', methods=['DELETE'])
# @require_admin
# def admin_album_delete(phone):
#     """Видалити прив'язку альбому (не сам альбом — він в Google/iCloud)."""
#     phone = norm_phone(phone)
#     conn = sqlite3.connect(DB_PATH)
#     conn.execute('DELETE FROM client_albums WHERE phone=?', (phone,))
#     conn.commit()
#     conn.close()
#     return jsonify({'ok': True})

@app.route('/api/admin/prices/edit', methods=['GET'])
@require_full_admin
def admin_prices_get():
    """Повертає prices.json у нормалізованому вигляді для редактора."""
    try:
        with open(PRICES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
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
                    items.append({'name': row[0] if len(row) > 0 else '', 'price': row[2] if len(row) > 2 else '', 'specialists': []})
                elif isinstance(row, dict):
                    items.append({
                        'name':        row.get('name') or row.get('service') or '',
                        'price':       row.get('price') or row.get('cost') or '',
                        'specialists': row.get('specialists', []),
                    })
            if items:
                result.append({'cat': cat_name, 'items': items})
        return jsonify(result)
    except FileNotFoundError:
        return jsonify([])
    except json.JSONDecodeError:
        return jsonify({'error': 'invalid_json'}), 500

@app.route('/api/admin/prices/edit', methods=['PUT'])
@require_full_admin
def admin_prices_put():
    """Зберігає відредагований prices.json."""
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({'error': 'invalid_format'}), 400
    # Validate basic structure
    for cat in data:
        if not isinstance(cat, dict) or 'cat' not in cat or 'items' not in cat:
            return jsonify({'error': 'invalid_format'}), 400
    try:
        import tempfile
        tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(PRICES_PATH), suffix='.json')
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, PRICES_PATH)  # atomic on POSIX
        except Exception:
            os.unlink(tmp_path)
            raise
        return jsonify({'ok': True})
    except Exception as e:
        logger.error('admin_prices_put error: {}'.format(e))
        return jsonify({'error': 'write_failed'}), 500

# ── AI intent helpers ──
_ai_clients_cache = []
_ai_clients_cache_ts = 0.0

def _load_clients_for_ai():
    """Returns list of {phone, name} for all clients, cached 5 min."""
    global _ai_clients_cache, _ai_clients_cache_ts
    if time.time() - _ai_clients_cache_ts < 300 and _ai_clients_cache:
        return _ai_clients_cache
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        c = conn.cursor()
        c.execute("SELECT phone, first_name, last_name FROM clients ORDER BY CASE WHEN last_visit IS NULL THEN 1 ELSE 0 END, last_visit DESC")
        result = []
        for row in c.fetchall():
            name = ((row[1] or '') + ' ' + (row[2] or '')).strip()
            if name:
                result.append({'phone': row[0], 'name': name})
        conn.close()
        _ai_clients_cache = result
        _ai_clients_cache_ts = time.time()
        return result
    except Exception as e:
        logger.error('_load_clients_for_ai error: {}'.format(e))
        return _ai_clients_cache  # повертаємо застарілий кеш замість порожнього списку

def _load_procs_for_ai():
    """Returns list of {name, cat, price, specialists} from prices.json."""
    try:
        with open(PRICES_PATH, 'r', encoding='utf-8') as f:
            prices = json.load(f)
        result = []
        for cat in prices:
            cat_name = cat.get('cat', '')
            for item in cat.get('items', []):
                if item.get('name'):
                    result.append({
                        'name':        item['name'],
                        'cat':         cat_name,
                        'price':       item.get('price', ''),
                        'specialists': item.get('specialists', []),
                    })
        return result
    except Exception:
        return []


_ai_rate = {}  # admin_phone -> last_request_ts
AI_RATE_COOLDOWN = 5  # seconds between requests

@app.route('/api/admin/ai-intent', methods=['POST'])
@require_admin
def admin_ai_intent():
    """Розбирає NLP-запит адміністратора через claude-sonnet-4-6."""
    now_ts = time.time()
    if now_ts - _ai_rate.get(request.admin_phone, 0) < AI_RATE_COOLDOWN:
        return jsonify({'error': 'rate_limited', 'retry_after': AI_RATE_COOLDOWN}), 429
    _ai_rate[request.admin_phone] = now_ts

    import urllib.request as _urlreq
    data = request.get_json() or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'empty_text'}), 400

    today = datetime.now().strftime('%Y-%m-%d')
    wd_names = ['понеділок','вівторок','середа','четвер','п\'ятниця','субота','неділя']
    today_wd = wd_names[datetime.now().weekday()]

    all_clients = _load_clients_for_ai()
    all_procs   = _load_procs_for_ai()

    clients_block = '\n'.join(
        '{} [{}]'.format(c['name'], c['phone']) for c in all_clients
    )
    procs_block = '\n'.join(
        '- {} → {}'.format(p['cat'], p['name']) if p['cat'] else '- ' + p['name']
        for p in all_procs
    )

    system_prompt = (
        'Ти — асистент адміністратора косметологічної клініки Dr. Gómon.\n'
        'Сьогодні: {today} ({wd}).\n\n'
        '== КЛІЄНТИ КЛІНІКИ ==\n'
        'Формат: Ім\'я Прізвище [телефон]\n'
        '{clients}\n\n'
        '== ПРОЦЕДУРИ КЛІНІКИ ==\n'
        '{procs}\n\n'
        'Проаналізуй запит і поверни ТІЛЬКИ JSON (без markdown):\n'
        '{{\n'
        '  "action": "create|find|edit|delete|list|unknown",\n'
        '  "client_name": "Ім\'я Прізвище ТОЧНО як у списку якщо знайдено, або ім\'я як згадано в запиті якщо клієнт новий, або null",\n'
        '  "client_phone": "телефон ТОЧНО як у списку якщо знайдено, або null",\n'
        '  "procedure": "назва ТОЧНО як у списку процедур, або null",\n'
        '  "date": "YYYY-MM-DD або null",\n'
        '  "time": "HH:MM або null",\n'
        '  "specialist": "victoria|anastasia|null",\n'
        '  "notes": "нотатки або null",\n'
        '  "reply": "підтвердження українською 1-2 речення"\n'
        '}}\n\n'
        'Правила:\n'
        '- Якщо клієнт згаданий і є у списку — повертай ТОЧНЕ ім\'я і телефон зі списку\n'
        '- Якщо клієнт згаданий але НЕ знайдений у списку — повертай client_name як згадано, client_phone=null\n'
        '- Якщо процедура згадана — знайди у списку процедур і повертай ТОЧНУ назву\n'
        '- Дати "завтра","наступна середа" — конвертуй відносно {today}\n'
        '- "наступна X" = найближчий такий день тижня після сьогодні\n'
        '- Вікторія/Вика → "victoria"; Настя/Анастасія → "anastasia"; не вказано → null\n'
        '- reply: "Записую [ім\'я] на [процедуру], [дата] о [час]." або уточнення'
    ).format(today=today, wd=today_wd, clients=clients_block, procs=procs_block)

    payload = json.dumps({
        'model': 'claude-sonnet-4-6',
        'max_tokens': 512,
        'system': system_prompt,
        'messages': [{'role': 'user', 'content': text}]
    }).encode('utf-8')
    req = _urlreq.Request(
        'https://api.anthropic.com/v1/messages',
        data=payload,
        headers={
            'x-api-key': ANTHROPIC_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        }
    )
    try:
        with _urlreq.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        ai_text = result['content'][0]['text'].strip()
        if ai_text.startswith('```'):
            lines = ai_text.split('\n')
            ai_text = '\n'.join(lines[1:]).strip()
            if ai_text.endswith('```'):
                ai_text = ai_text[:-3].strip()
        intent = json.loads(ai_text)
        for k in ('client_name', 'client_phone', 'procedure', 'date', 'time', 'specialist', 'notes'):
            if intent.get(k) == 'null':
                intent[k] = None
    except Exception as e:
        logger.error('ai_intent error: {}'.format(e))
        return jsonify({'error': 'ai_error'}), 500

    # Enrich client: exact phone lookup (Claude matched from our list)
    client = None
    client_options = []
    if intent.get('client_phone'):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            'SELECT phone, first_name, last_name FROM clients WHERE phone=?',
            (intent['client_phone'],)
        ).fetchone()
        conn.close()
        if row:
            full = ((row['first_name'] or '') + ' ' + (row['last_name'] or '')).strip()
            client = {'phone': row['phone'], 'name': full}
            client_options = [client]
    elif intent.get('client_name'):
        # Fallback: name-based search if phone not returned
        name_q = intent['client_name'].lower()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT phone, first_name, last_name FROM clients "
            "WHERE lower(first_name||' '||last_name)=? LIMIT 4",
            (name_q,)
        ).fetchall()
        conn.close()
        for row in rows:
            full = ((row['first_name'] or '') + ' ' + (row['last_name'] or '')).strip()
            client_options.append({'phone': row['phone'], 'name': full})
        if len(client_options) == 1:
            client = client_options[0]

    # Enrich procedure: exact name lookup (Claude matched from our list)
    procedure = None
    procedure_options = []
    if intent.get('procedure'):
        for p in all_procs:
            if p['name'] == intent['procedure']:
                procedure = p
                procedure_options = [p]
                break
        # Fallback: case-insensitive if exact failed
        if not procedure:
            proc_q = intent['procedure'].lower()
            for p in all_procs:
                if p['name'].lower() == proc_q:
                    procedure = p
                    procedure_options = [p]
                    break

    # Auto-fill specialist from procedure if only one assigned
    if not intent.get('specialist') and procedure and len(procedure.get('specialists', [])) == 1:
        intent['specialist'] = procedure['specialists'][0]

    return jsonify({
        'action':            intent.get('action', 'unknown'),
        'client':            client,
        'client_options':    client_options,
        'client_name':       intent.get('client_name'),
        'procedure':         procedure,
        'procedure_options': procedure_options,
        'procedure_raw':     intent.get('procedure'),
        'date':              intent.get('date'),
        'time':              intent.get('time'),
        'specialist':        intent.get('specialist'),
        'notes':             intent.get('notes'),
        'reply':             intent.get('reply', ''),
    })


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

    tg_text = (
        '\U0001f338 Dr.Gomon: AI підібрав для вас — {}.\n'
        'Запишіться зручним способом:\n'
        '\U0001f4f1 Instagram: instagram.com/dr.gomon\n'
        '\U0001f4de +38 073 310 31 10'
    ).format(procedure)

    push_ok = False
    if _push_ok:
        push_title = '\U0001f338 Ваша процедура чекає'
        push_body  = 'AI підібрав для вас {}. Запишіться — це займе хвилину \U0001f48c'.format(procedure)
        push_ok = send_push_to_phone(request.user_phone, push_title, push_body,
                                     url='https://ig.me/m/dr.gomon', tag='procedure-reminder')
        logger.info('procedure-reminder push: {} ok={}'.format(request.user_phone, push_ok))

    # TG-first, SMS fallback (незалежно від push)
    msg_ok = False
    channel = 'none'
    try:
        from notifier import _get_tg_id, _send_tg
        tg_id = _get_tg_id(request.user_phone)
        if tg_id:
            msg_ok = _send_tg(tg_id, tg_text)
            if msg_ok:
                channel = 'tg'
    except Exception as _e:
        logger.warning('procedure-reminder TG failed: {}'.format(_e))

    if not msg_ok:
        msg_ok = send_sms(request.user_phone, tg_text)
        channel = 'sms' if msg_ok else 'failed'

    logger.info('procedure-reminder msg ({}) {} ok={}'.format(channel, request.user_phone, msg_ok))

    save_lead(request.user_phone, procedure)
    return jsonify({'ok': push_ok or msg_ok})


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

    text = (
        '\U0001f338 Dr.Gomon: AI підібрав для вас — {}.\n'
        'Запишіться зручним способом:\n'
        '\U0001f4f1 Instagram: instagram.com/dr.gomon\n'
        '\U0001f4de +38 073 310 31 10'
    ).format(procedure)

    # TG-first, SMS fallback
    ok = False
    channel = 'none'
    try:
        from notifier import _get_tg_id, _send_tg
        tg_id = _get_tg_id(phone)
        if tg_id:
            ok = _send_tg(tg_id, text)
            if ok:
                channel = 'tg'
    except Exception as _e:
        logger.warning('guest procedure-reminder TG failed: {}'.format(_e))

    if not ok:
        ok = send_sms(phone, text)
        if not ok:
            ok = send_sms(phone, text)
        channel = 'sms' if ok else 'failed'

    logger.info('guest procedure-reminder ({}) {} ok={}'.format(channel, phone, ok))

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

    # Сповіщення клієнту + спеціалісту про скасування
    try:
        from notifier import send_cancellation
        from user_db import get_client_by_phone as _gcbp
        import json as _json
        _client = _gcbp(phone)
        _client_name = ((_client.get('first_name','') + ' ' + _client.get('last_name','')).strip()
                        if _client else '')
        _specialist = None
        if _client:
            for _it in _json.loads(_client.get('services_json','[]') or '[]'):
                if _it.get('date') == date and _it.get('service') == service:
                    _specialist = _it.get('specialist')
                    break
        send_cancellation({
            'appt_id':        appt_id,
            'client_phone':   phone,
            'client_name':    _client_name,
            'procedure_name': service,
            'specialist':     _specialist,
            'date':           date,
            'time':           '',
            'duration_min':   60,
        })
    except Exception as _e:
        logger.error('notifier cancel (client-initiated) error: {}'.format(_e))

    logger.info("Cancelled appointment: {} {} {}".format(phone, date, service))
    return jsonify({'ok': True})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=False)
