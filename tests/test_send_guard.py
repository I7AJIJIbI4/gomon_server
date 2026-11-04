# -*- coding: utf-8 -*-
"""
send_guard — запобіжник масових розсилок cron-скриптів.

17.10.2026 photo_reminder --cashback-notify за один прогін розіслав 125
повідомлень (100 SMS) 80 клієнтам. Звичайний пік — до 10. Тепер понад
GOMON_SEND_CAP за запуск — пауза всіх cron-розсилок, прапорець і одна
тривога адміну; поки прапорець лежить, cron не шле нічого.
"""
import os
import sys

import pytest

from conftest import load_real


@pytest.fixture
def guard(tmp_path, monkeypatch):
    mod = load_real('send_guard', 'send_guard.py')         # під справжнім ім'ям: його імпортують notifier і sms_fly
    monkeypatch.setattr(mod, 'FLAG_PATH', str(tmp_path / 'send_paused.flag'))
    alerts = []
    monkeypatch.setattr(mod, '_alert_admin', alerts.append)
    mod._alerts = alerts
    yield mod
    sys.modules.pop('send_guard', None)


def test_no_cap_means_no_limit(guard, monkeypatch):
    """API, боти, OTP: GOMON_SEND_CAP не задано — запобіжник не втручається взагалі."""
    monkeypatch.delenv('GOMON_SEND_CAP', raising=False)
    assert all(guard.allow('sms', '380500000000') for _ in range(500))
    assert not os.path.exists(guard.FLAG_PATH)
    open(guard.FLAG_PATH, 'w').close()
    assert guard.allow('sms', '380500000000'), 'пауза стосується лише cron'


def test_cap_trips_once_and_pauses(guard, monkeypatch):
    monkeypatch.setenv('GOMON_SEND_CAP', '3')
    assert [guard.allow('sms', str(i)) for i in range(5)] == [True, True, True, False, False]
    assert os.path.exists(guard.FLAG_PATH)
    assert len(guard._alerts) == 1, 'одна тривога, а не на кожне заблоковане'
    assert 'Розсилку зупинено' in guard._alerts[0]
    assert 'rm ' + guard.FLAG_PATH in guard._alerts[0]


def test_counts_all_channels_together(guard, monkeypatch):
    """17.10 це були SMS, TG і push разом — рахуємо сумарно."""
    monkeypatch.setenv('GOMON_SEND_CAP', '3')
    assert [guard.allow(ch) for ch in ('sms', 'tg', 'push', 'ig')] == [True, True, True, False]


def test_pause_flag_stops_the_next_run_too(guard, monkeypatch):
    """Наступний запуск крону (новий процес, лічильник з нуля) теж нічого не шле."""
    monkeypatch.setenv('GOMON_SEND_CAP', '30')
    open(guard.FLAG_PATH, 'w').close()
    assert guard.allow('sms') is False
    assert guard._alerts == []
    os.remove(guard.FLAG_PATH)                   # адмін розібрався і зняв паузу
    assert guard.allow('sms') is True


def test_manual_kill_switch(guard, monkeypatch):
    """touch прапорця вручну — той самий вимикач."""
    monkeypatch.setenv('GOMON_SEND_CAP', '30')
    open(guard.FLAG_PATH, 'w').close()
    assert [guard.allow(ch) for ch in ('sms', 'tg', 'push')] == [False, False, False]


# ── Підключення до справжніх відправників ─────────────────────────────────────

@pytest.fixture
def sms_fly(guard, monkeypatch):
    for k, v in (('SMS_FLY_PASSWORD', 'pw'), ('SMS_FLY_SENDER', 'Gomon'), ('SMS_FLY_VIBER_SENDER', '')):
        monkeypatch.setattr(sys.modules['config'], k, v, raising=False)
    mod = load_real('sms_fly_guard_real', 'sms_fly.py')
    posts = []

    class _R(object):
        status_code = 200
        text = '{"success":1}'

        def json(self):
            return {'success': 1, 'data': {}}
    monkeypatch.setattr(mod.requests, 'post', lambda *a, **kw: posts.append(kw.get('json') or a) or _R())
    mod._posts = posts
    return mod


def test_sms_gateway_stops_at_the_cap(sms_fly, guard, monkeypatch):
    monkeypatch.setenv('GOMON_SEND_CAP', '2')
    for _ in range(5):
        sms_fly.send_sms('0671234567', 'Нагадування')
    assert len(sms_fly._posts) == 2, 'після ліміту sms-fly не викликається'
    assert os.path.exists(guard.FLAG_PATH)


@pytest.fixture
def notifier(guard, tmp_path, monkeypatch):
    mod = load_real('notifier_guard_real', 'notifier.py', db_path=str(tmp_path / 'u.db'))
    sent = []

    class _R(object):
        def json(self):
            return {'ok': True}
    monkeypatch.setattr(mod.requests, 'post', lambda url, json=None, **kw: sent.append(json) or _R())
    mod._sent = sent
    return mod


def test_tg_to_clients_is_paused_but_admin_alerts_still_go(notifier, guard, monkeypatch):
    """Під час паузи службові повідомлення адміну мають доходити — інакше пауза глуха."""
    monkeypatch.setenv('GOMON_SEND_CAP', '30')
    open(guard.FLAG_PATH, 'w').close()
    admin = sys.modules['config'].ADMIN_USER_IDS[0]
    assert notifier._send_tg(111222333, 'клієнту') is False
    assert notifier._send_tg(admin, 'адміну') is True
    assert [m['chat_id'] for m in notifier._sent] == [admin]


def test_push_and_ig_respect_the_pause(notifier, guard, monkeypatch):
    monkeypatch.setenv('GOMON_SEND_CAP', '30')
    open(guard.FLAG_PATH, 'w').close()
    assert notifier._send_push('380671234567', 'T', 'B') is False
    assert notifier._send_ig('1784', 'text') is False
    assert notifier._sent == []


def test_crontab_turns_the_guard_on():
    """Без змінної в crontab запобіжник у cron не діяв би."""
    path = os.path.join(os.path.dirname(__file__), '..', 'deploy', 'crontab')
    lines = open(path, encoding='utf-8').read().splitlines()
    cap = [l for l in lines if l.startswith('GOMON_SEND_CAP=')]
    assert cap, 'GOMON_SEND_CAP не задано в deploy/crontab'
    assert 10 < int(cap[0].split('=')[1]) <= 50, 'вище звичайного піку (10), нижче за 17.10 (125)'
