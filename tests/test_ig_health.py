# -*- coding: utf-8 -*-
"""
ig_health.py — вартовий Instagram-токена.

Токен живе ~60 днів. Коли він протухає, вхідні в Direct приходять, GomonAI
генерує відповіді, але кожна відправка падає з 401, і клієнт мовчки лишається
без відповіді. Так було 12 днів у серпні 2026 і 16 годин 01–02.11.2026. Цей
скрипт — єдине, що це помічає, тож перевіряємо всі його гілки:

  - валідний свіжий токен          -> тиша
  - валідний, вік >= 53 дні         -> одне попередження, без повторів
  - протух (OAuthException/401)     -> одна тривога, без повторів, код 1
  - оновили після протухання        -> одне «токен оновлено», прапорці зняті
  - мережа/5xx                       -> тиша: короткі збої не будять адміна
"""
import io
import os
import sys
import time
import urllib.error

import pytest

from conftest import load_real


@pytest.fixture
def ig(tmp_path, monkeypatch):
    token_file = tmp_path / 'ig_token.txt'
    token_file.write_text('IGAA_test')
    monkeypatch.setattr(sys.modules['config'], '_IG_TOKEN_FILE', str(token_file), raising=False)
    mod = load_real('ig_health_real', 'ig_health.py')
    monkeypatch.setattr(mod, 'FLAG_EXPIRED', str(tmp_path / 'expired.flag'))
    monkeypatch.setattr(mod, 'FLAG_WARN', str(tmp_path / 'warn.flag'))
    monkeypatch.setattr(mod, '_IG_TOKEN_FILE', str(token_file))
    monkeypatch.setattr(mod, 'DRY_RUN', False)

    alerts = []
    monkeypatch.setattr(mod, '_tg_alert', alerts.append)
    mod._alerts = alerts
    mod._token_file = token_file
    return mod


def _age(mod, days):
    """Файл токена переписується лише при оновленні — його mtime і є вік."""
    t = time.time() - days * 86400
    os.utime(str(mod._token_file), (t, t))


def _graph(monkeypatch, mod, status=200, body='{"id":"1","username":"dr.gomon"}', exc=None):
    """Підмінити відповідь graph.instagram.com."""
    def _urlopen(req, timeout=None):
        if exc is not None:
            raise exc
        if status != 200:
            raise urllib.error.HTTPError(req.full_url, status, 'err', {},
                                         io.BytesIO(body.encode('utf-8')))

        class _Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        r = _Resp(body.encode('utf-8'))
        r.status = 200
        return r
    monkeypatch.setattr(mod.urllib.request, 'urlopen', _urlopen)


_EXPIRED = ('{"error":{"message":"Error validating access token: Session has expired",'
            '"type":"OAuthException","code":190}}')


def test_fresh_valid_token_is_quiet(ig, monkeypatch):
    _age(ig, 10)
    _graph(monkeypatch, ig)
    assert ig.main() == 0
    assert ig._alerts == []
    assert not os.path.exists(ig.FLAG_WARN)


def test_ageing_token_warns_once(ig, monkeypatch):
    _age(ig, 54.5)                  # не рівно 55: за мілісекунди вік стане 55.0001 і int() дасть 4
    _graph(monkeypatch, ig)
    assert ig.main() == 0
    assert len(ig._alerts) == 1
    assert 'скоро протухне' in ig._alerts[0]
    assert 'Залишилось приблизно 5 дн.' in ig._alerts[0]

    ig.main()                       # наступний запуск крону
    assert len(ig._alerts) == 1, 'попередження не має приходити щодня'


def test_expired_token_alerts_once_and_fails(ig, monkeypatch):
    _age(ig, 61)
    _graph(monkeypatch, ig, status=400, body=_EXPIRED)
    assert ig.main() == 1
    assert len(ig._alerts) == 1
    assert 'токен протух' in ig._alerts[0]

    assert ig.main() == 1
    assert len(ig._alerts) == 1, 'тривога про протухлий токен — один раз, не щозапуску'


def test_plain_401_counts_as_expired(ig, monkeypatch):
    _graph(monkeypatch, ig, status=401, body='Unauthorized')
    assert ig.main() == 1
    assert len(ig._alerts) == 1


def test_renewal_after_expiry_sends_recovery_and_clears_flags(ig, monkeypatch):
    _age(ig, 61)
    _graph(monkeypatch, ig, status=400, body=_EXPIRED)
    ig.main()

    _age(ig, 0)                     # поклали новий токен
    _graph(monkeypatch, ig)
    assert ig.main() == 0
    assert 'токен оновлено' in ig._alerts[-1]
    assert not os.path.exists(ig.FLAG_EXPIRED)
    assert not os.path.exists(ig.FLAG_WARN)


@pytest.mark.parametrize('kind', ['network', 'http_500'])
def test_transient_failures_never_alert(ig, monkeypatch, kind):
    if kind == 'network':
        _graph(monkeypatch, ig, exc=urllib.error.URLError('timed out'))
    else:
        _graph(monkeypatch, ig, status=500, body='{"error":"internal"}')
    assert ig.main() == 0
    assert ig._alerts == []
    assert not os.path.exists(ig.FLAG_EXPIRED)


def test_missing_token_is_an_error_not_silence(ig, monkeypatch):
    monkeypatch.setattr(ig, 'get_ig_token', lambda: '')
    assert ig.main() == 1
