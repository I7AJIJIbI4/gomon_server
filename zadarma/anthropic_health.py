#!/usr/bin/env python3
"""Synthetic Anthropic API ping — alert admin in TG when credit balance is exhausted.

Sends a ~$0.0002 request (max_tokens=5, single-token user input).
- HTTP 200            -> all good. If a previous low-balance flag exists, send "recovered" and clear it.
- HTTP 400 + "credit" -> low balance. Send alert once (idempotent via state flag) and exit.
- Anything else       -> log warning, do not alert (avoid noise on transient network errors).

Schedule via cron, e.g.:
  */30 * * * *  cd /opt/gomon/app/zadarma && /opt/gomon/venv/bin/python anthropic_health.py >> /var/log/gomon/anthropic_health.log 2>&1
"""
import os
import sys
import json
import logging
import logging.handlers
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import ANTHROPIC_KEY, TELEGRAM_TOKEN, ADMIN_USER_ID

LOG_PATH  = '/var/log/gomon/anthropic_health.log'
FLAG_PATH = '/tmp/anthropic_low_balance.flag'
MODEL     = 'claude-sonnet-4-6'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=512*1024, backupCount=2),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger('anthropic_health')


def _tg_alert(text):
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


def main():
    body = json.dumps({
        'model': MODEL,
        'max_tokens': 5,
        'messages': [{'role': 'user', 'content': 'hi'}],
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=body,
        headers={
            'x-api-key': ANTHROPIC_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status == 200:
                if os.path.exists(FLAG_PATH):
                    os.remove(FLAG_PATH)
                    _tg_alert('✅ Anthropic API: баланс відновлено, AI знов працює')
                    logger.info('balance recovered')
                else:
                    logger.info('OK')
                return 0
            logger.warning('unexpected status {}'.format(resp.status))
            return 0
    except urllib.error.HTTPError as e:
        payload = e.read().decode('utf-8', errors='replace')
        if e.code == 400 and 'credit balance' in payload.lower():
            if os.path.exists(FLAG_PATH):
                logger.info('low balance, flag already set, skip duplicate alert')
                return 0
            with open(FLAG_PATH, 'w') as f:
                f.write('low')
            _tg_alert(
                '🚨 <b>Anthropic API: кредити вичерпано</b>\n\n'
                'AI-чат у додатку, на сайті, в TG Business і IG зараз НЕ працює.\n\n'
                'Поповни баланс: https://console.anthropic.com/settings/billing'
            )
            logger.error('low balance alert sent')
            return 1
        # Other HTTP errors — auth failure, rate limit, server error — log but don't alert
        logger.warning('HTTP {}: {}'.format(e.code, payload[:200]))
        return 0
    except Exception as e:
        # Network errors etc. — transient, don't alert
        logger.warning('transient: {}'.format(e))
        return 0


if __name__ == '__main__':
    sys.exit(main())
