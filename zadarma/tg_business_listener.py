#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Business Bot Listener
Captures messages from business TG account DMs and saves to messages table.
Runs as a separate process alongside the main bot.

Bot: @DrGomonCosmetologyBot
Token: configured below
"""

import logging
import logging.handlers
import sqlite3
import json
import requests
import time
import signal
import sys
import os
import threading

# Config
sys.path.append('/home/gomoncli/zadarma')
from config import TG_BIZ_TOKEN as BOT_TOKEN, ANTHROPIC_KEY
DB_PATH = '/home/gomoncli/zadarma/users.db'
LOG_FILE = '/home/gomoncli/zadarma/tg_business.log'
PID_FILE = '/home/gomoncli/zadarma/tg_business.pid'
OFFSET_FILE = '/home/gomoncli/zadarma/.tg_business_offset'
SYSTEM_PROMPT_FILE = '/home/gomoncli/public_html/app/system_prompt.txt'
PRICES_FILE = '/home/gomoncli/private_data/prices.json'
PROMOS_FILE = '/home/gomoncli/private_data/promos.json'
POLL_TIMEOUT = 30
AI_RATE_LIMIT = 10       # max AI replies per client per day
AI_ADMIN_PAUSE = 1800    # 30 min — don't reply if admin replied recently
AI_MAX_HISTORY = 20      # max messages in context
AI_MODEL = 'claude-sonnet-4-5'

# Logging
logger = logging.getLogger('tg_business')
handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=2*1024*1024, backupCount=3)
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(handler)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

# Graceful shutdown
_running = True
def _signal_handler(sig, frame):
    global _running
    logger.info('Received signal {}, stopping...'.format(sig))
    _running = False

signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)

# AI thread limiter (actual semaphore instead of active_count)
_ai_sem = threading.Semaphore(3)


def init_db():
    """Ensure messages table exists."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'telegram',
            conversation_id TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            sender_name TEXT,
            client_phone TEXT,
            content TEXT,
            media_type TEXT,
            file_id TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            is_from_admin INTEGER DEFAULT 0,
            admin_phone TEXT,
            is_read INTEGER DEFAULT 0
        )''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_msg_created ON messages(created_at DESC)')
        conn.execute('''CREATE TABLE IF NOT EXISTS biz_connections (
            chat_id TEXT PRIMARY KEY,
            biz_conn_id TEXT NOT NULL
        )''')
        conn.commit()
    finally:
        conn.close()


def load_offset():
    """Load last processed offset from file."""
    try:
        with open(OFFSET_FILE, 'r') as f:
            return int(f.read().strip())
    except (IOError, ValueError):
        return 0


def save_offset(offset):
    """Persist offset to file."""
    try:
        with open(OFFSET_FILE, 'w') as f:
            f.write(str(offset))
    except IOError as e:
        logger.error('save_offset error: {}'.format(e))


def save_message(sender_id, sender_name, content, media_type='text', file_id=None,
                 is_from_admin=False, business_connection_id=None, chat_id=None,
                 tg_msg_id=None):
    """Save a message to the unified messages table."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        # Dedup: skip if this tg message was already saved
        if tg_msg_id is not None:
            conv_id_check = 'tg_{}'.format(chat_id or sender_id)
            exists = conn.execute(
                "SELECT 1 FROM messages WHERE conversation_id=? AND content=? AND sender_id=? "
                "AND created_at > datetime('now', '-600 seconds') LIMIT 1",
                (conv_id_check, content or '', str(sender_id))
            ).fetchone()
            if exists:
                logger.debug('Dedup: skipping msg_id={}'.format(tg_msg_id))
                return

        # Look up client phone from users table
        row = conn.execute("SELECT phone FROM users WHERE telegram_id=?", (sender_id,)).fetchone()
        client_phone = row[0] if row else None

        # Conversation ID — same format as main bot for unified view
        conv_id = 'tg_{}'.format(chat_id or sender_id)

        conn.execute(
            "INSERT INTO messages (platform, conversation_id, sender_id, sender_name, "
            "client_phone, content, media_type, file_id, is_from_admin, admin_phone) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            ('telegram', conv_id, str(sender_id), sender_name,
             client_phone, content, media_type, file_id,
             1 if is_from_admin else 0, None))

        # Save business_connection_id for sending replies as business account
        if business_connection_id and chat_id:
            conn.execute(
                "INSERT OR REPLACE INTO biz_connections (chat_id, biz_conn_id) VALUES (?,?)",
                (str(chat_id), business_connection_id))
        conn.commit()
        logger.info('Saved: {} from {} (admin={})'.format(
            (content or '')[:40], sender_name, is_from_admin))
    except Exception as e:
        logger.error('save_message error: {}'.format(e))
    finally:
        conn.close()


def get_bot_id():
    """Get bot's own user ID."""
    r = requests.get('https://api.telegram.org/bot{}/getMe'.format(BOT_TOKEN), timeout=10)
    return r.json().get('result', {}).get('id')


