"""
Tests for tg_business_listener.py pure logic functions.
No external API calls — Anthropic and Telegram are not contacted.
"""
import sys
import os
import sqlite3
import logging
import logging.handlers
import time
import pytest

# Re-patch RotatingFileHandler before importing tg_business_listener.
# conftest.py restores the original after importing pwa_api, so we must re-apply here.
_orig_rfh_tgbiz = logging.handlers.RotatingFileHandler


class _NullRFH(logging.NullHandler):
    def __init__(self, *a, **kw):
        super().__init__()


logging.handlers.RotatingFileHandler = _NullRFH

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'zadarma'))
import tg_business_listener as _tgbiz

logging.handlers.RotatingFileHandler = _orig_rfh_tgbiz

from conftest import _TEST_DIR

# Point the module at our test DB (same file used by pwa_api tests)
_tgbiz.DB_PATH = os.path.join(_TEST_DIR, 'users.db')
_tgbiz.init_db()


# ── helpers ────────────────────────────────────────────────────────────────

def _conn():
    return sqlite3.connect(_tgbiz.DB_PATH)


def _ensure_ai_mute_table():
    c = _conn()
    c.execute("CREATE TABLE IF NOT EXISTS ai_mute (user_id TEXT, channel TEXT, active INTEGER)")
    c.commit()
    c.close()


# ── init_db ────────────────────────────────────────────────────────────────

def test_init_db_creates_messages_table():
    c = _conn()
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    c.close()
    assert 'messages' in tables


def test_init_db_creates_biz_connections_table():
    c = _conn()
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    c.close()
    assert 'biz_connections' in tables


# ── save_message ───────────────────────────────────────────────────────────

def test_save_message_text_insert():
    cid = 90002
    _tgbiz.save_message(sender_id=cid, sender_name='User', content='Привіт', chat_id=cid)
    c = _conn()
    row = c.execute(
        "SELECT content, is_from_admin, platform FROM messages WHERE conversation_id=?",
        ('tg_{}'.format(cid),)
    ).fetchone()
    c.close()
    assert row is not None
    assert row[0] == 'Привіт'
    assert row[1] == 0
    assert row[2] == 'telegram'


def test_save_message_admin_flag():
    cid = 90003
    _tgbiz.save_message(sender_id=cid, sender_name='Admin', content='Відповідь', is_from_admin=True, chat_id=cid)
    c = _conn()
    row = c.execute(
        "SELECT is_from_admin FROM messages WHERE conversation_id=?", ('tg_{}'.format(cid),)
    ).fetchone()
    c.close()
    assert row[0] == 1


def test_save_message_dedup_within_600s():
    """Same content+sender within 600s with tg_msg_id → second call is skipped."""
    cid = 90004
    _tgbiz.save_message(sender_id=cid, sender_name='X', content='Dup!', chat_id=cid, tg_msg_id=9001)
    _tgbiz.save_message(sender_id=cid, sender_name='X', content='Dup!', chat_id=cid, tg_msg_id=9001)
    c = _conn()
    count = c.execute(
        "SELECT COUNT(*) FROM messages WHERE conversation_id=?", ('tg_{}'.format(cid),)
    ).fetchone()[0]
    c.close()
    assert count == 1


def test_save_message_no_dedup_without_tg_msg_id():
    """Without tg_msg_id the dedup check is skipped → both messages stored."""
    cid = 90005
    _tgbiz.save_message(sender_id=cid, sender_name='Y', content='A', chat_id=cid)
    _tgbiz.save_message(sender_id=cid, sender_name='Y', content='B', chat_id=cid)
    c = _conn()
    count = c.execute(
        "SELECT COUNT(*) FROM messages WHERE conversation_id=?", ('tg_{}'.format(cid),)
    ).fetchone()[0]
    c.close()
    assert count == 2


def test_save_message_stores_biz_connection():
    cid = 90006
    _tgbiz.save_message(
        sender_id=cid, sender_name='C', content='Hi',
        chat_id=cid, business_connection_id='biz-conn-xyz'
    )
    c = _conn()
    row = c.execute(
        "SELECT biz_conn_id FROM biz_connections WHERE chat_id=?", (str(cid),)
    ).fetchone()
    c.close()
    assert row is not None
    assert row[0] == 'biz-conn-xyz'


# ── _get_conversation_history ──────────────────────────────────────────────

def test_get_conversation_history_empty():
    hist = _tgbiz._get_conversation_history('tg_nonexistent_xyzabc123')
    assert hist == []


def test_get_conversation_history_ends_with_user():
    """Anthropic requires the last message to be user role."""
    conv = 'tg_hist_ends_user'
    c = _conn()
    c.execute("INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin) VALUES ('telegram',?,?,?,0)", (conv, '1', 'User msg'))
    c.execute("INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin) VALUES ('telegram',?,?,?,1)", (conv, 'ai_bot', 'AI reply'))
    c.execute("INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin) VALUES ('telegram',?,?,?,1)", (conv, 'ai_bot', 'AI trailing'))
    c.commit()
    c.close()
    hist = _tgbiz._get_conversation_history(conv)
    # Must strip trailing assistant messages so it ends on user
    assert hist == [] or hist[-1]['role'] == 'user'


def test_get_conversation_history_starts_with_user():
    """Anthropic requires the first message to be user role."""
    conv = 'tg_hist_starts_user'
    c = _conn()
    c.execute("INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin) VALUES ('telegram',?,?,?,1)", (conv, 'ai_bot', 'AI first'))
    c.execute("INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin) VALUES ('telegram',?,?,?,0)", (conv, '1', 'User after'))
    c.commit()
    c.close()
    hist = _tgbiz._get_conversation_history(conv)
    assert hist  # not empty
    assert hist[0]['role'] == 'user'


