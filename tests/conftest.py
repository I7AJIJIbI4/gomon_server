"""
pytest conftest for GomonClinic pwa_api tests.

Key challenge: pwa_api.py has module-level calls to sqlite3.connect() and
RotatingFileHandler() that use hardcoded /opt/gomon/... paths. We patch both
before importing the module so tests run on any machine without /opt/gomon.
"""
import sys
import types
import os
import io
import json
import sqlite3
import logging
import logging.handlers
import builtins
import secrets
import time
import tempfile
from typing import Optional
import pytest

# ── 1. Temp directory (module-level so patches can reference it) ───────────

_TEST_DIR = tempfile.mkdtemp(prefix='gomon_test_')


# ── 2. Inject mock config before pwa_api is imported ──────────────────────

def _make_config():
    m = types.ModuleType('config')
    m.TELEGRAM_TOKEN       = 'tg_test_token'
    m.TG_BIZ_TOKEN         = 'tg_biz_test_token'
    m.ANTHROPIC_KEY        = 'anthropic_test_key'
    m.WLAUNCH_API_URL      = 'https://mock-wlaunch.test/v1'
    m.WLAUNCH_API_KEY      = 'wl_test_api_key'
    m.COMPANY_ID           = 'test-company-id'
    m.WLAUNCH_TOKEN        = 'wl_test_token'
    m.WAYFORPAY_MERCHANT   = 'test_merchant'
    m.WAYFORPAY_SECRET     = 'test_secret'
    m.WFP_MERCHANT_ACCOUNT = 'test_merchant'
    m.WFP_MERCHANT_SECRET  = 'test_secret'
    m.VAPID_PRIVATE_KEY    = 'test_vapid_priv'
    m.VAPID_PUBLIC_KEY     = 'test_vapid_pub'
    m.VAPID_EMAIL          = 'test@example.com'
    m.IG_TOKEN             = 'ig_test_token'
    m.IG_PHONE_ID          = 'ig_test_phone_id'
    m.PIN_AUTH             = {'380000000001': '1234'}
    m.ADMIN_USER_IDS       = [573368771]
    m.get_ig_token         = lambda: 'ig_test_token'
    return m


def _make_wlaunch():
    m = types.ModuleType('wlaunch_api')
    m.HEADERS                    = {'Authorization': 'Bearer wl_test_token'}
    m.get_branch_id              = lambda: 'test-branch-id'
    m.get_specialist             = lambda phone: 'victoria'
    m.parse_appt_time            = lambda t: t
    m.create_wlaunch_appointment = lambda *a, **kw: {'id': 'wl-mock-id'}
    m.get_wlaunch_resources      = lambda: []
    m.WLAUNCH_API_BEARER         = 'Bearer wl_test_api_key'
    return m


def _make_sms():
    m = types.ModuleType('sms_fly')
    m.send_sms = lambda to, msg: True
    return m


def _make_notifier():
    m = types.ModuleType('notifier')
    m.send_tg             = lambda *a, **kw: None
    m.notify_admin        = lambda *a, **kw: None
    m.notify_specialist   = lambda *a, **kw: None
    m.send_cancellation   = lambda *a, **kw: None
    return m


def _make_push_sender():
    m = types.ModuleType('push_sender')
    m.init_push_tables    = lambda: None
    m.save_subscription   = lambda *a, **kw: None
    m.remove_subscription = lambda *a, **kw: None
    m.get_subscriptions   = lambda phone: []
    m.send_push_to_phone  = lambda *a, **kw: {'sent': 0, 'failed': 0}
    return m


_TIER_BASIC = {
    'name': 'Базовий', 'key': 'basic', 'rate': 0.03,
    'next_name': 'Срібний', 'next_visits': 5, 'next_redeems': 2,
    'visits': 0, 'redeems': 0,
}


def _make_loyalty():
    m = types.ModuleType('loyalty')
    m.get_client_tier        = lambda phone: dict(_TIER_BASIC)
    m.get_cashback_rate      = lambda phone: 0.03
    m.get_cashback_modifiers = lambda phone: []
    m.get_rate_modifier      = lambda phone: {'delta': 0.0, 'reasons': []}
    m.get_tier_name          = lambda tier: 'Базовий'
    return m


sys.modules.setdefault('config', _make_config())
sys.modules.setdefault('wlaunch_api', _make_wlaunch())
sys.modules.setdefault('sms_fly', _make_sms())
sys.modules.setdefault('notifier', _make_notifier())
sys.modules.setdefault('push_sender', _make_push_sender())
sys.modules.setdefault('loyalty', _make_loyalty())


