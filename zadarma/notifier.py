# notifier.py — Диспетчер сповіщень Dr. Gomon Cosmetology
# Канали: Push (завжди) → Telegram (основний) → SMS (fallback)
#
# СТАТУС: реалізовано, НЕ ПІДКЛЮЧЕНО до жодного тригера.
# Для підключення — дивись закоментовані блоки в pwa_api.py та appt_reminder.py.
#
# Логіка доставки:
#   Push  — завжди, якщо є активна підписка (fire-and-forget, не блокує)
#   TG    — основний канал. Якщо telegram_id знайдено і відправка успішна → SMS не надсилається
#           Якщо TG fail (403 заблоковано / timeout) → fallback на SMS
#   SMS   — тільки якщо TG ID невідомий або відправка TG провалилась
# ─────────────────────────────────────────────────────────────────────────

import sys
import sqlite3
import logging
import requests
from datetime import datetime

sys.path.insert(0, '/home/gomoncli/zadarma')

logger = logging.getLogger('notifier')

DB_PATH = '/home/gomoncli/zadarma/users.db'

# ─── Дані спеціалістів ────────────────────────────────────────────────────────
SPECIALIST_INFO = {
    'victoria': {
        'short_name': 'Вікторія',
        'phone':      '073-310-31-10',   # загальний номер клініки
        'phone_norm': '380996093860',    # для TG lookup у таблиці users
        'instagram':  '@dr.gomon',
    },
    'anastasia': {
        'short_name': 'Анастасія',
        'phone':      '073-310-31-10',
        'phone_norm': '380685129121',
        'instagram':  '@dr.gomon',
    },
}
_UNKNOWN_SPEC = {
    'short_name': 'Ваш спеціаліст',
    'phone':      '073-310-31-10',
    'phone_norm': '',
    'instagram':  '@dr.gomon',
}

# ─── Форматування ─────────────────────────────────────────────────────────────

def _fmt_duration(minutes):
    """60 → '60 хвилин'   90 → '1 год 30 хв'   120 → '2 год'"""
    m = int(minutes or 60)
    if m < 60:
        return '{} хвилин'.format(m)
    h, rem = divmod(m, 60)
    if rem == 0:
        return '{} год'.format(h)
    return '{} год {} хв'.format(h, rem)

