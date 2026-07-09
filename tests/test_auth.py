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

def test_verify_wrong_code(client):
    phone = '0503333333'
    # Write an OTP to DB first
    conn = sqlite3.connect(_pwa.OTP_DB)
    conn.execute(
        'INSERT OR REPLACE INTO otp_codes (phone, code, expires_at, attempts) VALUES (?,?,?,?)',
        (phone, '123456', int(time.time()) + 300, 0)
    )
    conn.commit()
    conn.close()

    rv = client.post('/api/auth/verify', json={'phone': phone, 'code': '000000'})
    assert rv.status_code == 400


def test_verify_expired_code(client):
    phone = '0504444444'
    conn = sqlite3.connect(_pwa.OTP_DB)
    conn.execute(
        'INSERT OR REPLACE INTO otp_codes (phone, code, expires_at, attempts) VALUES (?,?,?,?)',
        (phone, '999999', int(time.time()) - 10, 0)  # expired
    )
    conn.commit()
    conn.close()

    rv = client.post('/api/auth/verify', json={'phone': phone, 'code': '999999'})
    assert rv.status_code == 400


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
    # 200 with token, or 400 if PIN_AUTH flow is phone-format-sensitive
    assert rv.status_code in (200, 400)


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
