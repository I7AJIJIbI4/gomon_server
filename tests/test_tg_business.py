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


def _seed_ai_replies(conv, n=10):
    """n AI-відповідей 5 хвилин тому, у UTC — як їх пише прод (datetime('now')).

    Час беремо з самого SQLite: з ним порівнює 60-секундний cooldown, тож рядки
    гарантовано старші за нього за будь-якого годинника Python.
    Повертає UTC-дату цих рядків.
    """
    from datetime import datetime
    c = _conn()
    ts = c.execute("SELECT datetime('now','-5 minutes')").fetchone()[0]
    for i in range(n):
        c.execute(
            "INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin, created_at) VALUES ('telegram',?,?,?,1,?)",
            (conv, 'ai_bot', 'Reply {}'.format(i), ts)
        )
    c.commit()
    c.close()
    return datetime.strptime(ts[:10], '%Y-%m-%d')


def test_check_ai_should_reply_rate_limited(frozen_kyiv):
    """10+ AI replies today → rate_limited. Київський день той самий, що й UTC-дата рядків."""
    cid = 80003
    conv = 'tg_{}'.format(cid)
    day = _seed_ai_replies(conv)
    frozen_kyiv(day.replace(hour=12))
    should, reason = _tgbiz._check_ai_should_reply(conv, cid)
    assert not should
    assert reason == 'rate_limited'


def _night_setup(conv, n=10, client_tg=None):
    """Північ минула: 00:30 Києва, а UTC ще вчорашній вечір.

    Беремо минулу добу, щоб усі рядки були в минулому відносно справжнього
    SQLite now (з ним порівнює cooldown): 00:30 Києва D+1 = 22:30 UTC D (влітку 21:30).
    Повертає київський час, на який треба заморозити годинник.
    """
    from datetime import datetime, timedelta
    import tz_utils
    c = _conn()
    d = c.execute("SELECT date('now','-1 day')").fetchone()[0]
    c.close()
    kyiv = datetime.strptime(d, '%Y-%m-%d') + timedelta(days=1, minutes=30)
    utc = next(kyiv - timedelta(hours=o) for o in (3, 2)
               if tz_utils.kyiv_offset(kyiv - timedelta(hours=o)) == o)
    ts = (utc - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')     # 00:25 Києва
    c = _conn()
    for i in range(n):
        c.execute(
            "INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin, created_at) VALUES ('telegram',?,?,?,1,?)",
            (conv, 'ai_bot', 'Reply {}'.format(i), ts)
        )
    c.commit()
    c.close()
    return kyiv, utc


def test_rate_limit_counts_replies_right_after_kyiv_midnight(frozen_kyiv):
    """10 відповідей о 00:25 Києва — ліміт діє і о 00:30.

    created_at у UTC, а «сьогодні» рахувалось за київською датою: з 00:00 до 02:00
    (влітку 03:00) лічильник був 0 і ліміту вночі не було (виправлено 04.11.2026).
    """
    cid = 80006
    conv = 'tg_{}'.format(cid)
    kyiv, _ = _night_setup(conv)
    frozen_kyiv(kyiv)
    should, reason = _tgbiz._check_ai_should_reply(conv, cid)
    assert (should, reason) == (False, 'rate_limited')


def test_replies_before_kyiv_midnight_do_not_count_today(frozen_kyiv):
    """Відповіді з учорашнього вечора (за Києвом) у сьогоднішній ліміт не входять."""
    from datetime import timedelta
    cid = 80007
    conv = 'tg_{}'.format(cid)
    kyiv, _ = _night_setup(conv)
    frozen_kyiv(kyiv + timedelta(days=1))          # наступна київська доба
    should, reason = _tgbiz._check_ai_should_reply(conv, cid)
    assert (should, reason) == (True, 'ok')


def test_deposit_paid_after_kyiv_midnight_lifts_the_limit(frozen_kyiv):
    """Депозит о 00:20 Києва — сьогоднішній, хоча в UTC це ще вчора.

    Доба D+1 за Києвом позавчорашня, щоб усе було в минулому для SQLite now:
    депозит о 00:20 Києва (22:20 UTC D), 10 відповідей о 09:00, перевірка о 10:00.
    Раніше депозит шукали як date(created_at) = київська дата — і не знаходили.
    """
    from datetime import datetime, timedelta
    import tz_utils
    cid = 80008
    conv = 'tg_{}'.format(cid)
    c = _conn()
    d = c.execute("SELECT date('now','-2 days')").fetchone()[0]
    day = datetime.strptime(d, '%Y-%m-%d') + timedelta(days=1)          # київська доба D+1

    def utc(kyiv):
        return next(kyiv - timedelta(hours=o) for o in (3, 2)
                    if tz_utils.kyiv_offset(kyiv - timedelta(hours=o)) == o).strftime('%Y-%m-%d %H:%M:%S')
    for i in range(10):
        c.execute(
            "INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin, created_at) VALUES ('telegram',?,?,?,1,?)",
            (conv, 'ai_bot', 'Reply {}'.format(i), utc(day.replace(hour=9))))
    c.execute("INSERT OR REPLACE INTO users (telegram_id, phone) VALUES (?, ?)", (cid, '380507770808'))
    c.execute("INSERT INTO deposits (phone, amount_eur, amount_uah, order_id, status, created_at)"
              " VALUES ('380507770808', 5, 220, 'night-dep', 'Approved', ?)", (utc(day.replace(minute=20)),))
    c.commit()
    c.close()
    frozen_kyiv(day.replace(hour=10))
    should, reason = _tgbiz._check_ai_should_reply(conv, cid)
    assert (should, reason) == (True, 'ok')


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
    # Client message and admin message within 5s of each other (auto-greeting).
    # Час відносний: адмінське повідомлення має потрапити у вікно AI_ADMIN_PAUSE,
    # інакше його ніхто не вибирає і фільтр автопривітання не перевіряється —
    # так було з фіксованим '2026-06-01 10:00:00' після 04.06.2026.
    ts_sql = "datetime('now','-1 hour')"
    c.execute(
        "INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin, created_at) "
        "VALUES ('telegram',?,?,?,0,{})".format(ts_sql),
        (conv, str(cid), 'Hi')
    )
    c.execute(
        "INSERT INTO messages (platform, conversation_id, sender_id, content, is_from_admin, created_at) "
        "VALUES ('telegram',?,?,?,1,{})".format(ts_sql),
        (conv, '99999', 'Auto-greeting')  # same second = within 5s
    )
    c.commit()
    c.close()
    # Should NOT be blocked (auto-greeting is filtered out)
    should, reason = _tgbiz._check_ai_should_reply(conv, cid)
    assert should
    assert reason == 'ok'