def test_get_conversation_history_merges_consecutive_user():
    """Two consecutive user messages → merged into one entry."""
    conv = 'tg_hist_merge_user'
    c = _conn()
    c.execute("INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin) VALUES ('telegram',?,?,?,0)", (conv, '1', 'Line1'))
    c.execute("INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin) VALUES ('telegram',?,?,?,0)", (conv, '1', 'Line2'))
    c.commit()
    c.close()
    hist = _tgbiz._get_conversation_history(conv)
    assert len(hist) == 1
    assert 'Line1' in hist[0]['content']
    assert 'Line2' in hist[0]['content']


def test_get_conversation_history_no_adjacent_same_role():
    """Merged history must not have two adjacent entries with the same role."""
    conv = 'tg_hist_no_adj'
    c = _conn()
    for content in ('U1', 'U2'):
        c.execute("INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin) VALUES ('telegram',?,?,?,0)", (conv, '1', content))
    c.execute("INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin) VALUES ('telegram',?,?,?,1)", (conv, 'ai_bot', 'AI'))
    c.execute("INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin) VALUES ('telegram',?,?,?,0)", (conv, '1', 'Follow'))
    c.commit()
    c.close()
    hist = _tgbiz._get_conversation_history(conv)
    for i in range(len(hist) - 1):
        assert hist[i]['role'] != hist[i + 1]['role'], \
            "Adjacent roles at index {} and {}: {}".format(i, i + 1, [h['role'] for h in hist])


def test_get_conversation_history_voice_placeholder():
    """Voice media type → '[Клієнт надіслав голосове повідомлення]' text."""
    conv = 'tg_hist_voice'
    c = _conn()
    c.execute(
        "INSERT INTO messages (platform, conversation_id, sender_id, content, media_type, is_from_admin) VALUES ('telegram',?,?,?,?,0)",
        (conv, '1', '[voice]', 'voice')
    )
    c.commit()
    c.close()
    hist = _tgbiz._get_conversation_history(conv)
    assert hist
    assert 'голосове' in hist[0]['content']


# ── _check_ai_should_reply ─────────────────────────────────────────────────

def test_check_ai_should_reply_fresh_conv():
    """Fresh conversation → should reply."""
    should, reason = _tgbiz._check_ai_should_reply('tg_fresh_xyz9998', 9998)
    assert should
    assert reason == 'ok'


def test_check_ai_should_reply_muted():
    cid = 80001
    _ensure_ai_mute_table()
    c = _conn()
    c.execute("INSERT OR REPLACE INTO ai_mute (user_id, channel, active) VALUES (?, 'tg', 1)", (str(cid),))
    c.commit()
    c.close()
    should, reason = _tgbiz._check_ai_should_reply('tg_{}'.format(cid), cid)
    assert not should
    assert reason == 'muted'


def test_check_ai_should_reply_cooldown():
    """AI replied in the last 60s → cooldown."""
    cid = 80002
    conv = 'tg_{}'.format(cid)
    c = _conn()
    c.execute(
        "INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin) VALUES ('telegram',?,?,?,1)",
        (conv, 'ai_bot', 'Recent AI reply')
    )
    c.commit()
    c.close()
    should, reason = _tgbiz._check_ai_should_reply(conv, cid)
    assert not should
    assert reason == 'cooldown'


def test_check_ai_should_reply_rate_limited():
    """10+ AI replies today → rate_limited."""
    cid = 80003
    conv = 'tg_{}'.format(cid)
    from tz_utils import kyiv_now
    today = kyiv_now().strftime('%Y-%m-%d')
    c = _conn()
    for i in range(10):
        c.execute(
            "INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin, created_at) VALUES ('telegram',?,?,?,1,?)",
            (conv, 'ai_bot', 'Reply {}'.format(i), '{} 10:00:00'.format(today))
        )
    c.commit()
    c.close()
    should, reason = _tgbiz._check_ai_should_reply(conv, cid)
    assert not should
    assert reason == 'rate_limited'


def test_check_ai_should_reply_admin_active():
    """Real human admin replied recently (no nearby client msg) → admin_active."""
    cid = 80004
    conv = 'tg_{}'.format(cid)
    c = _conn()
    # Human admin message (sender_id != 'ai_bot') within AI_ADMIN_PAUSE window
    c.execute(
        "INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin, created_at) "
        "VALUES ('telegram',?,?,?,1,datetime('now','-1 hour'))",
        (conv, '99999', 'Human admin reply')
    )
    c.commit()
    c.close()
    should, reason = _tgbiz._check_ai_should_reply(conv, cid)
    assert not should
    assert reason == 'admin_active'


def test_check_ai_should_reply_auto_greeting_not_counted():
    """Admin message within 5s of a client message counts as auto-greeting, not real admin."""
    cid = 80005
    conv = 'tg_{}'.format(cid)
    c = _conn()
    # Client message and admin message within 5s of each other (auto-greeting)
    ts = '2026-06-01 10:00:00'
    c.execute(
        "INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin, created_at) VALUES ('telegram',?,?,?,0,?)",
        (conv, str(cid), 'Hi', ts)
    )
    c.execute(
        "INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin, created_at) VALUES ('telegram',?,?,?,1,?)",
        (conv, '99999', 'Auto-greeting', ts)  # same second = within 5s
    )
    c.commit()
    c.close()
    # Should NOT be blocked (auto-greeting is filtered out)
    should, reason = _tgbiz._check_ai_should_reply(conv, cid)
    assert should
    assert reason == 'ok'
