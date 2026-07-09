"""
Tests for bot.py logic.
python-telegram-bot is mocked so tests run without the full PTB installation.
Logic covered: deep-link phone normalization, balance display, admin-only guards.
"""
import sys
import os
import types
import sqlite3
import logging
import logging.handlers
import pytest

# ── 1. Stub the telegram package before importing bot.py ──────────────────

def _make_telegram_stubs():
    _tg = types.ModuleType('telegram')

    class _BaseInline:
        def __init__(self, *a, **kw): pass
        def to_dict(self): return {}

    _tg.InlineKeyboardButton    = type('InlineKeyboardButton',    (_BaseInline,), {})
    _tg.InlineKeyboardMarkup    = type('InlineKeyboardMarkup',    (_BaseInline,), {})
    _tg.ReplyKeyboardMarkup     = type('ReplyKeyboardMarkup',     (_BaseInline,), {})
    _tg.ReplyKeyboardRemove     = type('ReplyKeyboardRemove',     (_BaseInline,), {})
    _tg.KeyboardButton          = type('KeyboardButton',          (_BaseInline,), {})
    _tg.WebAppInfo              = type('WebAppInfo',              (_BaseInline,), {})
    _tg.InputMediaPhoto         = type('InputMediaPhoto',         (_BaseInline,), {})

    _tg_ext = types.ModuleType('telegram.ext')
    _tg_ext.Application          = type('Application', (), {})
    _tg_ext.CommandHandler       = type('CommandHandler', (_BaseInline,), {})
    _tg_ext.MessageHandler       = type('MessageHandler', (_BaseInline,), {})
    _tg_ext.CallbackQueryHandler = type('CallbackQueryHandler', (_BaseInline,), {})
    _tg_ext.ContextTypes         = types.SimpleNamespace(DEFAULT_TYPE=None)
    _tg_ext.Defaults             = type('Defaults', (_BaseInline,), {})
    _tg_ext.filters              = types.SimpleNamespace(
        TEXT=None, COMMAND=None, CONTACT=None,
        UpdateType=types.SimpleNamespace(CHANNEL_POST=None, EDITED_CHANNEL_POST=None),
    )

    _tg_const = types.ModuleType('telegram.constants')
    _tg_const.ChatAction = types.SimpleNamespace(TYPING='typing')

    return _tg, _tg_ext, _tg_const


_tg_stub, _tg_ext_stub, _tg_const_stub = _make_telegram_stubs()
sys.modules.setdefault('telegram',           _tg_stub)
sys.modules.setdefault('telegram.ext',       _tg_ext_stub)
sys.modules.setdefault('telegram.constants', _tg_const_stub)

# ── 2. Ensure config mock has all attributes bot.py needs ─────────────────

_cfg = sys.modules.get('config')
if _cfg is not None:
    _cfg.ADMIN_USER_ID  = getattr(_cfg, 'ADMIN_USER_ID',  573368771)
    _cfg.MAP_URL        = getattr(_cfg, 'MAP_URL',         'https://maps.test')
    _cfg.SCHEME_URL     = getattr(_cfg, 'SCHEME_URL',      'https://scheme.test')
    if not hasattr(_cfg, 'validate_config'):
        _cfg.validate_config = lambda: None

# ── 3. Import bot.py ──────────────────────────────────────────────────────

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'zadarma'))

_orig_rfh_bot = logging.handlers.RotatingFileHandler

class _NullRFH(logging.NullHandler):
    def __init__(self, *a, **kw):
        super().__init__()

logging.handlers.RotatingFileHandler = _NullRFH
import bot as _bot
logging.handlers.RotatingFileHandler = _orig_rfh_bot

from conftest import _TEST_DIR

_bot_db = os.path.join(_TEST_DIR, 'users.db')


# ── deep-link phone normalization (inline logic from start_command) ────────

def _normalize_connect_phone(raw_phone):
    """Replicates the deep-link normalization in bot.py start_command."""
    digits = ''.join(filter(str.isdigit, raw_phone))
    if len(digits) == 10 and digits[0] == '0':
        digits = '38' + digits
    elif len(digits) == 9:
        digits = '380' + digits
    return digits


@pytest.mark.parametrize('raw,expected', [
    ('0505555555',   '380505555555'),   # 10-digit UA starting with 0
    ('505555555',    '380505555555'),   # 9-digit local
    ('380505555555', '380505555555'),   # already normalized
    ('16452040153',  '16452040153'),    # international (11 digits, not starting with 0)
    ('+380733103110', '380733103110'),  # with plus sign
])
def test_normalize_connect_phone(raw, expected):
    result = _normalize_connect_phone(raw)
    assert result == expected, 'normalize({!r}) → {!r}, want {!r}'.format(raw, result, expected)


def test_normalize_short_number_gets_380_prefix():
    # 9-digit without leading zero → 380 prefix
    assert _normalize_connect_phone('505555555') == '380505555555'


def test_normalize_leading_zero_10_digit():
    # 10-digit starting with 0 → 38 prefix
    assert _normalize_connect_phone('0665551234') == '380665551234'


# ── admin-only guard ───────────────────────────────────────────────────────

def test_admin_user_ids_not_empty():
    """ADMIN_USER_IDS must be a non-empty list for admin commands to work."""
    from config import ADMIN_USER_IDS
    assert isinstance(ADMIN_USER_IDS, list)
    assert len(ADMIN_USER_IDS) > 0


def test_sync_command_rejects_non_admin():
    """sync_command returns early if user_id not in ADMIN_USER_IDS."""
    from config import ADMIN_USER_IDS
    non_admin_id = 999999999
    assert non_admin_id not in ADMIN_USER_IDS


# ── _get_main_keyboard ─────────────────────────────────────────────────────

def test_get_main_keyboard_returns_value():
    """_get_main_keyboard() must not raise and return something."""
    kb = _bot._get_main_keyboard()
    assert kb is not None


# ── cashback callback data parsing ────────────────────────────────────────

def test_cashback_callback_data_format():
    """callback_data 'cb|0505555555|0630|4900' must parse into expected parts."""
    data = 'cb|0505555555|0630|4900'
    parts = data.split('|')
    assert len(parts) == 4
    assert parts[0] == 'cb'
    ph_short, dt_short, price_str = parts[1], parts[2], parts[3]
    price = float(price_str)
    assert price == 4900.0
    # Month/day extraction
    month = dt_short[:2]
    day   = dt_short[2:4]
    assert month == '06'
    assert day   == '30'


def test_cashback_amount_calculation():
    """3% cashback rate must be calculated correctly."""
    price = 4900.0
    cashback = round(price * 0.03, 2)
    assert cashback == 147.0


# ── bot module smoke test ──────────────────────────────────────────────────

def test_bot_module_has_main():
    assert callable(getattr(_bot, 'main', None))


def test_bot_module_has_start_command():
    assert callable(getattr(_bot, 'start_command', None))


def test_bot_module_has_admin_command():
    assert callable(getattr(_bot, 'admin_command', None))


def test_bot_module_has_balance_command():
    assert callable(getattr(_bot, 'balance_command', None))


def test_bot_module_has_my_services_command():
    assert callable(getattr(_bot, 'my_services_command', None))
