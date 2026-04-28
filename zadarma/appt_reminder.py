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
import re
import json
import logging
import logging.handlers
import sqlite3
import fcntl
from datetime import date, datetime, timedelta

sys.path.insert(0, '/home/gomoncli/zadarma')
try:
    from tz_utils import kyiv_now
except ImportError:
    kyiv_now = datetime.now

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
OTP_DB_PATH = '/home/gomoncli/zadarma/otp_sessions.db'
PRICES_PATH = '/home/gomoncli/private_data/prices.json'
CASHBACK_RATE = 0.03  # 3%

def _is_app_user(phone):
    """Check if client has ever logged into the PWA (has session in otp_sessions.db)."""
    conn = None
    try:
        conn = sqlite3.connect(OTP_DB_PATH, timeout=5)
        row = conn.execute("SELECT 1 FROM sessions WHERE phone=? LIMIT 1", (phone,)).fetchone()
        return row is not None
    except Exception:
        return False
    finally:
        if conn:
            try: conn.close()
            except: pass

def _accrue_cashback(appt):
    """Auto-accrue 3% cashback for completed procedure. Only for app users."""
    phone = appt.get('client_phone', '')
    procedure = appt.get('procedure_name', '')
    appt_date = appt.get('date', '')
    if not phone or not procedure:
        return
    if not _is_app_user(phone):
        logger.info('    cashback skip: {} not an app user'.format(phone))
        return
    # Find price from prices.json (exact → substring → category match)
    price = 0
    try:
        with open(PRICES_PATH, 'r') as f:
            prices = json.load(f)
        proc_lower = procedure.lower().replace('«', '"').replace('»', '"')

        def _extract_price(item):
            p_str = str(item.get('price', '')).replace(' ', '')
            _m = re.search(r'\d+', p_str)
            return float(_m.group()) if _m else 0

        # 1. Exact match
        for cat in prices:
            for item in cat.get('items', []):
                if item.get('name', '').lower() == proc_lower:
                    price = _extract_price(item)
                    break
            if price:
                break

        # 2. Substring match (procedure contains item name or vice versa)
        if not price:
            best_len = 0
            for cat in prices:
                for item in cat.get('items', []):
                    iname = item.get('name', '').lower().replace('«', '"').replace('»', '"')
                    if len(iname) < 3:
                        continue
                    if iname in proc_lower or proc_lower in iname:
                        p = _extract_price(item)
                        if p and len(iname) > best_len:
                            price = p
                            best_len = len(iname)

        # 3. Category keyword match (e.g. "Ботулінотерапія" → first priced item in that category)
        if not price:
            CATEGORY_KEYWORDS = {
                'ботулін': 'Ботулінотерапія',
                'botox': 'Ботулінотерапія',
                'контурна пластика губ': 'Контурна пластика губ',
                'контурна пластика обличч': 'Контурна пластика обличчя',
                'контурна': 'Контурна пластика губ',
                'біорепар': 'Біорепарація',
                'біоревіталіз': 'Біоревіталізація',
                'мезотерап': 'Мезотерапія',
                'пілінг': 'Пілінги',
                'масаж': 'Масаж',
                'чистк': 'Апаратна косметологія',
            }
            for kw, cat_hint in CATEGORY_KEYWORDS.items():
                if kw in proc_lower:
                    for cat in prices:
                        if cat_hint.lower() in cat.get('cat', '').lower():
                            for item in cat.get('items', []):
                                p = _extract_price(item)
                                if p:
                                    price = p
                                    break
                        if price:
                            break
                if price:
                    break
    except Exception:
        pass
    if price <= 0:
        logger.info('    cashback skip: no price for "{}"'.format(procedure))
        return
    cashback_amount = round(price * CASHBACK_RATE, 2)
    if cashback_amount < 1:
        return
    # Atomic insert — skip if already exists (UNIQUE constraint on phone+procedure_name+appt_date)
    conn = _db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO cashback (phone, amount, procedure_name, procedure_price, appt_date) VALUES (?,?,?,?,?)",
            (phone, cashback_amount, procedure, price, appt_date))
        conn.commit()
        # H2 fix: use SELECT changes() instead of total_changes
        actual_changes = conn.execute("SELECT changes()").fetchone()[0]
    finally:
        conn.close()

    if actual_changes == 0:
        logger.info('    cashback already accrued for {} {} {}'.format(phone, procedure, appt_date))
    else:
        logger.info('    cashback +{} UAH (3% of {} for {})'.format(cashback_amount, price, procedure))
        # Check if total balance just reached 500 UAH → push notification
        conn2 = _db()
        try:
            total_cb = conn2.execute("SELECT COALESCE(SUM(amount),0) FROM cashback WHERE phone=?", (phone,)).fetchone()[0]
            cb_redeemed = conn2.execute("SELECT COALESCE(SUM(amount),0) FROM deposit_deductions WHERE phone=? AND reason LIKE 'cashback%'", (phone,)).fetchone()[0]
            dep = conn2.execute("SELECT COALESCE(SUM(amount_uah),0) FROM deposits WHERE phone=? AND status='Approved'", (phone,)).fetchone()[0]
            dep_ded = conn2.execute("SELECT COALESCE(SUM(amount),0) FROM deposit_deductions WHERE phone=?", (phone,)).fetchone()[0]
            total = round(dep - dep_ded + total_cb - cb_redeemed, 2)
            prev_total = round(total - cashback_amount, 2)
            if total >= 500 and prev_total < 500:
                logger.info('    cashback threshold reached! total={}'.format(total))
                from push_sender import send_push_to_phone
                send_push_to_phone(phone,
                    title='Ваш кешбек готовий до списання!',
                    body='Баланс {:.0f} грн. Оберіть процедуру і зверніться до лікаря'.format(total),
                    url='https://drgomon.beauty/app/#price',
                    tag='cashback_threshold')
        except Exception as e:
            logger.warning('    cashback threshold check error: {}'.format(e))
        finally:
            conn2.close()

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
    tomorrow = (kyiv_now().date() + timedelta(days=1)).strftime('%Y-%m-%d')
    logger.info('=== REMINDER 24h: перевіряємо manual записи на {} ==='.format(tomorrow))

    appts = _get_manual_appts(tomorrow)  # тільки наші записи, WLaunch сам шле SMS
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

