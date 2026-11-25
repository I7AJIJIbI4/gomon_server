# -*- coding: utf-8 -*-
"""
Описи процедур і курсові ціни не зникають «самі».

- Адмінський редактор цін показує й надсилає лише назву, ціну, спеціалістів і
  тривалість. Без злиття зі старим файлом перше ж збереження прайсу з адмінки
  стирало б опис, підготовку й догляд з картки процедури на сайті та в додатку.
- Кнопка «синхронізувати ціни з WLaunch» порівнювала ціну як рядок і переписувала
  «₴ 900 (курсом ₴ 720)» на «₴ 900» — курсова ціна зникала з прайсу.
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


class _Resp:
    status_code = 200

    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def _wlaunch(pwa, monkeypatch, prices_uah):
    """WLaunch з однією текою й послугами {назва: ціна в грн}."""
    sys_wl = __import__('sys').modules['wlaunch_api']
    monkeypatch.setattr(sys_wl, 'get_branch_id', lambda: 'branch-1', raising=False)
    monkeypatch.setattr(sys_wl, 'HEADERS', {}, raising=False)
    names = list(prices_uah)

    def get(url, params=None, **kw):
        params = params or {}
        if url.endswith('/prices'):
            sid = url.rsplit('/', 2)[-2]
            return _Resp({'content': [{'amount': prices_uah[names[int(sid)]] * 100}]})
        if params.get('type') == 'GROUP':
            return _Resp({'content': [{'id': 'g1'}]})
        return _Resp({'content': [{'id': str(i), 'name': n} for i, n in enumerate(names)]})

    monkeypatch.setattr(pwa._req, 'get', get)


def test_sync_prices_keeps_the_course_price(client, full_admin, prices_file, pwa, monkeypatch):
    write, read = prices_file
    write([{'cat': 'Тіло', 'items': [
        {'name': 'DrumRoll · усе тіло', 'price': '₴ 900 (курсом ₴ 720)', 'specialists': ['anastasia']},
        {'name': 'Пресотерапія', 'price': '₴ 650 (курсом ₴ 520)', 'specialists': ['anastasia']}]}])
    _wlaunch(pwa, monkeypatch, {'DrumRoll · усе тіло': 900, 'Пресотерапія': 700})

    rv = client.post('/api/admin/sync-prices', headers=auth(full_admin))
    assert rv.status_code == 200
    assert rv.get_json()['updated'] == 1

    items = {i['name']: i['price'] for i in read()[0]['items']}
    assert items['DrumRoll · усе тіло'] == '₴ 900 (курсом ₴ 720)', 'та сама сума — рядок не чіпаємо'
    assert items['Пресотерапія'] == '₴ 700', 'інша сума — оновлюємо'


# ── ціна у WLaunch: PUT лише створює, наявну оновлює POST з id ────────────────

class _Rec:
    def __init__(self, existing):
        self.existing = existing
        self.calls = []

    def get(self, url, **kw):
        return _Resp({'content': [{'id': 'price-1', 'amount': 120000}] if self.existing else []})

    def post(self, url, json=None, **kw):
        self.calls.append(('POST', json))
        return _Resp({})

    def put(self, url, json=None, **kw):
        self.calls.append(('PUT', json))
        return _Resp({})


@pytest.mark.parametrize('existing,method,with_id', [(True, 'POST', True), (False, 'PUT', False)])
def test_wlaunch_price_is_updated_or_created(pwa, monkeypatch, existing, method, with_id):
    rec = _Rec(existing)
    monkeypatch.setattr(pwa._req, 'get', rec.get)
    monkeypatch.setattr(pwa._req, 'post', rec.post)
    monkeypatch.setattr(pwa._req, 'put', rec.put)

    assert pwa._wl_set_price('svc-1', 150000, {}, 'list-1')
    assert len(rec.calls) == 1
    m, body = rec.calls[0]
    price = body['prices'][0]
    assert m == method
    assert (price['service_id'], price['amount']) == ('svc-1', 150000)
    assert ('id' in price) == with_id
