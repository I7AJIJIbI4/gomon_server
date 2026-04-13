# push_reminder.py — Push-нагадування для PWA
#
# Режими:
#   python3 push_reminder.py --repeat   — нагадування про повторні процедури (1/день)
#   python3 push_reminder.py --appt     — нагадування про запис завтра (кожні 2г)
#   python3 push_reminder.py            — обидва режими
#   python3 push_reminder.py --dry-run  — тільки лог, без реальних push
#
# Cron:
#   0 10 * * *          python3 push_reminder.py --repeat
#   0 */2 8-22 * * *    python3 push_reminder.py --appt

import logging
import logging.handlers
import json
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, '/home/gomoncli/zadarma')
try:
    from tz_utils import kyiv_now
except ImportError:
    kyiv_now = datetime.now

LOG_FILE = '/home/gomoncli/zadarma/push_reminder.log'

logger = logging.getLogger('push_reminder')

# =============================================================================
# PUSH ШАБЛОНИ ДЛЯ ПОВТОРНИХ ПРОЦЕДУР
# Формат: список (title, body) — обирається випадково
# {name} — ім'я, {service} — назва, {elapsed} — час ("4 місяці", "18 днів")
# =============================================================================
PUSH_REPEAT_TEMPLATES = {
    'botox': [
        ('Настав час оновити ботокс', '{name}, вже {elapsed} без процедури — обличчя вже натякає. Запишіться!'),
        ('{name}, ботокс чекає', 'Минуло {elapsed} з ботулінотерапії. Саме час повернути ефект!'),
        ('{elapsed} без ботоксу', '{name}, ефект зникає поступово. Dr.Gomon чекає на вас!'),
    ],
    'fillers': [
        ('Час освіжити контур', '{name}, {elapsed} після «{service}» — час підтримати результат!'),
        ('{name}, філери просять уваги', '{elapsed} без «{service}». Краса любить турботу — запишіться!'),
        ('Не дайте часу взяти гору', '{name}, аж {elapsed} без «{service}». Dr.Gomon чекає!'),
    ],
    'whitening': [
        ('Час оновити сяйво посмішки', '{name}, {elapsed} після відбілювання — саме час повернути блиск!'),
        ('{name}, ваша посмішка скучила', '{elapsed} без відбілювання. Magic Smile чекає!'),
        ('Зуби заслуговують блиску', '{name}, {elapsed} без «{service}». Час сяяти знову!'),
    ],
    'biorevital': [
        ('Шкіра хоче вологи', '{name}, {elapsed} без «{service}». Продовжимо курс?'),
        ('{name}, курс чекає', '{elapsed} без «{service}» — шкіра вже відчуває. Запишіться!'),
        ('Час наступного сеансу', '{name}, {elapsed} після «{service}». Не переривайте ефект!'),
    ],
    'meso': [
        ('Курс мезотерапії', '{name}, {elapsed} без «{service}» — не переривайте результат!'),
        ('{name}, шкіра чекає', '{elapsed} без «{service}». Продовжте курс — і ефект не змусить чекати!'),
        ('Аж {elapsed} без мезо?', '{name}, час повернутись до «{service}». Dr.Gomon чекає!'),
    ],
    'peeling': [
        ('Шкіра готова до оновлення', '{name}, {elapsed} після «{service}». Час новому сяянню!'),
        ('{name}, час пілінгу', '{elapsed} без «{service}» — шкіра вже підказує. Запишіться!'),
        ('Оновлення шкіри', '{name}, {elapsed} без пілінгу. Не тримайте шкіру в очікуванні!'),
    ],
    'body': [
        ('Час процедури для тіла', '{name}, {elapsed} після «{service}». Закріпіть ефект!'),
        ('{name}, тіло заслуговує', '{elapsed} без «{service}». Не зупиняйтесь на півдорозі!'),
        ('Результат чекає на продовження', '{name}, аж {elapsed} без «{service}». Dr.Gomon чекає!'),
    ],
    'cleaning': [
        ('Шкіра любить чистоту', '{name}, {elapsed} без «{service}». Час свіжого старту!'),
        ('{name}, час чистки', '{elapsed} після «{service}» — пори чекають на увагу!'),
        ('Свіжа шкіра кличе', '{name}, {elapsed} без «{service}». Повторимо?'),
    ],
    'general': [
        ('Час повторної процедури', '{name}, {elapsed} після «{service}». Саме час повторити!'),
        ('{name}, Dr.Gomon чекає', '{elapsed} без «{service}». Запишіться на повторну процедуру!'),
        ('Не зупиняйтесь', '{name}, {elapsed} після «{service}». Ви це заслуговуєте!'),
    ],
}

