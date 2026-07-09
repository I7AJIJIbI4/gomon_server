"""
Tests for public (no-auth) endpoints: /api/prices, /api/health, /api/feed.
"""
import json
import sqlite3
import pytest
from conftest import auth, _pwa


def test_health(client):
    rv = client.get('/api/health')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'db' in data or 'status' in data


def test_prices_returns_list(client):
    rv = client.get('/api/prices')
    assert rv.status_code == 200
    data = rv.get_json()
    assert isinstance(data, list)
    assert len(data) > 0
    # Each category has 'cat' and 'items'
    cat = data[0]
    assert 'cat' in cat
    assert 'items' in cat
    assert isinstance(cat['items'], list)


def test_prices_item_structure(client):
    rv = client.get('/api/prices')
    item = rv.get_json()[0]['items'][0]
    assert 'name' in item
    assert 'price' in item


def test_prices_broken_json(client):
    """If prices.json is invalid JSON, should return 500 with JSON error body."""
    import os
    orig = open(_pwa.PRICES_PATH, 'rb').read()
    try:
        with open(_pwa.PRICES_PATH, 'w') as f:
            f.write('not json {{{')
        rv = client.get('/api/prices')
        # Must not return HTML 500 — must return JSON
        assert rv.status_code == 500
        data = rv.get_json()
        assert data is not None
    finally:
        with open(_pwa.PRICES_PATH, 'wb') as f:
            f.write(orig)


def test_feed_returns_list(client):
    rv = client.get('/api/feed')
    assert rv.status_code == 200
    data = rv.get_json()
    assert isinstance(data, list)


def test_feed_with_posts(client, pwa):
    """Insert a feed post and verify it appears in the response.
    Feed endpoint returns day-grouped objects: [{date, texts:[...], media:[...]}, ...]
    """
    conn = sqlite3.connect(pwa.FEED_DB)
    conn.execute(
        "INSERT OR IGNORE INTO posts (tg_msg_id, text, date) VALUES (?,?,?)",
        (9999, 'Тест пост', 1700000000)
    )
    conn.commit()
    conn.close()

    rv = client.get('/api/feed')
    days = rv.get_json()
    # Flatten all texts across all day groups
    all_texts = []
    for day in days:
        all_texts.extend(day.get('texts', []))
        # also check 'text' field in case format changed
        if day.get('text'):
            all_texts.append(day['text'])
    assert any('Тест пост' in t for t in all_texts), \
        f"Post not found. Response: {days}"


def test_prices_duration_non_numeric(client, pwa):
    """duration as a string with units must not crash /api/admin/prices/edit.
    This is a regression test for the int(duration) ValueError fixed in pwa_api.py."""
    broken_prices = [
        {'cat': 'Тест', 'items': [
            {'name': 'Тест', 'price': '500 грн', 'specialists': ['victoria'], 'duration': '60 хв'},
        ]}
    ]
    orig = open(pwa.PRICES_PATH, 'rb').read()
    try:
        with open(pwa.PRICES_PATH, 'w', encoding='utf-8') as f:
            json.dump(broken_prices, f)
        from conftest import _insert_session
        token = _insert_session('380996093860')
        rv = client.get('/api/admin/prices/edit', headers=auth(token))
        assert rv.status_code == 200
        data = rv.get_json()
        dur = data[0]['items'][0].get('duration')
        assert isinstance(dur, int), f"duration should be int, got {type(dur)}: {dur}"
        assert dur == 60  # fallback default
    finally:
        with open(pwa.PRICES_PATH, 'wb') as f:
            f.write(orig)
