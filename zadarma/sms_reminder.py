# sms_reminder.py — Нагадування клієнтам про повторні процедури
# Запуск: python3 sms_reminder.py [--dry-run]
# Cron:   0 9-21 * * * cd /home/gomoncli/zadarma && /usr/bin/python3 sms_reminder.py 2>&1
#         0,30 22 * * * cd /home/gomoncli/zadarma && /usr/bin/python3 sms_reminder.py 2>&1

import logging
import logging.handlers
import json
import sqlite3
import random
import requests
from datetime import date, datetime, timedelta
import sys
sys.path.insert(0, '/home/gomoncli/zadarma')
try:
    from tz_utils import kyiv_now
except ImportError:
    kyiv_now = datetime.now
from user_db import DB_PATH
from sms_fly import send_sms


def _send_reminder(phone, tg_text, sms_text=None):
    """
    TG-first, SMS-fallback для нагадувань клієнту.
    Повертає (success: bool, channel: str).
    channel: 'tg' | 'sms' | 'failed'
    """
    try:
        from notifier import _get_tg_id, _send_tg
        tg_id = _get_tg_id(phone)
        if tg_id:
            ok = _send_tg(tg_id, tg_text)
            if ok:
                return True, 'tg'
            # TG fail → fallthrough to SMS
    except Exception as e:
        logger.warning('TG lookup/send failed for {}: {}'.format(phone, e))

    ok = send_sms(phone, sms_text or tg_text)
    return ok, ('sms' if ok else 'failed')

logger = logging.getLogger('sms_reminder')

LOG_FILE = '/home/gomoncli/zadarma/sms_reminder.log'

# Telegram: кому надсилати звіти (з config.py)
from config import ADMIN_USER_IDS, ADMIN_USER_ID
NOTIFY_ALL   = [ADMIN_USER_ID]     # тільки адмін (0933297777) — підсумки
NOTIFY_ADMIN = [ADMIN_USER_ID]     # тільки адмін — помилки

# =============================================================================
# КОНФІГУРАЦІЯ ІНТЕРВАЛІВ (днів до наступної процедури)
# Порядок важливий: від специфічного до загального
# =============================================================================
SERVICE_INTERVALS = {
    # Ботулінотерапія (130 днів)
    'ніфертіті':                    130,
    'нефертіті':                    130,
    'nefertiti':                    130,
    'full face':                    130,
    'ботулін':                      130,
    'ботулотоксин':                 130,   # "Корекція ботулотоксину"
    'botox':                        130,
    'neuronox':                     130,
    'nabota':                       130,
    'xeomin':                       130,
    # Філери обличчя (300 днів)
    'контурна пластика обличчя':    300,
    'neuramis volume':              300,
    'saypha volume':                300,
    'neauvia stimulate':            300,
    # Філери губ (210 днів)
    'контурна пластика губ':        210,
    'neuramis deep':                210,
    'saypha filler':                210,
    'perfecta':                     210,
    'genyal':                       210,
    'xcelence':                     210,
    'neauvia intense':              210,
    # Відбілювання зубів (270 днів)
    'magic smile':                  270,
    'відбілювання':                 270,
    # Біорепарація / Біоревіталізація (28 днів)
    'rejuran':                       28,
    'exoxe':                         28,
    'екзосоми':                      28,
    'біорепарація':                  28,
    'smart-біоревіталізація':        28,
    'smart-biore':                   28,
    'vitaran':                       28,
    'neauvia hydro':                 28,
    'skin booster':                  28,
    'біоревіталізація':              28,
    # Мезотерапія (21 день)
    'hair loss':                     21,
    'hair vital':                    21,
    'fill up':                       21,
    'plinest':                       21,
    'мезоботокс':                    21,
    'monaco':                        21,
    'монако':                        21,
    'мезотерапія':                   21,
    # Ферментотерапія / Ліполіз (21 день)
    'ліполітик':                     21,
    'lipolytic':                     21,
    # Пілінги (18 днів)
    'prx':                           18,
    'kemikum':                       18,
    'азелаїн':                       18,
    'мигдал':                        18,
    'феруло':                        18,
    'пілінг':                        18,
    # Карбокситерапія (14 днів)
    'карбокситерапія':               14,
    'carbotherapy':                  14,
    # Корекція тіла (8 днів)
    'drumroll':                       8,
    'пресотерапія':                   8,
    'pressotherapy':                  8,
    # Чистки та загальний догляд (35 днів)
    'wow':                           35,
    'підліткова':                    35,
    'кисневий':                      35,
    'oxygen':                        35,
    'glow skin':                     35,
    'spa':                           35,
    'spa-догляд':                    35,
    'christina':                     35,
}

