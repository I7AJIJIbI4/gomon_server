# -*- coding: utf-8 -*-
"""
Regression tests for the false "site down" alert of 25.10.2026.

At 14:20 the admin got «🔴 Dr. Gomon — проблеми: Сайт: з'єднання відхилено»,
and at 14:25 «Сайт — відновлено». The site never went down: nginx had not
restarted since 23.10, and only one of the five checks failed — the other four
hit the same host and passed.

Cause: the provider's primary resolver (first entry in /etc/resolv.conf) drops
DNS queries in bursts — measured 2 timeouts out of 5 queries, then 10 out of 10
clean a minute later. `requests` surfaces a DNS failure as ConnectionError, so a
single dropped query looked exactly like a refused connection. The same signature
hit on 14.06 and on 19.06, where the alert itself also failed to send with
NameResolutionError for api.telegram.org — nothing resolved at all.

`check_endpoint` now retries once before reporting a failure. A real outage
survives both attempts; a dropped DNS query does not.
"""
import os
import sys
import logging
import logging.handlers
import importlib.util

import pytest

ZADARMA = os.path.join(os.path.dirname(__file__), '..', 'zadarma')


class _NullRotatingHandler(logging.NullHandler):
    def __init__(self, *a, **kw):
        super().__init__()


@pytest.fixture(scope='module')
def hc():
    spec = importlib.util.spec_from_file_location(
        'health_check_real', os.path.join(ZADARMA, 'health_check.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules['health_check_real'] = mod
    _orig = logging.handlers.RotatingFileHandler
    logging.handlers.RotatingFileHandler = _NullRotatingHandler
    try:
        spec.loader.exec_module(mod)
    finally:
        logging.handlers.RotatingFileHandler = _orig
    return mod


@pytest.fixture(autouse=True)
def _no_real_sleep(hc, monkeypatch):
    """Повтор не має коштувати сюїті 5 секунд."""
    slept = []
    monkeypatch.setattr(hc.time, 'sleep', lambda s: slept.append(s))
    return slept


CHECK = {'name': 'Сайт', 'url': 'https://drgomon.beauty/', 'expect': 200,
         'contains': 'Dr. Gomon'}


def _attempts(hc, monkeypatch, results):
    """Підміняє _check_once послідовністю результатів; повертає лічильник."""
    calls = []

    def _fake(check):
        calls.append(check['name'])
        return results[min(len(calls) - 1, len(results) - 1)]

    monkeypatch.setattr(hc, '_check_once', _fake)
    return calls


class TestRetry:

    def test_healthy_check_is_not_retried(self, hc, monkeypatch, _no_real_sleep):
        calls = _attempts(hc, monkeypatch, [(True, None)])
        assert hc.check_endpoint(CHECK) == (True, None)
        assert len(calls) == 1, 'успішна перевірка не має робити зайвий запит'
        assert _no_real_sleep == []

    def test_transient_blip_does_not_alert(self, hc, monkeypatch, _no_real_sleep):
        """Саме випадок 25.10: перша спроба впала, друга пройшла."""
        calls = _attempts(hc, monkeypatch, [
            (False, "Сайт: з'єднання відхилено"),
            (True, None),
        ])
        ok, err = hc.check_endpoint(CHECK)
        assert ok is True
        assert err is None
        assert len(calls) == 2
        assert _no_real_sleep == [hc.RETRY_DELAY]

    def test_real_outage_still_alerts(self, hc, monkeypatch, _no_real_sleep):
        """Справжнє падіння переживає обидві спроби."""
        calls = _attempts(hc, monkeypatch, [(False, "Сайт: з'єднання відхилено")])
        ok, err = hc.check_endpoint(CHECK)
        assert ok is False
        assert err == "Сайт: з'єднання відхилено"
        assert len(calls) == 2

    def test_second_error_is_the_one_reported(self, hc, monkeypatch, _no_real_sleep):
        """Повідомляємо стан на момент повтору, а не перший, уже застарілий."""
        _attempts(hc, monkeypatch, [
            (False, "Сайт: з'єднання відхилено"),
            (False, 'Сайт: HTTP 502 (очікувався 200)'),
        ])
        ok, err = hc.check_endpoint(CHECK)
        assert ok is False
        assert err == 'Сайт: HTTP 502 (очікувався 200)'

    def test_retry_is_capped_at_one(self, hc, monkeypatch, _no_real_sleep):
        """Рівно дві спроби — крон ходить кожні 5 хв, довше висіти не можна."""
        calls = _attempts(hc, monkeypatch, [(False, 'Сайт: таймаут (15с)')])
        hc.check_endpoint(CHECK)
        assert len(calls) == 2
        assert len(_no_real_sleep) == 1

    def test_worst_case_fits_in_the_cron_interval(self, hc):
        """5 перевірок × 2 спроби × таймаут + паузи мають вкластися у 5 хвилин."""
        worst = len(hc.CHECKS) * (2 * hc.TIMEOUT + hc.RETRY_DELAY)
        assert worst < 300, 'прогін може накластися на наступний запуск крону'


class TestSingleAttemptUnchanged:
    """_check_once лишилась тією ж функцією, лише перейменованою."""

    def test_connection_error_text_preserved(self, hc, monkeypatch):
        import requests

        def _boom(*a, **kw):
            raise requests.exceptions.ConnectionError('dns')

        monkeypatch.setattr(hc.requests, 'get', _boom)
        ok, err = hc._check_once(CHECK)
        assert ok is False
        assert err == "Сайт: з'єднання відхилено"

    def test_timeout_text_preserved(self, hc, monkeypatch):
        import requests

        def _boom(*a, **kw):
            raise requests.exceptions.Timeout()

        monkeypatch.setattr(hc.requests, 'get', _boom)
        ok, err = hc._check_once(CHECK)
        assert ok is False
        assert err == 'Сайт: таймаут ({}с)'.format(hc.TIMEOUT)

    def test_content_mismatch_detected(self, hc, monkeypatch):
        class _R:
            status_code = 200
            text = 'сторінка-заглушка'

        monkeypatch.setattr(hc.requests, 'get', lambda *a, **kw: _R())
        ok, err = hc._check_once(CHECK)
        assert ok is False
        assert 'не містить' in err
