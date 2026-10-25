# -*- coding: utf-8 -*-
"""
Етап 4: спільне ядро створення записів.

Правила, які воно має тримати незалежно від каналу (веб, PWA, адмінка):

  - спершу WLaunch, потім локальне дзеркало. Запис, якого немає у WLaunch, не
    існує: там розклад лікаря;
  - будь-яка локальна помилка після успішного WLaunch відкочує WLaunch, інакше
    лишиться сирота, якої ніхто не чекає;
  - тривалість береться з каталогу, ніколи з запиту — у прайсі вона фіктивна
    (60 для всіх позицій), а клієнт не має права її задавати;
  - де спеціаліст один, вибір клієнта ігнорується; де їх двоє (відбілювання) —
    вимагається і перевіряється;
  - слот перевіряється на момент створення, а не на момент, коли клієнт
    відкрив сторінку.
"""
import os
import sys
import sqlite3
import logging
import logging.handlers
import importlib.util
from datetime import datetime, timedelta

import pytest

ZADARMA = os.path.join(os.path.dirname(__file__), '..', 'zadarma')


class _NullRotatingHandler(logging.NullHandler):
    def __init__(self, *a, **kw):
        super().__init__()


@pytest.fixture(scope='module')
def bk():
    spec = importlib.util.spec_from_file_location(
        'booking_real', os.path.join(ZADARMA, 'booking.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules['booking_real'] = mod
    _orig = logging.handlers.RotatingFileHandler
    logging.handlers.RotatingFileHandler = _NullRotatingHandler
    try:
        spec.loader.exec_module(mod)
    finally:
        logging.handlers.RotatingFileHandler = _orig
    return mod


TOMORROW = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

MENU = [
    {'name': 'Біорепарація шкіри', 'duration_min': 30, 'specialists': ['victoria'],
     'specialist_choice': False, 'price_from': 3500, 'price_to': 4500,
     'wl_id': 'svc-1', 'classify': 'needs_drug'},
    {'name': 'Відбілювання зубів', 'duration_min': 60,
     'specialists': ['anastasia', 'victoria'], 'specialist_choice': True,
     'price_from': 1400, 'price_to': 2200, 'wl_id': 'svc-2', 'classify': 'needs_drug'},
]


@pytest.fixture
def env(bk, tmp_path, monkeypatch):
    """Ядро з підміненими WLaunch, каталогом і слотами."""
    db = str(tmp_path / 'users.db')
    conn = sqlite3.connect(db)
    conn.executescript(
        'CREATE TABLE manual_appointments ('
        ' id INTEGER PRIMARY KEY AUTOINCREMENT, client_phone TEXT, client_name TEXT,'
        ' procedure_name TEXT, specialist TEXT, date TEXT, time TEXT, duration INTEGER,'
        " notes TEXT, wlaunch_id TEXT, created_by TEXT, status TEXT DEFAULT 'CONFIRMED');"
        'CREATE TABLE clients (id TEXT, phone TEXT, services_json TEXT);'
        'CREATE TABLE specialist_breaks (specialist TEXT, date TEXT,'
        ' time_from TEXT, time_to TEXT);'
        'CREATE TABLE appointment_audit_log ('
        ' id INTEGER PRIMARY KEY AUTOINCREMENT, appt_id TEXT, phone TEXT,'
        ' client_name TEXT, procedure_name TEXT, specialist TEXT, date TEXT, time TEXT,'
        ' status TEXT, prev_status TEXT, action TEXT, source TEXT, created_at TEXT);'
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(bk, 'DB_PATH', db)

    state = {
        'wl_result': ('wl-new-id', None),
        'wl_calls': [],
        'cancelled': [],
        'slots': {('Біорепарація шкіри', 'victoria'): ['10:00', '10:15', '10:30'],
                  ('Відбілювання зубів', 'victoria'): ['11:00'],
                  ('Відбілювання зубів', 'anastasia'): ['12:00']},
        'open': True,
    }

    stub_cat = type(sys)('wl_catalog')
    stub_cat.get_bookable_services = lambda db_path=None: list(MENU)
    monkeypatch.setitem(sys.modules, 'wl_catalog', stub_cat)

    def _slots(service, d_from, d_to, specialist=None, db_path=None):
        if not state['open']:
            return [{'date': d_from, 'open': False, 'specialists': {}}]
        times = state['slots'].get((service, specialist), [])
        return [{'date': d_from, 'open': True,
                 'specialists': {specialist: times} if times else {}}]

    stub_slots = type(sys)('booking_slots')
    stub_slots.get_free_slots = _slots
    monkeypatch.setitem(sys.modules, 'booking_slots', stub_slots)

    def _create(phone, name, proc, spec, date, time_str, dur):
        state['wl_calls'].append(
            {'phone': phone, 'name': name, 'procedure': proc,
             'specialist': spec, 'date': date, 'time': time_str, 'duration': dur})
        return state['wl_result']

    stub_wl = type(sys)('wlaunch_api')
    stub_wl.create_wlaunch_appointment = _create
    stub_wl.get_branch_id = lambda: 'branch-1'
    monkeypatch.setitem(sys.modules, 'wlaunch_api', stub_wl)

    monkeypatch.setattr(bk, 'cancel_wlaunch_appt',
                        lambda wl_id, branch_id=None: (
                            state['cancelled'].append(wl_id), (True, None))[1])

    stub_db = type(sys)('user_db')
    stub_db.normalize_phone = lambda p: ''.join(ch for ch in (p or '') if ch.isdigit())
    monkeypatch.setitem(sys.modules, 'user_db', stub_db)

    state['db'] = db
    return state


def _rows(db, where='', params=()):
    conn = sqlite3.connect(db)
    try:
        q = 'SELECT * FROM manual_appointments'
        if where:
            q += ' WHERE ' + where
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()


def _book(bk, env, **over):
    kw = {'phone': '0991234567', 'client_name': 'Тест Клієнт',
          'service_name': 'Біорепарація шкіри', 'date': TOMORROW,
          'time_str': '10:00', 'source': 'web', 'db_path': env['db']}
    kw.update(over)
    return bk.create_booking(**kw)


# ── Успішний шлях ─────────────────────────────────────────────────────────────

class TestHappyPath:

    def test_creates_in_wlaunch_then_locally(self, bk, env):
        res = _book(bk, env)
        assert res['wlaunch_id'] == 'wl-new-id'
        assert len(env['wl_calls']) == 1
        rows = _rows(env['db'])
        assert len(rows) == 1
        assert rows[0]['wlaunch_id'] == 'wl-new-id'
        assert rows[0]['created_by'] == 'booking:web'

    def test_duration_comes_from_the_catalogue(self, bk, env):
        """Клієнт не задає тривалість — її бере послуга."""
        res = _book(bk, env)
        assert res['duration_min'] == 30
        assert env['wl_calls'][0]['duration'] == 30
        assert _rows(env['db'])[0]['duration'] == 30

    def test_phone_is_normalised(self, bk, env):
        _book(bk, env, phone='+38 (099) 123-45-67')
        assert _rows(env['db'])[0]['client_phone'] == '380991234567'

    def test_audit_trail_records_the_source(self, bk, env):
        _book(bk, env, source='tg')
        conn = sqlite3.connect(env['db'])
        row = conn.execute(
            'SELECT action, source, status FROM appointment_audit_log').fetchone()
        conn.close()
        assert row == ('created', 'booking:tg', 'CONFIRMED')


# ── Спеціаліст ────────────────────────────────────────────────────────────────

class TestSpecialist:

    def test_single_specialist_is_forced(self, bk, env):
        """Ін'єкції робить лише Вікторія — підміна в запиті ігнорується."""
        res = _book(bk, env, specialist='anastasia')
        assert res['specialist'] == 'victoria'
        assert env['wl_calls'][0]['specialist'] == 'victoria'

    def test_choice_service_requires_a_specialist(self, bk, env):
        with pytest.raises(bk.BookingError) as e:
            _book(bk, env, service_name='Відбілювання зубів', time_str='11:00')
        assert e.value.code == 'specialist_required'
        assert env['wl_calls'] == []

    def test_choice_service_accepts_an_allowed_specialist(self, bk, env):
        res = _book(bk, env, service_name='Відбілювання зубів',
                    specialist='anastasia', time_str='12:00')
        assert res['specialist'] == 'anastasia'

    def test_unknown_specialist_is_refused(self, bk, env):
        with pytest.raises(bk.BookingError) as e:
            _book(bk, env, service_name='Відбілювання зубів',
                  specialist='hacker', time_str='11:00')
        assert e.value.code == 'specialist_not_allowed'
        assert env['wl_calls'] == []


# ── Валідація ─────────────────────────────────────────────────────────────────

class TestValidation:

    @pytest.mark.parametrize('field,value,code', [
        ('phone', '', 'phone_required'),
        ('client_name', '   ', 'name_required'),
        ('date', '26.10.2026', 'invalid_date'),
        ('time_str', '10-00', 'invalid_time'),
        ('date', YESTERDAY, 'past_date'),
        ('service_name', 'Онлайн-консультація', 'service_unavailable'),
    ])
    def test_bad_input_never_reaches_wlaunch(self, bk, env, field, value, code):
        with pytest.raises(bk.BookingError) as e:
            _book(bk, env, **{field: value})
        assert e.value.code == code
        assert env['wl_calls'] == [], 'перевірка має впасти до звернення у WLaunch'
        assert _rows(env['db']) == []


# ── Слот ──────────────────────────────────────────────────────────────────────

class TestSlotVerification:

    def test_taken_slot_is_refused(self, bk, env):
        """Клієнт міг тримати сторінку відкритою — час перевіряється зараз."""
        with pytest.raises(bk.BookingError) as e:
            _book(bk, env, time_str='09:00')
        assert e.value.code == 'slot_taken'
        assert env['wl_calls'] == []

    def test_closed_day_is_refused(self, bk, env):
        env['open'] = False
        with pytest.raises(bk.BookingError) as e:
            _book(bk, env)
        assert e.value.code == 'schedule_closed'
        assert env['wl_calls'] == []


# ── Відмови WLaunch і відкат ──────────────────────────────────────────────────

class TestWlaunchFailures:

    def test_refusal_leaves_nothing_local(self, bk, env):
        env['wl_result'] = (None, 'unavailable')
        with pytest.raises(bk.BookingError) as e:
            _book(bk, env)
        assert e.value.code == 'wlaunch_rejected'
        assert _rows(env['db']) == []

    def test_exception_leaves_nothing_local(self, bk, env, monkeypatch):
        def _boom(*a, **kw):
            raise RuntimeError('connection refused')
        monkeypatch.setattr(sys.modules['wlaunch_api'],
                            'create_wlaunch_appointment', _boom)
        with pytest.raises(bk.BookingError) as e:
            _book(bk, env)
        assert e.value.code == 'wlaunch_unavailable'
        assert _rows(env['db']) == []

    def test_local_overlap_rolls_wlaunch_back(self, bk, env):
        """Гонка: між перевіркою слота і вставкою час зайняли локально."""
        conn = sqlite3.connect(env['db'])
        conn.execute(
            "INSERT INTO manual_appointments (client_phone, procedure_name, specialist,"
            " date, time, duration, status) VALUES ('380000000000','Інше','victoria',"
            "?, '10:00', 60, 'CONFIRMED')", (TOMORROW,))
        conn.commit()
        conn.close()

        with pytest.raises(bk.BookingError) as e:
            _book(bk, env)
        assert e.value.code == 'slot_taken'
        assert env['cancelled'] == ['wl-new-id'], 'запис у WLaunch лишився сиротою'
        assert _rows(env['db'], 'wlaunch_id=?', ('wl-new-id',)) == []

    def test_db_failure_rolls_wlaunch_back(self, bk, env, monkeypatch):
        conn = sqlite3.connect(env['db'])
        conn.execute('DROP TABLE manual_appointments')
        conn.commit()
        conn.close()
        with pytest.raises(bk.BookingError) as e:
            _book(bk, env)
        assert e.value.code == 'db_error'
        assert env['cancelled'] == ['wl-new-id']


# ── Примітиви, які поділяються з pwa_api ──────────────────────────────────────

class TestSharedPrimitives:

    def test_time_to_min(self, bk):
        assert bk.time_to_min('09:30') == 570
        assert bk.time_to_min('') == 0
        assert bk.time_to_min('сміття') == 0

    def test_overlap_sees_manual_appointments(self, bk, env):
        conn = sqlite3.connect(env['db'])
        conn.execute(
            "INSERT INTO manual_appointments (specialist, date, time, duration, status)"
            " VALUES ('victoria', ?, '10:00', 60, 'CONFIRMED')", (TOMORROW,))
        conn.commit()
        assert bk.check_overlap(conn, 'victoria', TOMORROW, 630, 660) is True
        assert bk.check_overlap(conn, 'victoria', TOMORROW, 660, 690) is False
        conn.close()

    def test_overlap_sees_wlaunch_appointments(self, bk, env):
        """Друге сховище — пропустити його означає дозволити подвійний запис."""
        conn = sqlite3.connect(env['db'])
        conn.execute(
            "INSERT INTO clients (id, phone, services_json) VALUES ('c1','3801',?)",
            ('[{"date":"%s","hour":14,"minute":0,"duration_min":60,'
             '"specialist":"victoria","status":"CONFIRMED"}]' % TOMORROW,))
        conn.commit()
        assert bk.check_overlap(conn, 'victoria', TOMORROW, 870, 900) is True
        assert bk.check_overlap(conn, 'victoria', TOMORROW, 900, 930) is False
        conn.close()

    def test_overlap_sees_breaks(self, bk, env):
        conn = sqlite3.connect(env['db'])
        conn.execute(
            'INSERT INTO specialist_breaks VALUES (?,?,?,?)',
            ('victoria', TOMORROW, '13:00', '14:00'))
        conn.commit()
        assert bk.check_overlap(conn, 'victoria', TOMORROW, 780, 810) is True
        conn.close()

    def test_cancelled_rows_do_not_block(self, bk, env):
        conn = sqlite3.connect(env['db'])
        conn.execute(
            "INSERT INTO manual_appointments (specialist, date, time, duration, status)"
            " VALUES ('victoria', ?, '10:00', 60, 'CANCELLED')", (TOMORROW,))
        conn.commit()
        assert bk.check_overlap(conn, 'victoria', TOMORROW, 600, 630) is False
        conn.close()