# =============================================================================
# SMS ШАБЛОНИ
# {name}     — ім'я клієнта
# {service}  — назва послуги
# {elapsed}  — час з моменту процедури: "4 місяці" або "18 днів"
# =============================================================================
LINKS = 'Запис: ig.me/m/dr.gomon або t.me/DrGomonCosmetology'

SMS_TEMPLATES = {
    'botox': [
        '{name}, настав час попіклуватися про себе! Ботулінотерапія була аж {elapsed} тому — результат вже чекає на оновлення. {links}',
        '{name}, {elapsed} без ботоксу — і обличчя вже натякає. Самий час підтримати ефект! {links}',
        'Привіт, {name}! Минуло {elapsed} з процедури «{service}». Ефект поступово зникає — саме час його повернути. {links}',
    ],
    'fillers': [
        '{name}, {elapsed} тому ви були приголомшливі після «{service}» — час підтримати цей результат! {links}',
        'Привіт, {name}! «{service}» — вже {elapsed} тому. Краса любить турботу — запишіться на корекцію. {links}',
        '{name}, аж {elapsed} минуло з «{service}». Не дайте часу взяти гору — Dr.Gomon чекає. {links}',
    ],
    'whitening': [
        '{name}, ваша посмішка заслуговує на зірковий блиск! Відбілювання було {elapsed} тому — час оновити сяйво. {links}',
        'Привіт, {name}! {elapsed} тому ваші зуби сяяли після «{service}». Підтримайте результат. {links}',
        '{name}, {elapsed} без Magic Smile — і це вже помітно. Час виправити! {links}',
    ],
    'biorevital': [
        '{name}, шкіра потребує вологи — а {elapsed} без «{service}» це вже відчуває. Продовжимо курс? {links}',
        'Привіт, {name}! Минуло {elapsed} з вашого сеансу «{service}». Шкіра просить продовження — не відмовляйте їй. {links}',
        '{name}, {elapsed} тому ви вкладали в свою шкіру — саме час закріпити ефект «{service}». {links}',
    ],
    'meso': [
        '{name}, курс «{service}» дає результат тільки в комплексі! Минуло {elapsed} — не переривайте. {links}',
        'Привіт, {name}! {elapsed} тому — сеанс «{service}». Шкіра вже чекає на продовження. {links}',
        '{name}, аж {elapsed} без «{service}»? Поверніться до курсу — і ефект не змусить себе чекати. {links}',
    ],
    'peeling': [
        '{name}, {elapsed} тому ваша шкіра сяяла після «{service}». Час новому оновленню! {links}',
        'Привіт, {name}! Минуло {elapsed} — і шкіра знову готова до «{service}». Не тримайте її в очікуванні. {links}',
        '{name}, {elapsed} без пілінгу — шкіра вже підказує: час оновлення. {links}',
    ],
    'body': [
        '{name}, {elapsed} тому ваше тіло відчувало результат «{service}». Не зупиняйтесь — закріпіть ефект! {links}',
        'Привіт, {name}! Мине ще трохи — і {elapsed} без «{service}» дадуть про себе знати. Записуйтесь. {links}',
        '{name}, аж {elapsed} без «{service}» — тіло заслуговує на турботу! Dr.Gomon чекає. {links}',
    ],
    'cleaning': [
        '{name}, шкіра любить чистоту! Минуло {elapsed} з «{service}» — час дати їй свіжий старт. {links}',
        'Привіт, {name}! {elapsed} тому ваша шкіра дихала на повні груди після «{service}». Повторимо? {links}',
        '{name}, аж {elapsed} без «{service}» — пори чекають. Запишіться до Dr.Gomon: {links}',
    ],
    'general': [
        '{name}, настав час попіклуватися про себе! Процедура «{service}» була {elapsed} тому — ви на це заслуговуєте знову. {links}',
        'Привіт, {name}! Минуло {elapsed} з «{service}». Dr.Gomon чекає вас для повторної процедури. {links}',
        '{name}, {elapsed} без «{service}» — достатньо чекали. Запишіться: {links}',
    ],
}

