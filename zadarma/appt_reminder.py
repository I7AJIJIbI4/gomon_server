#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# appt_reminder.py — Cron-скрипт нагадувань та feedback після процедури
#
# СТАТУС: --reminder і --feedback — НЕ ДОДАНО В CRON
#         --specialist — АКТИВНО (перевірка)
#
# Після перевірки (--dry-run) додати в crontab:
#   0 10,18 * * *  python3 /home/gomoncli/zadarma/appt_reminder.py --reminder
#   0 20    * * *  python3 /home/gomoncli/zadarma/appt_reminder.py --feedback --specialist
#
# Режими запуску:
#   --reminder    нагадування за 24 год (запуск о 10:00 та 18:00)
#   --feedback    подяка + відгук о 20:00 в день процедури
#   --specialist  сповіщення спеціалісту о 20:00 дня створення запису
#   --dry-run     тільки лог, без реальної відправки
#   (без аргументів) — всі три режими
# ─────────────────────────────────────────────────────────────────────────

import sys
import json
import logging
import logging.handlers
import sqlite3
import fcntl
from datetime import date, datetime, timedelta

sys.path.insert(0, '/home/gomoncli/zadarma')

LOCK_FILE = '/tmp/appt_reminder.lock'
_lock_fh  = None

def _acquire_lock():
    global _lock_fh
    _lock_fh = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except IOError:
        _lock_fh.close()
        return False

def _release_lock():
    global _lock_fh
    if _lock_fh:
        fcntl.flock(_lock_fh, fcntl.LOCK_UN)
        _lock_fh.close()
        _lock_fh = None

LOG_FILE = '/home/gomoncli/zadarma/appt_reminder.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=2*1024*1024, backupCount=3),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger('appt_reminder')

DB_PATH = '/home/gomoncli/zadarma/users.db'

# ─── DB helpers ───────────────────────────────────────────────────────────────

def _db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _get_manual_appts(for_date_str):
    """manual_appointments зі статусом CONFIRMED на вказану дату."""
    conn = _db()
    rows = conn.execute(
        "SELECT id, client_phone, client_name, procedure_name, specialist, "
        "date, time, duration, notes FROM manual_appointments "
        "WHERE date=? AND status='CONFIRMED'",
        (for_date_str,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            'id':             r['id'],
            'client_phone':   r['client_phone'] or '',
            'client_name':    r['client_name'] or '',
            'procedure_name': r['procedure_name'] or '',
            'specialist':     r['specialist'] or '',
            'date':           r['date'],
            'time':           r['time'] or '',
            'duration_min':   r['duration'] or 60,
            'notes':          r['notes'] or '',
            'source':         'manual',
        })
    return result


