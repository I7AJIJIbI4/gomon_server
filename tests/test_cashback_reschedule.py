# -*- coding: utf-8 -*-
"""
Кешбек і перенесення записів.

Клієнт просить перенести візит — лікар скасовує поточний запис у WLaunch і
створює новий на інший день або час. Кешбек має впасти рівно за ОДИН візит:
за скасований не нараховується нічого, за новий — один раз, у його дату.

Покриває `appt_reminder.run_feedback` (автоматичний кешбек + post-visit) і
`photo_reminder.check_pending_cashback_reminders` (кешбек після підтвердження
лікаркою препарата/ціни).

Скасований візит із підтвердженою ціною (photo_tasks / cashback_pending) кешбеку
не дає: `photo_reminder.visit_is_cancelled`. Брифінг і run_feedback збирають записи
одним `_collect_appts`.
"""
import os
import sys
import json
import types
import sqlite3
from datetime import datetime

import pytest

from conftest import load_real as _load_real  # noqa: E402

if 'fcntl' not in sys.modules:       # appt_reminder імпортує його; на Windows немає
    try:
        import fcntl  # noqa: F401
    except ImportError:
        _f = types.ModuleType('fcntl')
        _f.flock = lambda *a, **kw: None
        _f.LOCK_EX, _f.LOCK_NB, _f.LOCK_UN = 2, 4, 8
        sys.modules['fcntl'] = _f

PHONE = '380631234519'
OLD_DAY = '2026-11-10'
NEW_DAY = '2026-11-17'


# ── спільні таблиці ───────────────────────────────────────────────────────────

def _make_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        'CREATE TABLE clients (id TEXT PRIMARY KEY, phone TEXT, first_name TEXT,'
        ' last_name TEXT, services_json TEXT);'
        'CREATE TABLE manual_appointments (id INTEGER PRIMARY KEY AUTOINCREMENT,'
        ' client_phone TEXT, client_name TEXT, procedure_name TEXT, specialist TEXT,'
        ' date TEXT, time TEXT, duration INTEGER, notes TEXT, wlaunch_id TEXT, status TEXT);'
        'CREATE TABLE cashback (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT,'
        ' amount REAL, procedure_name TEXT, procedure_price REAL DEFAULT 0, appt_date TEXT,'
        " created_at TEXT DEFAULT (datetime('now')),"
        ' UNIQUE(phone, procedure_name, appt_date));'
        'CREATE TABLE deposits (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT,'
        ' amount_uah REAL, status TEXT);'
        'CREATE TABLE deposit_deductions (id INTEGER PRIMARY KEY AUTOINCREMENT,'
        ' phone TEXT, amount REAL, reason TEXT);'
        'CREATE TABLE cashback_pending (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT,'
        ' client_name TEXT, procedure_generic TEXT, drug_specific TEXT, price REAL,'
        ' appt_date TEXT, confirmed_by TEXT, confirmed_at TEXT, accrued INTEGER DEFAULT 0);'
        'CREATE TABLE photo_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, appt_id TEXT,'
        ' client_phone TEXT NOT NULL, client_name TEXT, procedure_name TEXT,'
        ' specialist TEXT, appt_date TEXT NOT NULL, appt_time TEXT,'
        ' drive_folder_url TEXT, drive_folder_id TEXT,'
        ' photos_uploaded INTEGER DEFAULT 0, photos_checked_at TEXT,'
        " cashback_status TEXT DEFAULT 'pending', cashback_drug TEXT,"
        ' cashback_price REAL, cashback_confirmed_at TEXT, cashback_notified_at TEXT,'
        ' created_at TEXT DEFAULT CURRENT_TIMESTAMP,'
        ' UNIQUE(client_phone, appt_date, procedure_name));'
    )
    conn.commit()
    conn.close()


def _wl(appt_id, date, hour, minute=0, status='CONFIRMED_BY_CLIENT', service='WOW-чистка'):
    return {'appt_id': appt_id, 'date': date, 'hour': hour, 'minute': minute,
            'service': service, 'status': status, 'specialist': 'victoria',
            'duration_min': 60}


def _set_services(db, entries):
    conn = sqlite3.connect(db)
    conn.execute('DELETE FROM clients')
    conn.execute("INSERT INTO clients VALUES ('c1', ?, 'Світлана', 'Тест', ?)",
                 (PHONE, json.dumps(entries, ensure_ascii=False)))
    conn.commit()
    conn.close()


