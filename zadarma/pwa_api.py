#!/usr/bin/env python3
# pwa_api.py — Flask API для Dr. Gomon PWA
# Розташування: /home/gomoncli/zadarma/pwa_api.py
# Запуск: python3 pwa_api.py

import sqlite3
import string
import secrets
import time
import json
import logging
import logging.handlers
import os
import sys
import re
import requests as _req
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
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB upload limit
CORS(app, origins=['https://gomonclinic.com', 'https://www.gomonclinic.com', 'https://drgomon.beauty', 'https://www.drgomon.beauty'])

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
_log_handler = logging.handlers.RotatingFileHandler(
    '/home/gomoncli/zadarma/pwa_api.log', maxBytes=10*1024*1024, backupCount=5)
_log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logging.getLogger().addHandler(_log_handler)
logger = logging.getLogger('pwa_api')

# notifier.py imported lazily in endpoints that use it

# ── CONFIG ──
DB_PATH      = '/home/gomoncli/zadarma/users.db'
FEED_DB      = '/home/gomoncli/zadarma/feed.db'
from config import TELEGRAM_TOKEN as TG_TOKEN, ANTHROPIC_KEY, TG_BIZ_TOKEN
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
    c.execute('CREATE TABLE IF NOT EXISTS otp_rate (phone TEXT PRIMARY KEY, count INT, window_start INT)')
    conn.commit()
    # Cleanup expired sessions (older than 30 days)
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))
    # Cleanup expired OTP codes
    conn.execute("DELETE FROM otp_codes WHERE expires_at < ?", (int(time.time()),))
    # Cleanup old rate limit entries (older than 2 hours)
    conn.execute("DELETE FROM otp_rate WHERE window_start < ?", (int(time.time()) - 7200,))
    c.execute('''CREATE TABLE IF NOT EXISTS magic_tokens (
        token      TEXT PRIMARY KEY,
        phone      TEXT NOT NULL,
        created_at INTEGER NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sms_rate (
        phone      TEXT PRIMARY KEY,
        count      INTEGER NOT NULL DEFAULT 0,
        reset_date TEXT NOT NULL
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
    for col, ctype, default in [('duration', 'INTEGER', '60'), ('drive_folder_url', 'TEXT', 'NULL')]:
        try:
            conn.execute('ALTER TABLE manual_appointments ADD COLUMN {} {} DEFAULT {}'.format(col, ctype, default))
            conn.commit()
        except Exception:
            pass
    conn.commit()
    conn.close()

init_appointments_db()

def init_breaks_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS specialist_breaks (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        specialist TEXT NOT NULL,
        date       TEXT NOT NULL,
        time_from  TEXT NOT NULL,
        time_to    TEXT NOT NULL,
        reason     TEXT,
        created_by TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )''')
    conn.commit()
    conn.close()

init_breaks_db()