# ── AI Auto-Reply ──────────────────────────────────────────────────────────

def _build_system_prompt(client_phone=None):
    """Build system prompt with prices, promos, and client data."""
    try:
        with open(SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
            prompt = f.read()
    except IOError:
        logger.error('System prompt file not found')
        return None

    # Client data from DB
    if client_phone:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            try:
                tail = client_phone[-9:] if len(client_phone) >= 9 else client_phone
                row = conn.execute(
                    "SELECT first_name, last_name, services_json, visits_count FROM clients "
                    "WHERE REPLACE(REPLACE(REPLACE(phone,'+',''),'-',''),' ','') LIKE ?",
                    ('%' + tail,)).fetchone()
            finally:
                conn.close()
            if row:
                name_parts = []
                if row[0]: name_parts.append(row[0])
                if row[1]: name_parts.append(row[1])
                if name_parts:
                    prompt += "\n\n---\nДані поточного клієнта:\nІм'я: {}".format(' '.join(name_parts))
                services = json.loads(row[2] or '[]')
                visits = row[3] or 0
                if services:
                    from tz_utils import kyiv_now as _kyiv_now
                    _today = _kyiv_now().strftime('%Y-%m-%d')
                    _upcoming_active = [s for s in services
                                 if s.get('date', '') >= _today
                                 and s.get('status', '').upper() not in ('CANCELLED',)]
                    _upcoming_cancelled = [s for s in services
                                 if s.get('date', '') >= _today
                                 and s.get('status', '').upper() == 'CANCELLED']
                    _upcoming = _upcoming_active + _upcoming_cancelled
                    _past = [s for s in services
                             if s.get('date', '') < _today or s.get('status', '').upper() == 'CANCELLED']
                    _upcoming.sort(key=lambda x: x.get('date', ''))
                    _past.sort(key=lambda x: x.get('date', ''), reverse=True)
                    if _upcoming:
                        _ulines = []
                        for s in _upcoming:
                            _line = '- {} о {}:00: {} (спеціаліст: {})'.format(
                                s.get('date', ''), s.get('hour', '?'), s.get('service', ''), s.get('specialist', '?'))
                            if s.get('status', '').upper() == 'CANCELLED':
                                _line += ' [СКАСОВАНО]'
                            _ulines.append(_line)
                        prompt += '\n\n---\n## Майбутні записи клієнта\n{}'.format('\n'.join(_ulines))
                    else:
                        prompt += '\n\n---\n## Майбутні записи клієнта\nНемає майбутніх записів.'

                    if _past:
                        _plines = ['- {}: {} ({})'.format(
                            s.get('date', ''), s.get('service', ''), s.get('status', ''))
                            for s in _past[:5]]
                        prompt += '\n\n## Історія візитів (всього: {})\n{}'.format(
                            visits, '\n'.join(_plines))
        except Exception as e:
            logger.warning('Client data lookup error: {}'.format(e))
    else:
        prompt += ('\n\n---\n## Дані клієнта\n'
                   'Телефон клієнта невідомий — він ще не прив\'язав номер через бота. '
                   'Якщо клієнт питає про свої записи або хоче скасувати — '
                   'попроси його надіслати команду /start боту @DrGomonConciergeBot '
                   'і поділитись номером телефону, щоб система могла знайти його записи.')

    # Promos
    try:
        with open(PROMOS_FILE, 'r', encoding='utf-8') as f:
            promos = json.load(f)
        if promos:
            lines = ['- [{}] {} — {}'.format(p.get('tag', ''), p.get('title', ''), p.get('desc', ''))
                     for p in promos]
            prompt += '\n\n---\n## Поточні актуальні акції\n' + '\n'.join(lines)
    except Exception:
        pass

    # Prices (simplified — first sentence of each item)
    try:
        with open(PRICES_FILE, 'r', encoding='utf-8') as f:
            prices = json.load(f)
        if prices:
            lines = []
            for cat in prices:
                cat_name = cat.get('cat', '')
                items = cat.get('items', [])
                if not cat_name or not items:
                    continue
                lines.append('\n**{}**'.format(cat_name))
                for item in items:
                    name = item.get('name', '')
                    price = item.get('price', '')
                    desc = item.get('desc', '')
                    line = '- {}: {}'.format(name, price) if price else '- {} — ціна індивідуально'.format(name)
                    if desc:
                        first = desc.split('.')[0] + '.' if '.' in desc else desc
                        line += ' — ' + first
                    lines.append(line)
            prompt += '\n\n---\n## Актуальний прайс\n' + '\n'.join(lines)
    except Exception:
        pass

    # Telegram context + escalation rules
    prompt += ('\n\n---\n## Контекст: Telegram бізнес-акаунт'
               '\nТи спілкуєшся з клієнтом у Telegram бізнес-акаунті Dr. Gomon Cosmetology. '
               'Відповідай коротко і по суті (це месенджер, не лист). '
               'Для запису пропонуй написати сюди в чат, зателефонувати 073-310-31-10, або написати лікарю в Instagram (https://ig.me/m/dr.gomon). '
               'Також можна записатись через додаток drgomon.beauty/app — там діє -10% на ін\'єкційні процедури.'
               '\n\n## Ескалація до спеціаліста'
               '\nЯкщо виникає одна з цих ситуацій — передай розмову людині, написавши ТОЧНО цей тег: <ESCALATE>'
               '\n- Клієнт наполегливо просить поговорити з живою людиною'
               '\n- Клієнт скаржиться на якість послуг або має претензію'
               '\n- Клієнт описує медичну проблему, що потребує огляду лікаря'
               '\n- Клієнт хоче записатись на конкретну дату/час (збери ПІБ, номер телефону, бажану процедуру та зручний час — і передай через ескалацію)'
               '\n- Клієнт питає про щось, чого немає в прайсі або акціях'
               '\n- Ти не впевнений у відповіді'
               '\n\n## Скасування запису'
               '\nЯкщо клієнт просить скасувати свій запис — додай тег <CANCEL> або <CANCEL date="YYYY-MM-DD"> у свою відповідь.'
               '\nПравила:'
               '\n- Якщо у клієнта кілька майбутніх записів — перерахуй їх і запитай який скасувати'
               '\n- Після вибору клієнта додай <CANCEL date="YYYY-MM-DD">'
               '\n- Якщо тільки один запис — <CANCEL> (без дати)'
               '\n- Спочатку уточни: Ви точно хочете скасувати?'
               '\n- НЕ ВИГАДУЙ результат — система автоматично додасть статус скасування'
               '\n\nПри ескалації завжди додай коротке пояснення для клієнта, наприклад:'
               '\n"Зараз я з\'єднаю вас зі спеціалістом, щоб допомогти точніше. '
               'Очікуйте відповідь протягом робочого часу (9:00–21:00)."')
    return prompt


def _get_conversation_history(conv_id):
    """Get recent messages for AI context. Ensures valid alternation for Anthropic."""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        # Include all media types — represent non-text as descriptions
        rows = conn.execute(
            "SELECT content, is_from_admin, media_type FROM messages "
            "WHERE conversation_id=? AND content IS NOT NULL "
            "ORDER BY id DESC LIMIT ?",
            (conv_id, AI_MAX_HISTORY)).fetchall()
        rows.reverse()
        messages = []
        for content, is_admin, mtype in rows:
            if not content:
                continue
            # Convert media placeholders to meaningful text for AI
            if mtype == 'voice':
                text = '[Клієнт надіслав голосове повідомлення]'
            elif mtype == 'photo':
                text = '[Клієнт надіслав фото]' if content.startswith('[') else content
            elif mtype == 'video':
                text = '[Клієнт надіслав відео]' if content.startswith('[') else content
            elif mtype == 'sticker':
                text = '[стікер {}]'.format(content)
            elif mtype == 'document':
                text = '[Клієнт надіслав документ]' if content.startswith('[') else content
            else:
                text = content
            role = 'assistant' if is_admin else 'user'
            # Anthropic requires alternating roles — merge consecutive same-role
            if messages and messages[-1]['role'] == role:
                messages[-1]['content'] += '\n' + text
            else:
                messages.append({'role': role, 'content': text})
        # Anthropic requires last message to be 'user'
        while messages and messages[-1]['role'] != 'user':
            messages.pop()
        # Must start with 'user'
        while messages and messages[0]['role'] != 'user':
            messages.pop(0)
        return messages
    finally:
        conn.close()


def _check_ai_should_reply(conv_id, chat_id):
    """Check if AI should auto-reply. Returns False if admin is active or rate limited."""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        # Check if REAL human admin replied recently (not ai_bot)
        # Exclude auto-greetings: admin messages that have a client message within 5s
        rows = conn.execute(
            "SELECT created_at FROM messages WHERE conversation_id=? AND is_from_admin=1 "
            "AND sender_id != 'ai_bot' "
            "AND created_at > datetime('now', '-{} seconds') "
            "ORDER BY id DESC LIMIT 5".format(AI_ADMIN_PAUSE),
            (conv_id,)).fetchall()
        for (admin_ts,) in rows:
            # Check if this admin message has a client message within 5 seconds (= auto-greeting)
            nearby = conn.execute(
                "SELECT 1 FROM messages WHERE conversation_id=? AND is_from_admin=0 "
                "AND ABS(strftime('%s', created_at) - strftime('%s', ?)) < 5 LIMIT 1",
                (conv_id, admin_ts)).fetchone()
            if not nearby:
                # Real admin message, not auto-greeting
                return False, 'admin_active'

        # Rate limit: count AI replies today
        count_row = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE conversation_id=? AND is_from_admin=1 "
            "AND sender_id='ai_bot' AND created_at > date('now')",
            (conv_id,)).fetchone()
        if count_row and count_row[0] >= AI_RATE_LIMIT:
            # Deposit rate limit bypass
            client_phone_dep = None
            try:
                phone_row = conn.execute(
                    "SELECT phone FROM users WHERE telegram_id=?",
                    (str(chat_id),)).fetchone()
                if phone_row:
                    client_phone_dep = phone_row[0]
            except Exception:
                pass
            has_deposit = False
            if client_phone_dep:
                try:
                    dep_row = conn.execute(
                        "SELECT 1 FROM deposits WHERE phone=? AND status='Approved' AND date(created_at)=date('now') LIMIT 1",
                        (client_phone_dep,)).fetchone()
                    has_deposit = bool(dep_row)
                except Exception:
                    pass
            if not has_deposit:
                return False, 'rate_limited'

        return True, 'ok'
    finally:
        conn.close()