def _fmt_date(date_str):
    """'2026-04-01' → '01.04.2026'"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
    except Exception:
        return date_str or '—'

def _fmt_time(time_str):
    """'11:30:00' або '11:30' → '11:30'"""
    return (time_str or '').strip()[:5] or '—'

def _first_name(client_name):
    """'Іванна Петренко' → 'Іванна', None → 'клієнт'"""
    return (client_name or '').split()[0] if client_name else 'клієнт'

# ─── БД helpers ──────────────────────────────────────────────────────────────

def _db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _init_notification_log():
    """Таблиця notification_log — єдине місце дедуплікації всіх каналів."""
    conn = _db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notification_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            phone           TEXT    NOT NULL,
            type            TEXT    NOT NULL,
            -- типи: appt_reminder | feedback | cancel | appt_confirm
            reference       TEXT    NOT NULL,
            -- 'appt|2026-04-15'  'feedback|2026-04-15'  'cancel|{id}|2026-04-15'
            channel         TEXT    NOT NULL,   -- 'tg' | 'sms' | 'push'
            status          TEXT    DEFAULT 'sent',  -- 'sent' | 'failed'
            sent_at         TEXT    NOT NULL,
            message_preview TEXT,
            UNIQUE(phone, type, reference, channel)
        )
    ''')
    conn.commit()
    conn.close()

_init_notification_log()


def _already_sent(phone, type_, reference, channel):
    conn = _db()
    row = conn.execute(
        'SELECT 1 FROM notification_log WHERE phone=? AND type=? AND reference=? AND channel=?',
        (phone, type_, reference, channel)
    ).fetchone()
    conn.close()
    return row is not None


def _log(phone, type_, reference, channel, status, preview=''):
    try:
        conn = _db()
        conn.execute(
            '''INSERT OR IGNORE INTO notification_log
               (phone, type, reference, channel, status, sent_at, message_preview)
               VALUES (?,?,?,?,?,?,?)''',
            (phone, type_, reference, channel, status,
             datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), (preview or '')[:100])
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error('_log error: {}'.format(e))

# ─── Telegram ────────────────────────────────────────────────────────────────

def _get_tg_id(phone):
    """
    Шукає telegram_id за номером телефону.
    Спочатку точний збіг (380XXXXXXXXX), потім fuzzy за останніми 9 цифрами.
    """
    digits = ''.join(filter(str.isdigit, phone or ''))
    if not digits:
        return None
    try:
        conn = _db()
        # Точний збіг — прибираємо '+' та пробіли зі збереженого значення
        row = conn.execute(
            "SELECT telegram_id FROM users "
            "WHERE REPLACE(REPLACE(phone,'+',''),' ','') = ?",
            (digits,)
        ).fetchone()
        if not row:
            # Fuzzy: останні 9 цифр (UA-номер без коду країни)
            tail = digits[-9:]
            row = conn.execute(
                "SELECT telegram_id FROM users "
                "WHERE SUBSTR(REPLACE(REPLACE(phone,'+',''),' ',''), -9) = ?",
                (tail,)
            ).fetchone()
        conn.close()
        return row['telegram_id'] if row else None
    except Exception as e:
        logger.error('_get_tg_id error: {}'.format(e))
        return None


def _send_tg(tg_id, text):
    """
    Надсилає повідомлення через Telegram Bot API.
    Повертає True при успіху, False при будь-якій помилці (в т.ч. 403 заблоковано).
    """
    try:
        from config import TELEGRAM_TOKEN
        r = requests.post(
            'https://api.telegram.org/bot{}/sendMessage'.format(TELEGRAM_TOKEN),
            json={'chat_id': tg_id, 'text': text},
            timeout=10
        )
        data = r.json()
        if data.get('ok'):
            return True
        # 403 = клієнт заблокував бота
        err_code = data.get('error_code', 0)
        logger.warning('TG send failed tg_id={} code={}: {}'.format(
            tg_id, err_code, data.get('description', '')))
        return False
    except Exception as e:
        logger.error('_send_tg exception tg_id={}: {}'.format(tg_id, e))
        return False

# ─── Push ────────────────────────────────────────────────────────────────────

def _send_push(phone, title, body, tag='gomon', url='/app/'):
    try:
        from push_sender import send_push_to_phone
        return send_push_to_phone(phone, title, body, url, tag)
    except Exception as e:
        logger.error('push error for {}: {}'.format(phone, e))
        return False

# ─── SMS ────────────────────────────────────────────────────────────────────

def _send_sms(phone, text):
    try:
        from sms_fly import send_sms
        return send_sms(phone, text)
    except Exception as e:
        logger.error('sms error for {}: {}'.format(phone, e))
        return False

# ─── Центральний диспетчер ───────────────────────────────────────────────────

def notify_client(phone, tg_text, sms_text=None,
                  push_title=None, push_body=None,
                  push_tag='gomon', push_url='/app/'):
    """
    Надіслати сповіщення клієнту.

    push_title / push_body — якщо None, push не надсилається для цього виклику.
    sms_text               — якщо None, використовується tg_text (без HTML).

    Повертає: {'push': bool|None, 'tg': bool|None, 'sms': bool|None}
      None = канал не намагались (нема підписки / нема TG ID)
    """
    results = {'push': None, 'tg': None, 'sms': None}

    # 1. Push — завжди, не блокує рішення по TG/SMS
    if push_title and push_body:
        results['push'] = _send_push(phone, push_title, push_body, push_tag, push_url)

    # 2. TG → SMS fallback (взаємовиключно)
    tg_id = _get_tg_id(phone)
    if tg_id:
        ok = _send_tg(tg_id, tg_text)
        results['tg'] = ok
        if not ok:
            # TG fail (заблоковано або мережева помилка) → SMS fallback
            results['sms'] = _send_sms(phone, sms_text or tg_text)
    else:
        # TG ID невідомий → одразу SMS
        results['sms'] = _send_sms(phone, sms_text or tg_text)

    return results


def notify_specialist(specialist, tg_text):
    """
    Надіслати внутрішнє сповіщення спеціалісту через TG.
    Без SMS fallback — внутрішні повідомлення, не критичні.
    """
    info = SPECIALIST_INFO.get(specialist)
    if not info:
        logger.warning('notify_specialist: unknown specialist "{}"'.format(specialist))
        return False
    tg_id = _get_tg_id(info['phone_norm'])
    if not tg_id:
        logger.warning('notify_specialist: no TG ID for {}'.format(specialist))
        return False
    return _send_tg(tg_id, tg_text)

# ─── Шаблони повідомлень ─────────────────────────────────────────────────────

def _appt_vars(appt):
    """Витягує загальні змінні з dict запису (manual або WLaunch формат)."""
    spec = SPECIALIST_INFO.get(appt.get('specialist'), _UNKNOWN_SPEC)
    # time: manual_appointments має поле 'time', WLaunch — 'hour'
    raw_time = appt.get('time') or (
        '{:02d}:00'.format(appt['hour']) if appt.get('hour') is not None else ''
    )
    return {
        'first_name':  _first_name(appt.get('client_name') or appt.get('client_phone')),
        'service':     appt.get('procedure_name') or appt.get('service') or '—',
        'date':        _fmt_date(appt.get('date', '')),
        'time':        _fmt_time(raw_time),
        'duration':    _fmt_duration(appt.get('duration_min', 60)),
        'spec_name':   spec['short_name'],
        'spec_phone':  spec['phone'],
        'spec_insta':  spec['instagram'],
    }


def fmt_reminder_24h(appt):
    """Нагадування клієнту за 24 години. Повертає (tg, sms, push_title, push_body)."""
    v = _appt_vars(appt)
    tg = (
        '{first_name}, Ви записані на процедуру "{service}" Dr. Gomon Cosmetology '
        'на {date} о {time}. Орієнтовна тривалість процедури {duration}. '
        'Ваш спеціаліст {spec_name} (тел. {spec_phone}) чекатиме Вас за НОВОЮ адресою '
        'в БЦ Галерея (чорня скляна будівля поруч з ТЦ Будинок Торгівлі), '
        'вхід через двері з надписом "ЛІФТ", 6 поверх\n'
        'https://flyl.link/map або дивіться в додатку https://flyl.link/app'
    ).format(**v)
    sms = (
        'Dr.Gomon: нагадуємо — {date} о {time} "{service}". '
        'Адреса: БЦ Галерея, вхід "ЛІФТ", 6 пов. '
        'https://flyl.link/map'
    ).format(**v)
    push_title = 'Нагадування про запис'
    push_body  = '{service}, {date} о {time}'.format(**v)
    return tg, sms, push_title, push_body


def fmt_post_visit(appt):
    """Подяка + прохання залишити відгук о 20:00 в день процедури. Повертає (tg, sms, push_title, push_body)."""
    v = _appt_vars(appt)
    tg = (
        '{first_name}, Dr. Gomon Cosmetology дякує за довіру! '
        'Будемо вдячні і за Ваш відгук:\nhttps://flyl.link/google\n\n'
        'А ще в нас з\'явився додаток для зручного відстеження записів, новин і акцій:\n'
        'https://flyl.link/app'
    ).format(**v)
    sms = (
        'Dr.Gomon дякує за візит! '
        'Відгук: https://flyl.link/google  '
        'Додаток: https://flyl.link/app'
    )
    push_title = 'Дякуємо за візит!'
    push_body  = 'Залиште відгук — нам важлива ваша думка'
    return tg, sms, push_title, push_body


def fmt_cancel_client(appt):
    """Підтвердження скасування для клієнта. Повертає (tg, sms, push_title, push_body)."""
    v = _appt_vars(appt)
    tg = (
        '{first_name}, Ваш запис на {date} о {time} скасовано. '
        'Якщо виникнуть питання, спеціаліст {spec_name} з радістю відповість '
        'на них за тел. {spec_phone} або в Instagram {spec_insta}'
    ).format(**v)
    sms = (
        'Dr.Gomon: запис {date} о {time} скасовано. '
        'Питання: тел. {spec_phone} або Instagram {spec_insta}'
    ).format(**v)
    push_title = 'Запис скасовано'
    push_body  = '{service}, {date}'.format(**v)
    return tg, sms, push_title, push_body


def fmt_cancel_specialist(appt):
    """Сповіщення спеціалісту про скасування запису клієнта. Повертає str."""
    v = _appt_vars(appt)
    return (
        '{spec_name}, скасовано запис клієнта {first_name} '
        'на процедуру "{service}" на {date} о {time}'
    ).format(**v)

def _lookup_price(procedure_name):
    """Шукає ціну процедури в prices.json. Точний збіг → fuzzy (contains)."""
    import json as _json
    try:
        with open('/home/gomoncli/private_data/prices.json', encoding='utf-8') as f:
            cats = _json.load(f)
        pl = (procedure_name or '').lower()
        # Точний збіг
        for cat in cats:
            for item in cat.get('items', []):
                if item.get('name', '').lower() == pl:
                    return item.get('price', '')
        # Fuzzy: процедура містить ключове слово або навпаки
        for cat in cats:
            for item in cat.get('items', []):
                name_l = item.get('name', '').lower()
                if pl in name_l or name_l in pl:
                    return item.get('price', '')
    except Exception as e:
        logger.warning('_lookup_price error: {}'.format(e))
    return ''


def fmt_specialist_new_appt(appt):
    """
    Сповіщення спеціалісту о 20:00 дня створення запису.
    Повертає рядок TG-повідомлення.
    """
    v = _appt_vars(appt)
    price = _lookup_price(v['service'])
    if price:
        price_part = 'Нагадаю, що вартість процедури «{service}» {price}, а орієнтовна тривалість {duration}.'.format(
            price=price, **v)
    else:
        price_part = 'Орієнтовна тривалість процедури — {duration}.'.format(**v)
    return (
        '{spec_name}, до тебе записаний клієнт {first_name} '
        'на процедуру «{service}» на {date} о {time}. {price_part}'
    ).format(price_part=price_part, **v)


def send_specialist_new_appt(appt):
    """
    Надіслати спеціалісту повідомлення про новий запис.
    Дедуплікація за appt id — не надсилає повторно.
    Повертає {'ok': bool} або {'skipped': True}.
    """
    spec      = appt.get('specialist')
    appt_id   = appt.get('id', '')
    ref       = 'spec_new|{}'.format(appt_id)
    spec_info = SPECIALIST_INFO.get(spec)
    if not spec_info:
        logger.warning('send_specialist_new_appt: unknown specialist "{}"'.format(spec))
        return {'ok': False}

    spec_phone = spec_info['phone_norm']
    if _already_sent(spec_phone, 'spec_new', ref, 'tg'):
        return {'skipped': True}

    text = fmt_specialist_new_appt(appt)
    ok   = notify_specialist(spec, text)
    _log(spec_phone, 'spec_new', ref, 'tg', 'sent' if ok else 'failed', text)
    logger.info('spec_new {} appt={} ok={}'.format(spec, appt_id, ok))
    return {'ok': ok}

# ─── Зручні high-level відправники ──────────────────────────────────────────

def send_reminder_24h(appt):
    """
    Нагадування за 24 год. Дедуплікація за (phone, date).
    Не надсилає повторно якщо вже є запис у notification_log.
    """
    phone = appt.get('client_phone', '')
    ref   = 'appt|{}'.format(appt.get('date', ''))
    if not phone:
        return {}

    # Дедуплікація: якщо хоча б один канал відправлений — пропустити
    # (Push може відправлятись окремо через push_reminder --appt)
    if _already_sent(phone, 'appt_reminder', ref, 'tg') and \
       _already_sent(phone, 'appt_reminder', ref, 'sms'):
        return {'skipped': True}

    tg, sms, push_title, push_body = fmt_reminder_24h(appt)
    results = notify_client(phone, tg, sms, push_title, push_body, push_tag='reminder')

    for ch, ok in results.items():
        if ok is not None:
            _log(phone, 'appt_reminder', ref, ch, 'sent' if ok else 'failed', tg)

    logger.info('reminder_24h phone={} date={} → {}'.format(phone, appt.get('date'), results))
    return results


def send_post_visit(appt):
    """
    Відгук після процедури. Надсилати о 20:00 у день запису.
    Дедуплікація: один раз на (phone, date).
    """
    phone = appt.get('client_phone', '')
    ref   = 'feedback|{}'.format(appt.get('date', ''))
    if not phone:
        return {}

    if _already_sent(phone, 'feedback', ref, 'tg') or \
       _already_sent(phone, 'feedback', ref, 'sms'):
        return {'skipped': True}

    tg, sms, push_title, push_body = fmt_post_visit(appt)
    results = notify_client(phone, tg, sms, push_title, push_body, push_tag='feedback')

    for ch, ok in results.items():
        if ok is not None:
            _log(phone, 'feedback', ref, ch, 'sent' if ok else 'failed', tg)

    logger.info('post_visit phone={} date={} → {}'.format(phone, appt.get('date'), results))
    return results


def send_cancellation(appt):
    """
    Скасування: надіслати клієнту підтвердження + спеціалісту внутрішнє повідомлення.
    appt повинен містити: client_phone, client_name, procedure_name/service,
                          date, time/hour, specialist, id/appt_id
    """
    phone = appt.get('client_phone', '')
    appt_id = appt.get('id') or appt.get('appt_id', '')
    ref   = 'cancel|{}|{}'.format(appt_id, appt.get('date', ''))
    results = {'client': {}, 'specialist': False}

    if phone:
        tg, sms, push_title, push_body = fmt_cancel_client(appt)
        results['client'] = notify_client(phone, tg, sms, push_title, push_body, push_tag='cancel')
        for ch, ok in results['client'].items():
            if ok is not None:
                _log(phone, 'cancel', ref, ch, 'sent' if ok else 'failed', tg)

    spec = appt.get('specialist')
    if spec:
        spec_text = fmt_cancel_specialist(appt)
        results['specialist'] = notify_specialist(spec, spec_text)

    logger.info('cancellation phone={} date={} → {}'.format(phone, appt.get('date'), results))
    return results
