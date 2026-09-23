"""
Regression tests for the appointment-collection audit findings (23.09.2026).

3. _collect_appts deduped by (phone, date), so a client with two appointments
   on the same day appeared once in the tomorrow briefing. Live case: a client
   booked 12:00 with victoria and 13:00 with anastasia on 2026-09-19, and the
   briefing listed only the 13:00 one — victoria never saw her own appointment.
4. push_reminder keyed its dedup on the date alone, with the same effect.
5. A rescheduled appointment kept its notification reference, so the specialist
   was never told the slot had moved.
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


if 'fcntl' not in sys.modules:
    try:
        import fcntl  # noqa: F401
    except ImportError:
        _f = types.ModuleType('fcntl')
        _f.flock = lambda *a, **kw: None
        _f.LOCK_EX, _f.LOCK_NB, _f.LOCK_UN = 2, 4, 8
        sys.modules['fcntl'] = _f


def _wl(appt_id, hour, minute, service, specialist):
    return {
        'appt_id': appt_id, 'date': '2026-09-19', 'hour': hour, 'minute': minute,
        'service': service, 'status': 'CONFIRMED_BY_CLIENT',
        'specialist': specialist, 'duration_min': 60,
    }


def _make_db(path, services, manual_rows=()):
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
        "INSERT INTO clients VALUES ('c1','380976946479','Світлана','Олопенюк',?)",
        (json.dumps(services, ensure_ascii=False),)
    )
    for row in manual_rows:
        conn.execute(
            'INSERT INTO manual_appointments (client_phone, client_name, procedure_name,'
            ' specialist, date, time, duration, notes, wlaunch_id, status)'
            ' VALUES (?,?,?,?,?,?,?,?,?,?)', row)
    conn.commit()
    conn.close()
    return path


# ── 3. two appointments the same day both survive ─────────────────────────

def test_same_day_appointments_both_collected(tmp_path):
    db = _make_db(str(tmp_path / 'two.db'), [
        _wl('wl-a', 12, 0, 'Ботулінотерапія, Консультація', 'victoria'),
        _wl('wl-b', 13, 0, 'Моделювання всього тіла', 'anastasia'),
    ])
    ar = _load_real('appt_reminder_collect', 'appt_reminder.py', db_path=db)
    appts = ar._collect_appts('2026-09-19')
    assert sorted(a['time'] for a in appts) == ['12:00', '13:00']
    assert sorted(a['specialist'] for a in appts) == ['anastasia', 'victoria']


def test_briefing_groups_both_specialists(tmp_path):
    """The 12:00 victoria slot must reach victoria's group, not vanish."""
    db = _make_db(str(tmp_path / 'group.db'), [
        _wl('wl-a', 12, 0, 'Ботулінотерапія, Консультація', 'victoria'),
        _wl('wl-b', 13, 0, 'Моделювання всього тіла', 'anastasia'),
    ])
    ar = _load_real('appt_reminder_collect', 'appt_reminder.py', db_path=db)
    by_spec = {}
    for a in ar._collect_appts('2026-09-19'):
        by_spec.setdefault(a.get('specialist') or 'other', []).append(a)
    assert set(by_spec) == {'victoria', 'anastasia'}
    assert by_spec['victoria'][0]['time'] == '12:00'


# ── 3b. the manual↔wlaunch dedup it was originally protecting still works ──

def test_manual_copy_of_wlaunch_appt_deduped_by_id(tmp_path):
    db = _make_db(
        str(tmp_path / 'dedup_id.db'),
        [_wl('wl-a', 12, 0, 'Консультація', 'victoria')],
        manual_rows=[('380976946479', 'Світлана Олопенюк', 'Консультація',
                      'victoria', '2026-09-19', '12:00', 60, '', 'wl-a', 'CONFIRMED')],
    )
    ar = _load_real('appt_reminder_collect', 'appt_reminder.py', db_path=db)
    appts = ar._collect_appts('2026-09-19')
    assert len(appts) == 1
    assert appts[0]['source'] == 'manual'


