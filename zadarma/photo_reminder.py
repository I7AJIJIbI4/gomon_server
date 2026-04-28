#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Photo reminder — cron script for Google Drive photo folders.

Usage:
  python3 photo_reminder.py --create    # 21:30 — create folders + TG to specialists
  python3 photo_reminder.py --check     # 09:00 next day — check uploads, TG to admin
"""

import sys
import re
import json
import sqlite3
import logging
import logging.handlers
import argparse
from datetime import datetime

sys.path.insert(0, '/home/gomoncli/zadarma')
from config import TELEGRAM_TOKEN, ADMIN_USER_ID

DB_PATH = '/home/gomoncli/zadarma/users.db'
LOG_FILE = '/home/gomoncli/zadarma/photo_reminder.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=2*1024*1024, backupCount=2),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

SPEC_PHONES = {
    'victoria': '380996093860',
    'anastasia': '380685129121',
}
SPEC_NAMES = {
    'victoria': 'Вікторія',
    'anastasia': 'Анастасія',
}


PRICES_PATH = '/home/gomoncli/private_data/prices.json'

# Mapping: generic WLaunch procedure name → prices.json category names that contain drugs
# WLaunch generic name → prices.json category (for drug button selection)
PROCEDURE_TO_CATEGORIES = {
    'Ботулінотерапія': ['Ботулінотерапія Neuronox / Nabota', 'Ботулінотерапія Xeomin'],
    'Контурна пластика губ': ['Контурна пластика губ'],
    'Контурна пластика обличчя': ['Контурна пластика обличчя'],
    'Біорепарація шкіри': ['Біорепарація шкіри'],
    'Біоревіталізація шкіри': ['Біоревіталізація шкіри'],
    'Мезотерапія': ['Мезотерапія'],
    'Ліполітики (обличчя, 4 мл)': ['_ліполітики'],
    'Ліполітики (тіло, 10 мл)': ['_ліполітики'],
    'Гіалуронідаза (розчинення філера)': ['_гіалуронідаза'],
}
# Exact set of WLaunch service names that need doctor price confirmation (drug buttons)
NEEDS_DRUG_SELECTION = set(PROCEDURE_TO_CATEGORIES.keys())


def _get_drugs_for_procedure(procedure_name):
    """Get list of {name, price} drugs from prices.json for a generic procedure."""
    cats = PROCEDURE_TO_CATEGORIES.get(procedure_name)
    if not cats:
        return []
    try:
        with open(PRICES_PATH, 'r') as f:
            prices = json.load(f)
    except Exception:
        return []
    drugs = []
    for cat in prices:
        cat_name = cat.get('cat', '')
        # Virtual categories: _ліполітики, _гіалуронідаза — filter by keyword in item name
        for target_cat in cats:
            if target_cat.startswith('_'):
                keyword = target_cat[1:]
                if cat_name == 'Ферментотерапія':
                    for item in cat.get('items', []):
                        name = item.get('name', '')
                        if keyword.lower() not in name.lower():
                            continue
                        price_str = item.get('price', '')
                        if 'безкоштовно' in price_str.lower():
                            continue
                        p = re.search(r'\d+', str(price_str).replace(' ', ''))
                        price_val = int(p.group()) if p else 0
                        if price_val > 0:
                            drugs.append({'name': name, 'price': price_val})
            elif cat_name == target_cat:
                for item in cat.get('items', []):
                    name = item.get('name', '')
                    price_str = item.get('price', '')
                    if not name or 'безкоштовно' in price_str.lower():
                        continue
                    p = re.search(r'\d+', str(price_str).replace(' ', ''))
                    price_val = int(p.group()) if p else 0
                    if price_val > 0:
                        drugs.append({'name': name, 'price': price_val})
    return drugs


def _send_drug_buttons(tg_id, appts, date_str):
    """Send inline keyboard with drug options for each appointment that needs cashback confirmation."""
    import requests as _req
    for a in appts:
        procedure = a.get('procedure', '')
        drugs = _get_drugs_for_procedure(procedure)
        if not drugs:
            continue  # No drugs to choose — fixed price procedure, auto-accrue

        client_phone = a.get('client_phone', '')
        client_name = a.get('client_name', '')
        if not client_phone:
            continue

        # Build inline keyboard — 2 buttons per row
        # callback_data max 64 bytes (UTF-8). Use short phone (last 10 digits) + short date (MMDD)
        ph_short = client_phone[-10:] if len(client_phone) > 10 else client_phone
        dt_short = date_str[5:].replace('-', '')  # "2026-04-20" → "0420"
        rows = []
        for i in range(0, len(drugs), 2):
            row = []
            for d in drugs[i:i+2]:
                # cb|phone10|MMDD|price — drug name NOT in callback, resolved from price+procedure
                cb_data = 'cb|{}|{}|{}'.format(ph_short, dt_short, d['price'])
                row.append({'text': '{} ₴{}'.format(d['name'][:25], d['price']), 'callback_data': cb_data})
            rows.append(row)

        # Add "Enter custom price" button
        cb_custom = 'cc|{}|{}'.format(ph_short, dt_short)
        rows.append([{'text': '✏️ Ввести ціну вручну', 'callback_data': cb_custom}])

        text = '💰 Кешбек для {} ({})\nОберіть препарат або введіть ціну:'.format(client_name, procedure)

        try:
            _req.post(
                'https://api.telegram.org/bot{}/sendMessage'.format(TELEGRAM_TOKEN),
                json={
                    'chat_id': tg_id,
                    'text': text,
                    'reply_markup': {'inline_keyboard': rows}
                }, timeout=10)
        except Exception as e:
            logger.error('Drug buttons send error: {}'.format(e))


def _get_today_str():
    """Today's date in Kyiv timezone."""
    try:
        from tz_utils import kyiv_now
        return kyiv_now().strftime('%Y-%m-%d')
    except Exception:
        return datetime.now().strftime('%Y-%m-%d')


