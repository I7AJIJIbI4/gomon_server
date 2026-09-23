"""
Regression tests for the 23.09.2026 audit findings.

Covered here (HTTP / pwa_api level):
  1. ProxyFix — the localhost guard on internal endpoints accepted public
     traffic, because behind nginx every request has remote_addr 127.0.0.1.
  2. NULL first_name/last_name crashed three routes with TypeError.
  6. Unguarded int() on query/body params returned 500 on garbage input.
  7. _check_overlap kept a NO_SHOW appointment holding the slot.
  8. WayForPay signature compared with != instead of hmac.compare_digest.

The appointment-collection findings (3, 4, 5) live in
test_appt_time_minutes.py, next to the loader they need.
"""
import sqlite3
import pytest

from conftest import auth, _insert_session


# ── 1. ProxyFix: internal endpoints are internal again ────────────────────

INTERNAL_GET = '/api/internal/free-gaps-today?specialist=victoria'


def test_internal_endpoint_rejects_public_client(client):
    """A request forwarded by nginx carries X-Forwarded-For — must be 403."""
    r = client.get(INTERNAL_GET,
                   headers={'X-Forwarded-For': '203.0.113.9'},
                   environ_base={'REMOTE_ADDR': '127.0.0.1'})
    assert r.status_code == 403
    assert r.get_json()['error'] == 'forbidden'


def test_internal_endpoint_still_open_to_direct_localhost(client):
    """chat.php hits 127.0.0.1:5001 directly and sends no XFF — must pass."""
    r = client.get(INTERNAL_GET, environ_base={'REMOTE_ADDR': '127.0.0.1'})
    assert r.status_code != 403


def test_proxyfix_uses_last_forwarded_hop(client):
    """nginx appends the real IP, so a spoofed XFF chain must not help."""
    r = client.get(INTERNAL_GET,
                   headers={'X-Forwarded-For': '127.0.0.1, 203.0.113.9'},
                   environ_base={'REMOTE_ADDR': '127.0.0.1'})
    assert r.status_code == 403


@pytest.mark.parametrize('path', [
    '/api/deposit/reconcile',
    '/api/deposit/create-internal',
    '/api/chat/cancel-appointment',
])
def test_internal_post_endpoints_reject_public_client(client, path):
    r = client.post(path, json={},
                    headers={'X-Forwarded-For': '203.0.113.9'},
                    environ_base={'REMOTE_ADDR': '127.0.0.1'})
    assert r.status_code == 403


# ── 2. NULL name must not 500 ─────────────────────────────────────────────

NULL_NAME_PHONE = '380991110022'


@pytest.fixture
def client_with_null_name(pwa):
    """45 real clients have NULL first_name or last_name (WLaunch imports)."""
    conn = sqlite3.connect(pwa.DB_PATH)
    conn.execute(
        'INSERT OR REPLACE INTO clients (id, phone, first_name, last_name, services_json)'
        ' VALUES (?,?,NULL,NULL,?)',
        (NULL_NAME_PHONE, NULL_NAME_PHONE, '[]')
    )
    conn.commit()
    conn.close()
    return _insert_session(NULL_NAME_PHONE)


def test_cancel_appointment_survives_null_name(client, client_with_null_name):
    r = client.post('/api/me/appointments/cancel',
                    json={'date': '2026-09-30'},
                    headers=auth(client_with_null_name))
    assert r.status_code != 500


def test_deposit_create_survives_null_name(client, client_with_null_name):
    r = client.post('/api/deposit/create',
                    json={'amount': 500},
                    headers=auth(client_with_null_name))
    assert r.status_code != 500


def test_chat_cancel_survives_null_name(client):
    """Internal route — call it the way chat.php does, with no XFF."""
    r = client.post('/api/chat/cancel-appointment',
                    json={'phone': NULL_NAME_PHONE, 'date': '2026-09-30'},
                    environ_base={'REMOTE_ADDR': '127.0.0.1'})
    assert r.status_code != 500


# ── 6. Garbage numeric params ─────────────────────────────────────────────

def test_notif_history_rejects_garbage_days(client, admin_token):
    r = client.get('/api/admin/notifications/history?days=abc',
                   headers=auth(admin_token))
    assert r.status_code != 500


def test_messages_thread_rejects_garbage_limit(client, admin_token):
    r = client.get('/api/admin/messages/ig_test?limit=NaN',
                   headers=auth(admin_token))
    assert r.status_code != 500


def test_int_param_helper(pwa):
    assert pwa._int_param('7', 1) == 7
    assert pwa._int_param('abc', 1) == 1
    assert pwa._int_param(None, 5) == 5
    assert pwa._int_param(3, 1) == 3


# ── 7. NO_SHOW must not hold the slot ─────────────────────────────────────

def test_no_show_does_not_block_slot(pwa, tmp_path):
    db = str(tmp_path / 'overlap.db')
    conn = sqlite3.connect(db)
    conn.execute(
        'CREATE TABLE manual_appointments (id INTEGER PRIMARY KEY, specialist TEXT,'
        ' date TEXT, time TEXT, duration INTEGER, status TEXT)'
    )
    conn.execute('CREATE TABLE clients (phone TEXT, services_json TEXT)')
    conn.execute(
        'CREATE TABLE specialist_breaks (id INTEGER PRIMARY KEY, specialist TEXT,'
        ' date TEXT, time_from TEXT, time_to TEXT)'
    )
    conn.execute(
        "INSERT INTO manual_appointments VALUES (1,'victoria','2026-09-30','10:00',60,'NO_SHOW')"
    )
    conn.commit()
    try:
        assert pwa._check_overlap(conn, 'victoria', '2026-09-30', 600, 660) is False
    finally:
        conn.close()


def test_confirmed_appointment_still_blocks_slot(pwa, tmp_path):
    db = str(tmp_path / 'overlap2.db')
    conn = sqlite3.connect(db)
    conn.execute(
        'CREATE TABLE manual_appointments (id INTEGER PRIMARY KEY, specialist TEXT,'
        ' date TEXT, time TEXT, duration INTEGER, status TEXT)'
    )
    conn.execute('CREATE TABLE clients (phone TEXT, services_json TEXT)')
    conn.execute(
        'CREATE TABLE specialist_breaks (id INTEGER PRIMARY KEY, specialist TEXT,'
        ' date TEXT, time_from TEXT, time_to TEXT)'
    )
    conn.execute(
        "INSERT INTO manual_appointments VALUES (1,'victoria','2026-09-30','10:00',60,'CONFIRMED')"
    )
    conn.commit()
    try:
        assert pwa._check_overlap(conn, 'victoria', '2026-09-30', 600, 660) is True
    finally:
        conn.close()


# ── 8. Signature check is constant-time and still rejects forgeries ───────

def test_deposit_callback_rejects_bad_signature(client):
    r = client.post('/api/deposit/callback', json={
        'merchantAccount': 'x', 'orderReference': 'dep_test_1',
        'amount': '500', 'currency': 'UAH', 'authCode': '',
        'transactionStatus': 'Approved', 'reasonCode': '1100',
        'merchantSignature': 'deadbeef',
    })
    assert r.status_code == 200
    assert r.get_json()['status'] == 'refuse'