# ── 3. Patch sqlite3.connect, RotatingFileHandler, and bare open() before importing pwa_api

_orig_connect = sqlite3.connect


def _redirect_connect(path, *args, **kwargs):
    """Redirect any /opt/gomon/... or /home/gomoncli/... DB path to _TEST_DIR."""
    if isinstance(path, str) and (
        path.startswith('/opt/gomon/') or path.startswith('/home/gomoncli/')
    ):
        path = os.path.join(_TEST_DIR, os.path.basename(path))
    return _orig_connect(path, *args, **kwargs)


sqlite3.connect = _redirect_connect

# Patch builtins.open to intercept module-level reads of /opt/gomon/... files
_orig_open = builtins.open
_OPT_FILES = {
    '/opt/gomon/app/zadarma/vapid_public.txt': 'test_vapid_public_key',
}


def _redirect_open(path, *args, **kwargs):
    if isinstance(path, str) and path in _OPT_FILES:
        return io.StringIO(_OPT_FILES[path])
    return _orig_open(path, *args, **kwargs)


builtins.open = _redirect_open

# Replace RotatingFileHandler with NullHandler to avoid log file creation
_orig_rfh = logging.handlers.RotatingFileHandler


class _NullRotatingHandler(logging.NullHandler):
    def __init__(self, *a, **kw):
        super().__init__()


logging.handlers.RotatingFileHandler = _NullRotatingHandler

# ── 4. Import pwa_api with patches active ────────────────────────────────

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'zadarma'))
import pwa_api as _pwa  # noqa: E402

# Restore originals after import
sqlite3.connect = _orig_connect
builtins.open = _orig_open
logging.handlers.RotatingFileHandler = _orig_rfh

# Update module-level path constants so all runtime calls also use test dir
_pwa.DB_PATH     = os.path.join(_TEST_DIR, 'users.db')
_pwa.OTP_DB      = os.path.join(_TEST_DIR, 'otp_sessions.db')
_pwa.FEED_DB     = os.path.join(_TEST_DIR, 'feed.db')
_pwa.PRICES_PATH = os.path.join(_TEST_DIR, 'prices.json')
_pwa.PWA_DIR     = _TEST_DIR

# Also patch user_db's DB_PATH so init_db() creates clients table in test dir
import user_db as _user_db
_user_db.DB_PATH = _pwa.DB_PATH
_user_db.init_db()

# Re-init OTP db at the correct path (init ran during import using redirect,
# but explicitly calling again guarantees all tables exist at the final path)
_pwa.init_otp_db()
_pwa.init_appointments_db()
_pwa.init_breaks_db()
_pwa.init_permissions_db()
_pwa.init_messages_db()

# push_sender is mocked so we create its tables directly
_push_conn = sqlite3.connect(_pwa.DB_PATH)
_push_conn.execute(
    'CREATE TABLE IF NOT EXISTS push_subscriptions ('
    '  id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT NOT NULL,'
    '  endpoint TEXT NOT NULL, subscription TEXT NOT NULL,'
    "  created_at TEXT NOT NULL DEFAULT (datetime('now')),"
    '  active INTEGER DEFAULT 1, UNIQUE(phone, endpoint))'
)
_push_conn.execute(
    'CREATE TABLE IF NOT EXISTS push_log ('
    '  id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT NOT NULL,'
    '  type TEXT NOT NULL, reference TEXT NOT NULL, title TEXT,'
    "  sent_at TEXT NOT NULL DEFAULT (datetime('now')), status TEXT DEFAULT \"sent\")"
)
_push_conn.commit()
_push_conn.close()

# cashback table (used by /api/deposit/balance and appt_reminder.py)
_cb_conn = sqlite3.connect(_pwa.DB_PATH)
_cb_conn.execute(
    'CREATE TABLE IF NOT EXISTS cashback ('
    '  id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, amount REAL,'
    '  procedure_name TEXT, procedure_price REAL DEFAULT 0, appt_date TEXT,'
    "  created_at TEXT DEFAULT (datetime('now')),"
    '  UNIQUE(phone, procedure_name, appt_date))'
)
_cb_conn.execute(
    'CREATE TABLE IF NOT EXISTS deposits ('
    '  id INTEGER PRIMARY KEY AUTOINCREMENT,'
    '  order_ref TEXT UNIQUE, order_id TEXT UNIQUE,'
    '  phone TEXT, amount_eur REAL, amount_uah REAL, status TEXT,'
    "  created_at TEXT DEFAULT (datetime('now')),"
    '  approved_at TEXT, wfp_transaction_id TEXT, wfp_transaction_status TEXT)'
)
_cb_conn.execute(
    'CREATE TABLE IF NOT EXISTS deposit_deductions ('
    '  id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, amount REAL,'
    "  reason TEXT, created_by TEXT, created_at TEXT DEFAULT (datetime('now')))"
)
_cb_conn.commit()
_cb_conn.close()

