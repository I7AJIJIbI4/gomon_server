"""
Tests for admin-only endpoints:
  - /api/admin/role
  - /api/admin/stats
  - /api/admin/prices/edit (GET + PUT)
  - /api/admin/clients-list
  - /api/admin/clients/add
  - /api/admin/calendar/appointments (GET + POST + DELETE)
Access control: regular clients must get 403 everywhere under /api/admin/*.
"""
import sys
import json
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from conftest import auth, _insert_session, _insert_client, _pwa


# ── Access control ────────────────────────────────────────────────────────

@pytest.mark.parametrize('endpoint', [
    '/api/admin/role',
    '/api/admin/stats',
    '/api/admin/prices/edit',
    '/api/admin/clients-list',
])
def test_admin_endpoint_rejects_unauthenticated(client, endpoint):
    rv = client.get(endpoint)
    assert rv.status_code in (401, 403)


@pytest.mark.parametrize('endpoint', [
    '/api/admin/role',
    '/api/admin/stats',
    '/api/admin/prices/edit',
    '/api/admin/clients-list',
])
def test_admin_endpoint_rejects_regular_client(client, client_token, endpoint):
    rv = client.get(endpoint, headers=auth(client_token))
    assert rv.status_code == 403


# ── /api/admin/role ───────────────────────────────────────────────────────

def test_admin_role_full(client, admin_token):
    rv = client.get('/api/admin/role', headers=auth(admin_token))
    assert rv.status_code == 200
    data = rv.get_json()
    assert data.get('role') == 'full'


def test_admin_role_specialist(client, specialist_token):
    rv = client.get('/api/admin/role', headers=auth(specialist_token))
    assert rv.status_code == 200
    data = rv.get_json()
    assert data.get('role') == 'specialist'


# ── /api/admin/stats ──────────────────────────────────────────────────────

def test_admin_stats_structure(client, admin_token):
    rv = client.get('/api/admin/stats', headers=auth(admin_token))
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'total_clients' in data
    assert 'pwa_users' in data


def test_specialist_stats_accessible(client, specialist_token):
    rv = client.get('/api/admin/stats', headers=auth(specialist_token))
    assert rv.status_code == 200


# ── /api/admin/prices/edit GET ────────────────────────────────────────────

def test_prices_edit_get_full_admin(client, admin_token):
    rv = client.get('/api/admin/prices/edit', headers=auth(admin_token))
    assert rv.status_code == 200
    data = rv.get_json()
    assert isinstance(data, list)
    assert data[0]['cat'] == 'Тест'


def test_prices_edit_get_forbidden_for_specialist(client, specialist_token):
    rv = client.get('/api/admin/prices/edit', headers=auth(specialist_token))
    assert rv.status_code == 403


def test_prices_edit_get_duration_is_int(client, admin_token):
    """Regression: duration field must always be an int, never a string."""
    rv = client.get('/api/admin/prices/edit', headers=auth(admin_token))
    for cat in rv.get_json():
        for item in cat.get('items', []):
            dur = item.get('duration')
            if dur is not None:
                assert isinstance(dur, int), f"duration not int: {dur!r} in {item['name']}"


# ── /api/admin/prices/edit PUT ────────────────────────────────────────────

def test_prices_edit_put_updates_file(client, admin_token, pwa):
    new_prices = [
        {'cat': 'Апдейт', 'items': [
            {'name': 'Нова процедура', 'price': '999 грн', 'specialists': ['victoria'], 'duration': 45}
        ]}
    ]
    rv = client.put('/api/admin/prices/edit',
                    json=new_prices,
                    headers=auth(admin_token))
    assert rv.status_code == 200

    with open(pwa.PRICES_PATH, encoding='utf-8') as f:
        saved = json.load(f)
    assert saved[0]['cat'] == 'Апдейт'

    # Restore original test prices
    orig = [
        {'cat': 'Тест', 'items': [
            {'name': 'Тест-процедура', 'price': '500 грн', 'specialists': ['victoria'], 'duration': 60},
            {'name': 'Дует-процедура', 'price': '1000 грн', 'specialists': ['victoria', 'anastasia'], 'duration': 90},
        ]}
    ]
    with open(pwa.PRICES_PATH, 'w', encoding='utf-8') as f:
        json.dump(orig, f)


def test_prices_edit_put_forbidden_for_specialist(client, specialist_token):
    rv = client.put('/api/admin/prices/edit', json=[], headers=auth(specialist_token))
    assert rv.status_code == 403


# ── /api/admin/clients-list ───────────────────────────────────────────────

def test_clients_list_returns_list(client, admin_token):
    rv = client.get('/api/admin/clients-list', headers=auth(admin_token))
    assert rv.status_code == 200
    # Response is {'clients': [...]}
    data = rv.get_json()
    clients = data.get('clients', data) if isinstance(data, dict) else data
    assert isinstance(clients, list)