def _get_todays_appointments(date_str):
    """Get all non-cancelled appointments for a date (manual + WLaunch)."""
    appointments = []
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row

    # Manual appointments
    for r in conn.execute(
        "SELECT id, client_name, client_phone, procedure_name, specialist, time, drive_folder_url "
        "FROM manual_appointments WHERE date=? AND status != 'CANCELLED'",
        (date_str,)).fetchall():
        appointments.append({
            'id': r['id'],
            'client_name': r['client_name'] or r['client_phone'] or '—',
            'client_phone': r['client_phone'] or '',
            'procedure': r['procedure_name'],
            'specialist': r['specialist'],
            'time': r['time'] or '',
            'drive_url': r['drive_folder_url'],
            'source': 'manual',
        })

    # WLaunch appointments from services_json
    for r in conn.execute(
        "SELECT first_name, last_name, phone, services_json FROM clients WHERE services_json LIKE ?",
        ('%' + date_str + '%',)).fetchall():
        try:
            services = json.loads(r['services_json'] or '[]')
        except Exception:
            services = []
        for s in services:
            if s.get('date') != date_str:
                continue
            if (s.get('status') or '').upper() == 'CANCELLED':
                continue
            name = ((r['first_name'] or '') + ' ' + (r['last_name'] or '')).strip() or r['phone']
            appointments.append({
                'id': 'wl_' + (s.get('appt_id') or ''),
                'client_name': name,
                'client_phone': r['phone'] or '',
                'procedure': s.get('service', ''),
                'specialist': s.get('specialist', ''),
                'time': '{:02d}:00'.format(s['hour']) if s.get('hour') is not None else '',
                'drive_url': None,
                'source': 'wlaunch',
            })

    conn.close()
    appointments.sort(key=lambda x: x.get('time', ''))
    return appointments