# Insert client records for admin phones so /api/me works for them
_admin_phones = [
    ('380733103110', 'Superadmin', 'Test'),
    ('380996093860', 'Victoria', 'Gomon'),
    ('380685129121', 'Anastasia', 'Specialist'),
]
_acconn = sqlite3.connect(_pwa.DB_PATH)
for _ap, _af, _al in _admin_phones:
    _acconn.execute(
        'INSERT OR IGNORE INTO clients (id, phone, first_name, last_name, services_json) VALUES (?,?,?,?,?)',
        (_ap, _ap, _af, _al, '[]')
    )
_acconn.commit()
_acconn.close()

# Re-initialize feed DB at correct path and add thumb_id (migration column not in CREATE)
_pwa.init_feed_db()
_feed_mig_conn = sqlite3.connect(_pwa.FEED_DB)
try:
    _feed_mig_conn.execute('ALTER TABLE posts ADD COLUMN thumb_id TEXT')
    _feed_mig_conn.commit()
except Exception:
    pass  # column already exists
_feed_mig_conn.close()

# Silence any remaining log handlers
logging.getLogger('pwa_api').handlers = []

# Write minimal prices.json
_prices = [
    {'cat': 'Тест', 'items': [
        {'name': 'Тест-процедура', 'price': '500 грн', 'specialists': ['victoria'], 'duration': 60},
        {'name': 'Дует-процедура', 'price': '1000 грн', 'specialists': ['victoria', 'anastasia'], 'duration': 90},
    ]}
]
with open(_pwa.PRICES_PATH, 'w', encoding='utf-8') as _f:
    json.dump(_prices, _f)


# ── 5. Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope='session')
def pwa():
    """Direct access to pwa_api module."""
    return _pwa


@pytest.fixture(scope='session')
def app(pwa):
    pwa.app.config['TESTING'] = True
    pwa.app.config['WTF_CSRF_ENABLED'] = False
    return pwa.app


@pytest.fixture(scope='session')
def client(app):
    return app.test_client()


# ── 6. Token helpers ──────────────────────────────────────────────────────

def _insert_session(phone: str) -> str:
    """Insert a live session token and return it."""
    token = secrets.token_hex(32)
    conn = sqlite3.connect(_pwa.OTP_DB)
    conn.execute(
        'INSERT OR REPLACE INTO sessions (token, phone, created_at, expires_at) VALUES (?,?,?,?)',
        (token, phone, int(time.time()), int(time.time()) + 86400)
    )
    conn.commit()
    conn.close()
    return token


def _insert_client(phone: str, name: str = 'Тест Клієнт') -> None:
    """Insert a client row into users.db (uses pwa's norm_phone)."""
    from user_db import normalize_phone
    conn = sqlite3.connect(_pwa.DB_PATH)
    conn.execute(
        'INSERT OR IGNORE INTO clients (phone, first_name) VALUES (?,?)',
        (normalize_phone(phone), name)
    )
    conn.commit()
    conn.close()


@pytest.fixture(scope='session')
def client_phone():
    return '+380991234567'


@pytest.fixture(scope='session')
def client_token(client_phone, pwa):
    _insert_client(client_phone)
    return _insert_session(client_phone)


@pytest.fixture(scope='session')
def admin_token():
    """Token for full-admin role (380996093860 in ADMIN_ROLES)."""
    return _insert_session('380996093860')


@pytest.fixture(scope='session')
def specialist_token():
    """Token for specialist role (380685129121 in ADMIN_ROLES)."""
    return _insert_session('380685129121')


@pytest.fixture(scope='session')
def superadmin_token():
    return _insert_session('380733103110')


def auth(token: str) -> dict:
    """Return Authorization header dict for use in test_client calls."""
    return {'Authorization': f'Bearer {token}'}