PUSH_APPT_TEMPLATES = [
    ('Нагадування про запис', '{name}, завтра{time} — «{service}». Чекаємо!'),
    ('{name}, завтра ваш день', '«{service}»{time}. Не забудьте — будемо раді вас бачити!'),
    ('Ваш запис завтра', '{name}, готуємося до «{service}»{time}. До зустрічі у Dr.Gomon!'),
]


def _fmt_date(date_str):
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
    except Exception:
        return date_str


def send_repeat_push_reminders(dry_run=False):
    """
    Раз на день: знаходить клієнтів, яким сьогодні настає вікно нагадування
    про повторну процедуру, і надсилає push (якщо є підписка).
    Логіка інтервалів — та сама що в sms_reminder.
    """
    from push_sender import (
        init_push_tables, get_subscriptions, send_push,
        is_push_already_sent, log_push
    )
    from sms_reminder import get_interval_days, get_service_category, fmt_elapsed

    init_push_tables()

    stats = {'sent': 0, 'skipped': 0, 'no_sub': 0, 'errors': 0}
    today = kyiv_now().date()
    CANCELLED = {'CANCELLED', 'CANCELED', 'CANCEL', 'ANNULLED', 'REJECTED', 'NO_SHOW'}
    SKIP_SERVICES = ['hyaluronidase', '\u0433\u0456\u0430\u043b\u0443\u0440\u043e\u043d\u0456\u0434\u0430\u0437\u0430',
                     '\u043a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0456\u044f']

    conn = sqlite3.connect('/home/gomoncli/zadarma/users.db', timeout=30)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, first_name, phone, services_json FROM clients '
        'WHERE phone IS NOT NULL AND phone != "" '
        '  AND services_json IS NOT NULL AND services_json != "[]"'
    )
    clients = cursor.fetchall()
    conn.close()

    logger.info('[repeat] Checking {} clients...'.format(len(clients)))

    for client_id, first_name, phone, services_json_str in clients:
        subs = get_subscriptions(phone)
        if not subs:
            stats['no_sub'] += 1
            continue

        try:
            services = json.loads(services_json_str or '[]')
        except Exception:
            continue

        for entry in services:
            service = entry.get('service', '').strip()
            visit_date_str = entry.get('date', '')
            appt_status = (entry.get('status') or '').upper()

            if not service or not visit_date_str:
                continue
            if any(k in service.lower() for k in SKIP_SERVICES):
                continue

            try:
                visit_date_obj = datetime.strptime(visit_date_str, '%Y-%m-%d').date()
            except Exception:
                continue

            if visit_date_obj > today:
                stats['skipped'] += 1
                continue
            if appt_status in CANCELLED:
                stats['skipped'] += 1
                continue

            interval_days = get_interval_days(service)
            remind_date = visit_date_obj + timedelta(days=interval_days)
            window_end = remind_date + timedelta(days=3)

            if not (remind_date <= today <= window_end):
                stats['skipped'] += 1
                continue

            reference = 'repeat|{}|{}'.format(service[:40], visit_date_str)
            if is_push_already_sent(phone, 'repeat', reference):
                stats['skipped'] += 1
                continue

            days_ago = (today - visit_date_obj).days
            name = (first_name or '').strip() or 'Клієнт'
            elapsed = fmt_elapsed(days_ago)
            category = get_service_category(service)
            title_tpl, body_tpl = random.choice(
                PUSH_REPEAT_TEMPLATES.get(category, PUSH_REPEAT_TEMPLATES['general'])
            )
            title = title_tpl.format(name=name, service=service, elapsed=elapsed)
            body = body_tpl.format(name=name, service=service, elapsed=elapsed)

            logger.info('[repeat] {} | {} | {}'.format(phone, service, visit_date_str))

            if dry_run:
                logger.info('[repeat] DRY RUN: title="{}" body="{}"'.format(title, body))
                stats['sent'] += 1
            else:
                ok = False
                for sub in subs:
                    from push_sender import send_push as _send
                    if _send(sub, title, body, url='/app/#chat', tag='repeat'):
                        ok = True
                if ok:
                    log_push(phone, 'repeat', reference, title, status='sent')
                    stats['sent'] += 1
                else:
                    log_push(phone, 'repeat', reference, title, status='failed')
                    stats['errors'] += 1

    logger.info('[repeat] Done: sent={sent} skipped={skipped} no_sub={no_sub} errors={errors}'.format(**stats))
    return stats


