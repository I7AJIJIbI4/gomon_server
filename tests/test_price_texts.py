# -*- coding: utf-8 -*-
"""
Описи процедур і курсові ціни не зникають «самі».

- Адмінський редактор цін показує й надсилає лише назву, ціну, спеціалістів і
  тривалість. Без злиття зі старим файлом перше ж збереження прайсу з адмінки
  стирало б опис, підготовку й догляд з картки процедури на сайті та в додатку.
- Редактор не пов'язаний з WLaunch: збереження прайсу нічого у WLaunch не змінює,
  а маршруту, що тягнув ціни з WLaunch у прайс, більше немає.
"""
import json

import pytest

from conftest import auth, _insert_session


@pytest.fixture
def prices_file(pwa):
    orig = open(pwa.PRICES_PATH, 'rb').read()

    def write(data):
        with open(pwa.PRICES_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

    def read():
        with open(pwa.PRICES_PATH, encoding='utf-8') as f:
            return json.load(f)

    yield write, read
    with open(pwa.PRICES_PATH, 'wb') as f:
        f.write(orig)


@pytest.fixture
def full_admin():
    return _insert_session('380996093860')


WOW = {'name': 'WOW-чистка обличчя', 'price': '₴ 1800', 'specialists': ['victoria'],
       'desc': 'Демакіяж, гідруючий гель, ультразвуковий скрабінг.',
       'prep': 'Без макіяжу.', 'aftercare': 'SPF наступного дня.'}


def test_saving_prices_from_admin_keeps_descriptions(client, full_admin, prices_file):
    write, read = prices_file
    write([{'cat': 'WOW-чистка обличчя', 'items': [dict(WOW)]}])

    # Так надсилає редактор: без desc/prep/aftercare, з новою ціною
    payload = [{'cat': 'WOW-чистка обличчя', 'items': [
        {'name': 'WOW-чистка обличчя', 'price': '₴ 1900', 'specialists': ['victoria'], 'duration': 90}]}]
    rv = client.put('/api/admin/prices/edit', json=payload, headers=auth(full_admin))
    assert rv.status_code == 200

    item = read()[0]['items'][0]
    assert item['price'] == '₴ 1900'
    assert (item['desc'], item['prep'], item['aftercare']) == (WOW['desc'], WOW['prep'], WOW['aftercare'])


def test_new_item_from_admin_has_no_borrowed_description(client, full_admin, prices_file):
    write, read = prices_file
    write([{'cat': 'WOW-чистка обличчя', 'items': [dict(WOW)]}])
    payload = [{'cat': 'WOW-чистка обличчя', 'items': [
        {'name': 'WOW-чистка обличчя', 'price': '₴ 1800', 'specialists': ['victoria']},
        {'name': 'Нова чистка', 'price': '₴ 1000', 'specialists': ['victoria']}]}]
    client.put('/api/admin/prices/edit', json=payload, headers=auth(full_admin))

    items = {i['name']: i for i in read()[0]['items']}
    assert 'desc' not in items['Нова чистка']
    assert items['WOW-чистка обличчя']['desc'] == WOW['desc']


def test_saving_prices_from_admin_does_not_touch_wlaunch(client, full_admin, prices_file, pwa,
                                                         monkeypatch):
    """Редактор змінює лише наш прайс. Раніше фоновий потік пушив у WLaunch ціни,
    тривалість, перейменування, спеціалістів і вимикав послуги, яких немає в прайсі."""
    write, read = prices_file
    write([{'cat': 'WOW-чистка обличчя', 'items': [dict(WOW)]}])
    calls = []
    for m in ('get', 'post', 'put', 'delete'):
        monkeypatch.setattr(pwa._req, m, lambda *a, _m=m, **kw: calls.append((_m, a)))
    started = []
    monkeypatch.setattr('threading.Thread.start', lambda self: started.append(self))

    # Позицію видалено, ціну й тривалість змінено — нічого з цього не йде у WLaunch
    payload = [{'cat': 'WOW-чистка обличчя', 'items': [
        {'name': 'Нова чистка', 'price': '₴ 2000', 'specialists': ['anastasia'], 'duration': 45}]}]
    rv = client.put('/api/admin/prices/edit', json=payload, headers=auth(full_admin))
    assert rv.status_code == 200
    assert calls == [] and started == []
    assert 'duration' not in read()[0]['items'][0]


def test_sync_prices_from_wlaunch_is_gone(client, full_admin):
    """Зворотний бік — ціни з WLaunch у наш прайс — теж прибрано."""
    rv = client.post('/api/admin/sync-prices', headers=auth(full_admin))
    assert rv.status_code in (404, 405)


def test_editor_shows_duration_read_only():
    import os
    path = os.path.join(os.path.dirname(__file__), '..', 'public_html', 'app', 'index.html')
    src = open(path, encoding='utf-8').read()
    line = [ln for ln in src.splitlines() if 'adm-proc-dur-inp" type="number"' in ln][0]
    assert 'readonly' in line and 'oninput' not in line
