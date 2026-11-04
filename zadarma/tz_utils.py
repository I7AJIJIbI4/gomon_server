# tz_utils.py — Timezone utilities for Europe/Kyiv
# Single source of truth for DST offset calculation.

import calendar as _cal
from datetime import datetime, timedelta


def kyiv_offset(dt=None):
    """
    UTC offset for Europe/Kyiv: +2 (winter) or +3 (summer/DST).
    DST: last Sunday of March 01:00 UTC - last Sunday of October 01:00 UTC.

    dt: UTC datetime to check. If None, uses current UTC time.
    IMPORTANT: pass the appointment's UTC datetime, not datetime.utcnow(),
    when converting appointment times that may be in a different DST period.
    """
    if dt is None:
        dt = datetime.utcnow()
    year = dt.year
    mar_last_sun = 31 - _cal.weekday(year, 3, 31)
    oct_last_sun = 31 - _cal.weekday(year, 10, 31)
    dst_start = datetime(year, 3, mar_last_sun, 1, 0)
    dst_end = datetime(year, 10, oct_last_sun, 1, 0)
    return 3 if dst_start <= dt < dst_end else 2


def utc_to_kyiv(utc_dt):
    """Convert a UTC datetime to Kyiv datetime."""
    return utc_dt + timedelta(hours=kyiv_offset(utc_dt))


def kyiv_now():
    """Current time in Kyiv timezone."""
    return utc_to_kyiv(datetime.utcnow())


def kyiv_day_start_utc(kyiv_dt=None):
    """Київська північ поточної (або заданої) доби — як UTC-рядок 'YYYY-MM-DD HH:MM:SS'.

    Для порівняння з created_at, які SQLite пише в UTC (datetime('now'),
    CURRENT_TIMESTAMP). Порівнювати їх із київською датою 'YYYY-MM-DD' не можна:
    з 00:00 до 02:00 (влітку до 03:00) Києва UTC ще вчора, і «сьогодні» нічого немає.
    """
    k = (kyiv_dt or kyiv_now()).replace(hour=0, minute=0, second=0, microsecond=0)
    for off in (3, 2):
        utc = k - timedelta(hours=off)
        if kyiv_offset(utc) == off:
            return utc.strftime('%Y-%m-%d %H:%M:%S')
    return (k - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