# Статуси wlaunch, що означають скасування
CANCELLED_STATUSES = {'CANCELLED', 'CANCELED', 'CANCEL', 'ANNULLED', 'REJECTED', 'NO_SHOW'}

# Година за замовчуванням якщо час запису невідомий
DEFAULT_SEND_HOUR = 11

# Максимально дозволена година відправки (Київ)
MAX_SEND_HOUR = 22


def get_interval_days(service_name):
    """Повертає інтервал у днях для послуги (перший збіг перемагає)."""
    s = service_name.lower()
    for keyword, days in SERVICE_INTERVALS.items():
        if keyword in s:
            return days
    return 60


def get_service_category(service_name):
    """Повертає категорію SMS за назвою послуги."""
    s = service_name.lower()
    if any(k in s for k in ['ботулін', 'ботулотоксин', 'botox', 'neuronox', 'nabota',
                             'xeomin', 'ніфертіті', 'нефертіті', 'nefertiti', 'full face']):
        return 'botox'
    if any(k in s for k in ['контурна пластика', 'neuramis', 'saypha filler',
                             'perfecta', 'genyal', 'xcelence', 'neauvia intense']):
        return 'fillers'
    if any(k in s for k in ['magic smile', 'відбілювання зубів']):
        return 'whitening'
    if any(k in s for k in ['rejuran', 'exoxe', 'екзосоми', 'біорепарація',
                             'smart-біо', 'vitaran', 'neauvia hydro', 'skin booster',
                             'біоревіталізація']):
        return 'biorevital'
    if any(k in s for k in ['мезотерапія', 'мезоботокс', 'fill up', 'plinest',
                             'hair loss', 'hair vital', 'монако', 'monaco']):
        return 'meso'
    if any(k in s for k in ['prx', 'kemikum', 'пілінг', 'азелаїн', 'мигдал',
                             'феруло', 'карбокситерапія']):
        return 'peeling'
    if any(k in s for k in ['drumroll', 'пресотерапія', 'pressotherapy']):
        return 'body'
    if any(k in s for k in ['wow', 'чистка', 'cleaning', 'кисневий', 'oxygen',
                             'glow skin', 'spa', 'christina', 'підліткова']):
        return 'cleaning'
    return 'general'


def _tg_send(chat_id, text, token):
    """Відправляє повідомлення в Telegram (HTML). Делегує в notifier._send_tg."""
    try:
        from notifier import _send_tg
        ok = _send_tg(chat_id, text, parse_mode='HTML')
        if not ok:
            logger.warning('Telegram send failed via notifier to {}'.format(chat_id))
    except Exception as e:
        logger.warning('Telegram send failed to {}: {}'.format(chat_id, e))


def _tg_send_long(chat_id, text, token, limit=4000):
    """Відправляє довге повідомлення, розбиваючи на чанки по рядках."""
    if len(text) <= limit:
        _tg_send(chat_id, text, token)
        return
    lines = text.split('\n')
    chunk = ''
    for line in lines:
        if len(chunk) + len(line) + 1 > limit:
            _tg_send(chat_id, chunk.strip(), token)
            chunk = ''
        chunk += line + '\n'
    if chunk.strip():
        _tg_send(chat_id, chunk.strip(), token)