def create_folders_and_notify(date_str=None):
    """Create Drive folders for today's appointments and TG notify specialists."""
    if not date_str:
        date_str = _get_today_str()

    logger.info('Creating photo folders for {}'.format(date_str))
    appointments = _get_todays_appointments(date_str)
    if not appointments:
        logger.info('No appointments for {}'.format(date_str))
        return

    from gdrive import create_visit_folder

    # Create folders and group by specialist
    by_spec = {}
    created = 0
    for a in appointments:
        spec = a['specialist'] or 'other'
        if spec not in by_spec:
            by_spec[spec] = []

        # Create Drive folder if not already created
        if not a['drive_url']:
            try:
                visit_url, client_url = create_visit_folder(
                    a['client_name'], date_str, a['procedure'])
                a['drive_url'] = visit_url
                created += 1

                # Save URL for manual appointments
                if a['source'] == 'manual':
                    conn = sqlite3.connect(DB_PATH, timeout=5)
                    conn.execute('UPDATE manual_appointments SET drive_folder_url=? WHERE id=?',
                                 (visit_url, a['id']))
                    conn.commit()
                    conn.close()
            except Exception as e:
                logger.error('Drive folder error for {}: {}'.format(a['client_name'], e))
                a['drive_url'] = None

        by_spec[spec].append(a)

        # Save to photo_tasks for tracking
        if a['drive_url']:
            try:
                _pt_conn = sqlite3.connect(DB_PATH, timeout=5)
                import re as _re_pt
                _fid_m = _re_pt.search(r'/folders/([a-zA-Z0-9_-]+)', a['drive_url'])
                _fid = _fid_m.group(1) if _fid_m else ''
                _needs = a['procedure'] in NEEDS_DRUG_SELECTION
                _pt_conn.execute(
                    "INSERT OR IGNORE INTO photo_tasks (appt_id, client_phone, client_name, procedure_name, specialist, appt_date, appt_time, drive_folder_url, drive_folder_id, cashback_status) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (a.get('id',''), a.get('client_phone',''), a['client_name'], a['procedure'], spec,
                     date_str, a.get('time',''), a['drive_url'], _fid,
                     'needs_drug' if _needs else 'auto'))
                _pt_conn.commit()
                _pt_conn.close()
            except Exception as _pt_e:
                logger.warning('photo_tasks insert error: {}'.format(_pt_e))

    logger.info('Created {} new folders for {} appointments'.format(created, len(appointments)))

    # Send TG to each specialist
    from notifier import _get_tg_id, _send_tg

    for spec, appts in by_spec.items():
        if spec == 'other':
            continue
        phone = SPEC_PHONES.get(spec)
        if not phone:
            continue
        tg_id = _get_tg_id(phone)
        if not tg_id:
            continue

        spec_name = SPEC_NAMES.get(spec, spec)
        lines = ['{}, сьогодні у вас було {} записів.'.format(spec_name, len(appts)),
                 'Завантажте фото до/після:',
                 '']
        for a in appts:
            line = '{} — {} ({})'.format(
                a['time'][:5] if a['time'] else '?',
                a['client_name'],
                a['procedure'])
            if a['drive_url']:
                line += '\n   {}'.format(a['drive_url'])
            else:
                line += '\n   (папка не створена)'
            lines.append(line)

        text = '\n'.join(lines)
        try:
            _send_tg(tg_id, text)
            logger.info('TG sent to {} ({} appts)'.format(spec, len(appts)))
        except Exception as e:
            logger.error('TG error for {}: {}'.format(spec, e))

        # Send cashback drug selection buttons for each appointment
        try:
            if not date_str:
                from tz_utils import kyiv_now as _kn
                date_str = _kn().strftime('%Y-%m-%d')
            _send_drug_buttons(tg_id, appts, date_str)
        except Exception as e:
            logger.error('Drug buttons error for {}: {}'.format(spec, e))