def init_permissions_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS permissions (
        specialist TEXT NOT NULL,
        feature    TEXT NOT NULL,
        level      TEXT NOT NULL DEFAULT 'write',
        updated_at TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (specialist, feature)
    )''')
    conn.commit()
    conn.close()

init_permissions_db()

def _get_permission(specialist, feature):
    """Returns 'write', 'read', or 'deny'. Defaults to 'write' if not set."""
    if not specialist or not feature:
        return 'write'
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        row = conn.execute('SELECT level FROM permissions WHERE specialist=? AND feature=?',
                           (specialist, feature)).fetchone()
        conn.close()
        return row[0] if row else 'write'
    except Exception:
        return 'write'

def _check_perm(feature, need='read'):
    """Check permission for current admin. Returns None if OK, or 403 response."""
    role = getattr(request, 'admin_role', '')
    if role in ('superadmin', 'full'):
        return None
    spec = getattr(request, 'admin_specialist', '')
    if not spec and role == 'specialist':
        return jsonify({'error': 'permission_denied', 'feature': feature}), 403
    if not spec:
        return None
    level = getattr(request, 'admin_permissions', {}).get(feature, 'write')
    if level == 'allow':
        return None
    if need == 'read' and level in ('read', 'write', 'allow'):
        return None
    if need == 'write' and level in ('write', 'allow'):
        return None
    return jsonify({'error': 'permission_denied', 'feature': feature}), 403

def _get_visible_specialists(feature):
    """For specialist-select features, return list of visible specialist names.
    Returns ['all'] for superadmin/full, or ['own'] or ['victoria','anastasia'] etc."""
    role = getattr(request, 'admin_role', '')
    if role in ('superadmin', 'full'):
        return ['all']
    perms = getattr(request, 'admin_permissions', {})
    val = perms.get(feature, '["own"]')
    if isinstance(val, list):
        return val
    try:
        parsed = json.loads(val)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    return ['own']

def init_messages_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS messages (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        platform        TEXT NOT NULL DEFAULT 'telegram',
        conversation_id TEXT NOT NULL,
        sender_id       TEXT NOT NULL,
        sender_name     TEXT,
        client_phone    TEXT,
        content         TEXT,
        media_type      TEXT,
        file_id         TEXT,
        created_at      TEXT DEFAULT (datetime('now')),
        is_from_admin   INTEGER DEFAULT 0,
        admin_phone     TEXT,
        is_read         INTEGER DEFAULT 0
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_msg_created ON messages(created_at DESC)')
    # Partial index for unread messages
    try:
        conn.execute('CREATE INDEX IF NOT EXISTS idx_msg_unread ON messages(is_read) WHERE is_read=0')
    except Exception:
        conn.execute('CREATE INDEX IF NOT EXISTS idx_msg_unread ON messages(is_read)')
    conn.execute('''CREATE TABLE IF NOT EXISTS biz_connections (
        chat_id TEXT PRIMARY KEY,
        biz_conn_id TEXT NOT NULL
    )''')
    conn.commit()
    conn.close()

init_messages_db()


def _time_to_min(t):
    """Convert 'HH:MM' string to minutes since midnight."""
    try:
        h, m = map(int, (t or '00:00').split(':'))
        return h * 60 + m
    except Exception:
        return 0


def _check_overlap(conn, specialist, date, new_start, new_end, exclude_id=None, exclude_wl_id=None):
    """Return True if specialist already has a non-cancelled appointment overlapping [new_start, new_end) on date.
    exclude_id: manual appointment ID to skip (for editing)
    exclude_wl_id: WLaunch appointment ID to skip (the WLaunch copy of the same appointment)
    """
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
    # Check WLaunch appointments from services_json (pre-filter by date AND specialist)
    for row in conn.execute('SELECT services_json FROM clients WHERE services_json LIKE ? AND services_json LIKE ?',
                            ('%' + date + '%', '%' + specialist + '%')).fetchall():
        try:
            items = json.loads(row[0] or '[]')
        except Exception:
            items = []
        for it in items:
            if it.get('date') != date or it.get('specialist') != specialist:
                continue
            # Skip WLaunch copy of the appointment being edited
            if exclude_wl_id and it.get('appt_id') == exclude_wl_id:
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
    # Check specialist_breaks
    for row in conn.execute(
        'SELECT time_from, time_to FROM specialist_breaks WHERE specialist=? AND date=?',
        (specialist, date)).fetchall():
        s = _time_to_min(row[0])
        e = _time_to_min(row[1])
        if new_start < e and s < new_end:
            return True
    return False

def save_lead(phone: str, procedure: str, source: str = 'app'):
    """Зберігає потенційного клієнта якщо він ще не в clients."""
    if get_client(phone):
        return
    try:
        conn = sqlite3.connect(OTP_DB)
        try:
            conn.execute(
                'INSERT OR REPLACE INTO leads (phone, procedure, source) VALUES (?,?,?)',
                (phone, procedure, source)
            )
            conn.commit()
            logger.info('lead saved: {}'.format(phone))
        finally:
            conn.close()
    except Exception as e:
        logger.warning('save_lead error: {}'.format(e))

# ── HELPERS ──

# ── ADMIN ROLES ──
ADMIN_ROLES = {
    '380733103110': 'superadmin',
    '380996093860': 'full',
    '380685129121': 'specialist',
    '16452040153':  'specialist',   # test account (Anastasia role, no appointments)
    '380375840375': 'superadmin',   # superadmin panel
}
SUPERADMIN_PHONE = '380375840375'
# Features with simple levels (write/read/deny/allow)
PERM_SIMPLE = {
    'stat_clients_tap': ('allow', 'deny'),
    'stat_users_tap':   ('allow', 'deny'),
    'stat_push_tap':    ('allow', 'deny'),
    'calendar_edit':    ('write', 'deny'),
    'clients':          ('write', 'read', 'deny'),
    'prices':           ('write', 'read', 'deny'),
    'messenger':        ('write', 'read', 'deny'),
    'ai_assistant':     ('write', 'deny'),
    'ai_chat':          ('write', 'deny'),
    'sync':             ('write', 'deny'),
    'photo':            ('write', 'read', 'deny'),
}
# Features with specialist multi-select (JSON array: ["own"], ["victoria","anastasia"], ["all"])
PERM_SPECIALISTS = ('stat_month', 'stat_recent', 'calendar')
ALL_PERM_FEATURES = tuple(PERM_SIMPLE.keys()) + PERM_SPECIALISTS
# Backwards compat
PERMISSION_FEATURES = ALL_PERM_FEATURES
PERMISSION_LEVELS = ('write', 'read', 'deny', 'allow')
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

from user_db import normalize_phone as norm_phone
try:
    from tz_utils import kyiv_now
except ImportError:
    kyiv_now = datetime.now  # fallback if tz_utils missing

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
    try:
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
        return dict(row) if row else None
    finally:
        conn.close()

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

    # NOTE: Server timezone is Europe/Kyiv; appointment dates are also Kyiv — comparison is correct.
    today_str = kyiv_now().strftime('%Y-%m-%d')
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
        try:
            c = conn.cursor()
            now = int(time.time())
            c.execute('SELECT phone FROM sessions WHERE token=? AND expires_at>?',
                      (token, now))
            row = c.fetchone()
            if not row:
                return jsonify({'error': 'session_expired'}), 401
            # sliding window — продовжуємо сесію при кожному запиті
            c.execute('UPDATE sessions SET expires_at=? WHERE token=?',
                      (now + SESSION_TTL, token))
            conn.commit()
        finally:
            conn.close()
        request.user_phone = row[0]
        return f(*args, **kwargs)
    return wrapper

# ── AUTH ──

OTP_RATE_LIMIT = 3  # max OTPs per hour
OTP_RATE_WINDOW = 3600  # 1 hour
MAGIC_TOKEN_TTL = 300  # 5 min


def _save_magic_token(token, phone):
    """Save magic token to DB."""
    conn = sqlite3.connect(OTP_DB)
    try:
        conn.execute('INSERT OR REPLACE INTO magic_tokens (token, phone, created_at) VALUES (?,?,?)',
                     (token, phone, int(time.time())))
        conn.commit()
    finally:
        conn.close()


def _pop_magic_token(token):
    """Retrieve and delete magic token atomically. Returns (phone, created_at) or None."""
    conn = sqlite3.connect(OTP_DB, timeout=5)
    try:
        conn.execute('BEGIN IMMEDIATE')
        # Cleanup expired tokens (>5 min)
        conn.execute('DELETE FROM magic_tokens WHERE created_at < ?',
                     (int(time.time()) - MAGIC_TOKEN_TTL,))
        row = conn.execute('SELECT phone, created_at FROM magic_tokens WHERE token=?',
                           (token,)).fetchone()
        if row:
            conn.execute('DELETE FROM magic_tokens WHERE token=?', (token,))
            conn.commit()
            return row[0], row[1]
        conn.commit()
        return None
    finally:
        conn.close()

@app.route('/api/auth/send-otp', methods=['POST'])
def send_otp():
    data  = request.get_json() or {}
    phone = norm_phone(data.get('phone', ''))
    if len(phone) < 11:
        return jsonify({'error': 'invalid_phone'}), 400

    # PIN_AUTH phones skip rate limit and OTP sending
    if phone in PIN_AUTH:
        return jsonify({'ok': True})

    # Rate limit: max 3 OTPs per phone per hour (atomic transaction)
    now_ts = int(time.time())
    otp_conn = sqlite3.connect(OTP_DB, timeout=5)
    otp_conn.execute('CREATE TABLE IF NOT EXISTS otp_rate (phone TEXT PRIMARY KEY, count INT, window_start INT)')
    otp_conn.execute('BEGIN IMMEDIATE')
    row = otp_conn.execute('SELECT count, window_start FROM otp_rate WHERE phone=?', (phone,)).fetchone()
    if row:
        count, window_start = row
        if now_ts - window_start < OTP_RATE_WINDOW:
            if count >= OTP_RATE_LIMIT:
                otp_conn.rollback()
                otp_conn.close()
                return jsonify({'error': 'rate_limited'}), 429
            otp_conn.execute('UPDATE otp_rate SET count=count+1 WHERE phone=?', (phone,))
        else:
            otp_conn.execute('UPDATE otp_rate SET count=1, window_start=? WHERE phone=?', (now_ts, phone))
    else:
        otp_conn.execute('INSERT INTO otp_rate VALUES (?,1,?)', (phone, now_ts))
    otp_conn.commit()
    otp_conn.close()

    # Не клієнт → гостьовий режим (без OTP)
    if not get_client(phone) and phone not in ADMIN_ROLES:
        save_lead(phone, '', 'app_guest')
        logger.info(f"Guest mode (not a client): {phone}")
        return jsonify({'ok': True, 'guest': True})

    code    = ''.join(secrets.choice(string.digits) for _ in range(4))
    expires = int(time.time()) + OTP_TTL

    conn = sqlite3.connect(OTP_DB)
    conn.execute('INSERT OR REPLACE INTO otp_codes VALUES (?,?,?,0)',
                 (phone, code, expires))
    conn.commit()
    conn.close()

    # TG-first, SMS/Viber fallback з WebOTP
    tg_text  = 'Ваш код для входу:\n\n    {code}\n\nДійсний 5 хвилин.\nDr. Gomon Cosmetology'.format(code=code)
    sms_text = 'Ваш код — {code}. Дійсний 5 хвилин.\n\n@www.gomonclinic.com #{code}'.format(code=code)

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
    if not magic:
        return jsonify({'error': 'invalid_token'}), 400

    result = _pop_magic_token(magic)
    if not result:
        return jsonify({'error': 'invalid_token'}), 400

    phone, created_at = result

    if int(time.time()) - created_at > MAGIC_TOKEN_TTL:
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

    conn = sqlite3.connect(OTP_DB, timeout=5)
    conn.execute('BEGIN IMMEDIATE')
    c    = conn.cursor()
    c.execute('SELECT code, expires_at, attempts FROM otp_codes WHERE phone=?', (phone,))
    row = c.fetchone()

    if not row:
        conn.rollback()
        conn.close()
        return jsonify({'error': 'code_not_found'}), 400

    stored_code, expires_at, attempts = row

    if attempts >= 5:
        conn.rollback()
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

    # ✅ Успіх — delete OTP + create session atomically
    c.execute('DELETE FROM otp_codes WHERE phone=?', (phone,))
    # Cap sessions per phone (keep latest 5)
    c.execute('DELETE FROM sessions WHERE phone=? AND token NOT IN '
              '(SELECT token FROM sessions WHERE phone=? ORDER BY created_at DESC LIMIT 4)',
              (phone, phone))
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
        # NOTE: Server timezone is Europe/Kyiv; manual_appointments dates are also Kyiv.
        today_str = kyiv_now().strftime('%Y-%m-%d')
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
                    item = {
                        'name':  row.get('name') or row.get('service') or '',
                        'price': row.get('price') or row.get('cost') or ''
                    }
                    # Описи процедур — для всіх (публічна інформація про послуги)
                    if row.get('desc'):
                        item['desc'] = row['desc']
                    if row.get('duration'):
                        item['duration'] = row['duration']
                    if row.get('prep'):
                        item['prep'] = row['prep']
                    if row.get('aftercare'):
                        item['aftercare'] = row['aftercare']
                    items.append(item)
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
    """Повертає пости згруповані по днях. Кожен день = одна картка."""
    try:
        conn = sqlite3.connect(FEED_DB)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            'SELECT id, tg_msg_id, text, date, media_type, file_id, thumb_id FROM posts ORDER BY date ASC LIMIT 100'
        ).fetchall()
        conn.close()

        # Групуємо по днях (Київський час, не UTC)
        from collections import OrderedDict
        from tz_utils import kyiv_offset
        kyiv_off = kyiv_offset() * 3600  # секунд
        days = OrderedDict()
        for r in rows:
            kyiv_ts = r['date'] + kyiv_off
            day_ts = kyiv_ts - (kyiv_ts % 86400)  # початок дня Київ
            if day_ts not in days:
                days[day_ts] = {'date': r['date'], 'texts': [], 'media': []}
            if r['text'] and r['text'].strip():
                # Fix escaped newlines from TG (literal \n → real newline)
                clean_text = r['text'].strip().replace('\\n', '\n')
                days[day_ts]['texts'].append(clean_text)
            if r['media_type'] and r['file_id']:
                days[day_ts]['media'].append({
                    'type': r['media_type'],
                    'file_id': r['file_id'],
                    'thumb_id': r['thumb_id'] or None,
                })

        # Формуємо результат (новіші першими)
        result = []
        for day_ts in reversed(days):
            d = days[day_ts]
            text = '\n\n'.join(d['texts'])
            # Превью: пріоритет фото, потім відео
            preview_media = None
            for m in d['media']:
                if m['type'] == 'photo':
                    preview_media = m
                    break
            if not preview_media and d['media']:
                preview_media = d['media'][0]
            result.append({
                'date': d['date'],
                'text': text,
                'media': d['media'],
                'preview': preview_media,
                'media_count': len(d['media']),
            })

        return jsonify(result)
    except Exception:
        return jsonify([])

@app.route('/api/feed/media/<fid>')
def feed_media(fid):
    # NOTE: This endpoint is intentionally unauthenticated — media must load without auth
    # (images are referenced in feed posts visible to all users).

    if not re.match(r'^[A-Za-z0-9_-]+$', fid):
        return '', 403
    try:

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
        'permissions':  {},  # filled by frontend via /api/admin/role
    }




# ── ADMIN ──────────────────────────────────────────────────────────────────

def _get_session_phone(token: str):
    """Returns phone from token or None. Also slides session expiry."""
    conn = sqlite3.connect(OTP_DB, timeout=5)
    try:
        now = int(time.time())
        c = conn.cursor()
        c.execute('SELECT phone FROM sessions WHERE token=? AND expires_at>?', (token, now))
        row = c.fetchone()
        if row:
            # Slide session (same as require_auth)
            conn.execute('UPDATE sessions SET expires_at=? WHERE token=?',
                         (now + SESSION_TTL, token))
            conn.commit()
        return row[0] if row else None
    finally:
        conn.close()

def require_admin(f):
    """Декоратор: superadmin, full і specialist. Loads permissions."""
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
        # Load permissions for specialist
        request.admin_permissions = {}
        if request.admin_specialist and request.admin_role == 'specialist':
            try:
                conn = sqlite3.connect(DB_PATH, timeout=5)
                for feat, lvl in conn.execute('SELECT feature, level FROM permissions WHERE specialist=?',
                                              (request.admin_specialist,)).fetchall():
                    request.admin_permissions[feat] = lvl
                conn.close()
            except Exception:
                pass
        return f(*args, **kwargs)
    return decorated

def require_superadmin(f):
    """Декоратор: тільки superadmin panel phone."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
        if not token:
            return jsonify({'error': 'unauthorized'}), 401
        phone = _get_session_phone(token)
        if norm_phone(phone or '') != SUPERADMIN_PHONE:
            return jsonify({'error': 'forbidden'}), 403
        request.admin_phone = SUPERADMIN_PHONE
        request.admin_role = 'superadmin'
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


@app.route('/api/admin/messages/tg-media/<fid>')
def admin_msg_tg_media(fid):
    """Proxy TG Business bot media files. No auth required (media URLs are unguessable file_ids)."""

    if not re.match(r'^[A-Za-z0-9_-]+$', fid):
        return '', 403
    try:

        r = _req.get('https://api.telegram.org/bot{}/getFile'.format(TG_BIZ_TOKEN),
                      params={'file_id': fid}, timeout=5)
        fp = r.json().get('result', {}).get('file_path', '')
        if not fp:
            return '', 404
        media = _req.get('https://api.telegram.org/file/bot{}/{}'.format(TG_BIZ_TOKEN, fp), timeout=15)
        if media.status_code != 200:
            return '', 502
        from flask import Response
        ct = media.headers.get('Content-Type', 'application/octet-stream')
        return Response(media.content, content_type=ct,
                        headers={'Cache-Control': 'public, max-age=86400'})
    except Exception:
        return '', 502


@app.route('/api/admin/stats', methods=['GET'])
@require_admin
def admin_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM clients")
    total_clients = c.fetchone()[0]

    c.execute("SELECT COUNT(DISTINCT phone) FROM push_subscriptions WHERE active=1")
    push_subs = c.fetchone()[0]

    # Записи за останні 30 днів
    # Поточний календарний місяць (1-е число → кінець місяця), без CANCELLED
    # NOTE: kyiv_now() uses server local time (Europe/Kyiv on production).
    # Appointment dates in services_json are also in Kyiv timezone, so comparison is correct.
    now = kyiv_now()
    month_start = now.strftime('%Y-%m-01')
    if now.month == 12:
        month_end = '{}-12-31'.format(now.year)
    else:
        month_end = (now.replace(month=now.month+1, day=1) - timedelta(days=1)).strftime('%Y-%m-%d')
    vis_month = _get_visible_specialists('stat_month')
    if 'all' in vis_month:
        c.execute("""
            SELECT COUNT(*) FROM (
                SELECT json_each.value FROM clients, json_each(clients.services_json)
                WHERE json_extract(json_each.value, '$.date') >= ?
                  AND json_extract(json_each.value, '$.date') <= ?
                  AND IFNULL(json_extract(json_each.value, '$.status'),'') != 'CANCELLED'
            )
        """, (month_start, month_end))
    else:
        spec_names = [request.admin_specialist if s == 'own' else s for s in vis_month]
        spec_names = [s for s in spec_names if s]  # remove None/empty
        if not spec_names:
            spec_names = [request.admin_specialist or 'nobody']
        placeholders = ','.join('?' * len(spec_names))
        c.execute("""
            SELECT COUNT(*) FROM (
                SELECT json_each.value FROM clients, json_each(clients.services_json)
                WHERE json_extract(json_each.value, '$.date') >= ?
                  AND json_extract(json_each.value, '$.date') <= ?
                  AND json_extract(json_each.value, '$.specialist') IN ({})
                  AND IFNULL(json_extract(json_each.value, '$.status'),'') != 'CANCELLED'
            )
        """.format(placeholders), (month_start, month_end) + tuple(spec_names))
    visits_month = c.fetchone()[0]

    # Останні 10 відвідувань
    today_str = kyiv_now().strftime('%Y-%m-%d')
    vis_recent = _get_visible_specialists('stat_recent')
    if 'all' in vis_recent:
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
    else:
        spec_names = [request.admin_specialist if s == 'own' else s for s in vis_recent]
        spec_names = [s for s in spec_names if s]
        if not spec_names:
            spec_names = [request.admin_specialist or 'nobody']
        placeholders = ','.join('?' * len(spec_names))
        c.execute("""
            SELECT c.first_name, c.last_name, c.phone,
                   json_extract(s.value, '$.date') as date,
                   json_extract(s.value, '$.service') as service,
                   json_extract(s.value, '$.hour') as hour
            FROM clients c, json_each(c.services_json) s
            WHERE json_extract(s.value, '$.date') IS NOT NULL
              AND json_extract(s.value, '$.date') >= ?
              AND json_extract(s.value, '$.specialist') IN ({})
              AND IFNULL(json_extract(s.value, '$.status'),'') != 'CANCELLED'
            ORDER BY json_extract(s.value, '$.date') ASC
            LIMIT 10
        """.format(placeholders), (today_str,) + tuple(spec_names))
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
    denied = _check_perm('clients', 'read')
    if denied: return denied
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
        with open(PRICES_PATH, 'r', encoding='utf-8') as _pf:
            data = _json.load(_pf)
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
    denied = _check_perm('clients', 'read')
    if denied: return denied
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

@app.route('/api/admin/client-card/<phone>', methods=['GET'])
@require_admin
def admin_client_card(phone):
    """Client card with all visits — local DB + WLaunch full history."""
    denied = _check_perm('clients', 'read')
    if denied: return denied
    p = norm_phone(phone)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT first_name, last_name, phone, last_service, last_visit, visits_count, services_json "
        "FROM clients WHERE phone=? OR phone LIKE ?",
        (p, '%' + p[-9:])).fetchone()
    if not row:
        conn.close()
        return jsonify({'visits': [], 'visits_count': 0})
    # Manual appointments
    manual = conn.execute(
        "SELECT procedure_name, specialist, date, time, status FROM manual_appointments "
        "WHERE client_phone=? OR client_phone LIKE ? ORDER BY date DESC, time DESC",
        (p, '%' + p[-9:])).fetchall()
    conn.close()

    visits = []
    # Local DB services_json
    local_ids = set()
    try:
        services = json.loads(row['services_json'] or '[]')
        for s in services:
            visits.append({
                'date': s.get('date', ''),
                'service': s.get('service', ''),
                'specialist': s.get('specialist', ''),
                'status': s.get('status', ''),
                'source': 'wlaunch',
            })
            if s.get('appt_id'):
                local_ids.add(s['appt_id'])
    except Exception:
        pass

    # Fetch FULL history from WLaunch API (all time)
    try:
        from wlaunch_api import HEADERS, get_specialist, parse_appt_time
        from config import WLAUNCH_API_URL, COMPANY_ID

        from wlaunch_api import get_branch_id
        branch_id = get_branch_id()
        if branch_id:
            tail = p[-9:] if len(p) >= 9 else p
            url = '{}/company/{}/branch/{}/appointment'.format(WLAUNCH_API_URL, COMPANY_ID, branch_id)
            page = 0
            _deadline = time.time() + 15  # aggregate timeout 15s
            while page < 20 and time.time() < _deadline:
                r = _req.get(url, headers=HEADERS, params={
                    'sort': 'start_time,desc', 'page': page, 'size': 100,
                    'start': '2020-01-01T00:00:00.000Z',
                    'end': '2030-01-01T00:00:00.000Z',
                }, timeout=10)
                data = r.json()
                appts = data.get('content', [])
                if not appts:
                    break
                for appt in appts:
                    cl = appt.get('client', {})
                    cl_phone = ''.join(filter(str.isdigit, cl.get('phone', '')))
                    if cl_phone[-9:] != tail:
                        continue
                    aid = appt.get('id', '')
                    if aid in local_ids:
                        continue  # already have it
                    svcs = appt.get('services', [])
                    svc_name = ', '.join(s.get('name', '') for s in svcs if s.get('name'))
                    vdate, vhour = parse_appt_time(appt.get('start_time', ''))
                    visits.append({
                        'date': vdate,
                        'service': svc_name,
                        'specialist': get_specialist(appt.get('resources', [])),
                        'status': (appt.get('status') or '').upper(),
                        'source': 'wlaunch',
                    })
                total_pages = data.get('page', {}).get('total_pages', 0)
                page += 1
                if page >= total_pages:
                    break
    except Exception as e:
        logger.warning('client-card WLaunch fetch: {}'.format(e))

    # Manual visits
    for m in manual:
        visits.append({
            'date': m['date'],
            'service': m['procedure_name'],
            'specialist': m['specialist'],
            'status': m['status'],
            'source': 'manual',
        })
    visits.sort(key=lambda x: x.get('date', ''), reverse=True)

    return jsonify({
        'name': ((row['first_name'] or '') + ' ' + (row['last_name'] or '')).strip(),
        'phone': row['phone'],
        'last_service': row['last_service'] or '',
        'last_visit': row['last_visit'] or '',
        'visits_count': max(row['visits_count'] or 0, len(visits)),
        'visits': visits,
    })

@app.route('/api/admin/client-photos/<phone>', methods=['GET'])
@require_admin
def admin_client_photos(phone):
    """Get all photos for a client from Google Drive."""
    denied = _check_perm('photo', 'read')
    if denied: return denied
    p = norm_phone(phone)
    # Find client name
    conn = sqlite3.connect(DB_PATH, timeout=5)
    row = conn.execute(
        "SELECT first_name, last_name FROM clients WHERE phone=? OR phone LIKE ?",
        (p, '%' + p[-9:])).fetchone()
    conn.close()
    if not row:
        return jsonify({'photos': []})
    name = ('{} {}'.format(row[0] or '', row[1] or '')).strip()
    if not name:
        return jsonify({'photos': []})
    # Read from photo cache DB (built by photo_cache.py cron)
    PHOTO_CACHE_DB = '/home/gomoncli/zadarma/photo_cache.db'
    try:
        pconn = sqlite3.connect(PHOTO_CACHE_DB, timeout=5)
        pconn.row_factory = sqlite3.Row
        rows = pconn.execute(
            'SELECT file_id, file_name, visit, subfolder, thumbnail, created_time '
            'FROM photo_cache WHERE client_name=? ORDER BY created_time ASC',
            (name,)).fetchall()
        pconn.close()
        result = [{'id': r['file_id'], 'name': r['file_name'], 'visit': r['visit'],
                    'subfolder': r['subfolder'], 'thumbnail': r['thumbnail'],
                    'created': r['created_time']} for r in rows]
        return jsonify({'photos': result, 'client_name': name})
    except Exception as e:
        logger.warning('client-photos cache error: {}'.format(e))
        return jsonify({'photos': [], 'error': str(e)})


@app.route('/api/admin/users-list', methods=['GET'])
@require_admin
def admin_users_list():
    denied = _check_perm('clients', 'read')
    if denied: return denied
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
    denied = _check_perm('clients', 'read')
    if denied: return denied
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
    # Uses stat_month permission (specialist-select), not clients
    # No _check_perm — filtering by visible specialists instead
    from datetime import datetime
    from_date = request.args.get('from', '')
    to_date   = request.args.get('to', '')
    since = from_date if from_date else kyiv_now().strftime('%Y-%m') + '-01'
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT phone, first_name, last_name, services_json
                 FROM clients""")
    rows = c.fetchall()
    conn.close()
    price_lookup = _build_price_lookup()
    visits = []
    vis = _get_visible_specialists('stat_month')
    vis_names = vis if 'all' in vis else [request.admin_specialist if s == 'own' else s for s in vis]
    vis_names = [s for s in vis_names if s]
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
            spec = it.get('specialist', '')
            if 'all' not in vis_names and spec not in vis_names:
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
                'specialist': spec,
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
    perms = {}
    if request.admin_specialist and request.admin_role == 'specialist':
        defaults = {
            'stat_clients_tap': 'allow', 'stat_users_tap': 'allow', 'stat_push_tap': 'allow',
            'stat_month': '["own"]', 'stat_recent': '["own"]', 'calendar': '["own"]',
            'calendar_edit': 'write', 'clients': 'write', 'prices': 'write',
            'messenger': 'write', 'ai_assistant': 'write', 'ai_chat': 'write',
            'sync': 'write', 'photo': 'write',
        }
        for feat in ALL_PERM_FEATURES:
            perms[feat] = request.admin_permissions.get(feat, defaults.get(feat, 'write'))
    return jsonify({'role': request.admin_role, 'specialist': request.admin_specialist,
                    'permissions': perms})


# ── SUPERADMIN PANEL ──────────────────────────────────────────────────────

@app.route('/api/superadmin/resources', methods=['GET'])
@require_superadmin
def superadmin_resources():
    specialists = [
        {'name': 'victoria', 'phone': '380996093860', 'label': 'Вікторія', 'role': 'full'},
        {'name': 'anastasia', 'phone': '380685129121', 'label': 'Анастасія', 'role': 'specialist'},
    ]
    conn = sqlite3.connect(DB_PATH, timeout=5)
    perm_map = {}
    for spec, feat, lvl in conn.execute('SELECT specialist, feature, level FROM permissions').fetchall():
        perm_map.setdefault(spec, {})[feat] = lvl
    conn.close()
    # Default values per feature
    defaults = {
        'stat_clients_tap': 'allow', 'stat_users_tap': 'allow', 'stat_push_tap': 'allow',
        'stat_month': '["all"]', 'stat_recent': '["all"]', 'calendar': '["all"]',
        'calendar_edit': 'write', 'clients': 'write', 'prices': 'write',
        'messenger': 'write', 'ai_assistant': 'write', 'ai_chat': 'write',
        'sync': 'write', 'photo': 'write',
    }
    for s in specialists:
        s['permissions'] = {}
        for feat in ALL_PERM_FEATURES:
            s['permissions'][feat] = perm_map.get(s['name'], {}).get(feat, defaults.get(feat, 'write'))
    return jsonify({
        'specialists': specialists,
        'simple_features': dict(PERM_SIMPLE),
        'specialist_features': list(PERM_SPECIALISTS),
        'all_specialists': ['victoria', 'anastasia'],
    })

@app.route('/api/superadmin/permissions', methods=['PUT'])
@require_superadmin
def superadmin_put_permissions():
    data = request.get_json() or {}
    perms = data.get('permissions', [])
    if not perms:
        return jsonify({'error': 'empty'}), 400
    conn = sqlite3.connect(DB_PATH, timeout=5)
    for p in perms:
        spec = p.get('specialist', '')
        feat = p.get('feature', '')
        lvl = p.get('level', '')
        if spec not in SPECIALIST_MAP.values():
            continue
        if feat not in ALL_PERM_FEATURES:
            continue
        # Validate level: simple string or JSON array for specialist features
        if feat in PERM_SPECIALISTS:
            if not isinstance(lvl, (str, list)):
                continue
            if isinstance(lvl, list):
                lvl = json.dumps(lvl)
        else:
            valid = PERM_SIMPLE.get(feat, ('write', 'read', 'deny'))
            if lvl not in valid:
                continue
        conn.execute(
            'INSERT OR REPLACE INTO permissions (specialist, feature, level, updated_at) '
            'VALUES (?, ?, ?, datetime("now"))', (spec, feat, lvl))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# ── AI CHAT LOG ───────────────────────────────────────────────────────────

AI_CHAT_DB = '/home/gomoncli/zadarma/ai_chat.db'

@app.route('/api/admin/ai-conversations', methods=['GET'])
@require_admin
def admin_ai_conversations():
    """List AI chat sessions (site + app + TG) grouped by session_key."""
    denied = _check_perm('ai_assistant', 'read')
    if denied: return denied

    conversations = []

    # 1. Site/App conversations from ai_chat.db
    try:
        conn = sqlite3.connect(AI_CHAT_DB, timeout=5)
        conn.row_factory = sqlite3.Row
        rows = conn.execute('''
            SELECT session_key, source, user_phone, user_name,
                   MAX(created_at) as last_at,
                   COUNT(*) as msg_count
            FROM ai_messages
            GROUP BY session_key
            ORDER BY last_at DESC
            LIMIT 50
        ''').fetchall()
        for r in rows:
            conversations.append({
                'id': r['session_key'],
                'source': r['source'],
                'phone': r['user_phone'] or '',
                'name': r['user_name'] or r['session_key'],
                'last_at': r['last_at'],
                'msg_count': r['msg_count'],
                'type': 'chat',
            })
        conn.close()
    except Exception as e:
        logger.warning('ai_conversations chat db: {}'.format(e))

    # TG AI conversations NOT included — already visible in TG tab
    conversations.sort(key=lambda x: x.get('last_at', ''), reverse=True)
    return jsonify({'conversations': conversations[:50]})


@app.route('/api/admin/ai-conversations/<path:session_id>', methods=['GET'])
@require_admin
def admin_ai_conversation_thread(session_id):
    """Get messages for a specific AI conversation."""
    denied = _check_perm('ai_assistant', 'read')
    if denied: return denied

    messages = []
    try:
        conn = sqlite3.connect(AI_CHAT_DB, timeout=5)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT role, content, user_name, created_at "
            "FROM ai_messages WHERE session_key=? ORDER BY id ASC LIMIT 100",
            (session_id,)).fetchall()
        for r in rows:
            messages.append({
                'role': r['role'],
                'content': r['content'] or '',
                'name': r['user_name'] or '',
                'is_ai': r['role'] == 'assistant',
                'created_at': r['created_at'],
            })
        conn.close()
    except Exception as e:
        logger.warning('ai_thread: {}'.format(e))

    return jsonify({'messages': messages})


@app.route('/api/superadmin/wlaunch-resources', methods=['GET'])
@require_superadmin
def superadmin_wl_resources_list():
    """List WLaunch resources (specialists)."""
    try:
        from wlaunch_api import get_branch_id, HEADERS
        from config import WLAUNCH_API_URL, COMPANY_ID
        bid = get_branch_id()
        r = _req.get('{}/company/{}/branch/{}/resource'.format(WLAUNCH_API_URL, COMPANY_ID, bid),
                      headers=HEADERS, params={'page': 0, 'size': 50}, timeout=10)
        resources = []
        for res in r.json().get('content', []):
            resources.append({
                'id': res.get('id', ''),
                'name': res.get('name', ''),
                'last_name': res.get('last_name', ''),
                'phone': res.get('phone', ''),
                'active': res.get('active', True),
            })
        return jsonify({'resources': resources})
    except Exception as e:
        return jsonify({'resources': [], 'error': str(e)})


@app.route('/api/superadmin/wlaunch-resources', methods=['POST'])
@require_superadmin
def superadmin_wl_resources_create():
    """Create a WLaunch resource (specialist)."""
    d = request.get_json() or {}
    name = (d.get('name') or '').strip()
    last_name = (d.get('last_name') or '').strip()
    phone = (d.get('phone') or '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    # Normalize phone
    if phone and not phone.startswith('+'):
        phone = '+' + norm_phone(phone)
    try:
        from wlaunch_api import get_branch_id, HEADERS
        from config import WLAUNCH_API_URL, COMPANY_ID
        bid = get_branch_id()
        rt_id = '3f31393d-0b21-11ed-8355-65920565acdd'  # default resource_type_id
        url = '{}/company/{}/branch/{}/resource'.format(WLAUNCH_API_URL, COMPANY_ID, bid)
        h = dict(HEADERS, **{'Content-Type': 'application/json'})
        payload = {'resource': {'name': name, 'last_name': last_name, 'resource_type_id': rt_id}}
        if phone:
            payload['resource']['phone'] = phone
        r = _req.post(url, headers=h, json=payload, timeout=10)
        if r.status_code in (200, 201):
            return jsonify({'ok': True, 'id': r.json().get('id')})
        return jsonify({'error': 'WLaunch: {} {}'.format(r.status_code, r.text[:100])}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/superadmin/wlaunch-resources/<rid>', methods=['DELETE'])
@require_superadmin
def superadmin_wl_resources_deactivate(rid):
    """Deactivate a WLaunch resource."""
    try:
        from wlaunch_api import get_branch_id, HEADERS
        from config import WLAUNCH_API_URL, COMPANY_ID
        bid = get_branch_id()
        url = '{}/company/{}/branch/{}/resource/{}'.format(WLAUNCH_API_URL, COMPANY_ID, bid, rid)
        h = dict(HEADERS, **{'Content-Type': 'application/json'})
        r = _req.post(url, headers=h, json={'resource': {'active': False}}, timeout=10)
        if r.status_code == 200:
            return jsonify({'ok': True})
        return jsonify({'error': 'WLaunch: {}'.format(r.status_code)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/calendar/appointments', methods=['GET'])
@require_admin
def admin_cal_get():
    denied = _check_perm('calendar', 'read')
    if denied: return denied
    """Список записів: manual_appointments + WLaunch (services_json), фільтр по даті."""
    from_date = request.args.get('from', '')
    to_date   = request.args.get('to', '')
    result = []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Visible specialists for calendar
    vis_cal = _get_visible_specialists('calendar')
    vis_names = vis_cal if 'all' in vis_cal else [request.admin_specialist if s == 'own' else s for s in vis_cal]

    # 1. Manual appointments
    query = "SELECT * FROM manual_appointments WHERE 1=1"
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
        spec = row_dict.get('specialist', '')
        if 'all' not in vis_names and spec not in vis_names:
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
            if from_date and d < from_date:
                continue
            if to_date and d > to_date:
                continue
            specialist = it.get('specialist')
            hour = it.get('hour')
            time_str = '{:02d}:00'.format(hour) if hour is not None else ''
            name = ((row['first_name'] or '') + ' ' + (row['last_name'] or '')).strip()
            is_other_spec = 'all' not in vis_names and specialist not in vis_names
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

    # 3. Breaks
    brk_q = "SELECT id, specialist, date, time_from, time_to, reason FROM specialist_breaks WHERE 1=1"
    brk_params = []
    if from_date:
        brk_q += ' AND date >= ?'; brk_params.append(from_date)
    if to_date:
        brk_q += ' AND date <= ?'; brk_params.append(to_date)
    for bid, spec, bdate, tf, tt, reason in conn.execute(brk_q, brk_params).fetchall():
        if 'all' not in vis_names and spec not in vis_names:
            continue
        dur = _time_to_min(tt) - _time_to_min(tf)
        result.append({
            'id': 'brk_{}'.format(bid),
            'specialist': spec,
            'date': bdate,
            'time': tf,
            'duration_min': dur if dur > 0 else 60,
            'client_name': reason or 'Перерва',
            'procedure_name': 'Перерва',
            'source': 'break',
            'status': 'CONFIRMED',
            'break_id': bid,
        })

    conn.close()
    result.sort(key=lambda x: (x['date'], x['time'] or ''))
    return jsonify({'appointments': result})


@app.route('/api/admin/calendar/breaks', methods=['POST'])
@require_admin
def admin_break_create():
    """Create a specialist break / off-hours."""
    d = request.get_json() or {}
    specialist = (d.get('specialist') or '').strip()
    date = (d.get('date') or '').strip()
    time_from = (d.get('time_from') or '').strip()
    time_to = (d.get('time_to') or '').strip()
    reason = (d.get('reason') or '').strip()

    if not specialist or not date or not time_from or not time_to:
        return jsonify({'error': 'missing_fields'}), 400

    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        return jsonify({'error': 'invalid_date'}), 400
    if not re.match(r'^\d{2}:\d{2}$', time_from) or not re.match(r'^\d{2}:\d{2}$', time_to):
        return jsonify({'error': 'invalid_time'}), 400
    if specialist not in ('victoria', 'anastasia'):
        return jsonify({'error': 'invalid_specialist'}), 400
    if request.admin_role == 'specialist' and specialist != request.admin_specialist:
        return jsonify({'error': 'forbidden'}), 403
    if time_from >= time_to:
        return jsonify({'error': 'invalid_range', 'detail': 'Час початку має бути раніше за час кінця'}), 400

    start_min = _time_to_min(time_from)
    end_min = _time_to_min(time_to)

    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute('BEGIN IMMEDIATE')
    if _check_overlap(conn, specialist, date, start_min, end_min):
        conn.rollback()
        conn.close()
        return jsonify({'error': 'conflict', 'detail': 'Перетин з існуючим записом або перервою'}), 409
    conn.execute(
        'INSERT INTO specialist_breaks (specialist, date, time_from, time_to, reason, created_by) VALUES (?,?,?,?,?,?)',
        (specialist, date, time_from, time_to, reason, request.admin_phone))
    conn.commit()
    conn.close()

    # Sync to WLaunch — create OFF block
    wl_id = None
    try:

        from wlaunch_api import get_branch_id, get_wlaunch_resources, HEADERS
        from config import WLAUNCH_API_URL, COMPANY_ID
        bid = get_branch_id()
        resources = get_wlaunch_resources(bid)
        rid = resources.get(specialist)
        if rid and bid:
            wl_url = '{}/company/{}/branch/{}/resource/{}/schedule/day'.format(
                WLAUNCH_API_URL, COMPANY_ID, bid, rid)
            wl_h = dict(HEADERS, **{'Content-Type': 'application/json'})
            payload = {'frame': {
                'date': date,
                'start_time': start_min * 60,
                'end_time': end_min * 60,
                'type': 'OFF',
            }}
            r = _req.post(wl_url, headers=wl_h, json=payload, timeout=10)
            if r.status_code in (200, 201):
                wl_id = r.json().get('id')
                logger.info('WLaunch break created: {}'.format(wl_id))
                # Save WLaunch ID to local break
                conn2 = sqlite3.connect(DB_PATH, timeout=5)
                conn2.execute('UPDATE specialist_breaks SET reason=? WHERE specialist=? AND date=? AND time_from=? AND time_to=? AND created_by=? ORDER BY id DESC LIMIT 1',
                    ((reason + ' wl:' + wl_id).strip() if reason else 'wl:' + wl_id,
                     specialist, date, time_from, time_to, request.admin_phone))
                conn2.commit()
                conn2.close()
            else:
                logger.warning('WLaunch break failed: {} {}'.format(r.status_code, r.text[:200]))
    except Exception as e:
        logger.warning('WLaunch break sync error: {}'.format(e))

    return jsonify({'ok': True, 'wlaunch_id': wl_id})


@app.route('/api/admin/calendar/breaks/<int:break_id>', methods=['DELETE'])
@require_admin
def admin_break_delete(break_id):
    """Delete a specialist break."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT * FROM specialist_breaks WHERE id=?', (break_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'not_found'}), 404
    if request.admin_role == 'specialist' and row['specialist'] != request.admin_specialist:
        conn.close()
        return jsonify({'error': 'forbidden'}), 403
    # Extract WLaunch ID from reason field (wl:UUID)

    wl_id = None
    reason = row['reason'] or ''
    m = re.search(r'wl:([a-f0-9-]+)', reason, re.IGNORECASE)
    if m:
        wl_id = m.group(1)

    conn.execute('DELETE FROM specialist_breaks WHERE id=?', (break_id,))
    conn.commit()
    conn.close()

    # Delete from WLaunch
    if wl_id:
        try:
    
            from wlaunch_api import get_branch_id, get_wlaunch_resources, HEADERS
            from config import WLAUNCH_API_URL, COMPANY_ID
            bid = get_branch_id()
            resources = get_wlaunch_resources(bid)
            rid = resources.get(row['specialist'])
            if rid and bid:
                wl_url = '{}/company/{}/branch/{}/resource/{}/schedule/day/{}'.format(
                    WLAUNCH_API_URL, COMPANY_ID, bid, rid, wl_id)
                wl_h = dict(HEADERS, **{'Content-Type': 'application/json'})
                r = _req.post(wl_url, headers=wl_h, json={'frame': {'active': False}}, timeout=10)
                logger.info('WLaunch break deleted: {} status={}'.format(wl_id, r.status_code))
        except Exception as e:
            logger.warning('WLaunch break delete error: {}'.format(e))

    return jsonify({'ok': True})


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

    from_date = (kyiv_now() - timedelta(days=7)).strftime('%Y-%m-%d')
    to_date   = (kyiv_now() + timedelta(days=90)).strftime('%Y-%m-%d')

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

    # WLaunch — pre-filter by date range in JSON (avoids scanning all 600 clients)
    wl_q = 'SELECT phone, first_name, last_name, services_json FROM clients WHERE 1=1'
    wl_params = []
    if from_date:
        wl_q += ' AND services_json LIKE ?'; wl_params.append('%' + from_date[:7] + '%')  # YYYY-MM prefix
    for row in conn.execute(wl_q, wl_params).fetchall():
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
    denied = _check_perm('calendar', 'write')
    if denied: return denied
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


    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        return jsonify({'error': 'invalid_date'}), 400
    if not re.match(r'^\d{2}:\d{2}$', appt_time):
        return jsonify({'error': 'invalid_time'}), 400
    if specialist not in ('victoria', 'anastasia'):
        return jsonify({'error': 'invalid_specialist'}), 400

    # Specialist може записувати тільки до себе
    if request.admin_role == 'specialist' and specialist != request.admin_specialist:
        return jsonify({'error': 'forbidden'}), 403

    # Validate end time doesn't exceed 21:00
    start_min = int(appt_time[:2]) * 60 + int(appt_time[3:5])
    end_min = start_min + duration
    if end_min > 21 * 60:
        return jsonify({'error': 'too_late', 'detail': 'Запис не може закінчуватись пізніше 21:00'}), 400

    # 1. Спробувати створити в WLaunch. Якщо WLaunch відмовив через конфлікт
    #    розкладу (validation) — повертаємо помилку. Якщо WLaunch недоступний
    #    (мережа, серверна помилка) — створюємо локально як fallback.
    wl_id = None
    wl_warning = None
    try:
        from wlaunch_api import create_wlaunch_appointment
        wl_id, wl_err = create_wlaunch_appointment(
            client_phone, client_name, procedure_name,
            specialist, date, appt_time, duration
        )
        if wl_err:
            wl_lower = wl_err.lower()
            if 'unavailable' in wl_lower:
                return jsonify({'error': 'wlaunch_rejected',
                    'detail': 'Спеціаліст недоступний у WLaunch у цей час. Перевірте розклад або оберіть інший час.'}), 409
            if wl_err.startswith('http_422'):
                return jsonify({'error': 'wlaunch_rejected',
                    'detail': 'WLaunch відхилив запис. Перевірте дані.'}), 409
            # Any other WLaunch error — block creation
            logger.error('WLaunch error: {}'.format(wl_err))
            return jsonify({'error': 'wlaunch_rejected',
                'detail': 'WLaunch помилка: {}. Спробуйте пізніше.'.format(wl_err)}), 409
    except Exception as _e:
        logger.error('WLaunch create exception: {}'.format(_e))
        return jsonify({'error': 'wlaunch_rejected',
            'detail': 'WLaunch недоступний. Спробуйте пізніше.'}), 503

    # 2. WLaunch OK — створюємо локальний запис
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute('BEGIN IMMEDIATE')
    new_start = _time_to_min(appt_time)
    new_end   = new_start + duration
    if _check_overlap(conn, specialist, date, new_start, new_end):
        conn.rollback()
        conn.close()
        # Rollback WLaunch if overlap detected locally
        if wl_id:
            try:
                _cancel_wlaunch_appt(wl_id)
                logger.warning('WLaunch rollback (local overlap): {}'.format(wl_id))
            except Exception as _re:
                logger.error('WLaunch rollback failed: {}'.format(_re))
                try:
                    from notifier import _send_tg, _get_tg_id
                    _send_tg(_get_tg_id('380733103110'), 'WLaunch orphan: rollback failed for wl_id={}. Manual cleanup needed.'.format(wl_id))
                except Exception:
                    pass
        return jsonify({'error': 'conflict'}), 409

    wl_notes = 'wl:{}'.format(wl_id) if wl_id else ''
    full_notes = (notes + ' ' + wl_notes).strip() if notes else wl_notes

    try:
        c = conn.cursor()
        c.execute(
            '''INSERT INTO manual_appointments
               (client_phone, client_name, procedure_name, specialist, date, time, duration, notes, wlaunch_id, created_by)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (client_phone, client_name, procedure_name, specialist, date, appt_time, duration, full_notes, wl_id, request.admin_phone)
        )
        new_id = c.lastrowid
        conn.commit()
    except Exception as _db_err:
        conn.rollback()
        conn.close()
        # Rollback WLaunch if local DB failed
        if wl_id:
            try:
                _cancel_wlaunch_appt(wl_id)
                logger.warning('WLaunch rollback (DB error): {}'.format(wl_id))
            except Exception as _re:
                logger.error('WLaunch rollback failed: {}'.format(_re))
                try:
                    from notifier import _send_tg, _get_tg_id
                    _send_tg(_get_tg_id('380733103110'), 'WLaunch orphan: rollback failed for wl_id={}. Manual cleanup needed.'.format(wl_id))
                except Exception:
                    pass
        logger.error('Local DB insert failed: {}'.format(_db_err))
        return jsonify({'error': 'db_error'}), 500
    conn.close()

    # Push підтвердження клієнту (тільки push, TG/SMS — WLaunch)
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

    resp = {'ok': True, 'id': new_id, 'wlaunch_id': wl_id}
    if wl_warning:
        resp['warning'] = wl_warning
    return jsonify(resp)