# ─── Режим --feedback (відгук після процедури) ────────────────────────────────
#
# Поточна реалізація: запуск через cron о 20:00, обробляє всі записи за день.
#
# TODO: Ідеальна реалізація — через 2 години після кожної процедури:
#   1. Cron кожні 15 хвилин (*/15 * * * *)
#   2. Для кожного запису: порівняти time + duration_min + 120 хв з kyiv_now()
#   3. Якщо минуло 2+ години → send_post_visit
#   4. Dedup через notification_log (вже реалізовано)
#
# Для активації TG/SMS — розкоментувати блок у notifier.py::send_post_visit()
# Текст повідомлення (notifier.py::fmt_post_visit):
#   TG: "{first_name}, Dr. Gomon Cosmetology дякує за довіру! Будемо вдячні
#        і за Ваш відгук: https://flyl.link/google
#        [якщо app user: Вам нараховано кешбек +XX грн (3%). Ваш баланс: YY грн]
#        [якщо не app user: А ще в нас є додаток: https://flyl.link/app]"
#   SMS: "{first_name}, Dr.Gomon дякує за довіру!
#         Відгук: https://flyl.link/google Додаток: https://flyl.link/app"
# ─────────────────────────────────────────────────────────────────────────────

def run_feedback(dry_run=False, override_date=None):
    """
    Знаходить всі записи на вказану дату (або сьогодні) зі статусом CONFIRMED/DONE
    і надсилає подяку + посилання на відгук + нараховує кешбек.
    Запускати о 20:00. Підтримує --date YYYY-MM-DD для минулих дат.
    """
    target_date = override_date or kyiv_now().date().strftime('%Y-%m-%d')
    logger.info('=== FEEDBACK: перевіряємо записи на {} ==='.format(target_date))

    manual = _get_manual_appts(target_date)
    wlaunch = _get_wlaunch_appts(target_date)
    # Dedup manual vs wlaunch by phone+time (keep manual), but allow multiple procedures per client
    manual_keys = set()
    for a in manual:
        ph = (a.get('client_phone') or '')[-9:]
        manual_keys.add((ph, a.get('time', '')))
    appts = list(manual)
    for a in wlaunch:
        ph = (a.get('client_phone') or '')[-9:]
        if (ph, a.get('time', '')) not in manual_keys:
            appts.append(a)
    logger.info('Знайдено {} записів (manual={}, wlaunch={})'.format(len(appts), len(manual), len(appts) - len(manual)))

    sent = skipped = failed = cashback_ok = 0

    now = kyiv_now()

    for appt in appts:
        phone = appt.get('client_phone', '')
        if not phone:
            continue

        # Check if 2+ hours passed since procedure end
        appt_time = appt.get('time', '')
        appt_date = appt.get('date', '')
        duration_min = appt.get('duration_min') or 60
        if appt_time and appt_date:
            try:
                appt_start = datetime.strptime('{} {}'.format(appt_date, appt_time), '%Y-%m-%d %H:%M')
                appt_end = appt_start + timedelta(minutes=duration_min)
                send_after = appt_end + timedelta(hours=2)
                if now < send_after:
                    continue  # Too early — skip, will be picked up on next cron run
            except (ValueError, TypeError):
                pass  # Can't parse time — send anyway

        logger.info('  → {} | {} | {}'.format(
            phone, appt.get('client_name', '—'), appt.get('procedure_name', '—')
        ))

        # Cashback: auto-accrue only for procedures without drug selection
        # (procedures not in PROCEDURE_TO_CATEGORIES use auto-accrual)
        procedure = appt.get('procedure_name', '')
        # Exact WLaunch service names that need doctor price confirmation
        try:
            from photo_reminder import NEEDS_DRUG_SELECTION
        except ImportError:
            NEEDS_DRUG_SELECTION = {'Ботулінотерапія', 'Контурна пластика губ', 'Контурна пластика обличчя',
                                    'Біорепарація шкіри', 'Біоревіталізація шкіри', 'Мезотерапія',
                                    'Ліполітики (обличчя, 4 мл)', 'Ліполітики (тіло, 10 мл)',
                                    'Гіалуронідаза (розчинення філера)'}
        _is_drug = procedure in NEEDS_DRUG_SELECTION
        if not _is_drug:
            try:
                _accrue_cashback(appt)
                cashback_ok += 1
            except Exception as _ce:
                logger.warning('    cashback accrue error: {}'.format(_ce))

        if dry_run:
            logger.info('    [DRY-RUN] пропускаємо відправку')
            skipped += 1
            continue

        # Drug selection procedures: skip post_visit now — will be sent after doctor confirms price
        if _is_drug:
            logger.info('    skip post_visit (needs_drug) — will send after cashback confirmation')
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

    # Process pending cashback (confirmed by doctor, 24h passed)
    pending_accrued = _process_pending_cashback(dry_run)
    cashback_ok += pending_accrued

    logger.info('=== FEEDBACK done: sent={} skipped={} failed={} cashback={} (pending={}) ==='.format(
        sent, skipped, failed, cashback_ok, pending_accrued))
    return sent, skipped, failed