def check_uploads(date_str=None):
    """Check if photos were uploaded to today's folders. TG admin about uploads."""
    if not date_str:
        date_str = _get_today_str()

    logger.info('Checking photo uploads for {}'.format(date_str))
    appointments = _get_todays_appointments(date_str)

    from gdrive import count_files_in_folder
    import re

    uploaded = []
    for a in appointments:
        url = a.get('drive_url')
        if not url:
            continue
        # Extract folder ID from URL
        m = re.search(r'/folders/([a-zA-Z0-9_-]+)', url)
        if not m:
            continue
        folder_id = m.group(1)
        count = count_files_in_folder(folder_id)
        if count > 0:
            uploaded.append({
                'client': a['client_name'],
                'procedure': a['procedure'],
                'specialist': a['specialist'],
                'count': count,
                'url': url,
            })

    # TG to admin — both uploaded and missing
    import requests as _req
    total_appts = len([a for a in appointments if a.get('drive_url')])

    if uploaded:
        lines = ['📷 Фото за {} ({}/{} завантажено):'.format(date_str, len(uploaded), total_appts), '']
        for u in uploaded:
            spec_name = SPEC_NAMES.get(u['specialist'], '')
            lines.append('✅ {} — {} ({}) — {} фото'.format(
                spec_name, u['client'], u['procedure'], u['count']))
            lines.append('   {}'.format(u['url']))
    else:
        lines = ['📷 Фото за {} — не завантажено (0/{})'.format(date_str, total_appts)]

    # List missing
    uploaded_clients = {u['client'] for u in uploaded}
    missing = [a for a in appointments if a.get('drive_url') and a['client_name'] not in uploaded_clients]
    if missing:
        lines.append('')
        lines.append('❌ Без фото:')
        for a in missing:
            spec_name = SPEC_NAMES.get(a['specialist'], '')
            lines.append('   {} — {} ({})'.format(spec_name, a['client_name'], a['procedure']))

    text = '\n'.join(lines)
    try:
        _req.post('https://api.telegram.org/bot{}/sendMessage'.format(TELEGRAM_TOKEN),
                   json={'chat_id': ADMIN_USER_ID, 'text': text}, timeout=10)
        logger.info('Admin notified: {}/{} with photos'.format(len(uploaded), total_appts))
    except Exception as e:
        logger.error('Admin TG error: {}'.format(e))


def check_pending_photos():
    """Re-remind specialists about missing photos older than 2 days but within 7 days."""
    from tz_utils import kyiv_now
    from datetime import timedelta
    now = kyiv_now()
    cutoff_old = (now - timedelta(days=7)).strftime('%Y-%m-%d')
    cutoff_recent = (now - timedelta(days=2)).strftime('%Y-%m-%d')

    conn = sqlite3.connect(DB_PATH, timeout=5)
    # Find photo_tasks without photos, 2-7 days old
    rows = conn.execute(
        "SELECT id, client_phone, client_name, procedure_name, specialist, appt_date, appt_time, drive_folder_url, drive_folder_id "
        "FROM photo_tasks WHERE photos_uploaded=0 AND appt_date >= ? AND appt_date <= ? AND drive_folder_id != ''",
        (cutoff_old, cutoff_recent)).fetchall()
    conn.close()

    if not rows:
        logger.info('check_pending_photos: no pending photos')
        return

    # Re-check Drive and update
    from gdrive import count_files_in_folder
    from notifier import _get_tg_id, _send_tg
    from tz_utils import kyiv_now as _kn

    by_spec = {}
    updated = 0
    for r in rows:
        rid, phone, name, proc, spec, date, time_str, url, fid = r
        try:
            count = count_files_in_folder(fid)
        except Exception:
            count = 0
        conn2 = sqlite3.connect(DB_PATH, timeout=5)
        conn2.execute("UPDATE photo_tasks SET photos_uploaded=?, photos_checked_at=datetime('now') WHERE id=?",
                       (count, rid))
        conn2.commit()
        conn2.close()
        if count > 0:
            updated += 1
        else:
            if spec not in by_spec:
                by_spec[spec] = []
            by_spec[spec].append({'name': name, 'proc': proc, 'date': date, 'time': time_str, 'url': url})

    # Send reminders per specialist
    for spec, missing in by_spec.items():
        spec_phone = SPEC_PHONES.get(spec)
        if not spec_phone:
            continue
        tg_id = _get_tg_id(spec_phone)
        if not tg_id:
            continue
        spec_name = SPEC_NAMES.get(spec, spec)
        lines = ['⚠️ {}, є незавантажені фото ({} шт):'.format(spec_name, len(missing)), '']
        for m in missing:
            lines.append('{} {} — {} ({})'.format(m['date'], m['time'][:5] if m['time'] else '', m['name'], m['proc']))
            if m['url']:
                lines.append('   {}'.format(m['url']))
        try:
            _send_tg(tg_id, '\n'.join(lines))
        except Exception as e:
            logger.error('Pending photo TG error: {}'.format(e))

    logger.info('check_pending_photos: {} total, {} now have photos, {} still missing'.format(
        len(rows), updated, sum(len(v) for v in by_spec.values())))


