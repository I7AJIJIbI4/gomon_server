# -*- coding: utf-8 -*-
"""
Гроші клієнта: депозит і кешбек.

Три адмінські маршрути рухають баланс:
  - POST /api/admin/deposit/add-cash   — клієнт заплатив готівкою
  - POST /api/admin/deposit/deduct     — оплата процедури з депозиту
  - POST /api/admin/cashback/redeem    — списання кешбеку (від 500 грн разом)

Баланс ніде не зберігається, він щоразу рахується з таблиць:
  депозит = Approved deposits.amount_uah − deductions (reason NOT LIKE 'cashback%')
  кешбек  = cashback.amount − deductions (reason LIKE 'cashback%')
Тож кожен тест звіряє результат із /api/deposit/balance — тим, що бачить клієнт.

Усе на справжньому SQLite (тестова схема = продова), без моків бази.
"""
import sqlite3
import itertools

import pytest

from conftest import auth, load_real

_seq = itertools.count(1)


def _phone():
    """Свій номер на кожен тест: база спільна на сесію."""
    return '38050{:07d}'.format(700000 + next(_seq))


def _q(pwa, sql, args=()):
    conn = sqlite3.connect(pwa.DB_PATH)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _deposit(pwa, phone, uah, status='Approved'):
    conn = sqlite3.connect(pwa.DB_PATH)
    conn.execute("INSERT INTO deposits (phone, amount_eur, amount_uah, order_id, status)"
                 " VALUES (?,5,?,?,?)", (phone, uah, 'ord-{}-{}'.format(phone, next(_seq)), status))
    conn.commit()
    conn.close()


def _cashback(pwa, phone, amount):
    conn = sqlite3.connect(pwa.DB_PATH)
    conn.execute("INSERT INTO cashback (phone, amount, procedure_name, appt_date) VALUES (?,?,?,?)",
                 (phone, amount, 'Процедура {}'.format(next(_seq)), '2026-10-01'))
    conn.commit()
    conn.close()


def _balance(client, admin_token, phone):
    rv = client.get('/api/deposit/balance?phone={}'.format(phone), headers=auth(admin_token))
    assert rv.status_code == 200
    d = rv.get_json()
    return d['deposit_balance'], d['cashback_balance']


def _deductions(pwa, phone):
    return _q(pwa, 'SELECT amount, reason, deducted_by FROM deposit_deductions WHERE phone=? ORDER BY id',
              (phone,))


@pytest.fixture
def real_loyalty(pwa, monkeypatch):
    """Справжній loyalty.py на тестовій базі — redeem після коміту рахує рівень."""
    mod = load_real('loyalty_money_real', 'loyalty.py', db_path=pwa.DB_PATH)
    monkeypatch.setitem(sys_modules(), 'loyalty', mod)
    monkeypatch.setattr(pwa, '_get_client_tier', mod.get_client_tier)
    return mod


def sys_modules():
    import sys
    return sys.modules


@pytest.fixture
def notified(monkeypatch):
    """Повідомлення клієнту після списання кешбеку — синхронно і в список."""
    import sys
    import threading
    sent = []
    monkeypatch.setattr(sys.modules['notifier'], 'notify_client',
                        lambda phone, tg, sms, **kw: sent.append((phone, tg, sms, kw)), raising=False)
    monkeypatch.setattr(sys.modules['notifier'], '_first_name',
                        lambda *a, **kw: 'Олена', raising=False)

    class _Now(object):
        def __init__(self, target=None, args=(), kwargs=None, daemon=None):
            self._t, self._a, self._k = target, args, kwargs or {}

        def start(self):
            self._t(*self._a, **self._k)
    monkeypatch.setattr(threading, 'Thread', _Now)
    return sent


ROUTES = ['/api/admin/deposit/add-cash', '/api/admin/deposit/deduct', '/api/admin/cashback/redeem']


# ── Доступ ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('route', ROUTES)
def test_money_routes_require_auth(client, route):
    assert client.post(route, json={'phone': _phone(), 'amount': 100}).status_code == 401