def _process_pending_cashback(dry_run=False):
    """Accrue cashback for pending entries where 24h passed since confirmation."""
    now = kyiv_now()
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT id, phone, drug_specific, price, appt_date, confirmed_at "
            "FROM cashback_pending WHERE accrued=0 AND confirmed_at IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()

    accrued = 0
    for row_id, phone, drug, price, appt_date, confirmed_at in rows:
        try:
            confirmed_dt = datetime.strptime(confirmed_at, '%Y-%m-%d %H:%M:%S')
            if now < confirmed_dt + timedelta(hours=24):
                continue  # Not yet 24h
        except (ValueError, TypeError):
            continue

        if dry_run:
            logger.info('    [DRY] pending cashback: {} {} {} ₴{}'.format(phone, appt_date, drug, price))
            continue

        cashback_amount = round(price * CASHBACK_RATE, 2)
        if cashback_amount < 1:
            c = _db()
            try:
                c.execute("UPDATE cashback_pending SET accrued=1 WHERE id=?", (row_id,))
                c.commit()
            finally:
                c.close()
            continue

        # Insert into cashback table — close DB before network calls
        c = _db()
        total = 0
        try:
            c.execute(
                "INSERT OR IGNORE INTO cashback (phone, amount, procedure_name, procedure_price, appt_date) VALUES (?,?,?,?,?)",
                (phone, cashback_amount, drug, price, appt_date))
            c.execute("UPDATE cashback_pending SET accrued=1 WHERE id=?", (row_id,))
            c.commit()
            accrued += 1
            logger.info('    pending cashback accrued: {} +{} ({}  ₴{})'.format(phone, cashback_amount, drug, price))

            # Read balance while still in DB
            dep = c.execute("SELECT COALESCE(SUM(amount_uah),0) FROM deposits WHERE phone=? AND status='Approved'", (phone,)).fetchone()[0]
            ded = c.execute("SELECT COALESCE(SUM(amount),0) FROM deposit_deductions WHERE phone=?", (phone,)).fetchone()[0]
            cb = c.execute("SELECT COALESCE(SUM(amount),0) FROM cashback WHERE phone=?", (phone,)).fetchone()[0]
            cb_red = c.execute("SELECT COALESCE(SUM(amount),0) FROM deposit_deductions WHERE phone=? AND reason LIKE 'cashback%'", (phone,)).fetchone()[0]
            total = round(dep - ded + cb - cb_red, 2)
        except Exception as e:
            logger.error('    pending cashback accrual error: {}'.format(e))
            continue
        finally:
            c.close()

        # Network calls AFTER closing DB connection
        try:
            from notifier import notify_client
            text = 'Вам нараховано кешбек +{:.0f} грн (3% від {}). Ваш баланс: {:.0f} грн\n\nhttps://flyl.link/app'.format(
                cashback_amount, drug, total)
            notify_client(phone, text, text,
                push_title='Кешбек нараховано!',
                push_body='+{:.0f} грн від {}'.format(cashback_amount, drug),
                push_tag='cashback_accrued', push_url='/app/#home')
        except Exception as ne:
            logger.warning('    cashback notify error: {}'.format(ne))

        # Check threshold
        try:
            prev_total = round(total - cashback_amount, 2)
            if total >= 500 and prev_total < 500:
                from push_sender import send_push_to_phone
                send_push_to_phone(phone,
                    title='Ваш кешбек готовий до списання!',
                    body='Баланс {:.0f} грн. Оберіть процедуру і зверніться до лікаря'.format(total),
                    url='https://drgomon.beauty/app/#price',
                    tag='cashback_threshold')
        except Exception as e:
            logger.error('    cashback threshold push error: {}'.format(e))

    return accrued

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
    today    = kyiv_now().date().strftime('%Y-%m-%d')
    max_date = (kyiv_now().date() + timedelta(days=30)).strftime('%Y-%m-%d')
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

    # Load per-specialist notification settings from DB
    _spec_new_appt_enabled = {}
    try:
        _sc = _db()
        for _row in _sc.execute("SELECT specialist, enabled FROM notification_settings WHERE type='spec_new_appt'").fetchall():
            _spec_new_appt_enabled[_row['specialist']] = bool(_row['enabled'])
        _sc.close()
    except Exception:
        pass  # Table may not exist — defaults apply
    # Default: victoria=off (briefing only), anastasia=on
    _spec_new_appt_enabled.setdefault('victoria', False)
    _spec_new_appt_enabled.setdefault('anastasia', True)

    # Group new (not yet notified) appointments by specialist, send one message per specialist
    from notifier import _already_sent, _log, _get_tg_id, _send_tg, SPECIALIST_INFO
    new_by_spec = {}
    for appt in appts:
        spec = appt.get('specialist', '')
        if not spec:
            continue
        if not _spec_new_appt_enabled.get(spec, True):
            skipped += 1
            continue
        ref = appt.get('id', '')
        if not ref:
            continue
        spec_info = SPECIALIST_INFO.get(spec)
        if not spec_info:
            continue
        spec_phone = spec_info['phone_norm']
        if _already_sent(spec_phone, 'spec_new', ref, 'tg'):
            skipped += 1
            continue
        if spec not in new_by_spec:
            new_by_spec[spec] = []
        new_by_spec[spec].append(appt)

    if dry_run:
        for spec, spec_appts in new_by_spec.items():
            logger.info('  [DRY-RUN] {} — {} нових записів'.format(spec, len(spec_appts)))
            skipped += len(spec_appts)
    else:
        for spec, spec_appts in new_by_spec.items():
            spec_info = SPECIALIST_INFO.get(spec, {})
            spec_phone = spec_info.get('phone_norm', '')
            spec_name = spec_info.get('short_name', spec)
            tg_id = _get_tg_id(spec_phone)
            if not tg_id:
                failed += len(spec_appts)
                continue
            # Build one grouped message
            lines = ['📋 {} нових записів:'.format(len(spec_appts)), '']
            for a in sorted(spec_appts, key=lambda x: (x.get('date',''), x.get('time',''))):
                lines.append('{} о {} — {} ({})'.format(
                    a.get('date',''), (a.get('time','') or '?')[:5],
                    a.get('client_name',''), a.get('procedure_name','')))
            ok = _send_tg(tg_id, '\n'.join(lines))
            if ok:
                for a in spec_appts:
                    _log(spec_phone, 'spec_new', a.get('id',''), 'tg', 'sent', '')
                sent += len(spec_appts)
                logger.info('  {} — {} нових записів відправлено одним повідомленням'.format(spec, len(spec_appts)))
            else:
                failed += len(spec_appts)

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
    tomorrow = (kyiv_now().date() + timedelta(days=1)).strftime('%Y-%m-%d')
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
        # Skip per-specialist messages for those with spec_new_appt=OFF
        # (they still get admin digest if they're the admin)
        _spec_settings = {}
        try:
            _bc = _db()
            for _br in _bc.execute("SELECT specialist, enabled FROM notification_settings WHERE type='spec_new_appt'").fetchall():
                _spec_settings[_br['specialist']] = bool(_br['enabled'])
            _bc.close()
        except Exception:
            pass
        _spec_settings.setdefault('victoria', False)
        _spec_settings.setdefault('anastasia', True)
        skip_spec_msg = [s for s, en in _spec_settings.items() if not en]
        from notifier import send_tomorrow_briefing
        results = send_tomorrow_briefing(by_spec, skip_specialist_msg=skip_spec_msg)
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
        override_date = None
        for i, arg in enumerate(sys.argv):
            if arg == '--date' and i + 1 < len(sys.argv):
                override_date = sys.argv[i + 1]
        all_flags = ('--reminder', '--feedback', '--specialist', '--tomorrow')
        no_flags = not any(f in sys.argv for f in all_flags)
        do_rem   = '--reminder'   in sys.argv or no_flags
        do_fb    = '--feedback'   in sys.argv or no_flags
        do_spec  = '--specialist' in sys.argv or no_flags
        do_tmrw  = '--tomorrow'   in sys.argv or no_flags

        if dry_run:
            logger.info('*** DRY-RUN MODE — відправки не буде ***')
        if override_date:
            logger.info('*** OVERRIDE DATE: {} ***'.format(override_date))

        if do_rem:
            run_reminder(dry_run=dry_run)

        if do_fb:
            run_feedback(dry_run=dry_run, override_date=override_date)

        if do_spec:
            run_specialist_notifications(dry_run=dry_run)

        if do_tmrw:
            run_tomorrow_briefing(dry_run=dry_run)
    finally:
        _release_lock()
