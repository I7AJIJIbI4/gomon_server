#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Photo reminder — cron script for Google Drive photo folders.

Usage:
  python3 photo_reminder.py --create    # 21:30 — create folders + TG to specialists
  python3 photo_reminder.py --check     # 09:00 next day — check uploads, TG to admin
"""

import sys
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

    if not uploaded:
        logger.info('No photos uploaded for {}'.format(date_str))
        return

    # TG to admin
    import requests as _req
    lines = ['Фото за {}:'.format(date_str), '']
    for u in uploaded:
        spec_icon = SPEC_NAMES.get(u['specialist'], '')
        lines.append('{} — {} ({}) — {} фото'.format(
            spec_icon, u['client'], u['procedure'], u['count']))
        lines.append('   {}'.format(u['url']))

    text = '\n'.join(lines)
    try:
        _req.post('https://api.telegram.org/bot{}/sendMessage'.format(TELEGRAM_TOKEN),
                   json={'chat_id': ADMIN_USER_ID, 'text': text}, timeout=10)
        logger.info('Admin notified: {} appointments with photos'.format(len(uploaded)))
    except Exception as e:
        logger.error('Admin TG error: {}'.format(e))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--create', action='store_true', help='Create folders + notify specialists')
    parser.add_argument('--check', action='store_true', help='Check uploads + notify admin')
    parser.add_argument('--date', type=str, help='Override date (YYYY-MM-DD)')
    args = parser.parse_args()

    target_date = args.date or None

    if args.create:
        create_folders_and_notify(target_date)
    elif args.check:
        check_uploads(target_date)
    else:
        print('Usage: --create or --check')