def _add_manual(db, date, time, status, wlaunch_id='', proc='WOW-чистка'):
    conn = sqlite3.connect(db)
    conn.execute(
        'INSERT INTO manual_appointments (client_phone, client_name, procedure_name,'
        ' specialist, date, time, duration, notes, wlaunch_id, status)'
        " VALUES (?,?,?,'victoria',?,?,60,'',?,?)",
        (PHONE, 'Світлана Тест', proc, date, time, wlaunch_id, status))
    conn.commit()
    conn.close()


def _cashback(db):
    conn = sqlite3.connect(db)
    rows = conn.execute(
        'SELECT appt_date, procedure_name, amount FROM cashback ORDER BY id').fetchall()
    conn.close()
    return rows


# ── 1. run_feedback: автоматичний кешбек ──────────────────────────────────────

@pytest.fixture
def fb(tmp_path, monkeypatch, frozen_kyiv):
    """Справжній appt_reminder на тимчасових БД, з 20:00 у день візиту."""
    db = str(tmp_path / 'users.db')
    _make_db(db)

    otp = str(tmp_path / 'otp_sessions.db')
    c = sqlite3.connect(otp)
    c.execute('CREATE TABLE sessions (id INTEGER PRIMARY KEY, phone TEXT)')
    c.execute('INSERT INTO sessions (phone) VALUES (?)', (PHONE,))
    c.commit()
    c.close()

    prices = str(tmp_path / 'prices.json')
    # appt_reminder читає prices.json без encoding=, тож на Windows (cp1251)
    # кирилиця в UTF-8 не збіглась би; ASCII-екрановане JSON не залежить від ОС.
    with open(prices, 'w') as fh:
        json.dump([{'cat': 'Апаратна косметологія',
                    'items': [{'name': 'WOW-чистка', 'price': '1400 грн'}]}], fh)

    ar = _load_real('appt_reminder_cashback', 'appt_reminder.py', db_path=db)
    ar.OTP_DB_PATH = otp
    ar.PRICES_PATH = prices

    post_visits = []
    notifier = types.ModuleType('notifier')
    notifier.send_post_visit = lambda appt: post_visits.append(appt) or {}
    notifier.notify_client = lambda *a, **kw: None
    photo = _load_real('photo_reminder_fb', 'photo_reminder.py', db)
    loyalty = types.ModuleType('loyalty')
    loyalty.get_cashback_rate = lambda phone: 0.03
    monkeypatch.setitem(sys.modules, 'notifier', notifier)
    monkeypatch.setitem(sys.modules, 'photo_reminder', photo)
    monkeypatch.setitem(sys.modules, 'loyalty', loyalty)

    frozen_kyiv('{} 20:00'.format(OLD_DAY))
    ar._db_file = db
    ar._post_visits = post_visits
    ar._freeze = frozen_kyiv
    return ar


def test_reschedule_to_another_day_old_visit_earns_nothing(fb):
    """Старий запис скасовано, новий ще попереду — у день старого кешбеку немає."""
    _set_services(fb._db_file, [
        _wl('old', OLD_DAY, 10, status='CANCELLED'),
        _wl('new', NEW_DAY, 10),
    ])
    fb.run_feedback(override_date=OLD_DAY)

    assert _cashback(fb._db_file) == []
    assert fb._post_visits == []


def test_rescheduled_visit_earns_once_on_its_own_day(fb):
    """Новий візит дає один кешбек у свою дату, навіть якщо крон ганяє його кілька разів."""
    _set_services(fb._db_file, [
        _wl('old', OLD_DAY, 10, status='CANCELLED'),
        _wl('new', NEW_DAY, 10),
    ])
    fb.run_feedback(override_date=OLD_DAY)

    fb._freeze('{} 20:00'.format(NEW_DAY))
    for _ in range(3):
        fb.run_feedback(override_date=NEW_DAY)

    assert _cashback(fb._db_file) == [(NEW_DAY, 'WOW-чистка', 42.0)]


def test_same_day_reschedule_pays_one_visit(fb):
    """10:00 скасовано, 15:00 створено в той самий день — один кешбек, один post-visit."""
    _set_services(fb._db_file, [
        _wl('old', OLD_DAY, 10, status='CANCELLED'),
        _wl('new', OLD_DAY, 15),
    ])
    fb.run_feedback(override_date=OLD_DAY)

    assert _cashback(fb._db_file) == [(OLD_DAY, 'WOW-чистка', 42.0)]
    assert [a['time'] for a in fb._post_visits] == ['15:00']


@pytest.mark.parametrize('status', ['CANCELLED', 'cancelled', 'NO_SHOW'])
def test_cancelled_and_no_show_never_earn(fb, status):
    _set_services(fb._db_file, [_wl('old', OLD_DAY, 10, status=status)])
    fb.run_feedback(override_date=OLD_DAY)

    assert _cashback(fb._db_file) == []
    assert fb._post_visits == []