def _get_wlaunch_appts(for_date_str):
    """WLaunch-записи з services_json клієнтів на вказану дату."""
    conn = _db()
    rows = conn.execute(
        'SELECT phone, first_name, last_name, services_json FROM clients'
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        try:
            items = json.loads(row['services_json'] or '[]')
        except Exception:
            continue
        for it in items:
            if it.get('date') != for_date_str:
                continue
            status = (it.get('status') or '').upper()
            if status in ('CANCELLED', 'NO_SHOW'):
                continue
            name = ((row['first_name'] or '') + ' ' + (row['last_name'] or '')).strip()
            hour = it.get('hour')
            result.append({
                'appt_id':        it.get('appt_id', ''),
                'client_phone':   row['phone'] or '',
                'client_name':    name,
                'procedure_name': it.get('service') or '',
                'specialist':     it.get('specialist') or '',
                'date':           for_date_str,
                'time':           '{:02d}:00'.format(hour) if hour is not None else '',
                'duration_min':   it.get('duration_min') or 60,
                'source':         'wlaunch',
            })
    return result


def _collect_appts(for_date_str):
    """
    Збирає записи з обох джерел, дедуплікує за (phone, date).
    Пріоритет: manual > wlaunch (якщо обидва є для того самого клієнта і дати).
    """
    manual  = _get_manual_appts(for_date_str)
    wlaunch = _get_wlaunch_appts(for_date_str)

    seen = set()
    result = []
    for a in manual + wlaunch:
        phone = a.get('client_phone', '')
        if not phone:
            continue
        key = (phone[-9:], for_date_str)   # останні 9 цифр → universal dedup
        if key in seen:
            continue
        seen.add(key)
        result.append(a)
    return result

# ─── Режим --reminder (нагадування за 24 год) ────────────────────────────────

def run_reminder(dry_run=False):
    """
    Знаходить всі CONFIRMED-записи на завтра і надсилає нагадування.
    Запускати о 10:00 та 18:00.
    """
    tomorrow = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    logger.info('=== REMINDER 24h: перевіряємо записи на {} ==='.format(tomorrow))

    appts = _collect_appts(tomorrow)
    logger.info('Знайдено {} записів'.format(len(appts)))

    sent = skipped = failed = 0

    for appt in appts:
        phone = appt.get('client_phone', '')
        if not phone:
            logger.warning('  skip: немає телефону для {}'.format(appt))
            continue

        logger.info('  → {} | {} | {} о {} | {}'.format(
            phone, appt.get('client_name', '—'),
            appt.get('procedure_name', '—'), appt.get('time', '—'),
            appt.get('specialist', '—')
        ))

        if dry_run:
            logger.info('    [DRY-RUN] пропускаємо відправку')
            skipped += 1
            continue

        try:
            from notifier import send_reminder_24h
            results = send_reminder_24h(appt)
            if results.get('skipped'):
                logger.info('    вже відправлено раніше — пропускаємо')
                skipped += 1
            else:
                ok = any(v for v in results.values() if v)
                if ok:
                    sent += 1
                else:
                    failed += 1
                    logger.warning('    всі канали провалились: {}'.format(results))
        except Exception as e:
            logger.error('    помилка send_reminder_24h: {}'.format(e))
            failed += 1

    logger.info('=== REMINDER done: sent={} skipped={} failed={} ==='.format(
        sent, skipped, failed))
    return sent, skipped, failed

# ─── Режим --feedback (відгук після процедури, о 20:00) ──────────────────────

def run_feedback(dry_run=False):
    """
    Знаходить всі записи на сьогодні зі статусом CONFIRMED/DONE
    і надсилає подяку + посилання на відгук.
    Запускати о 20:00.
    """
    today = date.today().strftime('%Y-%m-%d')
    logger.info('=== FEEDBACK: перевіряємо записи на {} ==='.format(today))

    appts = _collect_appts(today)
    logger.info('Знайдено {} записів'.format(len(appts)))

    sent = skipped = failed = 0

    for appt in appts:
        phone = appt.get('client_phone', '')
        if not phone:
            continue

        logger.info('  → {} | {} | {}'.format(
            phone, appt.get('client_name', '—'), appt.get('procedure_name', '—')
        ))

        if dry_run:
            logger.info('    [DRY-RUN] пропускаємо відправку')
            skipped += 1
            continue

        try:
            from notifier import send_post_visit
            results = send_post_visit(appt)
            if results.get('skipped'):
                logger.info('    вже відправлено — пропускаємо')
                skipped += 1
            else:
                ok = any(v for v in results.values() if v)
                if ok:
                    sent += 1
                else:
                    failed += 1
                    logger.warning('    всі канали провалились: {}'.format(results))
        except Exception as e:
            logger.error('    помилка send_post_visit: {}'.format(e))
            failed += 1

    logger.info('=== FEEDBACK done: sent={} skipped={} failed={} ==='.format(
        sent, skipped, failed))
    return sent, skipped, failed

# ─── Режим --specialist (сповіщення спеціалістам, о 20:00) ──────────────────

def run_specialist_notifications(dry_run=False):
    """
    Збирає всі записи (manual + WLaunch) і надсилає спеціалісту сповіщення про кожен,
    якого ще не було надіслано (дедуплікація через notification_log).

    manual_appointments: тільки ті, що створені сьогодні (date >= today).
    WLaunch (services_json): всі майбутні у вікні today..+30 днів — нові знаходяться
    через відсутність запису в notification_log (деdup via send_specialist_new_appt).

    Запускати о 20:00.
    """
    today    = date.today().strftime('%Y-%m-%d')
    max_date = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')
    logger.info('=== SPECIALIST NOTIFY: перевіряємо записи (manual created={}, WL range {}..{}) ==='.format(
        today, today, max_date))

    # 1. Manual: лише створені сьогодні
    conn = _db()
    manual_rows = conn.execute(
        "SELECT id, client_phone, client_name, procedure_name, specialist, "
        "date, time, duration FROM manual_appointments "
        "WHERE DATE(created_at) = ? AND status != 'CANCELLED' AND date >= ?",
        (today, today)
    ).fetchall()
    conn.close()

    appts = []
    for r in manual_rows:
        appts.append({
            'id':             r['id'],
            'client_phone':   r['client_phone'] or '',
            'client_name':    r['client_name'] or '',
            'procedure_name': r['procedure_name'] or '',
            'specialist':     r['specialist'] or '',
            'date':           r['date'],
            'time':           r['time'] or '',
            'duration_min':   r['duration'] or 60,
            'source':         'manual',
        })

    # 2. WLaunch: майбутні записи у вікні today..+30 днів (нові — через відсутність в notification_log)
    conn = _db()
    clients = conn.execute(
        'SELECT phone, first_name, last_name, services_json FROM clients'
    ).fetchall()
    conn.close()
    for row in clients:
        try:
            items = json.loads(row['services_json'] or '[]')
        except Exception:
            continue
        for it in items:
            appt_date = it.get('date', '')
            if not (today <= appt_date <= max_date):
                continue
            status = (it.get('status') or '').upper()
            if status in ('CANCELLED', 'NO_SHOW'):
                continue
            name = ((row['first_name'] or '') + ' ' + (row['last_name'] or '')).strip()
            hour = it.get('hour')
            appts.append({
                'id':             it.get('appt_id', ''),
                'client_phone':   row['phone'] or '',
                'client_name':    name,
                'procedure_name': it.get('service') or '',
                'specialist':     it.get('specialist') or '',
                'date':           appt_date,
                'time':           '{:02d}:00'.format(hour) if hour is not None else '',
                'duration_min':   it.get('duration_min') or 60,
                'source':         'wlaunch',
            })

    logger.info('Знайдено {} записів (manual={}, wlaunch перевірено через dedup)'.format(
        len(appts), len(manual_rows)))

    sent = skipped = failed = 0

    for appt in appts:
        if not appt.get('specialist'):
            logger.warning('  skip: немає спеціаліста для запису id={}'.format(appt.get('id')))
            continue

        logger.info('  → id={} | {} | {} | {} о {} | spec={}'.format(
            appt.get('id'), appt.get('client_phone'), appt.get('client_name'),
            appt.get('procedure_name'), appt.get('time'), appt.get('specialist')
        ))

        if dry_run:
            logger.info('    [DRY-RUN] пропускаємо відправку')
            skipped += 1
            continue

        try:
            from notifier import send_specialist_new_appt
            results = send_specialist_new_appt(appt)
            if results.get('skipped'):
                logger.info('    вже відправлено раніше — пропускаємо')
                skipped += 1
            elif results.get('ok'):
                sent += 1
            else:
                failed += 1
                logger.warning('    відправка не вдалась: {}'.format(results))
        except Exception as e:
            logger.error('    помилка send_specialist_new_appt: {}'.format(e))
            failed += 1

    logger.info('=== SPECIALIST done: sent={} skipped={} failed={} ==='.format(
        sent, skipped, failed))
    return sent, skipped, failed


# ─── Режим --tomorrow (зведення записів на завтра, о 20:00) ─────────────────

def run_tomorrow_briefing(dry_run=False):
    """
    Збирає всі записи на завтра (manual + WLaunch) і надсилає:
    1. Адміну (Victoria) — повний список
    2. Кожному спеціалісту — його записи з цінами

    Шаблон адміну: "{date} о {time} «{service}». {name}, {phone}"
    Шаблон спеціалісту: "{spec}, до тебе на завтра {date} о {time}
        записаний клієнт {name} на процедуру "{service}". Вартість {price}, тривалість {duration}."
    """
    tomorrow = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    logger.info('=== TOMORROW BRIEFING: записи на {} ==='.format(tomorrow))

    appts = _collect_appts(tomorrow)
    logger.info('Знайдено {} записів на завтра'.format(len(appts)))

    if not appts:
        logger.info('Записів на завтра немає — не надсилаємо')
        return 0, 0, 0

    # Групуємо за спеціалістом
    by_spec = {}
    for a in appts:
        spec = a.get('specialist', '') or 'other'
        if spec not in by_spec:
            by_spec[spec] = []
        by_spec[spec].append(a)

    for spec, spec_appts in by_spec.items():
        logger.info('  {} — {} записів'.format(spec, len(spec_appts)))
        for a in spec_appts:
            logger.info('    {} о {} | {} | {}'.format(
                a.get('date'), a.get('time', '?'), a.get('client_name', '—'),
                a.get('procedure_name', '—')))

    if dry_run:
        logger.info('[DRY-RUN] не надсилаємо')
        return len(appts), 0, 0

    try:
        from notifier import send_tomorrow_briefing
        results = send_tomorrow_briefing(by_spec)
        logger.info('=== TOMORROW BRIEFING done: admin={} specialists={} ==='.format(
            results.get('admin'), results.get('specialists')))
        return len(appts), 1 if results.get('admin') else 0, 0
    except Exception as e:
        logger.error('tomorrow briefing error: {}'.format(e))
        return len(appts), 0, 1


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if not _acquire_lock():
        logging.basicConfig(level=logging.WARNING)
        logging.getLogger('appt_reminder').warning(
            'appt_reminder вже запущено (lock зайнятий). Пропускаємо.')
        sys.exit(0)

    try:
        dry_run  = '--dry-run' in sys.argv
        all_flags = ('--reminder', '--feedback', '--specialist', '--tomorrow')
        no_flags = not any(f in sys.argv for f in all_flags)
        do_rem   = '--reminder'   in sys.argv or no_flags
        do_fb    = '--feedback'   in sys.argv or no_flags
        do_spec  = '--specialist' in sys.argv or no_flags
        do_tmrw  = '--tomorrow'   in sys.argv or no_flags

        if dry_run:
            logger.info('*** DRY-RUN MODE — відправки не буде ***')

        if do_rem:
            run_reminder(dry_run=dry_run)

        if do_fb:
            run_feedback(dry_run=dry_run)

        if do_spec:
            run_specialist_notifications(dry_run=dry_run)

        if do_tmrw:
            run_tomorrow_briefing(dry_run=dry_run)
    finally:
        _release_lock()