def check_pending_cashback_reminders():
    """Send post_visit (cashback + review) for confirmed drug-selection cashback.
    Sends next day after doctor confirmed, at the client's original visit time.
    Uses same notifier.send_post_visit as fixed-price procedures."""
    from tz_utils import kyiv_now
    now = kyiv_now()
    today = now.strftime('%Y-%m-%d')
    current_time = now.strftime('%H:%M')

    conn = sqlite3.connect(DB_PATH, timeout=5)
    # Send when: confirmed AND current time >= visit time AND (confirmed before visit time today OR confirmed yesterday+)
    # Simply: confirmed AND now >= appt_time AND confirmed_at < today's appt_time (or confirmed yesterday)
    rows = conn.execute(
        "SELECT id, client_phone, client_name, procedure_name, cashback_drug, cashback_price, appt_date, appt_time, specialist, cashback_confirmed_at "
        "FROM photo_tasks "
        "WHERE cashback_status='confirmed' AND cashback_notified_at IS NULL "
        "AND (appt_time IS NULL OR appt_time <= ?)",
        (current_time,)).fetchall()
    conn.close()
    # Filter: only send if confirmed at least 1 hour before current time (give doctor time, avoid instant send)
    filtered = []
    for r in rows:
        confirmed_at = r[9] or ''
        if not confirmed_at:
            continue
        # Confirmed more than 1 hour ago → send
        from datetime import datetime as _dt
        try:
            conf_dt = _dt.strptime(confirmed_at, '%Y-%m-%d %H:%M:%S')
            if (now - conf_dt).total_seconds() >= 3600:
                filtered.append(r)
        except Exception:
            filtered.append(r)
    rows = filtered

    if not rows:
        return

    for r in rows:
        rid, phone, name, proc, drug, price, date, time_str, specialist = r
        if not phone or not price:
            continue
        # Accrue cashback first (INSERT OR IGNORE — dedup by UNIQUE)
        amount = round(price * 0.03, 2)
        try:
            conn2 = sqlite3.connect(DB_PATH, timeout=5)
            conn2.execute(
                "INSERT OR IGNORE INTO cashback (phone, amount, procedure_name, procedure_price, appt_date) VALUES (?,?,?,?,?)",
                (phone, amount, drug or proc, price, date))
            conn2.commit()
            conn2.close()
        except Exception as _ce:
            logger.warning('cashback accrue error: {}'.format(_ce))

        # Send post_visit via notifier (same as fixed-price: thank + review + cashback info)
        try:
            from notifier import send_post_visit
            appt = {
                'client_phone': phone,
                'client_name': name or '',
                'procedure_name': drug or proc,
                'specialist': specialist or '',
                'date': date,
                'time': time_str or '',
                'duration_min': 60,
            }
            send_post_visit(appt)
        except Exception as _nf:
            logger.warning('post_visit for confirmed cashback error: {}'.format(_nf))

        # Mark notified
        try:
            conn3 = sqlite3.connect(DB_PATH, timeout=5)
            conn3.execute("UPDATE photo_tasks SET cashback_status='notified', cashback_notified_at=datetime('now') WHERE id=?", (rid,))
            conn3.commit()
            conn3.close()
            logger.info('Post-visit (drug cashback) sent: {} {} ₴{:.0f} cb={:.0f}'.format(phone, drug or proc, price, amount))
        except Exception:
            pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--create', action='store_true', help='Create folders + notify specialists')
    parser.add_argument('--check', action='store_true', help='Check uploads + notify admin')
    parser.add_argument('--check-pending', action='store_true', help='Re-remind about missing photos (2-7 days old)')
    parser.add_argument('--cashback-notify', action='store_true', help='Notify clients about confirmed cashback')
    parser.add_argument('--date', type=str, help='Override date (YYYY-MM-DD)')
    args = parser.parse_args()

    target_date = args.date or None

    if args.create:
        create_folders_and_notify(target_date)
    elif args.check:
        check_uploads(target_date)
    elif args.check_pending:
        check_pending_photos()
    elif args.cashback_notify:
        check_pending_cashback_reminders()
    else:
        print('Usage: --create | --check | --check-pending | --cashback-notify')