@app.route('/api/admin/calendar/appointments/<int:appt_id>', methods=['PUT'])
@require_admin
def admin_cal_update(appt_id):
    d = request.get_json() or {}
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT * FROM manual_appointments WHERE id=?', (appt_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'not_found'}), 404
    if request.admin_role == 'specialist' and row['specialist'] != request.admin_specialist:
        conn.close()
        return jsonify({'error': 'forbidden'}), 403

    # Validate date/time/specialist if provided

    if 'date' in d and d['date']:
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', d['date']):
            conn.close()
            return jsonify({'error': 'invalid_date'}), 400
    if 'time' in d and d['time']:
        if not re.match(r'^\d{2}:\d{2}$', d['time']):
            conn.close()
            return jsonify({'error': 'invalid_time'}), 400
    if 'specialist' in d and d['specialist']:
        if d['specialist'] not in ('victoria', 'anastasia'):
            conn.close()
            return jsonify({'error': 'invalid_specialist'}), 400

    fields = ['procedure_name', 'specialist', 'date', 'time', 'status', 'notes', 'client_name', 'client_phone', 'duration']
    updates, params = [], []
    for f in fields:
        if f in d:
            updates.append('{} = ?'.format(f))
            params.append(d[f])
    if not updates:
        conn.close()
        return jsonify({'ok': True})

    # Atomic overlap check + update
    conn.execute('BEGIN IMMEDIATE')

    # Overlap check only when time/date/specialist/duration is being changed
    time_related = {'specialist', 'date', 'time', 'duration'}
    if time_related.intersection(set(d.keys())):
        eff_specialist = d.get('specialist', row['specialist'])
        eff_date       = d.get('date',       row['date'])
        eff_time       = d.get('time',       row['time'])
        eff_duration   = int(d.get('duration', row['duration'] or 60) or 60)
        new_start = _time_to_min(eff_time)
        new_end   = new_start + eff_duration
        # Extract WLaunch ID to exclude its copy from overlap check
        wl_id_to_exclude = row['wlaunch_id'] or None
        if not wl_id_to_exclude:
            notes = row['notes'] or ''
            m = re.search(r'wl:([a-f0-9-]+)', notes, re.IGNORECASE)
            if m:
                wl_id_to_exclude = m.group(1)
        if _check_overlap(conn, eff_specialist, eff_date, new_start, new_end, exclude_id=appt_id, exclude_wl_id=wl_id_to_exclude):
            conn.rollback()
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
    # Cancel in WLaunch FIRST (before local commit)
    wl_id = row['wlaunch_id'] if row['wlaunch_id'] else None
    wl_warning = None
    if not wl_id:
    
        m = re.search(r'wl:([a-f0-9-]+)', row['notes'] or '', re.IGNORECASE)
        if m:
            wl_id = m.group(1)
    if wl_id:
        try:
            _cancel_wlaunch_appt(wl_id)
            logger.info('WLaunch cancel on delete: {}'.format(wl_id))
        except Exception as _wle:
            logger.error('WLaunch cancel failed on delete: {}'.format(_wle))
            wl_warning = 'WLaunch cancel failed: {}'.format(_wle)

    conn.execute("UPDATE manual_appointments SET status='CANCELLED' WHERE id=?", (appt_id,))
    conn.commit()
    conn.close()

    # Push клієнту + TG спеціалісту (SMS/TG клієнту — WLaunch)
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

    resp = {'ok': True}
    if wl_warning:
        resp['warning'] = wl_warning
    return jsonify(resp)

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


