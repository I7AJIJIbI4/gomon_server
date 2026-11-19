# -*- coding: utf-8 -*-
"""
/api/deposit/reconcile: старі pending і тривога на поламаний ключ WayForPay.

З 01.09 по 19.11.2026 ключ у config.py не відповідав мерчанту: WayForPay на кожен
платіж і CHECK_STATUS відповідав 1113 Invalid signature, і ніхто цього не бачив.
reconcile дивився лише на добу назад, тож замовлення клієнтів висіли pending.
"""
import sqlite3

import pytest


class _Resp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


@pytest.fixture
def wfp(pwa, monkeypatch, tmp_path):
    """Підміняє WayForPay і Telegram; повертає список TG-повідомлень і setter відповіді."""
    state = {'reply': {'transactionStatus': 'Approved', 'amount': 3000, 'reasonCode': 1100}}
    tg = []
    checked = []

    def _post(url, json=None, **kw):
        if 'api.telegram.org' in url:
            tg.append(json['text'])
            return _Resp({'ok': True})
        checked.append(json['orderReference'])
        return _Resp(state['reply'])

    monkeypatch.setattr(pwa._req, 'post', _post)
    monkeypatch.setattr(pwa, 'WFP_SIGNATURE_FLAG', str(tmp_path / 'wfp_bad.flag'))

    conn = sqlite3.connect(pwa.DB_PATH)
    conn.execute("DELETE FROM deposits WHERE order_id LIKE 'rec_%'")
    conn.commit()
    conn.close()

    state['tg'] = tg
    state['checked'] = checked
    yield state

    conn = sqlite3.connect(pwa.DB_PATH)
    conn.execute("DELETE FROM deposits WHERE order_id LIKE 'rec_%'")
    conn.commit()
    conn.close()


def _deposit(pwa, order_id, age_days, status='pending'):
    conn = sqlite3.connect(pwa.DB_PATH)
    conn.execute(
        "INSERT INTO deposits (phone, amount_eur, amount_uah, order_id, status, created_at)"
        " VALUES ('380631234519', 0, 3000, ?, ?, datetime('now', ?))",
        (order_id, status, '-{} days'.format(age_days)))
    conn.commit()
    conn.close()


def _status(pwa, order_id):
    conn = sqlite3.connect(pwa.DB_PATH)
    v = conn.execute('SELECT status FROM deposits WHERE order_id=?', (order_id,)).fetchone()[0]
    conn.close()
    return v


def _reconcile(client):
    r = client.post('/api/deposit/reconcile')
    assert r.status_code == 200
    return r.get_json()


def test_pending_from_weeks_ago_is_still_reconciled(pwa, client, wfp):
    """Раніше дивились лише на добу: жовтневі замовлення не перевірялись ніколи."""
    _deposit(pwa, 'rec_old', 47)
    _reconcile(client)

    assert 'rec_old' in wfp['checked']
    assert _status(pwa, 'rec_old') == 'Approved'


def test_pending_beyond_90_days_is_left_alone(pwa, client, wfp):
    _deposit(pwa, 'rec_ancient', 120)
    _reconcile(client)

    assert 'rec_ancient' not in wfp['checked']
    assert _status(pwa, 'rec_ancient') == 'pending'


def test_invalid_signature_alerts_admin_once(pwa, client, wfp):
    wfp['reply'] = {'reason': 'Invalid signature', 'reasonCode': 1113}
    _deposit(pwa, 'rec_a', 0)
    _deposit(pwa, 'rec_b', 1)
    _reconcile(client)
    _reconcile(client)

    assert len(wfp['tg']) == 1
    assert '1113' in wfp['tg'][0] and 'config.py' in wfp['tg'][0]
    assert _status(pwa, 'rec_a') == 'pending'


def test_alert_fires_again_after_the_key_was_fixed_and_broke_again(pwa, client, wfp):
    wfp['reply'] = {'reason': 'Invalid signature', 'reasonCode': 1113}
    _deposit(pwa, 'rec_a', 0)
    _reconcile(client)

    wfp['reply'] = {'reason': 'Ok', 'reasonCode': 1100, 'transactionStatus': 'InProcessing'}
    _reconcile(client)

    wfp['reply'] = {'reason': 'Invalid signature', 'reasonCode': '1113'}
    _reconcile(client)

    assert len(wfp['tg']) == 2


def test_no_alert_when_the_signature_is_accepted(pwa, client, wfp):
    _deposit(pwa, 'rec_a', 0)
    _reconcile(client)

    assert wfp['tg'] == []