@pytest.mark.parametrize('route', ROUTES)
def test_client_cannot_move_money(client, client_token, pwa, route):
    """Клієнт не може сам собі ні поповнити, ні списати."""
    phone = _phone()
    rv = client.post(route, json={'phone': phone, 'amount': 100}, headers=auth(client_token))
    assert rv.status_code == 403
    assert _deductions(pwa, phone) == []
    assert _q(pwa, 'SELECT 1 FROM deposits WHERE phone=?', (phone,)) == []


@pytest.mark.parametrize('route', ROUTES)
@pytest.mark.parametrize('amount', [0, -100, 'abc', '', None])
def test_bad_amount_moves_nothing(client, admin_token, pwa, route, amount):
    phone = _phone()
    _deposit(pwa, phone, 1000)
    _cashback(pwa, phone, 600)
    rv = client.post(route, json={'phone': phone, 'amount': amount}, headers=auth(admin_token))
    assert rv.status_code == 400
    assert _deductions(pwa, phone) == []
    assert len(_q(pwa, 'SELECT 1 FROM deposits WHERE phone=?', (phone,))) == 1


# ── Готівка ───────────────────────────────────────────────────────────────────

def test_add_cash_tops_up_the_deposit(client, admin_token, pwa):
    phone = _phone()
    _deposit(pwa, phone, 200)
    rv = client.post('/api/admin/deposit/add-cash', json={'phone': phone, 'amount': 500},
                     headers=auth(admin_token))
    assert rv.status_code == 200
    assert rv.get_json()['new_balance'] == 700
    (row,) = _q(pwa, "SELECT amount_uah, status, wfp_transaction_status, order_id FROM deposits"
                     " WHERE phone=? AND order_id LIKE 'cash_%'", (phone,))
    assert row[:3] == (500, 'Approved', 'cash')
    assert _balance(client, admin_token, phone) == (700, 0)


def test_add_cash_normalises_the_phone(client, admin_token, pwa):
    """0XX… з форми адміна і 380XX… з бази мають бути одним клієнтом."""
    phone = _phone()
    rv = client.post('/api/admin/deposit/add-cash', json={'phone': '0' + phone[3:], 'amount': 300},
                     headers=auth(admin_token))
    assert rv.status_code == 200
    assert _balance(client, admin_token, phone) == (300, 0)


def test_specialist_can_take_cash(client, specialist_token, admin_token, pwa):
    phone = _phone()
    rv = client.post('/api/admin/deposit/add-cash', json={'phone': phone, 'amount': 400},
                     headers=auth(specialist_token))
    assert rv.status_code == 200
    assert _balance(client, admin_token, phone) == (400, 0)


def test_add_cash_is_all_or_nothing(client, admin_token, pwa, monkeypatch):
    """Збій читання балансу не має лишати внесену готівку при помилці для адміна:
    інакше повторне натискання вносить удруге (виправлено 04.11.2026)."""
    phone = _phone()
    real = pwa._get_deposit_balance

    def _locked(p, conn=None):
        raise sqlite3.OperationalError('database is locked')
    monkeypatch.setattr(pwa, '_get_deposit_balance', _locked)
    try:
        status = client.post('/api/admin/deposit/add-cash', json={'phone': phone, 'amount': 500},
                             headers=auth(admin_token)).status_code
    except sqlite3.OperationalError:
        status = 500          # тестовий клієнт прокидає виняток; у проді це 500
    assert status != 200
    assert _q(pwa, 'SELECT 1 FROM deposits WHERE phone=?', (phone,)) == [], 'помилка, а гроші внесено'

    monkeypatch.setattr(pwa, '_get_deposit_balance', real)
    rv = client.post('/api/admin/deposit/add-cash', json={'phone': phone, 'amount': 500},
                     headers=auth(admin_token))
    assert rv.get_json()['new_balance'] == 500
    assert _balance(client, admin_token, phone) == (500, 0), 'повтор вніс рівно один раз'