# (Photo albums: see gdrive.py + photo_reminder.py)

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

    today = kyiv_now().strftime('%Y-%m-%d')
    wd_names = ['понеділок','вівторок','середа','четвер','п\'ятниця','субота','неділя']
    today_wd = wd_names[kyiv_now().weekday()]

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
        'Ти — асистент адміністратора студії краси Dr. Gómon.\n'
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

    # Rate limit: max 5 SMS per phone per day
    today_str = kyiv_now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(OTP_DB)
    try:
        row = conn.execute('SELECT count, reset_date FROM sms_rate WHERE phone=?', (phone,)).fetchone()
        if row:
            if row[1] == today_str:
                if row[0] >= 5:
                    return jsonify({'error': 'rate_limited'}), 429
            else:
                conn.execute('UPDATE sms_rate SET count=0, reset_date=? WHERE phone=?', (today_str, phone))
                conn.commit()
        # else: will be inserted after sending
    finally:
        conn.close()

    # Захист від зловживань: тільки якщо телефон є в leads (юзер проходив через додаток)
    conn = sqlite3.connect(OTP_DB)
    try:
        c = conn.cursor()
        c.execute("SELECT phone FROM leads WHERE phone=? AND created_at >= datetime('now','-3 hours')", (phone,))
        row = c.fetchone()
    finally:
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

    # Increment SMS rate limit counter
    try:
        conn = sqlite3.connect(OTP_DB)
        try:
            today_str = kyiv_now().strftime('%Y-%m-%d')
            conn.execute(
                'INSERT INTO sms_rate (phone, count, reset_date) VALUES (?,1,?) '
                'ON CONFLICT(phone) DO UPDATE SET count=count+1, reset_date=?',
                (phone, today_str, today_str))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass

    # Оновлюємо процедуру в leads
    try:
        conn = sqlite3.connect(OTP_DB)
        try:
            conn.execute('UPDATE leads SET procedure=? WHERE phone=?', (procedure, phone))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass

    return jsonify({'ok': ok})


