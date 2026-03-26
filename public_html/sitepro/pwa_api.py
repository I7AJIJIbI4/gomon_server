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

from flask import Flask, request, jsonify, send_from_directory
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
OTP_DB       = '/home/gomoncli/zadarma/otp_sessions.db'
PRICES_PATH  = '/home/gomoncli/private_data/prices.json'
PWA_DIR      = '/home/gomoncli/public_html/app'
OTP_TTL      = 300    # 5 хв
SESSION_TTL  = 86400  # 24 год

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

# ── HELPERS ──

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

def get_client(phone: str) -> dict | None:
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
        date_str = item.get('date', '')
        result.append({
            'service': item.get('service', ''),
            'date':    date_str,
            # Якщо дата в майбутньому — "upcoming", інакше — "done"
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
        c.execute('SELECT phone FROM sessions WHERE token=? AND expires_at>?',
                  (token, int(time.time())))
        row = c.fetchone()
        conn.close()
        if not row:
            return jsonify({'error': 'session_expired'}), 401
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

    code    = ''.join(random.choices(string.digits, k=4))
    expires = int(time.time()) + OTP_TTL

    conn = sqlite3.connect(OTP_DB)
    conn.execute('INSERT OR REPLACE INTO otp_codes VALUES (?,?,?,0)',
                 (phone, code, expires))
    conn.commit()
    conn.close()

    msg = f"Dr.Gomon: ваш код — {code}. Дійсний 5 хвилин."
    ok  = send_sms(phone, msg)

    if ok:
        logger.info(f"OTP відправлено: {phone}")
        return jsonify({'ok': True})
    else:
        # ⚠️ ВИДАЛИТИ debug_code перед продом!
        logger.warning(f"SMS fail, debug код: {code}")
        return jsonify({'ok': True, 'debug_code': code})

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
    """
    Читає /sitepro/prices.json і нормалізує у масив категорій для PWA.

    Вхід:  {"1": [{"title": "...", "rows": [["name","desc","price","dur"], ...]}, ...], "2": [...]}
    Вихід: [{"cat": "...", "items": [{"name":"","desc":"","price":"","duration":""}]}, ...]
    """
    try:
        with open(PRICES_PATH, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except FileNotFoundError:
        return jsonify({'error': 'prices_not_found'}), 404
    except json.JSONDecodeError:
        return jsonify({'error': 'prices_invalid_json'}), 500

    result = []
    for key in sorted(raw.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        groups = raw[key]
        if not isinstance(groups, list):
            continue
        for group in groups:
            title = group.get('title', '')
            rows  = group.get('rows', [])
            items = []
            for row in rows:
                if not isinstance(row, list) or len(row) < 1:
                    continue
                items.append({
                    'name':     row[0] if len(row) > 0 else '',
                    'desc':     row[1] if len(row) > 1 else None,
                    'price':    row[2] if len(row) > 2 else '',
                    'duration': row[3] if len(row) > 3 else None,
                })
            if items:
                result.append({'cat': title, 'items': items})

    return jsonify(result)

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

# ── PWA STATIC FILES ──

@app.route('/app/', defaults={'path': ''})
@app.route('/app/<path:path>')
def serve_pwa(path):
    if path and os.path.exists(os.path.join(PWA_DIR, path)):
        return send_from_directory(PWA_DIR, path)
    return send_from_directory(PWA_DIR, 'index.html')

# ── INTERNAL ──

def _client_payload(client: dict | None, phone: str) -> dict:
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
        }
    return {
        'name':         client.get('first_name') or 'Клієнт',
        'last_name':    client.get('last_name') or '',
        'phone':        client.get('phone') or phone,
        'wlaunch_id':   str(client.get('id') or ''),
        'last_service': client.get('last_service') or '',
        'last_visit':   client.get('last_visit') or '',
        'visits_count': client.get('visits_count') or 0,
    }

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=False)