@pytest.mark.parametrize('route', ROUTES)
@pytest.mark.parametrize('amount', ['inf', '-inf', 'nan', 'Infinity'])
def test_non_finite_amount_moves_nothing(client, admin_token, pwa, route, amount):
    """float('inf') проходив amount<=0: add-cash робив депозит нескінченним, а NaN
    давав 500 на NOT NULL (виправлено 04.11.2026)."""
    phone = _phone()
    _deposit(pwa, phone, 1000)
    _cashback(pwa, phone, 600)
    rv = client.post(route, json={'phone': phone, 'amount': amount}, headers=auth(admin_token))
    assert rv.status_code == 400
    assert _deductions(pwa, phone) == []
    assert _balance(client, admin_token, phone) == (1000, 600)


# ── Оплата з депозиту ─────────────────────────────────────────────────────────

def test_deduct_pays_from_the_deposit(client, admin_token, pwa):
    phone = _phone()
    _deposit(pwa, phone, 1000)
    _cashback(pwa, phone, 600)
    rv = client.post('/api/admin/deposit/deduct',
                     json={'phone': phone, 'amount': 300, 'reason': 'Оплата процедури'},
                     headers=auth(admin_token))
    assert rv.status_code == 200
    assert rv.get_json()['new_balance'] == 700
    assert _deductions(pwa, phone) == [(300, 'Оплата процедури', '380996093860')]
    assert _balance(client, admin_token, phone) == (700, 600), 'кешбек не чіпаємо'


def test_deduct_cannot_overdraw(client, admin_token, pwa):
    phone = _phone()
    _deposit(pwa, phone, 500)
    rv = client.post('/api/admin/deposit/deduct', json={'phone': phone, 'amount': 501},
                     headers=auth(admin_token))
    assert rv.status_code == 400
    assert rv.get_json() == {'error': 'insufficient', 'balance': 500}
    assert _deductions(pwa, phone) == []


@pytest.mark.parametrize('status', ['pending', 'Declined', 'Expired'])
def test_unpaid_deposits_are_not_spendable(client, admin_token, pwa, status):
    """Неоплачений WayForPay-депозит не дає грошей на балансі."""
    phone = _phone()
    _deposit(pwa, phone, 1000, status=status)
    rv = client.post('/api/admin/deposit/deduct', json={'phone': phone, 'amount': 100},
                     headers=auth(admin_token))
    assert rv.status_code == 400
    assert _balance(client, admin_token, phone) == (0, 0)


def test_deposit_is_spent_down_to_zero_and_no_further(client, admin_token, pwa):
    phone = _phone()
    _deposit(pwa, phone, 1000)
    for _ in range(2):
        assert client.post('/api/admin/deposit/deduct', json={'phone': phone, 'amount': 500},
                           headers=auth(admin_token)).status_code == 200
    rv = client.post('/api/admin/deposit/deduct', json={'phone': phone, 'amount': 1},
                     headers=auth(admin_token))
    assert rv.status_code == 400
    assert _balance(client, admin_token, phone) == (0, 0)


@pytest.mark.parametrize('reason', ['cashback за минулий візит', 'Cashback', 'CASHBACK_REDEEM'])
def test_deduct_reason_text_cannot_redirect_to_cashback(client, admin_token, pwa, reason):
    """Тип списання визначається за reason LIKE 'cashback%' (без урахування регістру);
    оплата з депозиту з такою причиною списувала кешбек (виправлено 04.11.2026)."""
    phone = _phone()
    _deposit(pwa, phone, 1000)
    _cashback(pwa, phone, 600)
    rv = client.post('/api/admin/deposit/deduct',
                     json={'phone': phone, 'amount': 300, 'reason': reason},
                     headers=auth(admin_token))
    assert rv.status_code == 200
    assert _balance(client, admin_token, phone) == (700, 600)
    assert _deductions(pwa, phone)[0][1] == 'депозит: ' + reason, 'текст адміна збережено'


# ── Кешбек ────────────────────────────────────────────────────────────────────