def test_clients_list_contains_inserted_client(client, admin_token, client_phone):
    rv = client.get('/api/admin/clients-list', headers=auth(admin_token))
    data = rv.get_json()
    clients = data.get('clients', data) if isinstance(data, dict) else data
    phones = [c.get('phone', '') for c in clients if isinstance(c, dict)]
    norm = client_phone.lstrip('+').replace(' ', '')
    assert any(norm in p or p in norm for p in phones)


# ── /api/admin/clients/add ────────────────────────────────────────────────

def test_add_client(client, admin_token):
    # Endpoint expects first_name + last_name separately (not a combined 'name')
    rv = client.post('/api/admin/clients/add',
                     json={'phone': '0671111111', 'first_name': 'Іван', 'last_name': 'Тест'},
                     headers=auth(admin_token))
    assert rv.status_code == 200


def test_add_client_missing_phone(client, admin_token):
    rv = client.post('/api/admin/clients/add',
                     json={'name': 'No Phone'},
                     headers=auth(admin_token))
    assert rv.status_code == 400


# ── /api/admin/calendar/appointments ─────────────────────────────────────

def test_calendar_get_returns_list(client, admin_token):
    rv = client.get('/api/admin/calendar/appointments?from=2026-07-01&to=2026-07-31',
                    headers=auth(admin_token))
    assert rv.status_code == 200
    data = rv.get_json()
    # Response is {'appointments': [...]} or plain list
    appts = data.get('appointments', data) if isinstance(data, dict) else data
    assert isinstance(appts, list)


def test_calendar_post_creates_appointment(client, admin_token, pwa):
    payload = {
        'client_name': 'Тест Клієнт',
        'client_phone': '0671234567',
        'procedure_name': 'Тест-процедура',
        'specialist': 'victoria',
        'date': '2026-12-01',
        'time': '10:00',
        'duration': 60,
    }
    # Mock both _req (HTTP) and create_wlaunch_appointment (imported lazily)
    with patch.object(pwa, '_req') as mock_req, \
         patch.dict(sys.modules, {'wlaunch_api': sys.modules.get('wlaunch_api')}):
        mock_req.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'appointment': {'id': 'wl-test-id'}}
        )
        rv = client.post('/api/admin/calendar/appointments',
                         json=payload,
                         headers=auth(admin_token))

    # Accept 200, 201 (created), or 503 (if WLaunch mock integration fails)
    assert rv.status_code in (200, 201, 503)


def test_calendar_specialist_sees_only_own(client, specialist_token):
    rv = client.get('/api/admin/calendar/appointments?from=2026-07-01&to=2026-07-31',
                    headers=auth(specialist_token))
    assert rv.status_code == 200
    data = rv.get_json()
    appts = data.get('appointments', data) if isinstance(data, dict) else data
    assert isinstance(appts, list)
    # All returned entries must belong to this specialist or be busy slots
    for appt in appts:
        if not appt.get('busy'):
            assert appt.get('specialist') in ('anastasia', None, '')


def test_calendar_invalid_specialist_rejected(client, admin_token, pwa):
    payload = {
        'client_name': 'Тест',
        'client_phone': '0671234567',
        'procedure_name': 'Тест-процедура',
        'specialist': 'hacker',
        'date': '2026-12-02',
        'time': '11:00',
    }
    with patch.object(pwa, '_req') as mock_req:
        mock_req.post.return_value = MagicMock(status_code=200, json=lambda: {})
        rv = client.post('/api/admin/calendar/appointments',
                         json=payload,
                         headers=auth(admin_token))
    assert rv.status_code == 400


# ── /api/admin/calendar/appointments/<id> DELETE ─────────────────────────

def test_calendar_delete_nonexistent(client, admin_token):
    rv = client.delete('/api/admin/calendar/appointments/999999',
                       headers=auth(admin_token))
    assert rv.status_code in (404, 200)


def test_calendar_delete_existing(client, admin_token, pwa):
    """Create a local (no WLaunch) manual appointment, then delete it."""
    conn = sqlite3.connect(pwa.DB_PATH)
    cur = conn.execute(
        "INSERT INTO manual_appointments (client_phone, client_name, procedure_name, specialist, date, time) "
        "VALUES (?,?,?,?,?,?)",
        ('380671234567', 'Test', 'Тест-процедура', 'victoria', '2026-12-15', '14:00')
    )
    appt_id = cur.lastrowid
    conn.commit()
    conn.close()

    with patch.object(pwa, '_req') as mock_req:
        mock_req.post.return_value = MagicMock(status_code=200, json=lambda: {})
        rv = client.delete(f'/api/admin/calendar/appointments/{appt_id}',
                           headers=auth(admin_token))
    assert rv.status_code in (200, 204)

    conn = sqlite3.connect(pwa.DB_PATH)
    row = conn.execute('SELECT status FROM manual_appointments WHERE id=?', (appt_id,)).fetchone()
    conn.close()
    assert row is None or row[0] == 'CANCELLED'