# ── CANCEL APPOINTMENT ──

def _find_wlaunch_appt_id(phone, date_str, service, branch_id=None):
    """Шукає ID запису в WLaunch за телефоном і датою.
    Розширений UTC діапазон +-1 день для коректної роботи з DST."""

    from config import WLAUNCH_API_KEY, COMPANY_ID, WLAUNCH_API_URL
    from datetime import datetime as _dt, timedelta as _td
    headers = {
        "Authorization": "Bearer " + WLAUNCH_API_KEY,
        "Accept": "application/json"
    }
    if not branch_id:
        from wlaunch_api import get_branch_id
        branch_id = get_branch_id()
    if not branch_id:
        return None

    # Expand search range +-1 day to handle UTC/Kyiv timezone edge cases
    try:
        d = _dt.strptime(date_str, '%Y-%m-%d')
        start_d = (d - _td(days=1)).strftime('%Y-%m-%d')
        end_d = (d + _td(days=1)).strftime('%Y-%m-%d')
    except Exception:
        start_d = end_d = date_str

    phone_digits = ''.join(filter(str.isdigit, phone))
    url = "{}/company/{}/branch/{}/appointment".format(WLAUNCH_API_URL, COMPANY_ID, branch_id)
    params = {
        "sort": "start_time,desc", "page": 0, "size": 100,
        "start": start_d + "T00:00:00.000Z",
        "end":   end_d + "T23:59:59.999Z"
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


def _cancel_wlaunch_appt(appt_id, branch_id=None):
    """Скасовує запис у WLaunch через POST {"appointment": {"id": ..., "status": "CANCELLED"}}"""

    from config import WLAUNCH_API_KEY, COMPANY_ID, WLAUNCH_API_URL
    headers = {
        "Authorization": "Bearer " + WLAUNCH_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    if not branch_id:
        from wlaunch_api import get_branch_id
        branch_id = get_branch_id()
    if not branch_id:
        return False, "no_branch"

    url = "{}/company/{}/branch/{}/appointment/{}".format(WLAUNCH_API_URL, COMPANY_ID, branch_id, appt_id)
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
        try:
            conn.execute("UPDATE clients SET services_json=? WHERE phone=? OR phone=?",
                         (json.dumps(items, ensure_ascii=False), phone, norm_phone(phone)))
            conn.commit()
        finally:
            conn.close()


def _tg_notify_cancel(name, phone, date_str, service):
    """Telegram notification to admin about cancellation"""

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

    # Fetch branch_id once for both find + cancel
    from wlaunch_api import get_branch_id as _get_bid
    _branch_id = _get_bid()

    # Extract specialist BEFORE updating local DB (so status is still CONFIRMED)
    _client = get_client(phone)
    _client_name = ((_client.get('first_name','') + ' ' + _client.get('last_name','')).strip()
                    if _client else '')
    _specialist = None
    if _client:
        for _it in json.loads(_client.get('services_json','[]') or '[]'):
            if _it.get('date') == date and (not service or _it.get('service') == service):
                _specialist = _it.get('specialist')
                break

    # Знаходимо WLaunch ID якщо не переданий
    if not appt_id:
        appt_id = _find_wlaunch_appt_id(phone, date, service, branch_id=_branch_id)
        if not appt_id:
            return jsonify({'error': 'appointment_not_found'}), 404

    # Скасовуємо в WLaunch
    ok, err = _cancel_wlaunch_appt(appt_id, branch_id=_branch_id)
    if not ok:
        logger.error("cancel failed for {}: {}".format(phone, err))
        return jsonify({'error': 'cancel_failed', 'detail': err}), 502

    # Оновлюємо локальну БД
    _update_local_appt_cancelled(phone, date, service)

    # Push клієнту + TG спеціалісту (SMS/TG клієнту — WLaunch)
    try:
        from notifier import send_cancellation
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
        logger.error('notifier cancel error: {}'.format(_e))

    logger.info("Cancelled appointment: {} {} {}".format(phone, date, service))
    return jsonify({'ok': True})

# ── UNIFIED MESSENGER ENDPOINTS ──

def _get_client_name(conn, phone):
    """Get client name from clients table by phone."""
    if not phone:
        return None
    row = conn.execute(
        "SELECT first_name, last_name FROM clients WHERE phone=? OR phone=?",
        (phone, norm_phone(phone))
    ).fetchone()
    if row:
        return '{} {}'.format(row[0] or '', row[1] or '').strip() or None
    return None


@app.route('/api/admin/messages', methods=['GET'])
@require_admin
def admin_messages_list():
    denied = _check_perm('messenger', 'read')
    if denied: return denied
    """List conversations with last message, unread count."""
    platform = request.args.get('platform', '').strip()
    unread_only = request.args.get('unread_only', '') == '1'

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Subquery: get latest message per conversation
        query = """
            SELECT m.conversation_id, m.client_phone, m.sender_name, m.platform,
                   m.content AS last_message, m.created_at AS last_at,
                   m.media_type, m.is_from_admin,
                   (SELECT COUNT(*) FROM messages m2
                    WHERE m2.conversation_id = m.conversation_id
                      AND m2.is_read = 0 AND m2.is_from_admin = 0) AS unread_count
            FROM messages m
            WHERE m.id = (SELECT MAX(id) FROM messages m3
                          WHERE m3.conversation_id = m.conversation_id)
        """
        params = []
        if platform:
            query += " AND m.platform = ?"
            params.append(platform)
        query += " ORDER BY m.created_at DESC LIMIT 50"

        rows = conn.execute(query, params).fetchall()

        result = []
        for r in rows:
            uc = r['unread_count']
            if unread_only and uc == 0:
                continue
            client_name = _get_client_name(conn, r['client_phone']) or r['sender_name']
            result.append({
                'conversation_id': r['conversation_id'],
                'client_phone':    r['client_phone'],
                'client_name':     client_name,
                'sender_name':     r['sender_name'],
                'platform':        r['platform'],
                'last_message':    r['last_message'],
                'last_at':         r['last_at'],
                'media_type':      r['media_type'],
                'is_from_admin':   r['is_from_admin'],
                'unread_count':    uc,
            })
        return jsonify({'conversations': result})
    finally:
        conn.close()


@app.route('/api/admin/messages/<conv_id>', methods=['GET'])
@require_admin
def admin_messages_thread(conv_id):
    """Get messages for a conversation."""

    if not re.match(r'^[a-z]{2,10}_[A-Za-z0-9_-]+$', conv_id):
        return jsonify({'error': 'invalid_conv_id'}), 400

    limit = min(int(request.args.get('limit', 50)), 200)
    before_id = request.args.get('before_id', '')

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT * FROM messages WHERE conversation_id = ?"
        params = [conv_id]
        if before_id:
            query += " AND id < ?"
            params.append(int(before_id))
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        messages = []
        for r in rows:
            messages.append({
                'id':            r['id'],
                'platform':      r['platform'],
                'sender_id':     r['sender_id'],
                'sender_name':   r['sender_name'],
                'client_phone':  r['client_phone'],
                'content':       r['content'],
                'media_type':    r['media_type'],
                'file_id':       r['file_id'],
                'created_at':    r['created_at'],
                'is_from_admin': r['is_from_admin'],
                'admin_phone':   r['admin_phone'],
                'is_read':       r['is_read'],
            })
        # Return in chronological order
        messages.reverse()
        return jsonify({'messages': messages})
    finally:
        conn.close()


def _get_biz_connection_id(chat_id):
    """Get business_connection_id for a chat from biz_connections table."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        try:
            row = conn.execute(
                "SELECT biz_conn_id FROM biz_connections WHERE chat_id=?",
                (str(chat_id),)).fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    except Exception as e:
        logger.error('_get_biz_connection_id error: {}'.format(e))
        return None

def _send_tg_from_api(chat_id, text, media_type='text', media_url=None, file_id=None, file_path=None):
    """Send a Telegram message via Business Bot API (used by admin messenger).

    media_type: 'text', 'photo', 'video', 'voice'
    media_url:  URL to forward (not used for TG currently)
    file_id:    existing TG file_id to re-send
    file_path:  local file path to upload
    """

    base = 'https://api.telegram.org/bot{}'.format(TG_BIZ_TOKEN)
    cid = int(chat_id)
    biz_conn = _get_biz_connection_id(chat_id)

    if media_type == 'text' or (not media_url and not file_id and not file_path):
        payload = {'chat_id': cid, 'text': text or '.'}
        if biz_conn:
            payload['business_connection_id'] = biz_conn
        r = _req.post(base + '/sendMessage', json=payload, timeout=10)
        return r.json()

    method_map = {'photo': 'sendPhoto', 'video': 'sendVideo', 'voice': 'sendVoice'}
    field_map = {'photo': 'photo', 'video': 'video', 'voice': 'voice'}
    method = method_map.get(media_type, 'sendDocument')
    field = field_map.get(media_type, 'document')

    # Option 1: re-send by file_id (cheapest)
    if file_id:
        payload = {'chat_id': cid, field: file_id}
        if text:
            payload['caption'] = text
        if biz_conn:
            payload['business_connection_id'] = biz_conn
        r = _req.post(base + '/' + method, json=payload, timeout=15)
        return r.json()

    # Option 2: upload local file
    if file_path and os.path.isfile(file_path):
        with open(file_path, 'rb') as fobj:
            data = {'chat_id': str(cid)}
            if text:
                data['caption'] = text
            if biz_conn:
                data['business_connection_id'] = biz_conn
            r = _req.post(base + '/' + method,
                          data=data,
                          files={field: fobj},
                          timeout=30)
        return r.json()

    # Option 3: send by URL
    if media_url:
        payload = {'chat_id': cid, field: media_url}
        if text:
            payload['caption'] = text
        r = _req.post(base + '/' + method, json=payload, timeout=15)
        return r.json()

    # Fallback: text only
    r = _req.post(base + '/sendMessage',
                  json={'chat_id': cid, 'text': text or '.'},
                  timeout=10)
    return r.json()


@app.route('/api/admin/messages/send', methods=['POST'])
@require_admin
def admin_messages_send():
    """Send a reply in a conversation (text or media)."""
    data = request.get_json() or {}
    conv_id = (data.get('conversation_id') or '').strip()
    text = (data.get('text') or data.get('message') or '').strip()
    media_type = (data.get('media_type') or 'text').strip()
    media_url = (data.get('media_url') or '').strip()
    file_id = (data.get('file_id') or '').strip()
    file_ref = (data.get('file_ref') or '').strip()  # local filename from upload

    if not conv_id:
        return jsonify({'error': 'missing_fields'}), 400
    # Need either text or media
    if not text and media_type == 'text':
        return jsonify({'error': 'missing_fields'}), 400


    if not re.match(r'^[a-z]{2,10}_[A-Za-z0-9_-]+$', conv_id):
        return jsonify({'error': 'invalid_conv_id'}), 400

    if media_type not in ('text', 'photo', 'video', 'voice'):
        return jsonify({'error': 'invalid_media_type'}), 400

    # Determine platform and recipient from conversation_id
    parts = conv_id.split('_', 1)
    platform = parts[0]  # 'tg', 'ig', etc.
    recipient_id = parts[1] if len(parts) > 1 else ''

    # Resolve local file path from file_ref
    file_path = None
    if file_ref:
    
        if re.match(r'^[A-Za-z0-9_.-]+$', file_ref):
            candidate = os.path.join('/home/gomoncli/zadarma/msg_media', file_ref)
            if os.path.isfile(candidate):
                file_path = candidate

    sent = False
    error_detail = None
    tg_file_id = None  # capture file_id from TG response for DB

    if platform == 'tg':
        # Send via Telegram Bot API
        try:
            result = _send_tg_from_api(
                recipient_id, text,
                media_type=media_type,
                media_url=media_url or None,
                file_id=file_id or None,
                file_path=file_path
            )
            if result.get('ok'):
                sent = True
                # Extract file_id from response for DB storage
                msg_result = result.get('result', {})
                if media_type == 'photo' and msg_result.get('photo'):
                    tg_file_id = msg_result['photo'][-1].get('file_id', '')
                elif media_type == 'video' and msg_result.get('video'):
                    tg_file_id = msg_result['video'].get('file_id', '')
                elif media_type == 'voice' and msg_result.get('voice'):
                    tg_file_id = msg_result['voice'].get('file_id', '')
            else:
                error_detail = result.get('description', 'telegram_error')
        except Exception as e:
            error_detail = str(e)
    elif platform == 'ig':
        # TODO: Instagram Graph API media sending
        # For now, only text is supported for IG
        if media_type != 'text':
            error_detail = 'instagram_media_not_implemented'
        else:
            error_detail = 'instagram_not_implemented'
    else:
        error_detail = 'unknown_platform'

    if not sent and error_detail:
        logger.error("admin_messages_send failed: {} {}".format(conv_id, error_detail))
        return jsonify({'error': 'send_failed', 'detail': error_detail}), 502

    # Save admin message to DB
    content_for_db = text
    if media_type != 'text' and not text:
        type_labels = {'photo': '[Фото]', 'video': '[Відео]', 'voice': '[Голосове]'}
        content_for_db = type_labels.get(media_type, '[Медіа]')

    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        # Look up client_phone for this conversation
        row = conn.execute(
            "SELECT client_phone FROM messages WHERE conversation_id=? LIMIT 1",
            (conv_id,)
        ).fetchone()
        client_phone = row[0] if row else None

        conn.execute(
            "INSERT INTO messages (platform, conversation_id, sender_id, sender_name, "
            "client_phone, content, media_type, file_id, is_from_admin, admin_phone) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (platform, conv_id, 'admin_' + request.admin_phone,
             'Admin', client_phone, content_for_db, media_type,
             tg_file_id or file_id or '', 1, request.admin_phone))
        conn.commit()
    finally:
        conn.close()

    return jsonify({'ok': True, 'media_type': media_type, 'file_id': tg_file_id or file_id or ''})


MSG_MEDIA_DIR = '/home/gomoncli/zadarma/msg_media'


@app.route('/api/admin/messages/upload', methods=['POST'])
@require_admin
def admin_messages_upload():
    """Upload media file for messenger (photo/video/voice)."""
    if 'file' not in request.files:
        return jsonify({'error': 'no_file'}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'empty_filename'}), 400

    # Determine media type from content type
    ct = (f.content_type or '').lower()
    if ct.startswith('image/'):
        media_type = 'photo'
    elif ct.startswith('video/'):
        media_type = 'video'
    elif ct.startswith('audio/') or 'ogg' in ct or 'webm' in ct:
        media_type = 'voice'
    else:
        return jsonify({'error': 'unsupported_type', 'detail': ct}), 400

    # Limit file size (10MB)
    f.seek(0, 2)
    size = f.tell()
    f.seek(0)
    if size > 10 * 1024 * 1024:
        return jsonify({'error': 'file_too_large'}), 400

    # Ensure directory exists
    os.makedirs(MSG_MEDIA_DIR, exist_ok=True)

    # Generate safe filename

    ext_map = {
        'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp',
        'video/mp4': '.mp4', 'video/quicktime': '.mov',
        'audio/ogg': '.ogg', 'audio/webm': '.webm', 'audio/mpeg': '.mp3',
        'audio/ogg; codecs=opus': '.ogg',
    }
    ext = ext_map.get(ct, '')
    if not ext:
        # Try from filename
        orig = f.filename or ''
        if '.' in orig:
            ext = '.' + re.sub(r'[^a-zA-Z0-9]', '', orig.rsplit('.', 1)[-1])[:5]
        else:
            ext = '.bin'
    safe_name = secrets.token_urlsafe(16) + ext
    save_path = os.path.join(MSG_MEDIA_DIR, safe_name)
    f.save(save_path)

    logger.info("admin_messages_upload: {} ({}, {} bytes) by {}".format(
        safe_name, media_type, size, request.admin_phone))

    return jsonify({
        'ok': True,
        'file_ref': safe_name,
        'media_type': media_type,
        'size': size
    })


@app.route('/api/admin/messages/media/<fname>')
@require_admin
def admin_messages_media(fname):
    """Serve uploaded media file (admin only)."""

    if not re.match(r'^[A-Za-z0-9_.-]+$', fname):
        return '', 403
    fpath = os.path.join(MSG_MEDIA_DIR, fname)
    if not os.path.isfile(fpath):
        return '', 404
    return send_from_directory(MSG_MEDIA_DIR, fname)


@app.route('/api/admin/messages/read', methods=['POST'])
@require_admin
def admin_messages_read():
    """Mark all messages in a conversation as read."""
    data = request.get_json() or {}
    conv_id = (data.get('conversation_id') or '').strip()
    if not conv_id:
        return jsonify({'error': 'missing_conversation_id'}), 400


    if not re.match(r'^[a-z]{2,10}_[A-Za-z0-9_-]+$', conv_id):
        return jsonify({'error': 'invalid_conv_id'}), 400

    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute(
            "UPDATE messages SET is_read = 1 "
            "WHERE conversation_id = ? AND is_read = 0 AND is_from_admin = 0",
            (conv_id,))
        conn.commit()
        updated = conn.execute("SELECT changes()").fetchone()[0]
    finally:
        conn.close()

    return jsonify({'ok': True, 'marked': updated})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=False)
