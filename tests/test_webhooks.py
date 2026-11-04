"""
Tests for incoming webhook/callback endpoints:
  - /api/deposit/callback (WayForPay HMAC)
  - WLaunch webhook (if any)
These never require Bearer auth — they're called by third-party services.
"""
import hashlib
import hmac
import json
import time
import sqlite3
import pytest
from conftest import _pwa


def _wfp_sig(merchant_secret: str, *fields) -> str:
    """Compute WayForPay HMAC-MD5 signature."""
    data = ';'.join(str(f) for f in fields)
    return hmac.new(merchant_secret.encode(), data.encode(), hashlib.md5).hexdigest()


# ── /api/deposit/callback ─────────────────────────────────────────────────

def test_deposit_callback_missing_body(client):
    rv = client.post('/api/deposit/callback', json={})
    assert rv.status_code in (400, 200)  # WayForPay expects 200 even on reject


def test_deposit_callback_invalid_signature(client):
    payload = {
        'merchantAccount': 'test_merchant',
        'orderReference': 'TEST-001',
        'amount': '5',
        'currency': 'EUR',
        'authCode': '1234',
        'cardPan': '4111...',
        'transactionStatus': 'Approved',
        'reasonCode': '1100',
        'merchantSignature': 'badsignature',
    }
    rv = client.post('/api/deposit/callback', json=payload)
    # Invalid sig → must not process but also not 500
    assert rv.status_code in (200, 400, 403)


def _seed_pending_deposit(pwa, order_id, phone='380991000001'):
    conn = sqlite3.connect(pwa.DB_PATH)
    conn.execute(
        "INSERT INTO deposits (order_id, phone, amount_eur, amount_uah, status)"
        " VALUES (?,?,5,0,'pending')", (order_id, phone))
    conn.commit()
    conn.close()


def _deposit_status(pwa, order_id):
    conn = sqlite3.connect(pwa.DB_PATH)
    row = conn.execute('SELECT status FROM deposits WHERE order_id=?', (order_id,)).fetchone()
    conn.close()
    return row[0] if row else None


def _wfp_payload(order_id, status='Approved', sig=None, amount=5):
    fields = ('test_merchant', order_id, amount, 'EUR', '123456', '411111...', status, '1100')
    return {
        'merchantAccount': fields[0], 'orderReference': order_id, 'amount': amount,
        'currency': 'EUR', 'authCode': '123456', 'cardPan': '411111...',
        'transactionStatus': status, 'reasonCode': '1100',
        'merchantSignature': sig or _wfp_sig('test_secret', *fields),
    }


def test_deposit_callback_valid_signature_approved(client, pwa):
    """Валідний підпис + Approved → депозит підтверджено.

    Раніше тест вставляв рядок у колонку order_ref, якої в проді немає (код
    оновлює WHERE order_id=?), і приймав 'Pending' — тобто проходив, навіть
    якщо оплачений депозит ніколи не застосовувався.
    """
    order_id = 'VALID-{}'.format(int(time.time() * 1000))
    _seed_pending_deposit(pwa, order_id)

    rv = client.post('/api/deposit/callback', json=_wfp_payload(order_id))

    assert rv.status_code == 200
    assert rv.get_json()['status'] == 'accept'
    assert _deposit_status(pwa, order_id) == 'Approved'


def test_deposit_callback_bad_signature_leaves_deposit_unpaid(client, pwa):
    """Підроблений callback не має підтверджувати депозит."""
    order_id = 'FORGED-{}'.format(int(time.time() * 1000))
    _seed_pending_deposit(pwa, order_id)

    rv = client.post('/api/deposit/callback', json=_wfp_payload(order_id, sig='badsignature'))

    assert rv.status_code == 200
    assert rv.get_json()['status'] == 'refuse'
    assert _deposit_status(pwa, order_id) == 'pending'


def test_deposit_callback_declined_is_recorded(client, pwa):
    order_id = 'DECL-{}'.format(int(time.time() * 1000))
    _seed_pending_deposit(pwa, order_id)

    rv = client.post('/api/deposit/callback', json=_wfp_payload(order_id, status='Declined'))

    assert rv.status_code == 200
    assert _deposit_status(pwa, order_id) == 'Declined'


# ── /api/deposit/balance ─────────────────────────────────────────────────

def test_deposit_balance_requires_auth(client):
    rv = client.get('/api/deposit/balance')
    assert rv.status_code == 401


def test_deposit_balance_client(client, client_token):
    rv = client.get('/api/deposit/balance',
                    headers={'Authorization': f'Bearer {client_token}'})
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'deposit' in data or 'balance' in data or 'cashback' in data


def test_deposit_balance_admin_phone_query(client, admin_token):
    """Admin can query balance for specific phone."""
    rv = client.get('/api/deposit/balance?phone=380991234567',
                    headers={'Authorization': f'Bearer {admin_token}'})
    assert rv.status_code == 200


# ── /api/push/vapid-key ───────────────────────────────────────────────────

def test_vapid_key_public(client):
    rv = client.get('/api/push/vapid-key')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'key' in data or 'publicKey' in data or 'vapid_key' in data


# ── /api/push/subscribe ───────────────────────────────────────────────────

def test_push_subscribe_requires_auth(client):
    rv = client.post('/api/push/subscribe', json={})
    assert rv.status_code == 401


def test_push_subscribe_valid(client, client_token):
    # Endpoint expects {'subscription': {<Web Push object>}}
    payload = {
        'subscription': {
            'endpoint': 'https://fcm.googleapis.com/test/endpoint',
            'keys': {'p256dh': 'test_p256dh', 'auth': 'test_auth'},
        }
    }
    rv = client.post('/api/push/subscribe', json=payload,
                     headers={'Authorization': f'Bearer {client_token}'})
    # 200 if push_ok (mocked), 503 if push_ok=False
    assert rv.status_code in (200, 201, 503)