def send_appt_push_reminders(dry_run=False):
    """
    Кожні 2 години: знаходить записи, заплановані на завтра,
    і надсилає push-нагадування (якщо є підписка і ще не надсилали).
    """
    from push_sender import (
        init_push_tables, get_subscriptions, send_push,
        is_push_already_sent, log_push
    )

    init_push_tables()

    stats = {'sent': 0, 'skipped': 0, 'no_sub': 0, 'errors': 0}
    today = kyiv_now().date()
    tomorrow = today + timedelta(days=1)
    CANCELLED = {'CANCELLED', 'CANCELED', 'CANCEL', 'ANNULLED', 'REJECTED', 'NO_SHOW'}

    conn = sqlite3.connect('/home/gomoncli/zadarma/users.db', timeout=30)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, first_name, phone, services_json FROM clients '
        'WHERE phone IS NOT NULL AND phone != "" '
        '  AND services_json IS NOT NULL AND services_json != "[]"'
    )
    clients = cursor.fetchall()
    conn.close()

    logger.info('[appt] Checking {} clients for appointments on {}...'.format(
        len(clients), tomorrow))

    for client_id, first_name, phone, services_json_str in clients:
        subs = get_subscriptions(phone)
        if not subs:
            stats['no_sub'] += 1
            continue

        try:
            services = json.loads(services_json_str or '[]')
        except Exception:
            continue

        for entry in services:
            service = entry.get('service', '').strip()
            appt_date_str = entry.get('date', '')
            appt_status = (entry.get('status') or '').upper()
            appt_hour_utc = entry.get('hour')

            if not service or not appt_date_str:
                continue

            try:
                appt_date_obj = datetime.strptime(appt_date_str, '%Y-%m-%d').date()
            except Exception:
                continue

            # Тільки завтрашні записи
            if appt_date_obj != tomorrow:
                stats['skipped'] += 1
                continue

            # Скасовані — пропускаємо
            if appt_status in CANCELLED:
                stats['skipped'] += 1
                continue

            reference = 'appt|{}'.format(appt_date_str)
            if is_push_already_sent(phone, 'appt', reference):
                stats['skipped'] += 1
                continue

            # Формуємо час у повідомленні (hour вже в київському часі після sync)
            if appt_hour_utc is not None:
                time_str = ' \u043e {:02d}:00'.format(appt_hour_utc)
            else:
                time_str = ''

            name = (first_name or '').strip() or 'Клієнт'
            title_tpl, body_tpl = random.choice(PUSH_APPT_TEMPLATES)
            title = title_tpl.format(name=name, service=service, time=time_str)
            body = body_tpl.format(name=name, service=service, time=time_str)

            logger.info('[appt] {} | {} | {}{}'.format(phone, service, appt_date_str, time_str))

            if dry_run:
                logger.info('[appt] DRY RUN: title="{}" body="{}"'.format(title, body))
                stats['sent'] += 1
            else:
                ok = False
                for sub in subs:
                    from push_sender import send_push as _send
                    if _send(sub, title, body, url='/app/#appointments', tag='appt'):
                        ok = True
                if ok:
                    log_push(phone, 'appt', reference, title, status='sent')
                    stats['sent'] += 1
                else:
                    log_push(phone, 'appt', reference, title, status='failed')
                    stats['errors'] += 1

    logger.info('[appt] Done: sent={sent} skipped={skipped} no_sub={no_sub} errors={errors}'.format(**stats))
    return stats


if __name__ == '__main__':
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1 * 1024 * 1024, backupCount=7, encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])

    dry_run = '--dry-run' in sys.argv
    do_repeat = '--repeat' in sys.argv or ('--appt' not in sys.argv)
    do_appt   = '--appt'   in sys.argv or ('--repeat' not in sys.argv)

    if dry_run:
        logger.info('DRY RUN mode')

    results = {}
    if do_repeat:
        results['repeat'] = send_repeat_push_reminders(dry_run=dry_run)
    if do_appt:
        results['appt'] = send_appt_push_reminders(dry_run=dry_run)

    print('Result: {}'.format(results))