def test_cancelled_manual_appointment_earns_nothing(fb):
    """Адмінка: ручний запис скасовано, новий — на інший день."""
    _add_manual(fb._db_file, OLD_DAY, '10:00', 'CANCELLED')
    _add_manual(fb._db_file, NEW_DAY, '10:00', 'CONFIRMED')
    fb.run_feedback(override_date=OLD_DAY)

    assert _cashback(fb._db_file) == []
    assert fb._post_visits == []


def test_cancelled_wlaunch_with_live_manual_copy_pays_only_the_live_one(fb):
    """Перенесення через адмінку: старий WLaunch-запис CANCELLED, новий — manual того ж дня."""
    _set_services(fb._db_file, [_wl('old', OLD_DAY, 10, status='CANCELLED')])
    _add_manual(fb._db_file, OLD_DAY, '15:00', 'CONFIRMED', wlaunch_id='new')
    fb.run_feedback(override_date=OLD_DAY)

    assert _cashback(fb._db_file) == [(OLD_DAY, 'WOW-чистка', 42.0)]
    assert [a['time'] for a in fb._post_visits] == ['15:00']


def test_manual_copy_with_a_different_time_is_not_processed_twice(fb):
    _set_services(fb._db_file, [_wl('new', OLD_DAY, 12, 30)])
    _add_manual(fb._db_file, OLD_DAY, '12:00', 'CONFIRMED', wlaunch_id='new')
    fb.run_feedback(override_date=OLD_DAY)

    assert len(fb._post_visits) == 1


# ── 2. кешбек після підтвердження лікаркою ────────────────────────────────────

@pytest.fixture
def confirmed(tmp_path, monkeypatch, frozen_kyiv):
    """Справжній photo_reminder: підтверджена ціна препарата, час слати наступного дня."""
    db = str(tmp_path / 'users.db')
    _make_db(db)
    otp = str(tmp_path / 'otp_sessions.db')
    c = sqlite3.connect(otp)
    c.execute('CREATE TABLE sessions (id INTEGER PRIMARY KEY, phone TEXT)')
    c.execute('INSERT INTO sessions (phone) VALUES (?)', (PHONE,))
    c.commit()
    c.close()

    photo = _load_real('photo_reminder_cashback', 'photo_reminder.py', db)
    _orig = sqlite3.connect

    def _redirect(path, *a, **kw):
        if isinstance(path, str) and path.startswith('/home/gomoncli/zadarma/'):
            path = str(tmp_path / os.path.basename(path))
        return _orig(path, *a, **kw)

    monkeypatch.setattr(sqlite3, 'connect', _redirect)

    sent = []
    notifier = types.ModuleType('notifier')
    notifier.send_post_visit = lambda appt: sent.append(appt) or {}
    loyalty = types.ModuleType('loyalty')
    loyalty.get_cashback_rate = lambda phone: 0.03
    monkeypatch.setitem(sys.modules, 'notifier', notifier)
    monkeypatch.setitem(sys.modules, 'loyalty', loyalty)
    frozen_kyiv(datetime(2026, 11, 11, 12, 0))

    conn = _orig(db)
    conn.execute(
        'INSERT INTO photo_tasks (client_phone, client_name, procedure_name,'
        " specialist, appt_date, appt_time, cashback_status, cashback_drug,"
        ' cashback_price, cashback_confirmed_at)'
        " VALUES (?,'Світлана','Ботулінотерапія','victoria',?,'10:00',"
        "'confirmed','Ботулінотерапія 1 зона (Neuronox)',2200,?)",
        (PHONE, OLD_DAY, '{} 20:05:00'.format(OLD_DAY)))
    conn.commit()
    conn.close()
    photo._db_file = db
    photo._sent = sent
    return photo


def test_confirmed_live_visit_accrues_once(confirmed):
    _set_services(confirmed._db_file, [
        _wl('v', OLD_DAY, 10, service='Ботулінотерапія')])
    confirmed.check_pending_cashback_reminders()
    confirmed.check_pending_cashback_reminders()      # крон повторює щочверть

    assert _cashback(confirmed._db_file) == [
        (OLD_DAY, 'Ботулінотерапія 1 зона (Neuronox)', 66.0)]
    assert len(confirmed._sent) == 1


