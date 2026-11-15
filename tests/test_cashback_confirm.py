# -*- coding: utf-8 -*-
"""
Підтвердження кешбеку лікаркою закриває завдання саме тієї процедури.

Раніше бот (кнопка препарата, ручна ціна) і IG-вебхук оновлювали photo_tasks за
телефоном і датою. За два живі візити в один день ціна одного позначала
підтвердженими обидва завдання: другий візит отримував кешбек за чужу процедуру
з чужою ціною.
"""
import os
import re
import sqlite3

import pytest

from conftest import load_real as _load_real  # noqa: E402

ZADARMA = os.path.join(os.path.dirname(__file__), '..', 'zadarma')
PHONE = '380631234519'
DAY = '2026-11-10'
BOTOX = 'Ботулінотерапія'
BIO = 'Біорепарація шкіри'
TS = '2026-11-10 20:05:00'


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    c.execute(
        'CREATE TABLE photo_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, appt_id TEXT,'
        ' client_phone TEXT NOT NULL, client_name TEXT, procedure_name TEXT,'
        ' specialist TEXT, appt_date TEXT NOT NULL, appt_time TEXT,'
        " cashback_status TEXT DEFAULT 'pending', cashback_drug TEXT,"
        ' cashback_price REAL, cashback_confirmed_at TEXT, cashback_notified_at TEXT,'
        ' UNIQUE(client_phone, appt_date, procedure_name))')
    yield c
    c.close()


@pytest.fixture
def cc():
    return _load_real('cashback_confirm_t', 'cashback_confirm.py')


def _task(conn, proc, status='needs_drug', date=DAY, phone=PHONE):
    conn.execute(
        'INSERT INTO photo_tasks (client_phone, procedure_name, appt_date, cashback_status)'
        ' VALUES (?,?,?,?)', (phone, proc, date, status))


def _rows(conn):
    return {p: (s, d, pr) for p, s, d, pr in conn.execute(
        'SELECT procedure_name, cashback_status, cashback_drug, cashback_price'
        ' FROM photo_tasks')}


def test_only_the_named_procedure_is_confirmed(conn, cc):
    _task(conn, BOTOX)
    _task(conn, BIO)
    n = cc.confirm_photo_tasks(conn, PHONE, DAY, BIO, 'Rejuran S', 3500, TS)

    assert n == 1
    assert _rows(conn) == {BOTOX: ('needs_drug', None, None),
                           BIO: ('confirmed', 'Rejuran S', 3500)}


def test_each_visit_keeps_its_own_drug_and_price(conn, cc):
    _task(conn, BOTOX)
    _task(conn, BIO)
    cc.confirm_photo_tasks(conn, PHONE, DAY, BOTOX, 'Neuronox', 2200, TS)
    cc.confirm_photo_tasks(conn, PHONE, DAY, BIO, 'Rejuran S', 3500, TS)

    assert _rows(conn) == {BOTOX: ('confirmed', 'Neuronox', 2200),
                           BIO: ('confirmed', 'Rejuran S', 3500)}


def test_already_confirmed_or_notified_tasks_are_left_alone(conn, cc):
    _task(conn, BOTOX, status='notified')
    _task(conn, BIO)
    cc.confirm_photo_tasks(conn, PHONE, DAY, BOTOX, 'Neuronox', 2200, TS)

    assert _rows(conn)[BOTOX][0] == 'notified'       # чужа ціна не перезаписала
    assert _rows(conn)[BIO][0] == 'needs_drug'


def test_repeated_click_does_not_move_the_price_to_the_neighbour_visit(conn, cc):
    """Ботокс уже підтверджено; повторне підтвердження ботоксу не чіпає біорепарацію."""
    _task(conn, BOTOX)
    _task(conn, BIO)
    cc.confirm_photo_tasks(conn, PHONE, DAY, BOTOX, 'Neuronox', 2200, TS)
    n = cc.confirm_photo_tasks(conn, PHONE, DAY, BOTOX, 'Dysport', 9999, TS)

    assert n == 0
    assert _rows(conn) == {BOTOX: ('confirmed', 'Neuronox', 2200),
                           BIO: ('needs_drug', None, None)}


def test_other_day_and_other_client_are_not_touched(conn, cc):
    _task(conn, BOTOX, date='2026-11-11')
    _task(conn, BOTOX, phone='380507653106')
    _task(conn, BOTOX)
    cc.confirm_photo_tasks(conn, PHONE, DAY, BOTOX, 'Neuronox', 2200, TS)

    got = conn.execute('SELECT client_phone, appt_date, cashback_status FROM photo_tasks'
                       ' ORDER BY id').fetchall()
    assert got == [(PHONE, '2026-11-11', 'needs_drug'),
                   ('380507653106', DAY, 'needs_drug'),
                   (PHONE, DAY, 'confirmed')]


def test_procedure_with_brackets_is_matched(conn, cc):
    """Бот бере з повідомлення лише текст у дужках — це все одно та сама процедура."""
    _task(conn, 'Ліполітики (обличчя, 4 мл)')
    _task(conn, BIO)
    cc.confirm_photo_tasks(conn, PHONE, DAY, 'обличчя, 4 мл', 'Ціна вручну', 1500, TS)

    assert _rows(conn)['Ліполітики (обличчя, 4 мл)'][0] == 'confirmed'
    assert _rows(conn)[BIO][0] == 'needs_drug'


def test_unrecognised_procedure_confirms_the_whole_day_as_before(conn, cc):
    """Назву не впізнали — поведінка лишається колишньою, підтвердження не губиться."""
    _task(conn, BOTOX)
    _task(conn, BIO)
    n = cc.confirm_photo_tasks(conn, PHONE, DAY, 'щось невідоме', 'Ціна вручну', 1000, TS)

    assert n == 2
    assert {s for s, _, _ in _rows(conn).values()} == {'confirmed'}


def test_single_task_is_confirmed_even_if_the_name_differs(conn, cc):
    _task(conn, BOTOX)
    n = cc.confirm_photo_tasks(conn, PHONE, DAY, '', 'Ціна вручну', 1000, TS)

    assert n == 1
    assert _rows(conn)[BOTOX][0] == 'confirmed'


@pytest.mark.parametrize('fname', ['bot.py', 'pwa_api.py'])
def test_no_raw_date_wide_photo_tasks_confirm_left(fname):
    """Три місця підтвердження мають іти через confirm_photo_tasks, а не сирий UPDATE."""
    with open(os.path.join(ZADARMA, fname), encoding='utf-8') as fh:
        src = fh.read()
    assert not re.search(r"UPDATE photo_tasks SET cashback_status='confirmed'", src)
    assert 'confirm_photo_tasks' in src
