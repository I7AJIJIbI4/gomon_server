"""
Tests for OTP auth flow: send-otp, verify, /api/me, session expiry.
External calls (sms_fly.send_sms, TG) are mocked by conftest sys.modules.
"""
import json
import sqlite3
import time
import secrets
import pytest
from unittest.mock import patch, MagicMock

from conftest import auth, _insert_session, _pwa


# ── /api/auth/send-otp ────────────────────────────────────────────────────

def test_send_otp_missing_phone(client):
    rv = client.post('/api/auth/send-otp', json={})
    assert rv.status_code == 400


def test_send_otp_invalid_phone(client):
    rv = client.post('/api/auth/send-otp', json={'phone': 'notaphone'})
    assert rv.status_code in (400, 422)


def test_send_otp_new_client(client):
    """For an unknown phone the OTP should still be sent (guest)."""
    with patch.object(_pwa, '_req') as mock_req:
        mock_req.post.return_value = MagicMock(status_code=200, json=lambda: {})
        rv = client.post('/api/auth/send-otp', json={'phone': '0501111111'})
    # Either 200 (sent) or 429 (rate limit if run multiple times) but not 500
    assert rv.status_code in (200, 429)


def test_send_otp_rate_limit(client):
    """Sending OTP more than 3 times in the window should hit 429."""
    phone = '0502222222'
    with patch.object(_pwa, '_req') as mock_req:
        mock_req.post.return_value = MagicMock(status_code=200, json=lambda: {})
        for _ in range(3):
            client.post('/api/auth/send-otp', json={'phone': phone})
        rv = client.post('/api/auth/send-otp', json={'phone': phone})
    assert rv.status_code == 429


# ── /api/auth/verify ─────────────────────────────────────────────────────

def _store_otp(raw_phone, code, ttl=300, attempts=0):
    """Код кладемо під нормалізованим номером — саме так його шукає verify.

    Під сирим '050…' (як було) verify відповідав code_not_found, і тести на
    неправильний та прострочений код ніколи не доходили до своїх перевірок.
    """
    from user_db import normalize_phone
    phone = normalize_phone(raw_phone)
    conn = sqlite3.connect(_pwa.OTP_DB)
    conn.execute(
        'INSERT OR REPLACE INTO otp_codes (phone, code, expires_at, attempts) VALUES (?,?,?,?)',
        (phone, code, int(time.time()) + ttl, attempts)
    )
    conn.commit()
    conn.close()
    return phone


def _attempts(phone):
    conn = sqlite3.connect(_pwa.OTP_DB)
    row = conn.execute('SELECT attempts FROM otp_codes WHERE phone=?', (phone,)).fetchone()
    conn.close()
    return row[0] if row else None


def test_verify_wrong_code(client):
    phone = _store_otp('0503333333', '123456')
    rv = client.post('/api/auth/verify', json={'phone': '0503333333', 'code': '000000'})
    assert rv.status_code == 400
    assert rv.get_json()['error'] == 'wrong_code'
    assert _attempts(phone) == 1


def test_verify_expired_code(client):
    _store_otp('0504444444', '999999', ttl=-10)
    rv = client.post('/api/auth/verify', json={'phone': '0504444444', 'code': '999999'})
    assert rv.status_code == 400
    assert rv.get_json()['error'] == 'code_expired'


def test_verify_locks_after_five_attempts(client):
    """Навіть правильний код після 5 невдалих спроб не пускає — інакше OTP перебирається."""
    _store_otp('0506666666', '424242', attempts=5)
    rv = client.post('/api/auth/verify', json={'phone': '0506666666', 'code': '424242'})
    assert rv.status_code == 429
    assert rv.get_json()['error'] == 'too_many_attempts'


def test_verify_correct_code(client):
    raw_phone = '0505555555'
    # pwa_api normalizes phone in verify endpoint — insert with the normalized form
    from user_db import normalize_phone
    phone = normalize_phone(raw_phone)  # '380505555555'
    code = '777777'
    conn = sqlite3.connect(_pwa.OTP_DB)
    conn.execute(
        'INSERT OR REPLACE INTO otp_codes (phone, code, expires_at, attempts) VALUES (?,?,?,?)',
        (phone, code, int(time.time()) + 300, 0)
    )
    conn.commit()
    conn.close()

    rv = client.post('/api/auth/verify', json={'phone': raw_phone, 'code': code})
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'token' in data


def test_verify_pin_auth(client):
    """PIN_AUTH bypass: phone + correct PIN should return a token."""
    rv = client.post('/api/auth/verify', json={
        'phone': '380000000001',
        'code': '1234',
    })
    assert rv.status_code == 200
    assert rv.get_json().get('token')


def test_verify_pin_auth_wrong_pin(client):
    rv = client.post('/api/auth/verify', json={'phone': '380000000001', 'code': '9999'})
    assert rv.status_code == 400
    assert rv.get_json()['error'] == 'wrong_code'


# ── /api/me ───────────────────────────────────────────────────────────────

def test_me_no_auth(client):
    rv = client.get('/api/me')
    assert rv.status_code == 401


def test_me_invalid_token(client):
    rv = client.get('/api/me', headers=auth('badtoken'))
    assert rv.status_code == 401


def test_me_valid_client(client, client_token):
    rv = client.get('/api/me', headers=auth(client_token))
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'phone' in data
    assert data.get('is_admin') is False


def test_me_valid_admin(client, admin_token):
    rv = client.get('/api/me', headers=auth(admin_token))
    assert rv.status_code == 200
    data = rv.get_json()
    assert data.get('is_admin') is True
    assert data.get('admin_role') == 'full'


def test_me_superadmin(client, superadmin_token):
    rv = client.get('/api/me', headers=auth(superadmin_token))
    assert rv.status_code == 200
    data = rv.get_json()
    assert data.get('admin_role') == 'superadmin'


def test_me_specialist(client, specialist_token):
    rv = client.get('/api/me', headers=auth(specialist_token))
    assert rv.status_code == 200
    data = rv.get_json()
    assert data.get('admin_role') == 'specialist'


def test_me_expired_session(client):
    """Expired session should return 401."""
    token = secrets.token_hex(32)
    conn = sqlite3.connect(_pwa.OTP_DB)
    conn.execute(
        'INSERT OR REPLACE INTO sessions (token, phone, created_at, expires_at) VALUES (?,?,?,?)',
        (token, '380991000000', int(time.time()) - 100, int(time.time()) - 10)
    )
    conn.commit()
    conn.close()

    rv = client.get('/api/me', headers=auth(token))
    assert rv.status_code == 401