def notify_telegram(stats, sent_details, error_details, dry_run):
    """
    Надсилає Telegram-звіти після завершення запуску.
    sent_details: [(phone, name, text, channel), ...]
    - Підсумок → NOTIFY_ALL (обидва)
    - Помилки  → тільки NOTIFY_ADMIN
    Якщо нічого не відправлено і помилок немає — мовчимо.
    """
    from config import TELEGRAM_TOKEN
    now = kyiv_now().strftime('%d.%m.%Y %H:%M')
    dry_tag = ' [DRY RUN]' if dry_run else ''

    if stats['sent'] == 0 and stats['errors'] == 0:
        return

    if stats['sent'] > 0:
        tg_count  = sum(1 for *_, ch in sent_details if ch == 'tg')
        sms_count = sum(1 for *_, ch in sent_details if ch == 'sms')
        lines = ['🔔 <b>НАГАДУВАННЯ{}</b>'.format(dry_tag), '🕐 {}'.format(now), '']
        for phone, name, text, channel in sent_details:
            ch_icon = '💬' if channel == 'tg' else '📱'
            lines.append('{} <b>{}</b> ({})'.format(ch_icon, phone, name))
            lines.append('<i>{}</i>'.format(text))
            lines.append('')
        lines.append('📊 Відправлено: <b>{}</b>  (💬 TG: {} | 📱 SMS: {})'.format(
            stats['sent'], tg_count, sms_count))
        if stats['errors']:
            lines.append('⚠️ Помилок: {}'.format(stats['errors']))
        text = '\n'.join(lines)
        for uid in NOTIFY_ALL:
            _tg_send_long(uid, text, TELEGRAM_TOKEN)

    if stats['errors'] > 0:
        lines = ['❌ <b>ПОМИЛКИ НАГАДУВАНЬ{}</b>'.format(dry_tag), '🕐 {}'.format(now), '']
        for phone, name, text, *_ in error_details:
            lines.append('❌ {} — {}'.format(phone, name))
            lines.append('<i>{}</i>'.format(text))
            lines.append('')
        text = '\n'.join(lines)
        for uid in NOTIFY_ADMIN:
            _tg_send_long(uid, text, TELEGRAM_TOKEN)


def init_db_tables():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        'CREATE TABLE IF NOT EXISTS sms_reminders ('
        '    id                INTEGER PRIMARY KEY AUTOINCREMENT,'
        '    client_id         TEXT NOT NULL,'
        '    phone             TEXT NOT NULL,'
        '    service           TEXT NOT NULL,'
        '    visit_date        TEXT NOT NULL,'
        '    sent_date         TEXT NOT NULL,'
        '    status            TEXT DEFAULT "sent",'
        '    template_category TEXT,'
        '    UNIQUE(client_id, service, visit_date)'
        ')'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS sms_reminder_runs ('
        '    id         INTEGER PRIMARY KEY AUTOINCREMENT,'
        '    run_at     TEXT NOT NULL,'
        '    hour       INTEGER,'
        '    sent       INTEGER DEFAULT 0,'
        '    skipped    INTEGER DEFAULT 0,'
        '    errors     INTEGER DEFAULT 0,'
        '    dry_run    INTEGER DEFAULT 0'
        ')'
    )
    conn.commit()
    conn.close()
    logger.info('✅ Таблиці sms_reminders / sms_reminder_runs готові')


def log_run(stats, current_hour):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            'INSERT INTO sms_reminder_runs (run_at, hour, sent, skipped, errors, dry_run) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (kyiv_now().strftime('%Y-%m-%d %H:%M:%S'), current_hour,
             stats['sent'], stats['skipped'], stats['errors'],
             1 if stats['dry_run'] else 0)
        )
        conn.commit()
    except Exception as e:
        logger.error('log_run error: {}'.format(e))
    finally:
        conn.close()


def init_reminders_table():
    """Зворотна сумісність — викликає init_db_tables."""
    init_db_tables()


def is_reminder_already_sent(client_id, service, visit_date, phone=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Dedup by phone if client_id is empty (some clients synced without WLaunch ID)
    if phone and (not client_id or client_id == ''):
        cursor.execute(
            'SELECT id FROM sms_reminders WHERE phone=? AND service=? AND visit_date=?',
            (phone, service, visit_date))
    else:
        cursor.execute(
            'SELECT id FROM sms_reminders WHERE client_id=? AND service=? AND visit_date=?',
            (client_id, service, visit_date))
    row = cursor.fetchone()
    conn.close()
    return row is not None


def mark_reminder_sent(client_id, phone, service, visit_date, category, status='sent'):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            'INSERT OR IGNORE INTO sms_reminders '
            '(client_id, phone, service, visit_date, sent_date, status, template_category) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (client_id, phone, service, visit_date, kyiv_now().date().isoformat(), status, category)
        )
        conn.commit()
    except Exception as e:
        logger.error('❌ Помилка запису нагадування: {}'.format(e))
    finally:
        conn.close()