def test_visit_cancelled_after_the_task_was_created_earns_nothing(confirmed):
    _set_services(confirmed._db_file, [
        _wl('v', OLD_DAY, 10, status='CANCELLED', service='Ботулінотерапія'),
        _wl('new', NEW_DAY, 10, service='Ботулінотерапія')])
    confirmed.check_pending_cashback_reminders()

    assert _cashback(confirmed._db_file) == []
    assert confirmed._sent == []


def _task_status(db):
    conn = sqlite3.connect(db)
    row = conn.execute('SELECT cashback_status, cashback_notified_at FROM photo_tasks').fetchone()
    conn.close()
    return row


def test_cancelled_task_is_closed_and_not_retried(confirmed):
    """Закрито як 'cancelled', щоб крон не перевіряв його щочверть."""
    _set_services(confirmed._db_file, [
        _wl('v', OLD_DAY, 10, status='CANCELLED', service='Ботулінотерапія')])
    confirmed.check_pending_cashback_reminders()
    status, notified = _task_status(confirmed._db_file)
    assert status == 'cancelled' and notified is not None

    confirmed.check_pending_cashback_reminders()
    assert _cashback(confirmed._db_file) == []
    assert confirmed._sent == []


def test_cancelled_task_dry_run_changes_nothing(confirmed):
    _set_services(confirmed._db_file, [
        _wl('v', OLD_DAY, 10, status='CANCELLED', service='Ботулінотерапія')])
    confirmed.check_pending_cashback_reminders(dry_run=True)

    assert _task_status(confirmed._db_file)[0] == 'confirmed'
    assert _cashback(confirmed._db_file) == []
    assert confirmed._sent == []


def test_live_visit_beside_a_cancelled_one_still_pays(confirmed):
    """Два записи в день, один скасовано: підтверджена ціна належить живому."""
    _set_services(confirmed._db_file, [
        _wl('gone', OLD_DAY, 9, status='CANCELLED', service='Ботулінотерапія'),
        _wl('live', OLD_DAY, 10, service='Ботулінотерапія')])
    confirmed.check_pending_cashback_reminders()

    assert [r[0] for r in _cashback(confirmed._db_file)] == [OLD_DAY]


def test_unknown_visit_does_not_block_the_cashback(confirmed):
    """Запису на дату немає взагалі (напр. вилетів з топ-50) — гроші клієнта не блокуємо."""
    _set_services(confirmed._db_file, [])
    confirmed.check_pending_cashback_reminders()

    assert [r[0] for r in _cashback(confirmed._db_file)] == [OLD_DAY]


def test_manual_cancelled_task_earns_nothing(confirmed):
    _add_manual(confirmed._db_file, OLD_DAY, '10:00', 'CANCELLED', proc='Ботулінотерапія')
    confirmed.check_pending_cashback_reminders()

    assert _cashback(confirmed._db_file) == []
    assert _task_status(confirmed._db_file)[0] == 'cancelled'


# ── 3. cashback_pending: підтвердження через бота, нарахування через 24 год ───

def _pending(db, appt_date=OLD_DAY):
    conn = sqlite3.connect(db)
    conn.execute(
        'INSERT INTO cashback_pending (phone, drug_specific, price, appt_date,'
        " confirmed_at) VALUES (?,'Ботулінотерапія 1 зона (Neuronox)',2200,?,"
        "'2026-11-08 10:00:00')", (PHONE, appt_date))
    conn.commit()
    conn.close()


def _accrued(db):
    conn = sqlite3.connect(db)
    v = conn.execute('SELECT accrued FROM cashback_pending').fetchone()[0]
    conn.close()
    return v


def test_pending_cashback_for_a_cancelled_visit_is_closed_not_paid(fb):
    _set_services(fb._db_file, [_wl('v', OLD_DAY, 10, status='CANCELLED'),
                                _wl('new', NEW_DAY, 10)])
    _pending(fb._db_file)
    assert fb._process_pending_cashback() == 0

    assert _cashback(fb._db_file) == []
    assert _accrued(fb._db_file) == 1


def test_pending_cashback_for_a_live_visit_is_paid(fb):
    _set_services(fb._db_file, [_wl('v', OLD_DAY, 10)])
    _pending(fb._db_file)
    assert fb._process_pending_cashback() == 1

    assert [r[0] for r in _cashback(fb._db_file)] == [OLD_DAY]
    assert _accrued(fb._db_file) == 1


def test_pending_dry_run_for_a_cancelled_visit_writes_nothing(fb):
    _set_services(fb._db_file, [_wl('v', OLD_DAY, 10, status='CANCELLED')])
    _pending(fb._db_file)
    fb._process_pending_cashback(dry_run=True)

    assert _cashback(fb._db_file) == []
    assert _accrued(fb._db_file) == 0
