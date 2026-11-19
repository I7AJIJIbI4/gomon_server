# -*- coding: utf-8 -*-
"""
Оплата частинами: не більше 3 частин.

Додаток просив від 5 000 грн 4 частини, від 7 000 — 6, від 10 000 — 10. Мерчанту
WayForPay дозволено до 3, тож від 5 000 грн віджет ховав оплату частинами.
"""
import itertools
import os
import re

import pytest

from conftest import auth

ROOT = os.path.join(os.path.dirname(__file__), '..')


@pytest.fixture(autouse=True)
def _unique_order_ids(pwa, monkeypatch):
    """order_id будується з секунди: кілька запитів за секунду дали б той самий номер."""
    real = pwa.time.time
    monkeypatch.setattr(pwa.time, 'time', lambda: real() + next(_TICK))


_TICK = itertools.count(1000)


def _systems(client, token, amount, parts):
    r = client.post('/api/deposit/create', json={'amount': amount, 'installments': parts},
                    headers=auth(token))
    assert r.status_code == 200, r.get_json()
    return r.get_json()['widget_params'].get('paymentSystems', '')


@pytest.mark.parametrize('amount,parts', [(5000, 4), (7000, 6), (10000, 10), (3000, 12)])
def test_old_app_asking_for_more_than_three_parts_gets_three(client, client_token, amount, parts):
    """Старі закешовані версії додатка ще шлють 4–10 частин — сервер урізає до 3."""
    systems = _systems(client, client_token, amount, parts)

    assert set(re.findall(r':(\d+)', systems)) == {'3'}
    assert 'payPartsMono:3' in systems and 'payPartsPrivat:3' in systems


def test_two_parts_stay_two(client, client_token):
    assert set(re.findall(r':(\d+)', _systems(client, client_token, 2000, 2))) == {'2'}


def test_regular_top_up_has_no_installments(client, client_token):
    assert _systems(client, client_token, 5000, 0) == ''


def test_app_always_asks_for_three_parts():
    with open(os.path.join(ROOT, 'public_html', 'app', 'index.html'), encoding='utf-8') as fh:
        src = fh.read()
    assert 'if (installments) body.installments = 3;' in src
