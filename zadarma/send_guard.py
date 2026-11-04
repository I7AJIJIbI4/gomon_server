#!/usr/bin/env python3
"""Запобіжник масових розсилок для cron-скриптів.

17.10.2026 лікар підтвердила в боті беклог із 124 кнопок, і `photo_reminder.py
--cashback-notify` за годину розіслав 125 повідомлень (100 SMS) 80 клієнтам —
про візити тримісячної давності. Звичайний пік — до 10 повідомлень за запуск.

Кожна відправка клієнту (SMS, TG, push, IG у notifier/sms_fly) спершу питає
allow(). Діє лише там, де задано GOMON_SEND_CAP — тобто в cron (змінна в
deploy/crontab). API, боти й OTP-коди не обмежуються.

  - Понад GOMON_SEND_CAP відправок за один запуск процесу — запобіжник
    спрацьовує: пише прапорець, один раз шле адміну TG і далі нічого не шле.
  - Поки прапорець лежить, ЖОДЕН cron-скрипт нічого не шле. Це ж і ручний
    вимикач: `touch` — зупинити розсилки, `rm` — відновити.

Заблоковані відправки повертають False, тож notifier запише їх як failed і
повторно не надсилатиме: зупинена розсилка не «доганяє» після зняття прапорця.
"""
import os
import json
import logging

logger = logging.getLogger('send_guard')

FLAG_PATH = os.environ.get('GOMON_SEND_PAUSE_FLAG', '/opt/gomon/send_paused.flag')

_count = 0
_tripped = False


def _cap():
    try:
        return int(os.environ.get('GOMON_SEND_CAP') or 0)
    except ValueError:
        return 0


def _alert_admin(text):
    """Напряму в Bot API, повз запобіжник і notifier."""
    try:
        import requests
        from config import TELEGRAM_TOKEN, ADMIN_USER_ID
        requests.post('https://api.telegram.org/bot{}/sendMessage'.format(TELEGRAM_TOKEN),
                      json={'chat_id': ADMIN_USER_ID, 'text': text}, timeout=10)
    except Exception as e:
        logger.error('send_guard alert failed: {}'.format(e))


def _trip(channel, to):
    global _tripped
    _tripped = True
    import sys
    script = os.path.basename(sys.argv[0]) + ' ' + ' '.join(sys.argv[1:])
    try:
        with open(FLAG_PATH, 'w') as f:
            json.dump({'script': script.strip(), 'cap': _cap(), 'channel': channel}, f)
    except OSError as e:
        logger.error('send_guard: cannot write {}: {}'.format(FLAG_PATH, e))
    logger.error('send_guard TRIPPED: {} tried more than {} sends (next: {} to {})'.format(
        script, _cap(), channel, to))
    _alert_admin(
        '🛑 Розсилку зупинено\n\n'
        '{} за один запуск спробував надіслати клієнтам більше {} повідомлень. '
        'Звичайно це до 10 — схоже на повтор 17.10.\n\n'
        'Усі cron-розсилки (SMS, TG, push) на паузі. Перевір /var/log/gomon/, '
        'а щоб відновити: rm {}'.format(script.strip(), _cap(), FLAG_PATH))


def allow(channel, to=''):
    """True — можна слати. False — запобіжник спрацював або розсилки на паузі."""
    global _count
    if not _cap():
        return True
    if _tripped or os.path.exists(FLAG_PATH):
        logger.warning('send_guard: {} to {} blocked (sends paused: {})'.format(channel, to, FLAG_PATH))
        return False
    _count += 1
    if _count > _cap():
        _trip(channel, to)
        return False
    return True
