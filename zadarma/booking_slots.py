#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вільні слоти для онлайн-запису.

Обидва джерела — живі з WLaunch, і це навмисно. Розклад лікаря ведеться там,
а записи приходять і з віджета, і з адмінки, і від самого лікаря. Локальна копія
оновлюється раз на годину (`sync_appointments.py`), тож слот, зайнятий десять
хвилин тому, у ній ще вільний. Показати такий слот — означає провести клієнта
через весь вибір і відмовити на останньому кроці.

Горизонт запису дорівнює тому, наскільки наперед лікар заповнила розклад у
WLaunch. День без робочих фреймів повертається як `open=False` — це «розклад ще
не відкрито», а не «все зайнято», і UI має казати різні речі.

Usage:
  python3 booking_slots.py "Біорепарація шкіри" 2026-10-26 2026-11-02
"""

import sys
import logging
from datetime import datetime, timedelta

sys.path.insert(0, '/home/gomoncli/zadarma')

logger = logging.getLogger('booking_slots')

#: Крок сітки стартів, хв.
SLOT_STEP_MIN = 15

#: Мінімальний запас до початку процедури, хв. Запис «через п'ять хвилин»
#: клієнт фізично не встигне, та й лікар не побачить.
MIN_LEAD_MIN = 60

#: Скільки днів максимум віддаємо за один запит.
MAX_RANGE_DAYS = 60

_CANCELLED = {'CANCELLED', 'NO_SHOW', 'DELETED'}


def _dates(date_from, date_to):
    d = datetime.strptime(date_from, '%Y-%m-%d').date()
    end = datetime.strptime(date_to, '%Y-%m-%d').date()
    if (end - d).days >= MAX_RANGE_DAYS:
        end = d + timedelta(days=MAX_RANGE_DAYS - 1)
    while d <= end:
        yield d.strftime('%Y-%m-%d')
        d += timedelta(days=1)


# ── Зайнятість: живцем з WLaunch ──────────────────────────────────────────────

def fetch_busy(date_from, date_to, branch_id=None):
    """{(дата, спеціаліст): [(хв_від, хв_до), ...]} з WLaunch.

    Локальну БД навмисно не чіпаємо — вона відстає до години.
    """
    import requests
    from config import WLAUNCH_API_URL, COMPANY_ID
    from wlaunch_api import (HEADERS, get_branch_id, get_wlaunch_resources,
                             parse_appt_time)

    bid = branch_id or get_branch_id()
    if not bid:
        raise RuntimeError('WLaunch: не вдалося визначити філію')

    res_to_spec = {rid: spec for spec, rid in get_wlaunch_resources(bid).items()}
    url = '{}/company/{}/branch/{}/appointment'.format(WLAUNCH_API_URL, COMPANY_ID, bid)

    busy, page = {}, 0
    while page < 50:
        resp = requests.get(url, headers=HEADERS, timeout=15, params={
            'page': page, 'size': 100, 'sort': 'start_time,asc',
            'start': '{}T00:00:00.000Z'.format(date_from),
            'end': '{}T23:59:59.999Z'.format(date_to),
        })
        resp.raise_for_status()
        data = resp.json()
        items = data.get('content', [])
        if not items:
            break
        for appt in items:
            if (appt.get('status') or '').upper() in _CANCELLED:
                continue
            date_str, hour, minute = parse_appt_time(appt.get('start_time'))
            if hour is None:
                continue
            start = hour * 60 + (minute or 0)
            end = start + max(int((appt.get('duration') or 3600) // 60), 1)
            for spec in _appt_specialists(appt, res_to_spec):
                busy.setdefault((date_str, spec), []).append((start, end))
        page += 1
        if page >= data.get('page', {}).get('total_pages', 1):
            break
    return busy


def _appt_specialists(appt, res_to_spec):
    """Хто зайнятий цим записом. Запис без ресурсу блокує всіх — інакше
    ми б запропонували слот, який WLaunch усе одно відхилить."""
    found = set()
    for srs in (appt.get('service_resource_settings') or []):
        for rid in (srs.get('resources') or []):
            if isinstance(rid, dict):
                rid = rid.get('id')
            if rid in res_to_spec:
                found.add(res_to_spec[rid])
    for r in (appt.get('resources') or []):
        rid = r.get('id') if isinstance(r, dict) else r
        if rid in res_to_spec:
            found.add(res_to_spec[rid])
    return found or set(res_to_spec.values())


# ── Робочі години ─────────────────────────────────────────────────────────────

def open_frames(date_str, specialist, resources=None):
    """Робочі інтервали дня (ON мінус OFF) або [] якщо розклад не відкрито."""
    from wlaunch_api import (WEEKDAY_NAMES, _fetch_schedule_raw,
                             _parse_resource_frames_for_date, _subtract_intervals,
                             get_wlaunch_resources)
    res = resources if resources is not None else get_wlaunch_resources()
    rid = res.get(specialist)
    if not rid:
        return []
    raw = _fetch_schedule_raw(date_str)
    if not raw:
        return []
    block = next((b for b in raw.get('content', []) if b.get('resource_id') == rid), None)
    if not block:
        return []
    weekday = WEEKDAY_NAMES[datetime.strptime(date_str, '%Y-%m-%d').weekday()]
    frames = _parse_resource_frames_for_date(block, date_str, weekday)
    on = [(s, e) for s, e, t in frames if t == 'ON']
    off = [(s, e) for s, e, t in frames if t == 'OFF']
    return _subtract_intervals(on, off)


def _local_breaks(date_str, specialist, db_path=None):
    """Перерви, заведені в нашій адмінці. Вони дзеркаляться у WLaunch як OFF,
    тож це подвійний відніматель — нешкідливий і рятує, якщо дзеркалення впало."""
    import sqlite3
    path = db_path or '/home/gomoncli/zadarma/users.db'
    try:
        conn = sqlite3.connect(path, timeout=5)
    except Exception:
        return []
    try:
        rows = conn.execute(
            'SELECT time_from, time_to FROM specialist_breaks WHERE specialist=? AND date=?',
            (specialist, date_str)).fetchall()
    except Exception:
        return []
    finally:
        conn.close()
    out = []
    for a, b in rows:
        try:
            out.append((int(a[:2]) * 60 + int(a[3:5]), int(b[:2]) * 60 + int(b[3:5])))
        except Exception:
            continue
    return out


# ── Слоти ─────────────────────────────────────────────────────────────────────

def _starts(free, duration_min, earliest_min, step=SLOT_STEP_MIN):
    out = []
    for s, e in free:
        first = max(s, earliest_min)
        if first % step:
            first += step - (first % step)
        t = first
        while t + duration_min <= e:
            out.append(t)
            t += step
    return sorted(set(out))


def _hhmm(m):
    return '{:02d}:{:02d}'.format(m // 60, m % 60)


def get_free_slots(service_name, date_from, date_to, specialist=None, db_path=None):
    """Вільні старти для послуги.

    Повертає [{'date', 'open', 'specialists': {spec: ['10:00', ...]}}].
    `open=False` означає, що лікар ще не відкрила розклад на цей день.
    """
    from tz_utils import kyiv_now
    from wl_catalog import get_bookable_services
    from wlaunch_api import get_branch_id, get_wlaunch_resources

    menu = {s['name']: s for s in get_bookable_services(db_path=db_path)}
    service = menu.get(service_name)
    if not service:
        raise ValueError('послуга недоступна для запису: {}'.format(service_name))

    allowed = service['specialists']
    if specialist:
        if specialist not in allowed:
            raise ValueError('{} не виконує «{}»'.format(specialist, service_name))
        allowed = [specialist]

    duration = service['duration_min']
    now = kyiv_now()
    today = now.strftime('%Y-%m-%d')
    earliest_today = now.hour * 60 + now.minute + MIN_LEAD_MIN

    bid = get_branch_id()
    resources = get_wlaunch_resources(bid)
    busy = fetch_busy(date_from, date_to, branch_id=bid)

    days = []
    for date_str in _dates(date_from, date_to):
        if date_str < today:
            continue
        day = {'date': date_str, 'open': False, 'specialists': {}}
        for spec in allowed:
            frames = open_frames(date_str, spec, resources=resources)
            if not frames:
                continue
            day['open'] = True
            taken = list(busy.get((date_str, spec), []))
            taken += _local_breaks(date_str, spec, db_path=db_path)
            free = _subtract(frames, taken)
            earliest = earliest_today if date_str == today else 0
            times = [_hhmm(t) for t in _starts(free, duration, earliest)]
            if times:
                day['specialists'][spec] = times
        days.append(day)
    return days


def _subtract(base, cuts):
    from wlaunch_api import _subtract_intervals
    return _subtract_intervals(base, cuts)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    if len(sys.argv) < 4:
        print(__doc__.strip().splitlines()[-1])
        sys.exit(1)
    service, d_from, d_to = sys.argv[1], sys.argv[2], sys.argv[3]
    spec = sys.argv[4] if len(sys.argv) > 4 else None
    for day in get_free_slots(service, d_from, d_to, specialist=spec):
        if not day['open']:
            print('{}  розклад не відкрито'.format(day['date']))
            continue
        if not day['specialists']:
            print('{}  вільних слотів немає'.format(day['date']))
            continue
        for s, times in sorted(day['specialists'].items()):
            print('{}  {:<10} {}'.format(day['date'], s, ' '.join(times)))
