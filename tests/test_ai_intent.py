"""
Tests for /api/admin/ai-intent NLP endpoint.
Anthropic API is mocked via monkeypatching urllib.request.urlopen.
"""
import json
import sqlite3
import time
import urllib.request
import pytest

from conftest import _pwa, _insert_session, auth, _TEST_DIR

_ADMIN_PHONE = '380733103110'  # superadmin, not used by other test files


@pytest.fixture
def c(app):
    return app.test_client()


@pytest.fixture
def admin_hdr():
    """Fresh admin session token each test to avoid rate-limit state bleed."""
    _pwa._ai_rate.pop(_ADMIN_PHONE, None)
    return auth(_insert_session(_ADMIN_PHONE))


def _anthropic_stub(ai_json_obj):
    """Return a urlopen stub that emits ai_json_obj wrapped in Anthropic format."""
    body = json.dumps({'content': [{'text': json.dumps(ai_json_obj)}]}).encode()

    class _Resp:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass
        def read(self):
            return body

    return lambda req, timeout=None: _Resp()


def _anthropic_raw_stub(raw_text):
    """Return a urlopen stub with arbitrary raw text (for non-JSON AI responses)."""
    body = json.dumps({'content': [{'text': raw_text}]}).encode()

    class _Resp:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass
        def read(self):
            return body

    return lambda req, timeout=None: _Resp()


_VALID_AI = {
    'action': 'create',
    'client_name': 'Тест Клієнт',
    'client_phone': None,
    'procedure': 'Тест-процедура',
    'date': '2026-06-30',
    'time': '14:00',
    'specialist': 'victoria',
    'notes': None,
    'reply': 'Записую Тест Клієнт на Тест-процедуру.'
}


# ── auth guards ────────────────────────────────────────────────────────────

def test_ai_intent_requires_auth(c):
    r = c.post('/api/admin/ai-intent', json={'text': 'Привіт'})
    assert r.status_code in (401, 403)


def test_ai_intent_client_role_forbidden(c):
    from conftest import _insert_session
    token = _insert_session('+380991234567')
    r = c.post('/api/admin/ai-intent', json={'text': 'Привіт'}, headers=auth(token))
    assert r.status_code == 403


# ── validation ─────────────────────────────────────────────────────────────

def test_ai_intent_empty_text_400(c, admin_hdr, monkeypatch):
    monkeypatch.setattr('urllib.request.urlopen', _anthropic_stub({}))
    r = c.post('/api/admin/ai-intent', json={'text': ''}, headers=admin_hdr)
    assert r.status_code == 400
    assert r.get_json()['error'] == 'empty_text'


def test_ai_intent_missing_text_400(c, admin_hdr, monkeypatch):
    monkeypatch.setattr('urllib.request.urlopen', _anthropic_stub({}))
    r = c.post('/api/admin/ai-intent', json={}, headers=admin_hdr)
    assert r.status_code == 400


# ── rate limiting ──────────────────────────────────────────────────────────

def test_ai_intent_rate_limited(c, admin_hdr, monkeypatch):
    """Rapid second call within cooldown → 429."""
    _pwa._ai_rate[_ADMIN_PHONE] = time.time()  # force rate-limit state
    r = c.post('/api/admin/ai-intent', json={'text': 'Запис'}, headers=admin_hdr)
    assert r.status_code == 429
    data = r.get_json()
    assert data['error'] == 'rate_limited'


# ── successful responses ───────────────────────────────────────────────────

def test_ai_intent_returns_all_keys(c, admin_hdr, monkeypatch):
    monkeypatch.setattr('urllib.request.urlopen', _anthropic_stub(_VALID_AI))
    r = c.post('/api/admin/ai-intent', json={'text': 'Запишіть Тест'}, headers=admin_hdr)
    assert r.status_code == 200
    data = r.get_json()
    for key in ('action', 'client', 'client_options', 'procedure', 'procedure_options',
                'date', 'time', 'specialist', 'notes', 'reply'):
        assert key in data, 'Missing key: {}'.format(key)


def test_ai_intent_action_and_reply_present(c, admin_hdr, monkeypatch):
    monkeypatch.setattr('urllib.request.urlopen', _anthropic_stub(_VALID_AI))
    r = c.post('/api/admin/ai-intent', json={'text': 'Запишіть'}, headers=admin_hdr)
    data = r.get_json()
    assert data['action'] == 'create'
    assert data['reply']


def test_ai_intent_null_string_normalized_to_none(c, admin_hdr, monkeypatch):
    """AI returns string 'null' for fields → endpoint must normalize to None."""
    ai = {
        'action': 'create', 'client_name': 'null', 'client_phone': 'null',
        'procedure': 'null', 'date': 'null', 'time': 'null',
        'specialist': 'null', 'notes': 'null', 'reply': 'Уточніть.'
    }
    monkeypatch.setattr('urllib.request.urlopen', _anthropic_stub(ai))
    r = c.post('/api/admin/ai-intent', json={'text': 'щось'}, headers=admin_hdr)
    assert r.status_code == 200
    data = r.get_json()
    assert data['date'] is None
    assert data['specialist'] is None
    assert data['notes'] is None
    assert data['client_name'] is None


