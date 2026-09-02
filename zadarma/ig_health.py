#!/usr/bin/env python3
"""Instagram token watchdog — alert admin in TG before/when the IG token dies.

The IG long-lived token lives ~60 days. When it expires, incoming DMs keep
arriving and GomonAI keeps generating replies, but every send fails with
HTTP 401 and the client silently gets nothing (this went unnoticed for 12 days
in August 2026). Nothing else monitors it.

- token valid, age < WARN_AT_DAYS   -> OK, clear stale flags
- token valid, age >= WARN_AT_DAYS  -> warn once: renewal is due
- token rejected (OAuthException)   -> critical alert once
- anything else                     -> log only (transient network/API noise)

Alerts are idempotent via flag files, mirroring anthropic_health.py.

Schedule via cron, e.g.:
  0 7 * * *  cd /opt/gomon/app/zadarma && /opt/gomon/venv/bin/python ig_health.py > /dev/null 2>> /var/log/gomon/ig_health.log

Renewal is manual (Meta Console -> Manage messaging & content on Instagram ->
Step 2 "Generate access tokens" -> dr.gomon), then write the token into
private_data/ig_token.txt.
"""
import os
import sys
import json
import time
import logging
import logging.handlers
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import get_ig_token, _IG_TOKEN_FILE, TELEGRAM_TOKEN, ADMIN_USER_ID

LOG_PATH      = '/var/log/gomon/ig_health.log'
FLAG_EXPIRED  = '/tmp/ig_token_expired.flag'
FLAG_WARN     = '/tmp/ig_token_warn.flag'
LIFETIME_DAYS = 60
WARN_AT_DAYS  = 53
GRAPH_URL     = 'https://graph.instagram.com/v23.0/me?fields=id,username&access_token={}'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=512*1024, backupCount=2),
        # stdout, not stderr: cron discards stdout (the rotating file already has it)
        # and keeps stderr, so only real tracebacks land in the log twice-free.
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger('ig_health')

DRY_RUN = '--dry-run' in sys.argv


def _tg_alert(text):
    if DRY_RUN:
        logger.info('[dry-run] TG alert suppressed: {}'.format(text.replace('\n', ' ')[:120]))
        return
    try:
        body = json.dumps({'chat_id': ADMIN_USER_ID, 'text': text, 'parse_mode': 'HTML'}).encode('utf-8')
        req = urllib.request.Request(
            'https://api.telegram.org/bot{}/sendMessage'.format(TELEGRAM_TOKEN),
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:
        logger.error('TG alert send failed: {}'.format(e))


def _set_flag(path):
    if DRY_RUN:
        return
    try:
        with open(path, 'w') as f:
            f.write(str(int(time.time())))
    except (OSError, IOError) as e:
        logger.error('cannot write flag {}: {}'.format(path, e))


def _clear_flag(path):
    if DRY_RUN or not os.path.exists(path):
        return
    try:
        os.remove(path)
    except (OSError, IOError) as e:
        logger.error('cannot remove flag {}: {}'.format(path, e))


def _token_age_days():
    """Age of the token file in days — it is rewritten only on renewal."""
    try:
        return (time.time() - os.path.getmtime(_IG_TOKEN_FILE)) / 86400.0
    except (OSError, IOError):
        return None


def _on_valid(age):
    if os.path.exists(FLAG_EXPIRED):
        _clear_flag(FLAG_EXPIRED)
        _clear_flag(FLAG_WARN)
        _tg_alert('✅ <b>Instagram: токен оновлено</b>\n\nGomonAI знову відповідає в Direct.')
        logger.info('token renewed, recovery alert sent')
        return 0

    if age is not None and age >= WARN_AT_DAYS:
        left = max(0, int(LIFETIME_DAYS - age))
        if os.path.exists(FLAG_WARN):
            logger.info('valid, {} day(s) left, warn flag already set'.format(left))
            return 0
        _set_flag(FLAG_WARN)
        _tg_alert(
            '⚠️ <b>Instagram: токен скоро протухне</b>\n\n'
            'Залишилось приблизно {} дн.\n\n'
            'Онови: Meta Console → Manage messaging &amp; content on Instagram → '
            'Step 2 «Generate access tokens» → dr.gomon'.format(left)
        )
        logger.warning('token expires in ~{} day(s), warning sent'.format(left))
        return 0

    _clear_flag(FLAG_WARN)
    logger.info('OK, age {} day(s)'.format(int(age) if age is not None else '?'))
    return 0


def _on_expired(payload):
    if os.path.exists(FLAG_EXPIRED):
        logger.info('expired, flag already set, skip duplicate alert')
        return 1
    _set_flag(FLAG_EXPIRED)
    _tg_alert(
        '🚨 <b>Instagram: токен протух</b>\n\n'
        'GomonAI НЕ відповідає в Direct — вхідні приходять, відповіді падають з 401. '
        'Клієнти лишаються без відповіді, поки не відпишете вручну.\n\n'
        'Онови: Meta Console → Manage messaging &amp; content on Instagram → '
        'Step 2 «Generate access tokens» → dr.gomon, '
        'потім поклади токен у private_data/ig_token.txt'
    )
    logger.error('token expired: {}'.format(payload[:200]))
    return 1


def main():
    token = get_ig_token()
    if not token:
        logger.error('no IG token configured')
        return 1

    age = _token_age_days()
    req = urllib.request.Request(GRAPH_URL.format(token), method='GET')

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status == 200:
                return _on_valid(age)
            logger.warning('unexpected status {}'.format(resp.status))
            return 0
    except urllib.error.HTTPError as e:
        payload = e.read().decode('utf-8', errors='replace')
        if 'OAuthException' in payload or e.code in (400, 401):
            return _on_expired(payload)
        logger.warning('HTTP {}: {}'.format(e.code, payload[:200]))
        return 0
    except Exception as e:
        # Network hiccup — transient, never alert on it
        logger.warning('transient: {}'.format(e))
        return 0


if __name__ == '__main__':
    sys.exit(main())
