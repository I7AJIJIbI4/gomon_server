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
from tz_utils import kyiv_now

logger = logging.getLogger('notifier')

DB_PATH = '/home/gomoncli/zadarma/users.db'

# ─── Дані спеціалістів ────────────────────────────────────────────────────────
SPECIALIST_INFO = {
    'victoria': {
        'short_name': 'Вікторія',
        'phone':      '073-310-31-10',   # загальний номер клініки
        'phone_norm': '380996093860',    # для TG lookup у таблиці users
        'instagram':  '@dr.gomon',
        'ig_user_id': '1453130765349790',  # IG scoped ID for DM notifications
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

def _fmt_date_short(date_str):
    """'2026-04-01' → '01.04'"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m')
    except Exception:
        return date_str or '—'

def _fmt_time(time_str):
    """'11:30:00' або '11:30' → '11:30'"""
    return (time_str or '').strip()[:5] or '—'

def _first_name(client_name, phone=None):
    """Get first name. Tries clients DB first (reliable), falls back to first word of client_name."""
    if phone:
        try:
            import sqlite3
            conn = sqlite3.connect(DB_PATH, timeout=5)
            row = conn.execute("SELECT first_name FROM clients WHERE phone=?", (phone,)).fetchone()
            conn.close()
            if row and row[0]:
                return row[0]
        except Exception:
            pass
    # Fallback: second word if 3+ words (Прізвище Ім'я По-батькові), else first word
    parts = (client_name or '').split()
    if len(parts) >= 3:
        return parts[1]  # "Колісник Олексій Миколайович" → "Олексій"
    return parts[0] if parts else 'клієнт'

# ─── БД helpers ──────────────────────────────────────────────────────────────

def _db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _init_notification_log():
    """Таблиця notification_log — єдине місце дедуплікації всіх каналів."""
    from datetime import timedelta
    conn = _db()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS notification_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                phone           TEXT    NOT NULL,
                type            TEXT    NOT NULL,
                -- типи: appt_reminder | feedback | cancel | appt_confirm | spec_new
                reference       TEXT    NOT NULL,
                -- 'appt|2026-04-15'  'feedback|2026-04-15'  'cancel|{id}|2026-04-15'
                channel         TEXT    NOT NULL,   -- 'tg' | 'sms' | 'push'
                status          TEXT    DEFAULT 'sent',  -- 'sent' | 'failed'
                sent_at         TEXT    NOT NULL,
                message_preview TEXT,
                UNIQUE(phone, type, reference, channel)
            )
        ''')
        # Очищення старих записів (старше 30 днів) — таблиця не має рости безмежно
        cutoff = (kyiv_now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            "DELETE FROM notification_log WHERE sent_at < ?", (cutoff,)
        )
        conn.commit()
    finally:
        conn.close()

_notification_log_ready = False


def _ensure_notification_log():
    global _notification_log_ready
    if _notification_log_ready:
        return
    try:
        _init_notification_log()
        _notification_log_ready = True
    except Exception as e:
        logger.error('_init_notification_log failed: {}'.format(e))


def _log(phone, type_, reference, channel, status, preview=''):
    _ensure_notification_log()
    conn = _db()
    try:
        conn.execute(
            '''INSERT OR IGNORE INTO notification_log
               (phone, type, reference, channel, status, sent_at, message_preview)
               VALUES (?,?,?,?,?,?,?)''',
            (phone, type_, reference, channel, status,
             kyiv_now().strftime('%Y-%m-%d %H:%M:%S'), (preview or '')[:100])
        )
        conn.commit()
    except Exception as e:
        logger.error('_log error: {}'.format(e))
    finally:
        conn.close()

def _already_sent(phone, type_, reference, channel):
    """Check if notification was already logged (dedup)."""
    _ensure_notification_log()
    conn = _db()
    try:
        row = conn.execute(
            'SELECT 1 FROM notification_log WHERE phone=? AND type=? AND reference=? AND channel=?',
            (phone, type_, reference, channel)).fetchone()
        return row is not None
    except Exception:
        return False
    finally:
        conn.close()

# ─── Telegram ────────────────────────────────────────────────────────────────

def _get_tg_id(phone):
    """
    Шукає telegram_id за номером телефону.
    Спочатку точний збіг (380XXXXXXXXX), потім fuzzy за останніми 9 цифрами.
    """
    digits = ''.join(filter(str.isdigit, phone or ''))
    if not digits:
        return None
    conn = _db()
    try:
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
        return row['telegram_id'] if row else None
    except Exception as e:
        logger.error('_get_tg_id error: {}'.format(e))
        return None
    finally:
        conn.close()


def _send_tg(tg_id, text, parse_mode=None):
    """
    Надсилає повідомлення через Telegram Bot API.
    parse_mode: None (plain text) або 'HTML'.
    Повертає True при успіху, False при будь-якій помилці (в т.ч. 403 заблоковано).
    """
    try:
        from config import TELEGRAM_TOKEN
        payload = {'chat_id': tg_id, 'text': text}
        if parse_mode:
            payload['parse_mode'] = parse_mode
        r = requests.post(
            'https://api.telegram.org/bot{}/sendMessage'.format(TELEGRAM_TOKEN),
            json=payload,
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


def _send_ig(ig_user_id, text):
    """Send IG DM to a user (requires 24h window — user must have messaged recently)."""
    try:
        from config import IG_FALLBACK_TOKEN
        r = requests.post('https://graph.instagram.com/v25.0/me/messages',
            headers={'Authorization': 'Bearer ' + IG_FALLBACK_TOKEN, 'Content-Type': 'application/json'},
            json={'recipient': {'id': ig_user_id}, 'message': {'text': text}},
            timeout=15)
        if r.status_code == 200:
            logger.info('IG DM sent to {}'.format(ig_user_id))
            return True
        logger.warning('IG DM failed {}: {} {}'.format(ig_user_id, r.status_code, r.text[:100]))
        return False
    except Exception as e:
        logger.error('_send_ig exception: {}'.format(e))
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
                  push_tag='gomon', push_url='/app/',
                  push_only=False):
    """
    Надіслати сповіщення клієнту.

    push_title / push_body — якщо None, push не надсилається для цього виклику.
    sms_text               — якщо None, використовується tg_text (без HTML).
    push_only              — якщо True, надсилає тільки push (TG/SMS обробляє WLaunch).

    Повертає: {'push': bool|None, 'tg': bool|None, 'sms': bool|None}
      None = канал не намагались (нема підписки / нема TG ID)
    """
    results = {'push': None, 'tg': None, 'sms': None}

    # 1. Push — завжди, не блокує рішення по TG/SMS
    if push_title and push_body:
        results['push'] = _send_push(phone, push_title, push_body, push_tag, push_url)

    # 2. TG → SMS fallback (Push не впливає на рішення по TG/SMS)
    #    Пропускаємо якщо push_only (WLaunch сам відправляє SMS/TG)
    if not push_only:
        tg_id = _get_tg_id(phone)
        if tg_id:
            ok = _send_tg(tg_id, tg_text)
            results['tg'] = ok
            if not ok:
                results['sms'] = _send_sms(phone, sms_text or tg_text)
        else:
            results['sms'] = _send_sms(phone, sms_text or tg_text)

    return results


def notify_specialist(specialist, tg_text):
    """
    Надіслати внутрішнє сповіщення спеціалісту через TG + IG (if available).
    IG is best-effort (24h window). TG is primary.
    """
    info = SPECIALIST_INFO.get(specialist)
    if not info:
        logger.warning('notify_specialist: unknown specialist "{}"'.format(specialist))
        return False
    tg_ok = False
    tg_id = _get_tg_id(info['phone_norm'])
    if tg_id:
        tg_ok = _send_tg(tg_id, tg_text)
    # Also try IG DM (best-effort, may fail if 24h window expired)
    ig_uid = info.get('ig_user_id')
    if ig_uid:
        _send_ig(ig_uid, tg_text)
    return tg_ok

# ─── Шаблони повідомлень ─────────────────────────────────────────────────────

def _appt_vars(appt):
    """Витягує загальні змінні з dict запису (manual або WLaunch формат)."""
    spec = SPECIALIST_INFO.get(appt.get('specialist'), _UNKNOWN_SPEC)
    # time: manual_appointments має поле 'time', WLaunch — 'hour'
    raw_time = appt.get('time') or (
        '{:02d}:00'.format(appt['hour']) if appt.get('hour') is not None else ''
    )
    date_str = appt.get('date', '')
    return {
        'first_name':  _first_name(appt.get('client_name') or appt.get('client_phone'), phone=appt.get('client_phone')),
        'service':     appt.get('procedure_name') or appt.get('service') or '—',
        'date':        _fmt_date(date_str),
        'date_short':  _fmt_date_short(date_str),
        'time':        _fmt_time(raw_time),
        'duration':    _fmt_duration(appt.get('duration_min', 60)),
        'spec_name':   spec['short_name'],
        'spec_phone':  spec['phone'],
        'spec_insta':  spec['instagram'],
    }


def fmt_appt_confirm(appt):
    """Підтвердження створення запису клієнту. Повертає (tg, sms, push_title, push_body)."""
    v = _appt_vars(appt)
    tg = (
        '{first_name}, Ви записані на процедуру "{service}" '
        'Dr. Gomon Cosmetology на {date} о {time}. '
        'Орієнтовна тривалість процедури {duration}. '
        'Ваш спеціаліст {spec_name} (тел. 073-310-31-10) '
        'чекатиме Вас за адресою в БЦ Галерея (чорна скляна будівля поруч з ТЦ Будинок Торгівлі), '
        'вхід через двері з надписом "ЛІФТ", 6 поверх\n\n'
        '📍 Карта: https://flyl.link/map\n'
        '📱 Додаток: https://drgomon.beauty/app/'
    ).format(**v)
    sms = (
        '{first_name}, Ви записані на "{service}" Dr.Gomon на {date_short} о {time}. '
        'Спеціаліст {spec_name} (073-310-31-10). '
        'БЦ Галерея, "ЛІФТ", 6 пов. '
        'Карта: https://flyl.link/map'
    ).format(**v)
    push_title = 'Запис підтверджено ✅'
    push_body  = '{service}, {date_short} о {time}'.format(**v)
    return tg, sms, push_title, push_body


def fmt_reminder_24h(appt):
    """Нагадування клієнту за 24 години. Повертає (tg, sms, push_title, push_body)."""
    v = _appt_vars(appt)
    tg = (
        '{first_name}, нагадуємо про ваш запис завтра!\n\n'
        '📅 {date}, {time}\n'
        '💆 {service}\n'
        '👩‍⚕️ {spec_name} (тел. 073-310-31-10)\n\n'
        '📍 БЦ Галерея (чорна скляна будівля поруч з ТЦ Будинок Торгівлі), '
        'вхід через двері з надписом "ЛІФТ", 6 поверх\n'
        '🗺 https://flyl.link/map\n'
        '📱 Додаток: https://drgomon.beauty/app/'
    ).format(**v)
    sms = (
        '{first_name}, нагадуємо — завтра {date_short} о {time} "{service}". '
        'Спеціаліст {spec_name} (073-310-31-10). '
        'БЦ Галерея, "ЛІФТ", 6 пов.'
    ).format(**v)
    push_title = 'Запис завтра 🌸'
    push_body  = '{service}, {time}'.format(**v)
    return tg, sms, push_title, push_body


def fmt_post_visit(appt):
    """Подяка + відгук через 2 години після процедури. З кешбек інфо для app users."""
    v = _appt_vars(appt)
    phone = appt.get('client_phone', '')

    # Check if app user and get balance info
    cashback_line = ''
    if phone:
        try:
            import sqlite3
            otp_conn = sqlite3.connect('/home/gomoncli/zadarma/otp_sessions.db', timeout=5)
            try:
                is_app = otp_conn.execute("SELECT 1 FROM sessions WHERE phone=? LIMIT 1", (phone,)).fetchone()
            finally:
                otp_conn.close()
            if is_app:
                conn = sqlite3.connect(DB_PATH, timeout=5)
                try:
                    dep = conn.execute("SELECT COALESCE(SUM(amount_uah),0) FROM deposits WHERE phone=? AND status='Approved'", (phone,)).fetchone()[0]
                    ded = conn.execute("SELECT COALESCE(SUM(amount),0) FROM deposit_deductions WHERE phone=?", (phone,)).fetchone()[0]
                    cb = conn.execute("SELECT COALESCE(SUM(amount),0) FROM cashback WHERE phone=?", (phone,)).fetchone()[0]
                    cb_red = conn.execute("SELECT COALESCE(SUM(amount),0) FROM deposit_deductions WHERE phone=? AND reason LIKE 'cashback%'", (phone,)).fetchone()[0]
                    total = round(dep - ded + cb - cb_red, 2)
                    last_cb_row = conn.execute("SELECT amount FROM cashback WHERE phone=? ORDER BY created_at DESC LIMIT 1", (phone,)).fetchone()
                    last_cb = last_cb_row[0] if last_cb_row else 0
                finally:
                    conn.close()
                if last_cb > 0 or total > 0:
                    try:
                        from loyalty import get_client_tier
                        tier = get_client_tier(phone)
                        tier_name = tier.get('name', 'Старт')
                        rate_pct = '{:.1f}'.format(tier.get('rate', 0.03) * 100)
                        cb_balance = round(cb - cb_red, 2)
                        cashback_min = 500
                        remaining_redeem = max(cashback_min - cb_balance, 0)

                        if last_cb > 0:
                            cashback_line = '\n\n💰 Кешбек +{:.0f} грн ({})'.format(last_cb, rate_pct + '%')
                        else:
                            cashback_line = ''

                        # Progress to redeem
                        if cb_balance >= cashback_min:
                            cashback_line += '\n✅ Кешбек {:.0f} грн — можна списати!'.format(cb_balance)
                        elif cb_balance > 0:
                            cashback_line += '\nДо списання ще {:.0f} грн (зібрано {:.0f} / {} грн)'.format(remaining_redeem, cb_balance, cashback_min)

                        # Tier progress
                        next_name = tier.get('next_name')
                        if next_name:
                            visits = tier.get('visits', 0)
                            redeems = tier.get('redeems', 0)
                            next_visits = tier.get('next_visits', 0)
                            next_redeems = tier.get('next_redeems', 0)
                            visits_left = max(next_visits - visits, 0)
                            redeems_left = max(next_redeems - redeems, 0)
                            if visits_left > 0 and redeems_left > 0:
                                v_word = 'візит' if visits_left == 1 else ('візити' if visits_left < 5 else 'візитів')
                                r_word = 'зняття' if redeems_left == 1 else ('зняття' if redeems_left < 5 else 'знять')
                                cashback_line += '\n🏆 {} → {}: ще {} {} або {} {}'.format(tier_name, next_name, visits_left, v_word, redeems_left, r_word)

                        cashback_line += '\n\nБаланс: {:.0f} грн'.format(total)
                    except Exception:
                        if last_cb > 0:
                            cashback_line = '\n\n💰 Кешбек +{:.0f} грн. Баланс: {:.0f} грн'.format(last_cb, total)
                        elif total > 0:
                            cashback_line = '\n\nБаланс: {:.0f} грн'.format(total)
        except Exception:
            pass

    # Check if client already left a Google review — don't ask again
    has_review = False
    try:
        from sync_reviews import has_google_review
        has_review = has_google_review(phone)
    except Exception:
        pass

    if has_review:
        # Already reviewed — just thank, no review link
        base_msg = '{first_name}, Dr. Gomon Cosmetology дякує за довіру!'.format(**v)
    else:
        base_msg = '{first_name}, Dr. Gomon Cosmetology дякує за довіру! Будемо вдячні і за Ваш відгук: https://flyl.link/google'.format(**v)

    app_msg = '\n\n💰 Не втрачайте кешбек 3% з кожної процедури — встановіть додаток Dr. Gomon: https://flyl.link/app'

    # SMS version: short, no emoji
    import re as _re_sms
    cashback_line_sms = _re_sms.sub(r'[^\w\s.,!?:;/%()+\-₴грн]', '', cashback_line).strip() if cashback_line else ''
    # Shorten SMS cashback line — keep only amount + balance
    if cashback_line_sms and last_cb > 0:
        cashback_line_sms = '\nКешбек +{:.0f} грн. Баланс: {:.0f} грн'.format(last_cb, total)

    if cashback_line:
        tg = base_msg + cashback_line
        sms = base_msg + cashback_line_sms
    else:
        tg = base_msg + app_msg
        sms = base_msg.replace('https://flyl.link/google', 'flyl.link/google') + '\nКешбек 3% в додатку: flyl.link/app'

    push_title = 'Дякуємо за візит!'
    if has_review:
        push_body = 'Кешбек нараховано!' if cashback_line else 'Дякуємо за візит!'
    else:
        push_body = 'Кешбек нараховано! Залиште відгук' if cashback_line else 'Залиште відгук — нам важлива ваша думка'
    return tg, sms, push_title, push_body


def fmt_cancel_client(appt):
    """Підтвердження скасування для клієнта. Повертає (tg, sms, push_title, push_body)."""
    v = _appt_vars(appt)
    tg = (
        '{first_name}, Ваш запис на {date} о {time} скасовано. '
        'Якщо виникнуть питання, спеціаліст {spec_name} з радістю відповість '
        'за тел. {spec_phone} або в Instagram {spec_insta}'
    ).format(**v)
    sms = (
        '{first_name}, запис на {date_short} о {time} скасовано. '
        'Питання: {spec_name} {spec_phone}'
    ).format(**v)
    push_title = 'Запис скасовано'
    push_body  = '{service}, {date_short}'.format(**v)
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
        '{spec_name}, до тебе на завтра {date} о {time} '
        'записаний клієнт {first_name} на процедуру "{service}". {price_part}'
    ).format(price_part=price_part, **v)


def fmt_admin_tomorrow_line(appt):
    """Один рядок для адмін-дайджесту завтрашніх записів.
    Формат: {date} о {time} «{service}». {name}, +380XXXXXXXXX, {notes}"""
    v = _appt_vars(appt)
    raw_phone = appt.get('client_phone') or ''
    # Format as +380... for TG auto-linking
    if raw_phone.startswith('380'):
        phone_display = '+' + raw_phone
    elif raw_phone.startswith('0'):
        phone_display = '+38' + raw_phone
    else:
        phone_display = raw_phone
    notes = (appt.get('notes') or '').strip()
    line = '{date_short} о {time} «{service}». {first_name}, {phone}'.format(
        phone=phone_display, **v)
    if notes:
        line += ', {}'.format(notes)
    return line


def fmt_specialist_tomorrow(appt):
    """Один рядок для спеціаліста — завтрашній запис з ціною і тривалістю.
    Формат: {spec_name}, до тебе на завтра {date} о {time} записаний клієнт {name}
    на процедуру "{service}". Вартість {price}, тривалість {duration}."""
    v = _appt_vars(appt)
    price = _lookup_price(v['service'])
    if price:
        price_part = 'Нагадаю, що вартість процедури «{service}» {price}, а орієнтовна тривалість {duration}.'.format(
            price=price, **v)
    else:
        price_part = 'Орієнтовна тривалість процедури — {duration}.'.format(**v)
    return (
        '{spec_name}, до тебе на завтра {date_short} о {time} '
        'записаний клієнт {first_name} на процедуру "{service}". {price_part}'
    ).format(price_part=price_part, **v)


def send_tomorrow_briefing(appts_by_specialist, admin_phones=None, skip_specialist_msg=None):
    """
    Надсилає о 20:00 зведення завтрашніх записів:
    1. Адміну (Victoria) — повний список всіх записів
    2. Кожному спеціалісту — його записи з цінами

    appts_by_specialist: {'victoria': [appt, ...], 'anastasia': [...]}
    admin_phones: список номерів адмінів для дайджесту (за замовч. SPECIALIST_INFO['victoria'])
    """
    results = {'admin': False, 'specialists': {}}

    # 1. Адмін-дайджест (всі записи одним повідомленням)
    all_appts = []
    for spec, appts in appts_by_specialist.items():
        all_appts.extend(appts)
    all_appts.sort(key=lambda a: (a.get('time') or ''))

    if not all_appts:
        return results

    lines = [fmt_admin_tomorrow_line(a) for a in all_appts]
    admin_text = 'Записи на завтра ({}):\n\n{}'.format(
        len(all_appts), '\n'.join(lines))

    # Надіслати адміну (Victoria = головний лікар) — TG + IG
    admin_phone = (admin_phones or [SPECIALIST_INFO['victoria']['phone_norm']])[0]
    tg_id = _get_tg_id(admin_phone)
    if tg_id:
        results['admin'] = _send_tg(tg_id, admin_text)
        if results['admin']:
            from tz_utils import kyiv_now as _kn_br
            _br_ref = 'briefing_' + _kn_br().strftime('%Y-%m-%d')
            _log(admin_phone, 'tomorrow_briefing', _br_ref, 'tg', 'sent', admin_text[:100])
    # Also IG (best-effort)
    victoria_ig = SPECIALIST_INFO.get('victoria', {}).get('ig_user_id')
    if victoria_ig:
        _send_ig(victoria_ig, admin_text)
    logger.info('tomorrow_briefing admin → {}'.format(results['admin']))

    # 2. Кожному спеціалісту — його записи (skip if in skip list)
    _skip = skip_specialist_msg or []
    for spec, appts in appts_by_specialist.items():
        if not appts:
            continue
        if spec in _skip:
            logger.info('tomorrow_briefing {} skipped (disabled in settings)'.format(spec))
            continue
        appts_sorted = sorted(appts, key=lambda a: (a.get('time') or ''))
        lines = [fmt_specialist_tomorrow(a) for a in appts_sorted]
        spec_text = '\n\n'.join(lines)
        ok = notify_specialist(spec, spec_text)
        results['specialists'][spec] = ok
        if ok:
            from tz_utils import kyiv_now as _kn_sp
            _sp_ref = 'briefing_{}_{}'.format(spec, _kn_sp().strftime('%Y-%m-%d'))
            spec_info = SPECIALIST_INFO.get(spec, {})
            _log(spec_info.get('phone_norm', ''), 'tomorrow_briefing', _sp_ref, 'tg', 'sent', spec_text[:100])
        logger.info('tomorrow_briefing {} ({} appts) → {}'.format(spec, len(appts), ok))

    return results


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
    results = notify_client(phone, tg, sms, push_title, push_body, push_tag='reminder', push_url='/app/#appointments')

    for ch, ok in results.items():
        if ok is not None:
            _log(phone, 'appt_reminder', ref, ch, 'sent' if ok else 'failed', tg)

    logger.info('reminder_24h phone={} date={} → {}'.format(phone, appt.get('date'), results))
    return results


def send_post_visit(appt):
    """
    Подяка + відгук через 2 години після процедури.
    Дедуплікація: один раз на (phone, date).

    Канали: Push + TG + SMS fallback.
    Для app users — додає інфо про кешбек і баланс.

    TODO: Запускати через 2 години після процедури (appt_reminder.py --feedback).
    Зараз: Push only. Розкоментувати TG/SMS блок для повної доставки.
    """
    phone = appt.get('client_phone', '')
    ref = 'feedback|{}'.format(appt.get('date', ''))
    if not phone:
        return {}
    if _already_sent(phone, 'feedback', ref, 'push'):
        return {'skipped': True}
    tg, sms, push_title, push_body = fmt_post_visit(appt)

    # Push — завжди
    push_ok = _send_push(phone, push_title, push_body, 'feedback', 'https://flyl.link/google')
    if push_ok is not None:
        _log(phone, 'feedback', ref, 'push', 'sent' if push_ok else 'failed', push_title)

    # TG + SMS fallback
    tg_ok = False
    sms_ok = False
    if not _already_sent(phone, 'feedback', ref, 'tg'):
        tg_id = _get_tg_id(phone)
        if tg_id:
            tg_ok = _send_tg(tg_id, tg)
            _log(phone, 'feedback', ref, 'tg', 'sent' if tg_ok else 'failed', tg[:80])
        if not tg_ok and not _already_sent(phone, 'feedback', ref, 'sms'):
            from sms_fly import send_sms
            sms_ok = send_sms(phone, sms)
            _log(phone, 'feedback', ref, 'sms', 'sent' if sms_ok else 'failed', sms[:80])

    logger.info('post_visit phone={} date={} → push={} tg={} sms={}'.format(phone, appt.get('date'), push_ok, tg_ok, sms_ok))
    return {'push': push_ok, 'tg': tg_ok, 'sms': sms_ok}


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
        results['client'] = notify_client(phone, tg, sms, push_title, push_body, push_tag='cancel', push_url='/app/#appointments')
        for ch, ok in results['client'].items():
            if ok is not None:
                _log(phone, 'cancel', ref, ch, 'sent' if ok else 'failed', tg)

    spec = appt.get('specialist')
    if spec:
        # Dedup: check if already sent cancel to specialist for this appt
        spec_ref = 'spec_cancel|{}|{}'.format(appt_id, appt.get('date', ''))
        spec_phone = SPECIALIST_INFO.get(spec, {}).get('phone_norm', '')
        if spec_phone and not _already_sent(spec_phone, 'cancel', spec_ref, 'tg'):
            spec_text = fmt_cancel_specialist(appt)
            results['specialist'] = notify_specialist(spec, spec_text)
            if results['specialist']:
                _log(spec_phone, 'cancel', spec_ref, 'tg', 'sent', '')

    logger.info('cancellation phone={} date={} → {}'.format(phone, appt.get('date'), results))
    return results


def send_appt_confirm(appt):
    """
    Підтвердження запису клієнту одразу після створення адміном.
    Дедуплікація за appt id — не надсилає повторно.
    appt повинен містити: client_phone, client_name, procedure_name,
                          specialist, date, time, duration_min, id
    """
    phone   = appt.get('client_phone', '')
    appt_id = appt.get('id', '')
    ref     = 'confirm|{}'.format(appt_id)
    if not phone:
        return {}

    if _already_sent(phone, 'appt_confirm', ref, 'tg') or \
       _already_sent(phone, 'appt_confirm', ref, 'sms') or \
       _already_sent(phone, 'appt_confirm', ref, 'push'):
        return {'skipped': True}

    tg, sms, push_title, push_body = fmt_appt_confirm(appt)
    results = notify_client(phone, tg, sms, push_title, push_body, push_tag='confirm', push_url='/app/#appointments')

    for ch, ok in results.items():
        if ok is not None:
            _log(phone, 'appt_confirm', ref, ch, 'sent' if ok else 'failed', tg)

    logger.info('appt_confirm phone={} id={} → {}'.format(phone, appt_id, results))
    return results