def test_ai_intent_strips_markdown_json_block(c, admin_hdr, monkeypatch):
    """AI wraps JSON in ```json ... ``` fences → endpoint strips and parses."""
    inner = json.dumps({
        'action': 'find', 'client_name': 'Хтось', 'client_phone': None,
        'procedure': None, 'date': None, 'time': None,
        'specialist': None, 'notes': None, 'reply': 'Шукаю.'
    })
    raw = '```json\n' + inner + '\n```'
    monkeypatch.setattr('urllib.request.urlopen', _anthropic_raw_stub(raw))
    r = c.post('/api/admin/ai-intent', json={'text': 'Знайди Хтось'}, headers=admin_hdr)
    assert r.status_code == 200
    data = r.get_json()
    assert data['action'] == 'find'


def test_ai_intent_non_json_returns_unknown_action(c, admin_hdr, monkeypatch):
    """Plain text AI response → action=unknown, text surfaced as reply."""
    monkeypatch.setattr('urllib.request.urlopen', _anthropic_raw_stub('Будь ласка, уточніть запит.'))
    r = c.post('/api/admin/ai-intent', json={'text': 'невідомо'}, headers=admin_hdr)
    assert r.status_code == 200
    data = r.get_json()
    assert data['action'] == 'unknown'
    assert 'Будь ласка' in data['reply']


# ── client enrichment ──────────────────────────────────────────────────────

def test_ai_intent_client_enriched_when_phone_matches(c, admin_hdr, monkeypatch):
    """AI returns client_phone from our DB → client dict populated in response."""
    conn = sqlite3.connect(_pwa.DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO clients (id, phone, first_name, last_name, services_json) VALUES (?,?,?,?,?)",
        ('380991234567', '380991234567', 'Тест', 'Клієнт', '[]')
    )
    conn.commit()
    conn.close()

    ai = dict(_VALID_AI, client_phone='380991234567')
    monkeypatch.setattr('urllib.request.urlopen', _anthropic_stub(ai))
    r = c.post('/api/admin/ai-intent', json={'text': 'Тест Клієнт'}, headers=admin_hdr)
    assert r.status_code == 200
    data = r.get_json()
    assert data['client'] is not None
    assert data['client']['phone'] == '380991234567'


def test_ai_intent_no_client_when_phone_unknown(c, admin_hdr, monkeypatch):
    """AI returns a phone not in DB → client is None."""
    ai = dict(_VALID_AI, client_phone='380000000099')
    monkeypatch.setattr('urllib.request.urlopen', _anthropic_stub(ai))
    r = c.post('/api/admin/ai-intent', json={'text': 'Невідомий клієнт'}, headers=admin_hdr)
    assert r.status_code == 200
    data = r.get_json()
    assert data['client'] is None


# ── procedure enrichment ───────────────────────────────────────────────────

def test_ai_intent_procedure_enriched(c, admin_hdr, monkeypatch):
    """AI returns a procedure name matching prices.json → procedure dict with price."""
    ai = dict(_VALID_AI, procedure='Тест-процедура')
    monkeypatch.setattr('urllib.request.urlopen', _anthropic_stub(ai))
    r = c.post('/api/admin/ai-intent', json={'text': 'Тест-процедура'}, headers=admin_hdr)
    assert r.status_code == 200
    data = r.get_json()
    assert data['procedure'] is not None
    assert data['procedure']['name'] == 'Тест-процедура'


def test_ai_intent_auto_fills_specialist_from_single_specialist_procedure(c, admin_hdr, monkeypatch):
    """Procedure with one specialist and AI returns specialist=null → auto-filled."""
    # 'Тест-процедура' has specialists=['victoria'] in conftest prices.json
    ai = dict(_VALID_AI, specialist=None, procedure='Тест-процедура')
    monkeypatch.setattr('urllib.request.urlopen', _anthropic_stub(ai))
    r = c.post('/api/admin/ai-intent', json={'text': 'Тест-процедура'}, headers=admin_hdr)
    assert r.status_code == 200
    data = r.get_json()
    assert data['specialist'] == 'victoria'


def test_ai_intent_no_auto_fill_for_multi_specialist_procedure(c, admin_hdr, monkeypatch):
    """Procedure with two specialists and AI returns null → specialist stays null."""
    # 'Дует-процедура' has specialists=['victoria','anastasia']
    ai = dict(_VALID_AI, specialist=None, procedure='Дует-процедура')
    monkeypatch.setattr('urllib.request.urlopen', _anthropic_stub(ai))
    r = c.post('/api/admin/ai-intent', json={'text': 'Дует'}, headers=admin_hdr)
    assert r.status_code == 200
    data = r.get_json()
    assert data['specialist'] is None