def test_redeem_spends_cashback_and_tells_the_client(client, admin_token, pwa,
                                                     real_loyalty, notified):
    phone = _phone()
    _cashback(pwa, phone, 600)
    _deposit(pwa, phone, 1000)
    rv = client.post('/api/admin/cashback/redeem', json={'phone': phone, 'amount': 200},
                     headers=auth(admin_token))
    assert rv.status_code == 200, rv.get_data(as_text=True)
    assert rv.get_json() == {'ok': True, 'new_cashback_balance': 400}
    assert _deductions(pwa, phone) == [(200, 'cashback_redeem', '380996093860')]
    assert _balance(client, admin_token, phone) == (1000, 400), 'депозит не чіпаємо'

    (to, tg, sms, kw) = notified[0]
    assert to == phone
    assert 'списано 200 грн кешбеку' in sms
    assert 'Залишок: 1400 грн' in sms          # депозит + кешбек, що лишились


def test_redeem_below_500_total_is_refused(client, admin_token, pwa, real_loyalty, notified):
    phone = _phone()
    _cashback(pwa, phone, 300)
    rv = client.post('/api/admin/cashback/redeem', json={'phone': phone, 'amount': 100},
                     headers=auth(admin_token))
    assert rv.status_code == 400
    assert rv.get_json()['error'] == 'min_not_reached'
    assert _deductions(pwa, phone) == []
    assert notified == []


def test_deposit_counts_towards_the_500_minimum(client, admin_token, pwa, real_loyalty, notified):
    phone = _phone()
    _cashback(pwa, phone, 200)
    _deposit(pwa, phone, 300)
    rv = client.post('/api/admin/cashback/redeem', json={'phone': phone, 'amount': 200},
                     headers=auth(admin_token))
    assert rv.status_code == 200
    assert _balance(client, admin_token, phone) == (300, 0)


def test_redeem_cannot_take_more_than_the_cashback(client, admin_token, pwa, real_loyalty, notified):
    """Великий депозит не дає списати кешбеку більше, ніж нараховано."""
    phone = _phone()
    _cashback(pwa, phone, 100)
    _deposit(pwa, phone, 5000)
    rv = client.post('/api/admin/cashback/redeem', json={'phone': phone, 'amount': 101},
                     headers=auth(admin_token))
    assert rv.status_code == 400
    assert rv.get_json() == {'error': 'insufficient', 'cashback_balance': 100}
    assert _deductions(pwa, phone) == []


def test_repeated_redeem_cannot_overspend(client, admin_token, pwa, real_loyalty, notified):
    """Подвійне натискання: другий раз грошей уже немає."""
    phone = _phone()
    _cashback(pwa, phone, 600)
    first = client.post('/api/admin/cashback/redeem', json={'phone': phone, 'amount': 400},
                        headers=auth(admin_token))
    second = client.post('/api/admin/cashback/redeem', json={'phone': phone, 'amount': 400},
                         headers=auth(admin_token))
    assert first.status_code == 200
    assert second.status_code == 400
    assert sum(a for a, _, _ in _deductions(pwa, phone)) == 400


def test_redeem_reports_success_if_money_was_taken(client, admin_token, pwa, monkeypatch, notified):
    """Списання комітиться до підрахунку рівня й повідомлення. Якщо ті падають, адмін
    має побачити успіх — інакше натисне ще раз і спише вдруге (виправлено 04.11.2026)."""
    phone = _phone()
    _cashback(pwa, phone, 600)

    def _boom(phone):
        raise sqlite3.OperationalError('database is locked')
    monkeypatch.setattr(pwa, '_get_client_tier', _boom)
    try:
        status = client.post('/api/admin/cashback/redeem', json={'phone': phone, 'amount': 200},
                             headers=auth(admin_token)).status_code
    except sqlite3.OperationalError:
        status = 500          # тестовий клієнт прокидає виняток; у проді це 500 для адміна
    taken = sum(a for a, _, _ in _deductions(pwa, phone))
    assert taken == 200, 'гроші списано до збою'
    assert status == 200, 'адмін бачить помилку при вже списаних грошах'