def fmt_elapsed(days):
    """Повертає людиночитабельний рядок: "18 днів" або "4 місяці"."""
    if days < 60:
        if days % 10 == 1 and days != 11:
            return '{} день'.format(days)
        elif 2 <= days % 10 <= 4 and not (12 <= days <= 14):
            return '{} дні'.format(days)
        return '{} днів'.format(days)
    months = days // 30
    if months % 10 == 1 and months != 11:
        return '{} місяць'.format(months)
    elif 2 <= months % 10 <= 4 and not (12 <= months <= 14):
        return '{} місяці'.format(months)
    return '{} місяців'.format(months)


def format_sms(template, first_name, service, visit_date_str, days_ago=0):
    name = first_name.strip() if first_name and first_name.strip() else 'Шановний клієнт'
    elapsed = fmt_elapsed(days_ago) if days_ago > 0 else ''
    return template.format(name=name, service=service, elapsed=elapsed, links=LINKS)


def check_and_send_reminders(dry_run=False):
    """
    Перевіряє всіх клієнтів і відправляє SMS тим, кому настав час нагадати.
    Запускається кроном щогодини (9-22).
    Кожен SMS відправляється тільки в ту годину, о якій був оригінальний запис.
    """
    stats = {'sent': 0, 'skipped': 0, 'errors': 0, 'dry_run': dry_run}
    sent_details = []    # (phone, name, sms_text) — для Telegram звіту
    error_details = []   # (phone, name, sms_text) — тільки адміну
    today = kyiv_now().date()
    current_hour = kyiv_now().hour

    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, first_name, phone, services_json FROM clients '
        'WHERE phone IS NOT NULL AND phone != "" '
        '  AND services_json IS NOT NULL AND services_json != "[]"'
    )
    clients = cursor.fetchall()
    conn.close()

    logger.info('👥 Перевіряємо {} клієнтів (година {:02d}:xx)...'.format(
        len(clients), current_hour))

    for client_id, first_name, phone, services_json_str in clients:
        try:
            services = json.loads(services_json_str or '[]')
        except (json.JSONDecodeError, TypeError):
            continue

        # Групуємо послуги по (категорія, інтервал).
        # Процедури з "корекція" в назві — це корекція ботоксу/філера,
        # а не окрема послуга. Відраховуємо від дати корекції якщо вона
        # пізніша за основну процедуру, інакше від основної.
        #
        # Особливий кейс "Корекція філера" — не знаємо губи (210д) чи обличчя (300д).
        # Спочатку групуємо всі звичайні записи, потім прив'язуємо такі корекції
        # до існуючої філлер-групи клієнта.
        FILLER_INTERVALS = [210, 300]

        groups = {}       # (cat, interval) → {'base': entry|None, 'correction': entry|None}
        loose_filler_corrs = []  # "Корекція філера" без конкретики — обробимо окремо

        for entry in services:
            svc = entry.get('service', '').strip()
            dt  = entry.get('date', '')
            if not svc or not dt:
                continue
            is_corr  = 'корекція' in svc.lower()
            cat      = get_service_category(svc)
            interval = get_interval_days(svc)

            # "Корекція філера" без конкретних ключових слів препарату → відкладаємо
            if is_corr and 'філер' in svc.lower() and interval == 60:
                loose_filler_corrs.append(entry)
                continue

            key = (cat, interval)
            if key not in groups:
                groups[key] = {'base': None, 'correction': None}
            field    = 'correction' if is_corr else 'base'
            existing = groups[key][field]
            if existing is None or dt > existing.get('date', ''):
                groups[key][field] = entry

        # Прив'язуємо "Корекція філера" до існуючої філлер-групи клієнта.
        # Шукаємо групу ('fillers', X) що має base-процедуру старішу за корекцію.
        for corr_entry in loose_filler_corrs:
            corr_dt = corr_entry.get('date', '')
            matched_key = None
            for fi in FILLER_INTERVALS:
                k = ('fillers', fi)
                if k in groups and groups[k]['base'] is not None:
                    if groups[k]['base'].get('date', '') < corr_dt:
                        matched_key = k
                        break
            if matched_key is None:
                # Не знайшли базову процедуру — беремо першу існуючу філлер-групу
                for fi in FILLER_INTERVALS:
                    k = ('fillers', fi)
                    if k in groups:
                        matched_key = k
                        break
            if matched_key is None:
                matched_key = ('fillers', 210)  # остаточний fallback
            if matched_key not in groups:
                groups[matched_key] = {'base': None, 'correction': None}
            existing = groups[matched_key]['correction']
            if existing is None or corr_dt > existing.get('date', ''):
                groups[matched_key]['correction'] = corr_entry

        # Формуємо ефективні записи: корекція перемагає якщо вона пізніша
        effective_entries = []
        for data in groups.values():
            base = data['base']
            corr = data['correction']
            if base is None and corr is None:
                continue
            if base is None:
                # Лише корекція без основної — рідкість, беремо як є
                effective_entries.append(corr)
                continue
            if corr is not None and corr.get('date', '') > base.get('date', ''):
                # Корекція була після основної — якщо не скасована, беремо її дату
                if (corr.get('status') or '').upper() not in CANCELLED_STATUSES:
                    effective = dict(base)
                    effective['date']   = corr['date']
                    effective['hour']   = corr.get('hour')
                    effective['status'] = corr.get('status', base.get('status', ''))
                    effective_entries.append(effective)
                    continue
            effective_entries.append(base)

        for entry in effective_entries:
            service = entry.get('service', '').strip()
            visit_date_str = entry.get('date', '')
            appt_hour_utc = entry.get('hour')        # int або None
            appt_status = (entry.get('status') or '').upper()

            if not service or not visit_date_str:
                continue

            # Послуги без нагадувань
            if any(k in service.lower() for k in ['гіалуронідаза', 'hyaluronidase', 'консультація']):
                continue

            try:
                visit_date_obj = datetime.strptime(visit_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                continue

            # Майбутній апоінтмент — не чіпаємо
            if visit_date_obj > today:
                stats['skipped'] += 1
                continue

            # Скасований запис — SMS не відправляємо
            if appt_status in CANCELLED_STATUSES:
                stats['skipped'] += 1
                continue

            # Визначаємо годину відправки (hour вже в київському часі після sync)
            if appt_hour_utc is not None:
                send_hour = appt_hour_utc
                if send_hour < 9:
                    send_hour = 9
                elif send_hour > MAX_SEND_HOUR:
                    send_hour = MAX_SEND_HOUR
            else:
                send_hour = DEFAULT_SEND_HOUR

            # Відправляємо тільки в потрібну годину
            if current_hour != send_hour:
                stats['skipped'] += 1
                continue

            # Перевіряємо вікно нагадування
            interval_days = get_interval_days(service)
            remind_date = visit_date_obj + timedelta(days=interval_days)
            reminder_window_end = remind_date + timedelta(days=3)

            if not (remind_date <= today <= reminder_window_end):
                stats['skipped'] += 1
                continue

            # Перевіряємо чи вже відправляли
            if is_reminder_already_sent(client_id, service, visit_date_str, phone=phone):
                logger.debug('⏭️  Вже відправлено: {} | {}'.format(phone, service))
                stats['skipped'] += 1
                continue

            # Формуємо SMS
            days_ago = (today - visit_date_obj).days
            category = get_service_category(service)
            templates = SMS_TEMPLATES.get(category, SMS_TEMPLATES['general'])
            template = random.choice(templates)
            message = format_sms(template, first_name, service, visit_date_str, days_ago)

            logger.info('{:02d}h | {} | {} | {} | {} дн. тому'.format(
                send_hour, phone, first_name, service, days_ago
            ))

            if dry_run:
                logger.info('🔇 DRY RUN: {}'.format(message))
                stats['sent'] += 1
                sent_details.append((phone, first_name or '', message, 'dry_run'))
            else:
                success, channel = _send_reminder(phone, message)
                ch_icon = '💬' if channel == 'tg' else '📱'
                if success:
                    mark_reminder_sent(client_id, phone, service, visit_date_str, category,
                                       status='sent_{}'.format(channel))
                    stats['sent'] += 1
                    sent_details.append((phone, first_name or '', message, channel))
                    logger.info('{} відправлено ({}) | {}'.format(ch_icon, channel, phone))
                else:
                    mark_reminder_sent(client_id, phone, service, visit_date_str, category, status='failed')
                    stats['errors'] += 1
                    error_details.append((phone, first_name or '', message, 'failed'))
                    logger.warning('❌ всі канали провалились | {}'.format(phone))

    logger.info('✅ Готово: відправлено={sent}, пропущено={skipped}, помилок={errors}'.format(**stats))
    log_run(stats, current_hour)

    # Save sent details to daily log file (for daily summary at 22:10)
    if sent_details or error_details:
        daily_log = '/tmp/sms_reminder_daily.json'
        existing = []
        try:
            with open(daily_log, 'r') as f:
                existing = json.load(f)
        except Exception:
            pass
        for phone, name, text, channel in sent_details:
            existing.append({'phone': phone, 'name': name, 'text': text, 'channel': channel, 'time': kyiv_now().strftime('%H:%M'), 'status': 'sent'})
        for phone, name, text, *_ in error_details:
            existing.append({'phone': phone, 'name': name, 'text': text, 'channel': 'failed', 'time': kyiv_now().strftime('%H:%M'), 'status': 'error'})
        try:
            with open(daily_log, 'w') as f:
                json.dump(existing, f, ensure_ascii=False)
        except Exception:
            pass

    return stats


def send_daily_summary():
    """Send daily summary of ALL notifications sent today. Called by cron at 22:10.
    Reads from notification_log (all types) + sms_reminder daily log."""
    from config import TELEGRAM_TOKEN
    today_str = kyiv_now().strftime('%Y-%m-%d')
    today_display = kyiv_now().strftime('%d.%m.%Y')

    # 1. Read notification_log (feedback, cancel, reminder, etc.)
    notif_entries = []
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        rows = conn.execute(
            "SELECT phone, type, channel, status, sent_at, message_preview "
            "FROM notification_log WHERE sent_at LIKE ? ORDER BY sent_at",
            (today_str + '%',)).fetchall()
        conn.close()
        for phone, ntype, channel, status, sent_at, preview in rows:
            notif_entries.append({
                'phone': phone, 'type': ntype, 'channel': channel,
                'status': status, 'time': (sent_at or '')[11:16],
                'preview': (preview or '')[:100]
            })
    except Exception as e:
        logger.error('daily_summary notification_log error: {}'.format(e))

    # 2. Read sms_reminder daily log (repeat procedure reminders)
    reminder_entries = []
    daily_log = '/tmp/sms_reminder_daily.json'
    try:
        with open(daily_log, 'r') as f:
            reminder_entries = json.load(f)
    except Exception:
        pass

    # Combine counts
    total_notif = len(notif_entries)
    total_remind = len([e for e in reminder_entries if e.get('status') == 'sent'])
    total_remind_err = len([e for e in reminder_entries if e.get('status') == 'error'])

    if total_notif == 0 and total_remind == 0 and total_remind_err == 0:
        return  # Nothing today

    TYPE_LABELS = {
        'feedback': '💬 Відгук', 'cancel': '❌ Скасування',
        'appt_reminder': '🔔 Нагадування', 'appt_confirm': '✅ Підтвердження',
        'spec_new': '👩‍⚕️ Спеціалісту (нові записи)', 'cashback_redeem': '💰 Кешбек',
        'tomorrow_briefing': '📋 Бріфінг на завтра',
    }

    lines = ['📊 <b>Повідомлення за {}</b>'.format(today_display), '']

    # Group notification_log by type
    # Don't count push failures as errors if TG/SMS succeeded for same phone+type
    sent_keys = set()  # (phone, type) where at least one channel succeeded
    for e in notif_entries:
        if e['status'] == 'sent':
            sent_keys.add((e['phone'], e['type']))

    # Dedup: show best channel per phone+type (tg > sms > push)
    CHAN_PRIO = {'tg': 0, 'sms': 1, 'push': 2}
    best_per_key = {}  # (phone, type) → entry with best channel
    for e in notif_entries:
        if e['status'] != 'sent':
            # Push fail with successful TG/SMS = not a real error
            if e['channel'] == 'push' and (e['phone'], e['type']) in sent_keys:
                continue
            key = (e['phone'], e['type'], 'fail')
            best_per_key[key] = e
            continue
        key = (e['phone'], e['type'])
        if key not in best_per_key or CHAN_PRIO.get(e['channel'], 9) < CHAN_PRIO.get(best_per_key[key].get('channel'), 9):
            best_per_key[key] = e

    by_type = {}
    for key, e in best_per_key.items():
        t = e['type']
        if t not in by_type:
            by_type[t] = {'sent': 0, 'failed': 0, 'entries': []}
        if e['status'] == 'sent':
            by_type[t]['sent'] += 1
            by_type[t]['entries'].append(e)
        else:
            by_type[t]['failed'] += 1
            by_type[t]['entries'].append(e)

    for ntype, data in by_type.items():
        label = TYPE_LABELS.get(ntype, ntype)
        lines.append('<b>{}</b>: {} відпр.{}'.format(
            label, data['sent'],
            ' ({} помилок)'.format(data['failed']) if data['failed'] else ''))
        for e in data['entries']:
            ch = '💬' if e['channel'] == 'tg' else '📱' if e['channel'] == 'sms' else '🔔'
            phone_display = e['phone'].replace('380', '+380', 1) if e['phone'].startswith('380') else e['phone']
            preview = ''
            if e.get('preview'):
                preview = ' · ' + e['preview'][:50].replace('<','&lt;').replace('\n',' ')
            lines.append('  {} {} {}{}'.format(e['time'], ch, phone_display, preview))
        lines.append('')

    # Repeat procedure reminders
    if total_remind > 0 or total_remind_err > 0:
        tg_r = sum(1 for e in reminder_entries if e.get('channel') == 'tg' and e.get('status') == 'sent')
        sms_r = sum(1 for e in reminder_entries if e.get('channel') == 'sms' and e.get('status') == 'sent')
        lines.append('<b>🔄 Повторні процедури</b>: {} відпр. (💬{} 📱{})'.format(total_remind, tg_r, sms_r))
        for e in reminder_entries:
            if e.get('status') != 'sent':
                continue
            ch = '💬' if e.get('channel') == 'tg' else '📱'
            preview = ''
            if e.get('procedure'):
                preview = ' · ' + (e.get('procedure',''))[:40]
            lines.append('  {} {} {} ({}){}'.format(e.get('time', ''), ch, e.get('phone', ''), e.get('name', ''), preview))
        if total_remind_err:
            lines.append('  ⚠️ Помилок: {}'.format(total_remind_err))
        lines.append('')

    # Total
    grand_total = total_notif + total_remind
    lines.append('📊 <b>Всього за день: {}</b>'.format(grand_total))

    text = '\n'.join(lines)
    for uid in NOTIFY_ALL:
        _tg_send_long(uid, text, TELEGRAM_TOKEN)

    # Clear daily reminder log
    try:
        import os
        os.remove(daily_log)
    except Exception:
        pass

    logger.info('Daily summary: {} notif + {} reminders'.format(total_notif, total_remind))


if __name__ == '__main__':
    import sys
    import os
    import fcntl

    # Check for --daily-summary flag
    if '--daily-summary' in sys.argv:
        send_daily_summary()
        sys.exit(0)

    # File lock to prevent overlapping runs
    _lock_fh = open('/tmp/sms_reminder.lock', 'w')
    try:
        fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print('Already running, exiting')
        sys.exit(0)

    # RotatingFileHandler: 1MB × 7 файлів = max 7MB, ротація автоматична
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1 * 1024 * 1024, backupCount=7, encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])

    init_db_tables()

    dry_run = '--dry-run' in sys.argv
    if dry_run:
        logger.info('🔇 РЕЖИМ DRY RUN — SMS відправлятися не будуть')

    results = check_and_send_reminders(dry_run=dry_run)
    print('Результат: {}'.format(results))
