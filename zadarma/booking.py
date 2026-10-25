#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Спільне ядро створення записів.

Один шлях для всіх каналів: сторінка `/booking`, екран у PWA, адмінський
календар. Два route-и редагування вже розійшлися в протилежні боки
(`admin_cal_update` пише локально першим і синхронізує WLaunch у fire-and-forget
треді, `admin_cal_update_wl` — навпаки), і це рівно те, що станеться з
каналами запису, якщо логіку дублювати.

Порядок непорушний: **спершу WLaunch, потім локальне дзеркало.** WLaunch веде
розклад лікаря, і запис, якого там немає, не існує. Якщо локальна вставка
впаде після успішного WLaunch — запис у WLaunch скасовується, інакше лишиться
сирота, якої ніхто не чекає.

Тривалість береться з каталогу WLaunch і ніколи з запиту: у прайсі вона
фіктивна (60 для всіх 56 позицій), а клієнт не має права її задавати.
Спеціаліст так само: де він один, вибір клієнта ігнорується.
"""

import sys
import re
import sqlite3
import logging

sys.path.insert(0, '/home/gomoncli/zadarma')

logger = logging.getLogger('booking')

DB_PATH = '/home/gomoncli/zadarma/users.db'

_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_TIME_RE = re.compile(r'^\d{2}:\d{2}$')


class BookingError(Exception):
    """Відмова, яку клієнт може зрозуміти й виправити."""

    def __init__(self, code, message, detail=None):
        super(BookingError, self).__init__(message)
        self.code = code
        self.message = message
        self.detail = detail      # сира відповідь WLaunch, для адмінських повідомлень


# ── Канонічні примітиви (pwa_api імпортує саме їх) ────────────────────────────

def time_to_min(t):
    """'HH:MM' -> хвилини від півночі."""
    try:
        h, m = map(int, (t or '00:00').split(':'))
        return h * 60 + m
    except Exception:
        return 0


def check_overlap(conn, specialist, date, new_start, new_end,
                  exclude_id=None, exclude_wl_id=None):
    """True, якщо у спеціаліста вже є перетин на цю дату.

    Дивиться обидва сховища — `manual_appointments` і WLaunch-записи в
    `clients.services_json` — плюс перерви. Пропустити одне зі сховищ означає
    дозволити подвійне бронювання.
    """
    import json

    q = ("SELECT time, duration FROM manual_appointments WHERE specialist=? AND date=? "
         "AND status NOT IN ('CANCELLED', 'NO_SHOW')")
    params = [specialist, date]
    if exclude_id is not None:
        q += ' AND id != ?'
        params.append(exclude_id)
    for row in conn.execute(q, params).fetchall():
        s = time_to_min(row[0] or '00:00')
        e = s + (row[1] or 60)
        if new_start < e and s < new_end:
            return True

    for row in conn.execute(
            'SELECT services_json FROM clients WHERE services_json LIKE ? AND services_json LIKE ?',
            ('%' + date + '%', '%' + specialist + '%')).fetchall():
        try:
            items = json.loads(row[0] or '[]')
        except Exception:
            items = []
        for it in items:
            if it.get('date') != date or it.get('specialist') != specialist:
                continue
            if exclude_wl_id and it.get('appt_id') == exclude_wl_id:
                continue
            if (it.get('status') or '').upper() in ('CANCELLED', 'NO_SHOW'):
                continue
            hour = it.get('hour')
            if hour is None:
                continue
            s = hour * 60 + (it.get('minute') or 0)
            e = s + (it.get('duration_min') or 60)
            if new_start < e and s < new_end:
                return True

    for row in conn.execute(
            'SELECT time_from, time_to FROM specialist_breaks WHERE specialist=? AND date=?',
            (specialist, date)).fetchall():
        if new_start < time_to_min(row[1]) and time_to_min(row[0]) < new_end:
            return True
    return False


def cancel_wlaunch_appt(appt_id, branch_id=None):
    """Скасувати запис у WLaunch. Returns (ok, error)."""
    import requests
    from config import WLAUNCH_API_KEY, COMPANY_ID, WLAUNCH_API_URL

    if not branch_id:
        from wlaunch_api import get_branch_id
        branch_id = get_branch_id()
    if not branch_id:
        return False, 'no_branch'

    url = '{}/company/{}/branch/{}/appointment/{}'.format(
        WLAUNCH_API_URL, COMPANY_ID, branch_id, appt_id)
    try:
        resp = requests.post(
            url,
            headers={'Authorization': 'Bearer ' + WLAUNCH_API_KEY,
                     'Accept': 'application/json',
                     'Content-Type': 'application/json'},
            json={'appointment': {'id': appt_id, 'status': 'CANCELLED'}},
            timeout=10)
        resp.raise_for_status()
        return True, None
    except Exception as e:
        return False, str(e)[:200]


def audit_appointment(appt_id, phone, client_name, procedure, specialist,
                      date, time_str, status, prev_status, action, source,
                      db_path=None):
    """Слід у appointment_audit_log. Fire-and-forget."""
    try:
        conn = sqlite3.connect(db_path or DB_PATH, timeout=5)
        conn.execute(
            'INSERT INTO appointment_audit_log (appt_id, phone, client_name, procedure_name,'
            ' specialist, date, time, status, prev_status, action, source, created_at)'
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
            (str(appt_id), phone or '', client_name or '', procedure or '',
             specialist or '', date or '', time_str or '', status or '',
             prev_status or '', action, source))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _rollback_wlaunch(wl_id, why):
    """Скасувати щойно створений запис у WLaunch. Якщо не вдалось — кричати."""
    ok, err = cancel_wlaunch_appt(wl_id)
    if ok:
        logger.warning('WLaunch rollback ({}): {}'.format(why, wl_id))
        return
    logger.error('WLaunch rollback FAILED for {}: {}'.format(wl_id, err))
    try:
        from notifier import _send_tg, _get_tg_id
        _send_tg(_get_tg_id('380733103110'),
                 'WLaunch orphan: не вдалось відкотити {} ({}). Потрібне ручне прибирання.'
                 .format(wl_id, why))
    except Exception:
        pass


# ── Ядро ──────────────────────────────────────────────────────────────────────

def resolve_service(service_name, db_path=None):
    """Послуга з каталогу або BookingError."""
    from wl_catalog import get_bookable_services
    for s in get_bookable_services(db_path=db_path):
        if s['name'] == service_name:
            return s
    raise BookingError('service_unavailable',
                       'Послуга недоступна для онлайн-запису')


def resolve_specialist(service, requested):
    """Хто виконуватиме. Де спеціаліст один — вибір клієнта ігнорується."""
    allowed = service['specialists']
    if not service.get('specialist_choice'):
        return allowed[0]
    if not requested:
        raise BookingError('specialist_required',
                           'Для цієї послуги треба обрати спеціаліста')
    if requested not in allowed:
        raise BookingError('specialist_not_allowed',
                           'Обраний спеціаліст не виконує цю послугу')
    return requested


def _verify_slot(service, specialist, date, time_str, db_path=None):
    """Слот має бути вільним зараз, а не коли клієнт відкривав сторінку."""
    from booking_slots import get_free_slots
    days = get_free_slots(service['name'], date, date,
                          specialist=specialist, db_path=db_path)
    day = days[0] if days else None
    if not day or not day['open']:
        raise BookingError('schedule_closed',
                           'На цей день запис ще не відкрито')
    if time_str not in day['specialists'].get(specialist, []):
        raise BookingError('slot_taken',
                           'Цей час щойно зайняли. Оберіть інший')


def place_appointment(phone, client_name, procedure_name, specialist, date,
                      time_str, duration, notes='', source='web',
                      created_by=None, db_path=None):
    """Інваріанти запису, спільні для всіх каналів. Політики тут немає.

    Спершу WLaunch, потім локальне дзеркало. Локальна помилка після успішного
    WLaunch відкочує WLaunch — інакше лишиться запис, якого ніхто не чекає.

    Викликачі самі вирішують, що можна: клієнтові послугу й тривалість диктує
    каталог, адміну — ні, він записує будь-кого і будь-коли.
    """
    from wlaunch_api import create_wlaunch_appointment
    try:
        wl_id, wl_err = create_wlaunch_appointment(
            phone, client_name, procedure_name, specialist, date, time_str, duration)
    except Exception as e:
        logger.error('WLaunch create exception: {}'.format(e))
        raise BookingError('wlaunch_unavailable',
                           'Сервіс запису тимчасово недоступний. Спробуйте пізніше',
                           detail=str(e)[:200])
    if wl_err or not wl_id:
        logger.error('WLaunch create refused: {}'.format(wl_err))
        raise BookingError('wlaunch_rejected',
                           'Не вдалося підтвердити час. Оберіть інший',
                           detail=wl_err)

    start = time_to_min(time_str)
    # Маркер wl: у нотатках — запасний шлях для місць, які шукають WLaunch ID там
    wl_note = 'wl:{}'.format(wl_id)
    full_notes = ((notes or '').strip() + ' ' + wl_note).strip()

    conn = sqlite3.connect(db_path or DB_PATH, timeout=5)
    try:
        conn.execute('BEGIN IMMEDIATE')
        if check_overlap(conn, specialist, date, start, start + duration):
            conn.rollback()
            _rollback_wlaunch(wl_id, 'local overlap')
            raise BookingError('conflict', 'Цей час щойно зайняли. Оберіть інший')
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO manual_appointments'
            ' (client_phone, client_name, procedure_name, specialist, date, time,'
            '  duration, notes, wlaunch_id, created_by)'
            ' VALUES (?,?,?,?,?,?,?,?,?,?)',
            (phone, client_name, procedure_name, specialist, date, time_str,
             duration, full_notes, wl_id, created_by or source))
        local_id = cur.lastrowid
        conn.commit()
    except BookingError:
        raise
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        _rollback_wlaunch(wl_id, 'db error')
        logger.error('local mirror failed: {}'.format(e))
        raise BookingError('db_error', 'Не вдалося зберегти запис. Спробуйте пізніше')
    finally:
        conn.close()

    audit_appointment(wl_id, phone, client_name, procedure_name, specialist,
                      date, time_str, 'CONFIRMED', None, 'created', source,
                      db_path=db_path)
    logger.info('appointment placed: {} {} {} {} {} (wl={})'.format(
        source, phone, procedure_name, date, time_str, wl_id))
    return {'wlaunch_id': wl_id, 'local_id': local_id, 'service': procedure_name,
            'specialist': specialist, 'date': date, 'time': time_str,
            'duration_min': duration}


def create_booking(phone, client_name, service_name, date, time_str,
                   specialist=None, source='web', notes='', db_path=None):
    """Створити запис клієнта. WLaunch-first, з відкотом.

    Повертає {'wlaunch_id', 'local_id', 'service', 'specialist', 'date',
              'time', 'duration_min'}.
    """
    from tz_utils import kyiv_now
    from user_db import normalize_phone

    phone = normalize_phone(phone or '')
    if not phone:
        raise BookingError('phone_required', 'Потрібен номер телефону')
    client_name = ' '.join((client_name or '').split())
    if not client_name:
        raise BookingError('name_required', "Потрібно вказати ім'я та прізвище")
    if len(client_name.split()) < 2:
        # create_wlaunch_appointment ділить рядок на first/last, і без прізвища
        # у картці WLaunch лишилось би порожнє поле
        raise BookingError('surname_required', 'Вкажіть імʼя та прізвище')
    if not _DATE_RE.match(date or ''):
        raise BookingError('invalid_date', 'Невірна дата')
    if not _TIME_RE.match(time_str or ''):
        raise BookingError('invalid_time', 'Невірний час')

    now = kyiv_now()
    if date < now.strftime('%Y-%m-%d'):
        raise BookingError('past_date', 'Ця дата вже минула')

    service = resolve_service(service_name, db_path=db_path)
    specialist = resolve_specialist(service, specialist)
    duration = service['duration_min']          # ніколи не з запиту

    _verify_slot(service, specialist, date, time_str, db_path=db_path)

    try:
        return place_appointment(
            phone, client_name, service['name'], specialist, date, time_str,
            duration, notes=notes, source='booking:' + source, db_path=db_path)
    except BookingError as e:
        if e.code == 'conflict':
            raise BookingError('slot_taken', 'Цей час щойно зайняли. Оберіть інший')
        raise
