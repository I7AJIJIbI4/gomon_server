# -*- coding: utf-8 -*-
"""
Групи прайсу в додатку = картки послуг на сайті.

Сайт розкладає категорії prices.json по картках у modal_prices.php ключовими
словами. Додаток робить те саме в pwa_api.price_group, і якщо два списки
розійдуться, клієнт побачить у додатку одне групування, а на сайті інше.
Категорії без картки (консультації, корекції) клієнту не показуються ніде,
але адмінка їх бачить — інакше їх не було б як редагувати.
"""
import os
import re
import json
import pytest
from conftest import auth, _insert_session

PHP = os.path.join(os.path.dirname(__file__), '..', 'public_html', 'sitepro', 'modal_prices.php')

# Категорії живого прайсу станом на 28.10.2026 і картки, у яких їх показує сайт
LIVE = [
    ('WOW-чистка обличчя', 1),
    ('Киснева терапія', 1),
    ('Консультація лікаря', None),
    ('Ботулінотерапія Neuronox / Nabota', 2),
    ('Ботулінотерапія Xeomin', 2),
    ('Контурна пластика губ', 2),
    ('Контурна пластика обличчя', 2),
    ('Біорепарація шкіри', 2),
    ('Біоревіталізація шкіри', 2),
    ('Мезотерапія', 2),
    ('Ферментотерапія', 2),
    ('Корекції', None),
    ('Ботулінотерапія (спеціальні)', 2),
    ('Доглядові процедури', 3),
    ('Пілінги-біоревіталізанти', 3),
    ('Пілінги Simildiet', 3),
    ('DrumRoll «Моделювання фігури»', 5),
    ('DrumRoll Релакс-масаж', 5),
    ('Лімфодренажна пресотерапія', 5),
    ('Відбілювання зубів Magic Smile', 6),
]


@pytest.mark.parametrize('cat,expected', LIVE)
def test_live_categories_land_where_the_site_shows_them(pwa, cat, expected):
    g = pwa.price_group(cat)
    assert (g[0] if g else None) == expected


def test_keywords_mirror_the_site(pwa):
    """Ті самі картки, ті самі слова, той самий порядок перевірки, що в PHP."""
    src = open(PHP, encoding='utf-8').read()
    block = re.search(r'\$catMap = \[(.*?)\n\];', src, re.S).group(1)
    php = [(int(gid), [a or b for a, b in re.findall(r"""'([^']*)'|"([^"]*)\"""", kws)])
           for gid, kws in re.findall(r'(\d+) => \[(.*?)\]', block)]
    assert php == [(gid, kws) for gid, _, kws in pwa.PRICE_GROUPS]


def _with_prices(pwa, prices):
    with open(pwa.PRICES_PATH, 'w', encoding='utf-8') as f:
        json.dump(prices, f)


_MIXED = [
    {'cat': 'Корекції', 'items': [{'name': 'Корекція філера', 'price': '0'}]},
    {'cat': 'Мезотерапія', 'items': [{'name': 'Мезо', 'price': '2000'}]},
    {'cat': 'WOW-чистка обличчя', 'items': [{'name': 'WOW', 'price': '1400'}]},
]


@pytest.fixture
def mixed(pwa):
    orig = open(pwa.PRICES_PATH, 'rb').read()
    _with_prices(pwa, _MIXED)
    yield
    with open(pwa.PRICES_PATH, 'wb') as f:
        f.write(orig)


def test_client_prices_hide_categories_without_a_card(client, mixed):
    data = client.get('/api/prices').get_json()
    assert [c['cat'] for c in data] == ['Мезотерапія', 'WOW-чистка обличчя']
    assert data[0]['group_id'] == 2 and data[0]['group'] == "Ін'єкційна косметологія"
    assert data[1]['group_id'] == 1 and data[1]['group'] == 'Апаратна косметологія'


def test_admin_editor_keeps_categories_without_a_card(client, mixed):
    token = _insert_session('380996093860')
    data = client.get('/api/admin/prices/edit', headers=auth(token)).get_json()
    assert [c['cat'] for c in data] == ['Корекції', 'Мезотерапія', 'WOW-чистка обличчя']
    assert data[0]['group_id'] is None and data[0]['group'] is None
    assert data[1]['group_id'] == 2


def test_saving_does_not_write_the_group_into_the_file(client, pwa, mixed):
    """Група виводиться з назви: збережена у файл, вона б застаріла при перейменуванні."""
    token = _insert_session('380996093860')
    data = client.get('/api/admin/prices/edit', headers=auth(token)).get_json()
    rv = client.put('/api/admin/prices/edit', json=data, headers=auth(token))
    assert rv.status_code == 200
    saved = json.load(open(pwa.PRICES_PATH, encoding='utf-8'))
    assert all('group' not in c and 'group_id' not in c for c in saved)
    assert [c['cat'] for c in saved] == ['Корекції', 'Мезотерапія', 'WOW-чистка обличчя']