def _download_tg_photo(file_id):
    """Download photo from TG and return (base64_data, media_type) or (None, None)."""
    try:
        # Get file path
        r = requests.get('https://api.telegram.org/bot{}/getFile'.format(BOT_TOKEN),
                         params={'file_id': file_id}, timeout=10)
        file_path = r.json().get('result', {}).get('file_path')
        if not file_path:
            return None, None
        # Download
        r2 = requests.get('https://api.telegram.org/file/bot{}/{}'.format(BOT_TOKEN, file_path), timeout=15)
        if r2.status_code != 200 or len(r2.content) > 5 * 1024 * 1024:
            return None, None
        import base64
        b64 = base64.standard_b64encode(r2.content).decode('ascii')
        # Detect media type
        ct = r2.headers.get('content-type', 'image/jpeg')
        if 'png' in ct:
            mt = 'image/png'
        elif 'webp' in ct:
            mt = 'image/webp'
        elif 'gif' in ct:
            mt = 'image/gif'
        else:
            mt = 'image/jpeg'
        logger.info('Downloaded TG photo: {} bytes, {}'.format(len(r2.content), mt))
        return b64, mt
    except Exception as e:
        logger.error('_download_tg_photo error: {}'.format(e))
        return None, None


def _call_anthropic(system_prompt, messages):
    """Call Anthropic API and return reply text."""
    payload = json.dumps({
        'model': AI_MODEL,
        'max_tokens': 1024,
        'system': system_prompt,
        'messages': messages,
    })
    try:
        r = requests.post(
            'https://api.anthropic.com/v1/messages',
            data=payload,
            headers={
                'x-api-key': ANTHROPIC_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            timeout=25)
        if r.status_code == 200:
            data = r.json()
            content = data.get('content', [])
            if content and isinstance(content, list) and len(content) > 0:
                return content[0].get('text', '').strip()
            logger.warning('Anthropic returned empty content: {}'.format(str(data)[:200]))
            return None
        else:
            logger.error('Anthropic API error: {} {}'.format(r.status_code, r.text[:200]))
            return None
    except Exception as e:
        logger.error('Anthropic call error: {}'.format(e))
        return None


def _send_ai_reply(chat_id, text, biz_conn_id):
    """Send AI reply via Business Bot API. Markdown first, plain text fallback."""
    payload = {'chat_id': int(chat_id), 'text': text, 'parse_mode': 'Markdown'}
    if biz_conn_id:
        payload['business_connection_id'] = biz_conn_id
    try:
        r = requests.post(
            'https://api.telegram.org/bot{}/sendMessage'.format(BOT_TOKEN),
            json=payload, timeout=10)
        result = r.json()
        if not result.get('ok'):
            # Markdown parse error — retry without parse_mode
            if 'parse' in result.get('description', '').lower() or 'can\'t' in result.get('description', '').lower():
                logger.warning('Markdown failed, retrying plain: {}'.format(result.get('description', '')))
                payload.pop('parse_mode', None)
                r2 = requests.post(
                    'https://api.telegram.org/bot{}/sendMessage'.format(BOT_TOKEN),
                    json=payload, timeout=10)
                result2 = r2.json()
                if not result2.get('ok'):
                    logger.error('TG send error (plain fallback): {}'.format(result2.get('description', '')))
                    return False
                return True
            logger.error('TG send error: {}'.format(result.get('description', '')))
            return False
        return True
    except Exception as e:
        logger.error('TG send error: {}'.format(e))
        return False


def _save_ai_message(conv_id, chat_id, content):
    """Save AI reply to messages table."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute(
            "INSERT INTO messages (platform, conversation_id, sender_id, sender_name, "
            "content, media_type, is_from_admin) VALUES (?,?,?,?,?,?,?)",
            ('telegram', conv_id, 'ai_bot', 'GomonAI', content, 'text', 1))
        conn.commit()
    except Exception as e:
        logger.error('save_ai_message error: {}'.format(e))
    finally:
        conn.close()


def _send_media_notice(chat_id, biz_conn_id, text):
    """Send a quick notice about text-only support with dedup."""
    conv_id = 'tg_{}'.format(chat_id)
    try:
        should, _ = _check_ai_should_reply(conv_id, chat_id)
        if not should:
            return
        # Dedup: don't send if same notice was sent in last 60s
        conn = sqlite3.connect(DB_PATH, timeout=5)
        try:
            recent = conn.execute(
                "SELECT 1 FROM messages WHERE conversation_id=? AND sender_id='ai_bot' "
                "AND content LIKE ? AND created_at > datetime('now', '-60 seconds') LIMIT 1",
                (conv_id, '%текстовими%')).fetchone()
        finally:
            conn.close()
        if recent:
            return
        if _send_ai_reply(chat_id, text, biz_conn_id):
            _save_ai_message(conv_id, chat_id, text)
            logger.info('Media notice sent to {}'.format(conv_id))
    except Exception as e:
        logger.error('Media notice error: {}'.format(e))
    finally:
        _ai_sem.release()


def _notify_admin_escalation(conv_id, chat_id, client_name):
    """Send escalation notification to admin via main bot."""
    try:
        from config import TELEGRAM_TOKEN, ADMIN_USER_ID
        text = ('🔔 Ескалація з Telegram\n\n'
                'Клієнт: {}\n'
                'Chat ID: {}\n\n'
                'GomonAI передав розмову вам. '
                'Відповідайте через адмін-месенджер у додатку.').format(
                    client_name or chat_id, chat_id)
        requests.post(
            'https://api.telegram.org/bot{}/sendMessage'.format(TELEGRAM_TOKEN),
            json={'chat_id': ADMIN_USER_ID, 'text': text},
            timeout=10)
        logger.info('Escalation notification sent for {}'.format(conv_id))
    except Exception as e:
        logger.error('Escalation notify error: {}'.format(e))


def _cancel_client_appointment(client_phone, target_date=None):
    """Cancel the nearest upcoming appointment for client. Returns (ok, message)."""
    if not client_phone:
        return False, 'Не вдалося визначити ваш номер телефону.'

    try:
        # Find upcoming appointments from services_json
        conn = sqlite3.connect(DB_PATH, timeout=5)
        try:
            tail = client_phone[-9:] if len(client_phone) >= 9 else client_phone
            row = conn.execute(
                "SELECT first_name, last_name, phone, services_json FROM clients "
                "WHERE REPLACE(REPLACE(REPLACE(phone,'+',''),'-',''),' ','') LIKE ?",
                ('%' + tail,)).fetchone()
        finally:
            conn.close()

        if not row:
            return False, 'Не знайдено вашого запису в базі.'

        client_name = ((row[0] or '') + ' ' + (row[1] or '')).strip()
        phone = row[2]
        services = json.loads(row[3] or '[]')

        # Find nearest future confirmed appointment
        from tz_utils import kyiv_now as _kyiv_now
        today = _kyiv_now().strftime('%Y-%m-%d')
        upcoming = [s for s in services
                    if s.get('date', '') >= today
                    and s.get('status', '').upper() not in ('CANCELLED',)]
        if target_date:
            targeted = [s for s in upcoming if s.get('date', '') == target_date]
            if targeted:
                upcoming = targeted
        upcoming.sort(key=lambda x: (x.get('date', ''), x.get('hour', 0)))

        if not upcoming:
            return False, 'У вас немає майбутніх записів для скасування.'

        appt = upcoming[0]
        date = appt.get('date', '')
        service = appt.get('service', '')
        specialist = appt.get('specialist', '')
        appt_id = appt.get('appt_id', '')

        # Import cancel functions from pwa_api context
        sys.path.insert(0, '/home/gomoncli/zadarma')
        from wlaunch_api import get_branch_id

        from config import WLAUNCH_API_KEY, COMPANY_ID, WLAUNCH_API_URL
        headers = {
            'Authorization': 'Bearer ' + WLAUNCH_API_KEY,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        branch_id = get_branch_id()

        # Find WLaunch appointment ID if not in local data
        if not appt_id:
            from datetime import timedelta as _td
            d = _dt.strptime(date, '%Y-%m-%d')
            start_d = (d - _td(days=1)).strftime('%Y-%m-%d')
            end_d = (d + _td(days=1)).strftime('%Y-%m-%d')
            phone_digits = ''.join(filter(str.isdigit, phone))
            url = '{}/company/{}/branch/{}/appointment'.format(WLAUNCH_API_URL, COMPANY_ID, branch_id)
            params = {
                'sort': 'start_time,desc', 'page': 0, 'size': 100,
                'start': start_d + 'T00:00:00.000Z',
                'end': end_d + 'T23:59:59.999Z'
            }
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            for wl_appt in resp.json().get('content', []):
                client = wl_appt.get('client') or {}
                cp = ''.join(filter(str.isdigit, client.get('phone', '')))
                if phone_digits[-9:] == cp[-9:]:
                    appt_id = wl_appt.get('id')
                    break

        if not appt_id:
            return False, 'Не вдалося знайти запис у системі для скасування.'

        # Cancel in WLaunch
        url = '{}/company/{}/branch/{}/appointment/{}'.format(WLAUNCH_API_URL, COMPANY_ID, branch_id, appt_id)
        resp = requests.post(url, headers=headers,
                             json={'appointment': {'id': appt_id, 'status': 'CANCELLED'}},
                             timeout=10)
        resp.raise_for_status()

        # Update local DB
        conn = sqlite3.connect(DB_PATH, timeout=5)
        try:
            raw = conn.execute(
                "SELECT services_json FROM clients WHERE phone=?", (phone,)).fetchone()
            if raw:
                items = json.loads(raw[0] or '[]')
                for item in items:
                    if item.get('date') == date and (not service or item.get('service') == service):
                        item['status'] = 'CANCELLED'
                        break
                conn.execute("UPDATE clients SET services_json=? WHERE phone=?",
                             (json.dumps(items, ensure_ascii=False), phone))
                conn.commit()
        finally:
            conn.close()

        # Send notifications (same as admin cancel)
        try:
            from notifier import send_cancellation
            send_cancellation({
                'appt_id': appt_id,
                'client_phone': phone,
                'client_name': client_name,
                'procedure_name': service,
                'specialist': specialist,
                'date': date,
                'time': '',
                'duration_min': 60,
            })
        except Exception as e:
            logger.error('cancel notification error: {}'.format(e))

        logger.info('AI cancelled appointment: {} {} {}'.format(phone, date, service))
        return True, 'Запис на {} ({}) скасовано.'.format(date, service or 'процедура')

    except Exception as e:
        logger.error('_cancel_client_appointment error: {}'.format(e))
        return False, 'Помилка при скасуванні: {}'.format(e)


def handle_ai_reply(chat_id, biz_conn_id, client_phone=None, client_name=None, image_b64=None, image_media_type=None):
    """Process AI auto-reply in a separate thread."""
    conv_id = 'tg_{}'.format(chat_id)

    try:
        # Check if should reply
        should, reason = _check_ai_should_reply(conv_id, chat_id)
        if not should:
            logger.debug('AI skip for {}: {}'.format(conv_id, reason))
            return

        # Build prompt
        prompt = _build_system_prompt(client_phone)
        if not prompt:
            return

        # Get history
        history = _get_conversation_history(conv_id)
        if not history:
            return

        # Inject image into last user message if provided
        if image_b64 and image_media_type and history:
            last = history[-1]
            if last.get('role') == 'user':
                text_content = last.get('content', '')
                last['content'] = [
                    {'type': 'image', 'source': {'type': 'base64', 'media_type': image_media_type, 'data': image_b64}},
                    {'type': 'text', 'text': text_content or 'Що ви бачите на цьому фото?'},
                ]

        # Call AI
        reply = _call_anthropic(prompt, history)
        if not reply:
            return

        # Check for cancel tag
        import re as _re
        _cancel_match = _re.search(r'<CANCEL(?:\s+date="(\d{4}-\d{2}-\d{2})")?\s*>', reply)
        if _cancel_match:
            _cancel_date = _cancel_match.group(1)
            reply = _re.sub(r'<CANCEL[^>]*>', '', reply).strip()
            ok, msg = _cancel_client_appointment(client_phone, target_date=_cancel_date)
            if ok:
                cancel_note = "\n\n\u2705 " + msg
            else:
                cancel_note = "\n\n\u26a0\ufe0f " + msg
            reply = (reply + cancel_note) if reply else cancel_note
            if _send_ai_reply(chat_id, reply, biz_conn_id):
                _save_ai_message(conv_id, chat_id, reply)
            logger.info("AI cancel for {}: ok={}".format(conv_id, ok))
            return

        # Check for escalation tag
        if '<ESCALATE>' in reply:
            reply = reply.replace('<ESCALATE>', '').strip()
            # Send reply to client (the polite handoff message)
            if reply and _send_ai_reply(chat_id, reply, biz_conn_id):
                _save_ai_message(conv_id, chat_id, reply)
            # Notify admin
            _notify_admin_escalation(conv_id, chat_id, client_name)
            logger.info('AI escalated conversation {} to admin'.format(conv_id))
            return

        # Send normal reply
        if _send_ai_reply(chat_id, reply, biz_conn_id):
            _save_ai_message(conv_id, chat_id, reply)
            logger.info('AI reply sent to {} ({} chars)'.format(conv_id, len(reply)))
    except Exception as e:
        logger.error('handle_ai_reply error: {}'.format(e))
    finally:
        _ai_sem.release()


def process_update(update, bot_id):
    """Process a single update from Telegram."""

    # Business message (someone writes to business account)
    bm = update.get('business_message')
    if bm:
        sender = bm.get('from', {})
        chat = bm.get('chat', {})
        sender_id = sender.get('id')
        sender_name = (sender.get('first_name', '') + ' ' + sender.get('last_name', '')).strip() or sender.get('username', str(sender_id))
        chat_id = chat.get('id')
        biz_conn_id = bm.get('business_connection_id')

        # Business API: from.id = actual sender, chat.id = client's chat
        # When client writes: sender_id == chat_id (client sends in own chat)
        # When admin replies: sender_id != chat_id (admin sends to client's chat)
        is_admin = (sender_id != chat_id)

        content = bm.get('text', '')
        media_type = 'text'
        file_id = None

        if bm.get('photo'):
            media_type = 'photo'
            file_id = bm['photo'][-1].get('file_id')
            content = bm.get('caption', '') or '[фото]'
        elif bm.get('video'):
            media_type = 'video'
            file_id = bm['video'].get('file_id')
            content = bm.get('caption', '') or '[відео]'
        elif bm.get('document'):
            media_type = 'document'
            file_id = bm['document'].get('file_id')
            content = bm.get('caption', '') or '[документ]'
        elif bm.get('voice'):
            media_type = 'voice'
            file_id = bm['voice'].get('file_id')
            content = '[голосове повідомлення]'
        elif bm.get('sticker'):
            media_type = 'sticker'
            content = bm['sticker'].get('emoji', '[стікер]')

        if content or media_type != 'text':
            save_message(
                sender_id=chat_id,  # Use chat_id as conversation key (client's chat)
                sender_name=sender_name,
                content=content,
                media_type=media_type,
                file_id=file_id,
                is_from_admin=is_admin,
                business_connection_id=biz_conn_id,
                chat_id=chat_id,
                tg_msg_id=bm.get('message_id')
            )

            # AI auto-reply for client messages (not admin)
            if not is_admin:
                if media_type == 'photo' and file_id:
                    # Photo — download and send to AI for analysis
                    _img_b64, _img_mt = _download_tg_photo(file_id)
                    if _img_b64:
                        client_phone = None
                        try:
                            _conn = sqlite3.connect(DB_PATH, timeout=5)
                            try:
                                _row = _conn.execute("SELECT phone FROM users WHERE telegram_id=?", (chat_id,)).fetchone()
                                client_phone = _row[0] if _row else None
                            finally:
                                _conn.close()
                        except Exception:
                            pass
                        if _ai_sem.acquire(blocking=False):
                            t = threading.Thread(
                                target=handle_ai_reply,
                                args=(chat_id, biz_conn_id, client_phone, sender_name, _img_b64, _img_mt),
                                daemon=True)
                            t.start()
                    else:
                        if _ai_sem.acquire(blocking=False):
                            t = threading.Thread(target=_send_media_notice,
                                args=(chat_id, biz_conn_id, 'Не вдалося завантажити фото. Спробуйте ще раз або напишіть текстом 🌸'),
                                daemon=True)
                            t.start()
                elif media_type != 'text' and media_type != 'sticker':
                    # Other media (video/voice/doc) — text-only notice
                    _media_notice = 'Дякую! На жаль, я працюю лише з текстом та фото. Напишіть ваше питання текстом, і я з радістю допоможу 🌸'
                    if _ai_sem.acquire(blocking=False):
                        t = threading.Thread(
                            target=_send_media_notice,
                            args=(chat_id, biz_conn_id, _media_notice),
                            daemon=True)
                        t.start()
                elif media_type == 'text' and content:
                    # Text — full AI reply
                    client_phone = None
                    try:
                        conn = sqlite3.connect(DB_PATH, timeout=5)
                        try:
                            row = conn.execute("SELECT phone FROM users WHERE telegram_id=?",
                                               (chat_id,)).fetchone()
                            client_phone = row[0] if row else None
                        finally:
                            conn.close()
                    except Exception:
                        pass
                    # Limit concurrent AI threads via semaphore
                    if _ai_sem.acquire(blocking=False):
                        t = threading.Thread(
                            target=handle_ai_reply,
                            args=(chat_id, biz_conn_id, client_phone, sender_name),
                            daemon=True)
                        t.start()
                    else:
                        logger.warning('AI thread limit reached, skipping for {}'.format(chat_id))
        return

    # Edited business message
    ebm = update.get('edited_business_message')
    if ebm:
        # Could update existing message, but for now just log
        logger.debug('Edited business message, ignoring')
        return

    # Business connection status change — update stored connection ID
    bc = update.get('business_connection')
    if bc:
        biz_id = bc.get('id')
        user_id = bc.get('user', {}).get('id')
        enabled = bc.get('is_enabled')
        logger.info('Business connection: id={} user={} enabled={}'.format(biz_id, user_id, enabled))
        if biz_id and user_id and enabled:
            try:
                conn = sqlite3.connect(DB_PATH, timeout=10)
                conn.execute(
                    "INSERT OR REPLACE INTO biz_connections (chat_id, biz_conn_id) VALUES (?,?)",
                    (str(user_id), biz_id))
                conn.commit()
                conn.close()
                logger.info('Updated biz_connection for user {}: {}'.format(user_id, biz_id))
            except Exception as e:
                logger.error('biz_connection update error: {}'.format(e))
        return

    # Deleted business messages
    dbm = update.get('deleted_business_messages')
    if dbm:
        logger.debug('Deleted business messages, ignoring')
        return


def run_polling():
    """Main polling loop for business messages."""
    logger.info('Starting business bot listener...')

    # Write PID
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

    bot_id = get_bot_id()
    logger.info('Bot ID: {}'.format(bot_id))

    init_db()

    offset = load_offset()
    logger.info('Loaded offset: {}'.format(offset))
    allowed = ['business_message', 'edited_business_message', 'business_connection', 'deleted_business_messages']

    while _running:
        try:
            r = requests.get(
                'https://api.telegram.org/bot{}/getUpdates'.format(BOT_TOKEN),
                params={
                    'offset': offset,
                    'timeout': POLL_TIMEOUT,
                    'allowed_updates': json.dumps(allowed)
                },
                timeout=POLL_TIMEOUT + 10
            )
            data = r.json()
            if not data.get('ok'):
                logger.error('getUpdates error: {}'.format(data))
                time.sleep(5)
                continue

            for update in data.get('result', []):
                offset = update['update_id'] + 1
                try:
                    process_update(update, bot_id)
                except Exception as e:
                    logger.error('process_update error: {}'.format(e))

            # Persist offset after processing batch
            if data.get('result'):
                save_offset(offset)

        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.ConnectionError as e:
            logger.warning('Connection error: {}, retrying in 5s'.format(e))
            time.sleep(5)
        except Exception as e:
            logger.error('Polling error: {}'.format(e))
            time.sleep(5)

    # Cleanup
    try:
        os.remove(PID_FILE)
    except OSError:
        pass
    logger.info('Business bot listener stopped.')


if __name__ == '__main__':
    _backoff = 5
    while True:
        _start = time.time()
        try:
            run_polling()
        except Exception as e:
            logger.error('Fatal error: {}'.format(e))
        if not _running:
            break
        # If ran for >60s, reset backoff (was a real run, not instant crash)
        if time.time() - _start > 60:
            _backoff = 5
        else:
            _backoff = min(_backoff * 2, 300)  # exponential backoff, max 5 min
        logger.info('Auto-restarting in {}s...'.format(_backoff))
        time.sleep(_backoff)