def test_manual_copy_without_id_deduped_by_phone_and_time(tmp_path):
    db = _make_db(
        str(tmp_path / 'dedup_time.db'),
        [_wl('wl-a', 12, 0, 'Консультація', 'victoria')],
        manual_rows=[('380976946479', 'Світлана Олопенюк', 'Консультація',
                      'victoria', '2026-09-19', '12:00', 60, '', '', 'CONFIRMED')],
    )
    ar = _load_real('appt_reminder_collect', 'appt_reminder.py', db_path=db)
    appts = ar._collect_appts('2026-09-19')
    assert len(appts) == 1
    assert appts[0]['source'] == 'manual'


def test_manual_at_a_different_time_is_not_swallowed(tmp_path):
    """Same client, same day, different slots — both must stay."""
    db = _make_db(
        str(tmp_path / 'dedup_mixed.db'),
        [_wl('wl-a', 12, 0, 'Консультація', 'victoria')],
        manual_rows=[('380976946479', 'Світлана Олопенюк', 'Масаж',
                      'anastasia', '2026-09-19', '16:30', 60, '', '', 'CONFIRMED')],
    )
    ar = _load_real('appt_reminder_collect', 'appt_reminder.py', db_path=db)
    appts = ar._collect_appts('2026-09-19')
    assert sorted(a['time'] for a in appts) == ['12:00', '16:30']


# ── 4. push dedup key carries the time ────────────────────────────────────

def test_push_reference_includes_time():
    """Source-level: the reference must not collapse to the bare date again."""
    path = os.path.join(ZADARMA, 'push_reminder.py')
    with open(path, encoding='utf-8') as fh:
        src = fh.read()
    assert "reference = 'appt|{}'.format(appt_date_str)" not in src
    assert "'appt|{}|{:02d}:{:02d}'" in src


# ── 5. a moved appointment is recognised as moved ─────────────────────────

@pytest.fixture
def notif_db(tmp_path):
    path = str(tmp_path / 'notif.db')
    conn = sqlite3.connect(path)
    conn.execute(
        'CREATE TABLE notification_log (id INTEGER PRIMARY KEY AUTOINCREMENT,'
        ' phone TEXT NOT NULL, type TEXT NOT NULL, reference TEXT NOT NULL,'
        ' channel TEXT NOT NULL, status TEXT DEFAULT "sent", sent_at TEXT NOT NULL,'
        ' message_preview TEXT, UNIQUE(phone, type, reference, channel))'
    )
    conn.commit()
    conn.close()
    return path


def test_reschedule_detected_as_other_reference(notif_db):
    nt = _load_real('notifier_reschedule', 'notifier.py', db_path=notif_db)
    old_ref = 'wl-a|2026-09-19|10:30'
    new_ref = 'wl-a|2026-09-19|14:00'
    nt._log('380996093860', 'spec_new', old_ref, 'tg', 'sent', 'announced')

    # not yet announced under the new slot
    assert nt._already_sent('380996093860', 'spec_new', new_ref, 'tg') is False
    # and we can tell it is a move rather than a brand-new appointment
    assert nt._sent_under_other_reference(
        '380996093860', 'spec_new', 'wl-a', new_ref) is True


def test_brand_new_appointment_is_not_flagged_as_moved(notif_db):
    nt = _load_real('notifier_reschedule', 'notifier.py', db_path=notif_db)
    assert nt._sent_under_other_reference(
        '380996093860', 'spec_new', 'wl-zzz', 'wl-zzz|2026-09-19|11:00') is False


def test_unchanged_appointment_is_skipped(notif_db):
    nt = _load_real('notifier_reschedule', 'notifier.py', db_path=notif_db)
    ref = 'wl-b|2026-09-19|09:00'
    nt._log('380996093860', 'spec_new', ref, 'tg', 'sent', 'announced')
    assert nt._already_sent('380996093860', 'spec_new', ref, 'tg') is True
