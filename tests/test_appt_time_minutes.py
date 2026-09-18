"""
Regression tests for appointment minutes being dropped in notifications.

Bug (18.09.2026): WLaunch appointment 10:30 was announced to the specialist as
"18.09 о 10:00". sync_appointments.py stores both `hour` and `minute` in
clients.services_json, but every notification builder formatted the time as
'{:02d}:00'.format(hour) — silently discarding the minutes. pwa_api's overlap
check had the same defect (s = hour * 60), so a :30 appointment looked like a
:00 one when validating a new booking slot.
"""
import os
import sys
import json
import types
import sqlite3
import logging
import logging.handlers
import importlib.util
import pytest

ZADARMA = os.path.join(os.path.dirname(__file__), '..', 'zadarma')


class _NullRotatingHandler(logging.NullHandler):
    def __init__(self, *a, **kw):
        super().__init__()


def _load_real(name, filename, db_path=None):
    """Load a zadarma module under an alias so conftest's stubs stay intact."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(ZADARMA, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    _orig_rfh = logging.handlers.RotatingFileHandler
    logging.handlers.RotatingFileHandler = _NullRotatingHandler
    try:
        spec.loader.exec_module(mod)
    finally:
        logging.handlers.RotatingFileHandler = _orig_rfh
    if db_path:
        mod.DB_PATH = db_path
    return mod


# fcntl is POSIX-only; appt_reminder imports it at module level
if 'fcntl' not in sys.modules:
    try:
        import fcntl  # noqa: F401
    except ImportError:
        _f = types.ModuleType('fcntl')
        _f.flock = lambda *a, **kw: None
        _f.LOCK_EX = 2
        _f.LOCK_NB = 4
        _f.LOCK_UN = 8
        sys.modules['fcntl'] = _f


@pytest.fixture(scope='module')
def wl_db(tmp_path_factory):
    """users.db with one WLaunch appointment at 10:30 and one at 12:00."""
    path = str(tmp_path_factory.mktemp('minutes') / 'users.db')
    conn = sqlite3.connect(path)
    conn.execute(
        'CREATE TABLE clients (id TEXT PRIMARY KEY, phone TEXT, first_name TEXT,'
        ' last_name TEXT, services_json TEXT)'
    )
    conn.execute(
        'CREATE TABLE manual_appointments (id INTEGER PRIMARY KEY, client_phone TEXT,'
        ' client_name TEXT, procedure_name TEXT, specialist TEXT, date TEXT, time TEXT,'
        ' duration INTEGER, notes TEXT, wlaunch_id TEXT, status TEXT)'
    )
    conn.execute(
        'CREATE TABLE specialist_breaks (id INTEGER PRIMARY KEY, specialist TEXT,'
        ' date TEXT, time_from TEXT, time_to TEXT)'
    )
    conn.execute(
        "INSERT INTO clients VALUES ('c1','380503861247','Лілія','Лосьева',?)",
        (json.dumps([{
            'appt_id': 'wl-1', 'date': '2026-09-18', 'hour': 10, 'minute': 30,
            'service': 'Карбокситерапія', 'status': 'CONFIRMED',
            'specialist': 'victoria', 'duration_min': 60,
        }], ensure_ascii=False),)
    )
    conn.execute(
        "INSERT INTO clients VALUES ('c2','380635383829','Шаима','Куллаб',?)",
        (json.dumps([{
            'appt_id': 'wl-2', 'date': '2026-09-18', 'hour': 12, 'minute': 0,
            'service': 'Консультація', 'status': 'CONFIRMED',
            'specialist': 'victoria', 'duration_min': 45,
        }], ensure_ascii=False),)
    )
    conn.commit()
    conn.close()
    return path


# ── appt_reminder: tomorrow briefing / 24h reminder / feedback ──────────────

def test_wlaunch_appts_keep_minutes(wl_db):
    ar = _load_real('appt_reminder_real', 'appt_reminder.py', db_path=wl_db)
    appts = {a['client_phone']: a for a in ar._get_wlaunch_appts('2026-09-18')}
    assert appts['380503861247']['time'] == '10:30'
    assert appts['380635383829']['time'] == '12:00'


def test_collect_appts_keeps_minutes(wl_db):
    ar = _load_real('appt_reminder_real', 'appt_reminder.py', db_path=wl_db)
    times = sorted(a['time'] for a in ar._collect_appts('2026-09-18'))
    assert times == ['10:30', '12:00']


# ── notifier: message templates ────────────────────────────────────────────

def test_appt_vars_keeps_minutes_from_hour_minute():
    nt = _load_real('notifier_real', 'notifier.py')
    v = nt._appt_vars({
        'client_name': 'Лілія', 'client_phone': '380503861247',
        'service': 'Карбокситерапія', 'specialist': 'victoria',
        'date': '2026-09-18', 'hour': 10, 'minute': 30, 'duration_min': 60,
    })
    assert v['time'] == '10:30'


def test_appt_vars_explicit_time_still_wins():
    nt = _load_real('notifier_real', 'notifier.py')
    v = nt._appt_vars({
        'client_name': 'Лілія', 'client_phone': '380503861247',
        'procedure_name': 'Карбокситерапія', 'specialist': 'victoria',
        'date': '2026-09-18', 'time': '11:15', 'hour': 10, 'minute': 30,
    })
    assert v['time'] == '11:15'


def test_admin_tomorrow_line_shows_half_hour():
    nt = _load_real('notifier_real', 'notifier.py')
    line = nt.fmt_admin_tomorrow_line({
        'client_name': 'Лілія', 'client_phone': '380503861247',
        'service': 'Карбокситерапія', 'specialist': 'victoria',
        'date': '2026-09-18', 'hour': 10, 'minute': 30, 'duration_min': 60,
    })
    assert '10:30' in line
    assert '10:00' not in line


# ── pwa_api: slot overlap validation ───────────────────────────────────────

def test_overlap_uses_real_start_minute(pwa, wl_db):
    """A 10:30-11:30 WLaunch appointment must not be treated as 10:00-11:00."""
    conn = sqlite3.connect(wl_db)
    conn.row_factory = sqlite3.Row
    try:
        # 10:00-10:30 ends exactly when the real appointment starts → free
        assert pwa._check_overlap(conn, 'victoria', '2026-09-18', 600, 630) is False
        # 11:00-11:30 sits inside 10:30-11:30 → busy (was wrongly "free" before)
        assert pwa._check_overlap(conn, 'victoria', '2026-09-18', 660, 690) is True
        # 10:15-10:45 straddles the start → busy
        assert pwa._check_overlap(conn, 'victoria', '2026-09-18', 615, 645) is True
    finally:
        conn.close()


# ── source guard: nobody reintroduces the hour-only format ─────────────────

def test_no_module_formats_appointment_time_as_hour_only():
    import re
    bad = []
    pattern = re.compile(r"\{:02d\}:00['\"]\.format")
    for fname in sorted(os.listdir(ZADARMA)):
        if not fname.endswith('.py') or fname.startswith('test_'):
            continue
        path = os.path.join(ZADARMA, fname)
        with open(path, encoding='utf-8', errors='replace') as fh:
            for i, line in enumerate(fh, 1):
                if pattern.search(line) and 'hour' in line:
                    bad.append('{}:{}'.format(fname, i))
    assert not bad, 'hour-only time formatting (minutes dropped) at: ' + ', '.join(bad)
