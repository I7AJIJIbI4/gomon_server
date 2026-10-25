# -*- coding: utf-8 -*-
"""
Етап 1 онлайн-запису: кеш каталогу WLaunch + детектор розходжень.

Меню запису — активні послуги філії WLaunch, бо саме WLaunch веде розклад лікаря.
Клієнт записується на узагальнену послугу («Біорепарація шкіри»), препарат лікар
проставляє після процедури кнопками в TG.

Детектор потрібен тому, що каталог змінюють у WLaunch, а не в нас, і про зміну
ніхто не повідомляє. Без нього `_cat_map` у wlaunch_api згнив непомітно: 18 із 33
цілей указували на послуги, яких уже не існує, і виявилось це лише через відмови
при записі.

Фікстури — живі дані, зняті 25.10.2026.
"""
import os
import sys
import json
import sqlite3
import logging
import logging.handlers
import importlib.util

import pytest

ZADARMA = os.path.join(os.path.dirname(__file__), '..', 'zadarma')


class _NullRotatingHandler(logging.NullHandler):
    def __init__(self, *a, **kw):
        super().__init__()


@pytest.fixture(scope='module')
def wc():
    spec = importlib.util.spec_from_file_location(
        'wl_catalog_real', os.path.join(ZADARMA, 'wl_catalog.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules['wl_catalog_real'] = mod
    _orig = logging.handlers.RotatingFileHandler
    logging.handlers.RotatingFileHandler = _NullRotatingHandler
    try:
        spec.loader.exec_module(mod)
    finally:
        logging.handlers.RotatingFileHandler = _orig
    return mod


#: Зрізи prices.json, 25.10.2026 — поле specialists стоїть на рівні препарату
PRICES = [
    {'cat': 'Ботулінотерапія Neuronox / Nabota', 'items': [
        {'name': 'Ботулінотерапія 1 зона (Neuronox)', 'price': '₴ 2200',
         'specialists': ['victoria']},
        {'name': 'Ботулінотерапія Full Face (Neuronox)', 'price': '₴ 8800',
         'specialists': ['victoria']},
    ]},
    {'cat': 'Біорепарація шкіри', 'items': [
        {'name': 'Біорепарація Rejuran HB', 'price': '₴ 4500', 'specialists': ['victoria']},
        {'name': 'Біорепарація Rejuran I', 'price': '₴ 4000', 'specialists': ['victoria']},
    ]},
    {'cat': 'DrumRoll «Моделювання фігури»', 'items': [
        {'name': 'Моделювання всього тіла', 'price': '₴ 900', 'specialists': ['anastasia']},
        {'name': 'Моделювання окремої ділянки', 'price': '₴ 600', 'specialists': ['anastasia']},
    ]},
    {'cat': 'Відбілювання зубів Magic Smile', 'items': [
        {'name': 'Відбілювання зубів Light', 'price': '₴ 1400',
         'specialists': ['anastasia', 'victoria']},
        {'name': 'Відбілювання зубів Maximum', 'price': '₴ 2200',
         'specialists': ['victoria']},
    ]},
    {'cat': 'Консультація лікаря', 'items': [
        {'name': 'Офлайн-консультація', 'price': '₴ 500', 'specialists': ['victoria']},
    ]},
]

P2C = {
    'Ботулінотерапія': ['Ботулінотерапія Neuronox / Nabota'],
    'Біорепарація шкіри': ['Біорепарація шкіри'],
    'Відбілювання зубів': ['Відбілювання зубів Magic Smile'],
    'Консультація': ['_консультація'],
}


# ── Хто виконує послугу ───────────────────────────────────────────────────────

class TestDeriveSpecialists:

    def test_exact_price_item_wins(self, wc):
        assert wc.derive_specialists('Моделювання всього тіла', PRICES, P2C) == {'anastasia'}

    def test_generic_service_aggregates_its_drugs(self, wc):
        """«Біорепарація шкіри» як позиції прайсу немає — тільки препарати."""
        assert wc.derive_specialists('Біорепарація шкіри', PRICES, P2C) == {'victoria'}

    def test_teeth_whitening_is_the_one_with_two(self, wc):
        """Єдина послуга, де клієнт обирає спеціаліста сам."""
        assert wc.derive_specialists('Відбілювання зубів', PRICES, P2C) == \
            {'anastasia', 'victoria'}

    def test_virtual_category_yields_nothing(self, wc):
        """Віртуальна категорія спеціалістів не несе — має бути видно як прогалину."""
        assert wc.derive_specialists('Лазерна епіляція', PRICES,
                                     {'Лазерна епіляція': ['_епіляція']}) == set()

    def test_consultation_comes_from_override(self, wc):
        """`_консультація` порожня, тож спеціаліст заданий вручну."""
        assert wc.derive_specialists('Консультація', PRICES, P2C) == {'victoria'}

    def test_unknown_service_yields_nothing(self, wc):
        assert wc.derive_specialists('Невідома послуга', PRICES, P2C) == set()

    def test_override_beats_the_price_list(self, wc, monkeypatch):
        monkeypatch.setitem(wc.SPECIALIST_OVERRIDE,
                            'Моделювання всього тіла', ['victoria'])
        assert wc.derive_specialists('Моделювання всього тіла', PRICES, P2C) == {'victoria'}


# ── Детектор розходжень ───────────────────────────────────────────────────────

def _svc(name, dur=30, active=1):
    return {'name': name, 'duration_min': dur, 'active': active}


class TestDiffCatalog:

    def test_no_changes_is_silent(self, wc):
        same = {'a': _svc('Ботулінотерапія')}
        assert wc.diff_catalog(same, {'a': {'name': 'Ботулінотерапія', 'duration_min': 30}}) == []

    def test_new_service_detected(self, wc):
        changes = wc.diff_catalog({}, {'a': {'name': 'Лазерна епіляція', 'duration_min': 45}})
        assert len(changes) == 1
        assert 'нова послуга' in changes[0] and 'Лазерна епіляція' in changes[0]

    def test_rename_detected(self, wc):
        """Саме цей клас зміни згноїв _cat_map непомітно."""
        changes = wc.diff_catalog(
            {'a': _svc('Ліполіз (ліполітики)')},
            {'a': {'name': 'Ліполітики (тіло, 10 мл)', 'duration_min': 30}})
        assert len(changes) == 1
        assert 'перейменовано' in changes[0]
        assert 'Ліполіз (ліполітики)' in changes[0]
        assert 'Ліполітики (тіло, 10 мл)' in changes[0]

    def test_duration_change_detected(self, wc):
        """Тривалість керує сіткою слотів — зміна не має пройти тихо."""
        changes = wc.diff_catalog(
            {'a': _svc('WOW-чистка обличчя', dur=80)},
            {'a': {'name': 'WOW-чистка обличчя', 'duration_min': 60}})
        assert len(changes) == 1
        assert '80 -> 60' in changes[0]

    def test_disappearance_detected(self, wc):
        changes = wc.diff_catalog({'a': _svc('Smart-біоревіталізація')}, {})
        assert len(changes) == 1
        assert 'зникла або вимкнена' in changes[0]

    def test_inactive_service_disappearing_is_not_reported_twice(self, wc):
        """Вже вимкнена і далі відсутня — не шумимо щосинку."""
        assert wc.diff_catalog({'a': _svc('Старе', active=0)}, {}) == []

    def test_reactivation_detected(self, wc):
        changes = wc.diff_catalog(
            {'a': _svc('Біорепарація Rejuran HB', active=0)},
            {'a': {'name': 'Біорепарація Rejuran HB', 'duration_min': 30}})
        assert any('знову активна' in c for c in changes)


# ── Запис у кеш ───────────────────────────────────────────────────────────────

INJ = {'category': "Ін'єкційна косметологія", 'category_ord': 1}
BODY = {'category': 'Догляд за тілом', 'category_ord': 3}
TEETH = {'category': 'Відбілювання зубів', 'category_ord': 2}
ROOT = {'category': '', 'category_ord': 999}

LIVE = {
    'id-botox':  dict(name='Ботулінотерапія',        duration_min=30, **INJ),
    'id-biorep': dict(name='Біорепарація шкіри',      duration_min=30, **INJ),
    'id-teeth':  dict(name='Відбілювання зубів',      duration_min=60, **TEETH),
    'id-body':   dict(name='Моделювання всього тіла', duration_min=55, **BODY),
    'id-consult': dict(name='Консультація',           duration_min=30, **ROOT),
    'id-laser':  dict(name='Лазерна епіляція',        duration_min=45, **ROOT),
}


@pytest.fixture
def db(tmp_path, wc, monkeypatch):
    path = str(tmp_path / 'users.db')
    monkeypatch.setattr(wc, 'DB_PATH', path)
    monkeypatch.setattr(wc, 'PRICES_PATH', str(tmp_path / 'prices.json'))
    with open(str(tmp_path / 'prices.json'), 'w', encoding='utf-8') as f:
        json.dump(PRICES, f, ensure_ascii=False)
    monkeypatch.setattr(wc, '_fetch_live', lambda: dict(LIVE))

    stub = type(sys)('photo_reminder')
    stub.PROCEDURE_TO_CATEGORIES = P2C
    stub.cashback_classify = lambda n: 'needs_drug' if n in P2C else 'auto'
    stub._get_drugs_for_procedure = lambda n: (
        [{'name': 'Rejuran HB', 'price': 4500}, {'name': 'Rejuran I', 'price': 4000}]
        if n == 'Біорепарація шкіри' else [])
    monkeypatch.setitem(sys.modules, 'photo_reminder', stub)
    return path


class TestSyncCatalog:

    def test_dry_run_writes_nothing(self, wc, db):
        changes, services, _ = wc.sync_catalog(dry_run=True, db_path=db, notify=False)
        assert len(services) == len(LIVE)
        assert len(changes) == len(LIVE)      # перший прогін: усі нові
        conn = sqlite3.connect(db)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert 'wl_services' not in tables,             'dry-run не має створювати навіть таблицю в проді'

    def test_sync_populates_cache(self, wc, db):
        wc.sync_catalog(db_path=db, notify=False)
        conn = sqlite3.connect(db)
        rows = dict(conn.execute('SELECT name, duration_min FROM wl_services').fetchall())
        conn.close()
        assert rows['Моделювання всього тіла'] == 55
        assert rows['Відбілювання зубів'] == 60

    def test_first_run_does_not_alert(self, wc, db, monkeypatch):
        """На порожньому кеші новим є весь каталог — 32 рядки в TG ні до чого."""
        alerts = []
        monkeypatch.setattr(wc, '_alert', lambda c, n: alerts.append(c))
        changes, _, _ = wc.sync_catalog(db_path=db, notify=True)
        assert len(changes) == len(LIVE)
        assert alerts == []

    def test_alert_goes_to_the_admin_not_the_studio_account(self, wc, db, monkeypatch):
        """Детектор без доставки не має сенсу.

        Раніше алерт шукав tg_id за телефоном студії `380733103110`, а той
        резолвиться в акаунт DrGomonCosmetology — туди ніхто не дивиться як у
        пошту для інцидентів, і 30 рядків про переїзд тек просто зникли.
        """
        sent = []
        stub = type(sys)('notifier')
        stub.alert_admin = lambda text: sent.append(text) or True
        stub._send_tg = lambda *a, **kw: pytest.fail(
            'алерт має йти через alert_admin, а не напряму в _send_tg')
        monkeypatch.setitem(sys.modules, 'notifier', stub)

        wc.sync_catalog(db_path=db, notify=False)
        renamed = dict(LIVE)
        renamed['id-botox'] = dict(name='Ботулінотерапія (Xeomin)', duration_min=30, **INJ)
        monkeypatch.setattr(wc, '_fetch_live', lambda: renamed)
        wc.sync_catalog(db_path=db, notify=True)

        assert len(sent) == 1
        assert 'перейменовано' in sent[0]

    def test_later_change_does_alert(self, wc, db, monkeypatch):
        wc.sync_catalog(db_path=db, notify=False)
        alerts = []
        monkeypatch.setattr(wc, '_alert', lambda c, n: alerts.append(c))
        renamed = dict(LIVE)
        renamed['id-botox'] = {'name': 'Ботулінотерапія (Xeomin)', 'duration_min': 30}
        monkeypatch.setattr(wc, '_fetch_live', lambda: renamed)
        wc.sync_catalog(db_path=db, notify=True)
        assert len(alerts) == 1
        assert any('перейменовано' in c for c in alerts[0])

    def test_second_sync_reports_no_changes(self, wc, db):
        wc.sync_catalog(db_path=db, notify=False)
        changes, _, _ = wc.sync_catalog(db_path=db, notify=False)
        assert changes == []

    def test_service_without_specialist_is_flagged(self, wc, db):
        _, _, no_spec = wc.sync_catalog(db_path=db, notify=False)
        assert no_spec == ['Лазерна епіляція']

    def test_price_range_from_drugs(self, wc, db):
        wc.sync_catalog(db_path=db, notify=False)
        conn = sqlite3.connect(db)
        row = conn.execute(
            'SELECT price_from, price_to FROM wl_services WHERE name=?',
            ('Біорепарація шкіри',)).fetchone()
        conn.close()
        assert row == (4000, 4500), 'має давати «від 4000 до 4500 грн»'

    def test_disappeared_service_is_deactivated_not_deleted(self, wc, db, monkeypatch):
        wc.sync_catalog(db_path=db, notify=False)
        shrunk = {k: v for k, v in LIVE.items() if k != 'id-teeth'}
        monkeypatch.setattr(wc, '_fetch_live', lambda: shrunk)
        changes, _, _ = wc.sync_catalog(db_path=db, notify=False)
        assert any('зникла або вимкнена' in c for c in changes)
        conn = sqlite3.connect(db)
        active = conn.execute(
            'SELECT active FROM wl_services WHERE name=?', ('Відбілювання зубів',)).fetchone()[0]
        conn.close()
        assert active == 0, 'історію не видаляємо, лише знімаємо активність'


class TestBookableMenu:

    def test_menu_excludes_services_without_specialist(self, wc, db):
        wc.sync_catalog(db_path=db, notify=False)
        names = [s['name'] for s in wc.get_bookable_services(db_path=db)]
        assert 'Лазерна епіляція' not in names, 'невідомий спеціаліст — не показуємо'
        assert 'Ботулінотерапія' in names

    def test_only_teeth_whitening_offers_a_choice(self, wc, db):
        wc.sync_catalog(db_path=db, notify=False)
        choice = {s['name'] for s in wc.get_bookable_services(db_path=db)
                  if s['specialist_choice']}
        assert choice == {'Відбілювання зубів'}

    def test_predefined_services_carry_exactly_one_specialist(self, wc, db):
        wc.sync_catalog(db_path=db, notify=False)
        for s in wc.get_bookable_services(db_path=db):
            if not s['specialist_choice']:
                assert len(s['specialists']) == 1, \
                    '{} має {} спеціалістів — клієнт не має це вирішувати'.format(
                        s['name'], len(s['specialists']))

    def test_consultation_is_bookable_via_override(self, wc, db):
        """Прайс спеціаліста не дає — беремо з SPECIALIST_OVERRIDE."""
        wc.sync_catalog(db_path=db, notify=False)
        menu = {s['name']: s for s in wc.get_bookable_services(db_path=db)}
        assert 'Консультація' in menu
        assert menu['Консультація']['specialists'] == ['victoria']
        assert menu['Консультація']['specialist_choice'] is False

    def test_only_one_consultation_in_the_menu(self, wc, db, monkeypatch):
        """«Офлайн-консультація» дублює «Консультацію» — показуємо одну."""
        live = dict(LIVE)
        live['id-offline'] = {'name': 'Офлайн-консультація', 'duration_min': 30}
        monkeypatch.setattr(wc, '_fetch_live', lambda: live)
        wc.sync_catalog(db_path=db, notify=False)
        names = [s['name'] for s in wc.get_bookable_services(db_path=db)]
        assert names.count('Консультація') == 1
        assert 'Офлайн-консультація' not in names

    def test_hidden_service_stays_out_of_the_menu(self, wc, db, monkeypatch):
        """Онлайн-консультацій поки не проводимо, хоча у WLaunch послуга активна."""
        live = dict(LIVE)
        live['id-online'] = {'name': 'Онлайн-консультація', 'duration_min': 30}
        monkeypatch.setattr(wc, '_fetch_live', lambda: live)
        monkeypatch.setitem(wc.SPECIALIST_OVERRIDE, 'Онлайн-консультація', ['victoria'])
        wc.sync_catalog(db_path=db, notify=False)

        names = [s['name'] for s in wc.get_bookable_services(db_path=db)]
        assert 'Онлайн-консультація' not in names
        # але в кеші лишається — щоб детектор бачив її зміни
        conn = sqlite3.connect(db)
        assert conn.execute('SELECT active FROM wl_services WHERE name=?',
                            ('Онлайн-консультація',)).fetchone()[0] == 1
        conn.close()

    def test_menu_carries_the_wlaunch_folder(self, wc, db):
        """Меню групується тими ж теками, що бачить лікар у WLaunch."""
        wc.sync_catalog(db_path=db, notify=False)
        cats = {s['name']: s['category'] for s in wc.get_bookable_services(db_path=db)}
        assert cats['Ботулінотерапія'] == "Ін'єкційна косметологія"
        assert cats['Моделювання всього тіла'] == 'Догляд за тілом'
        assert cats['Консультація'] == '', 'послуга з кореня лишається без теки'

    def test_menu_is_ordered_by_folder(self, wc, db):
        """Порядок тек — той самий, що у WLaunch (ordinal), не алфавітний."""
        wc.sync_catalog(db_path=db, notify=False)
        cats = [s['category'] for s in wc.get_bookable_services(db_path=db)]
        seen = [c for i, c in enumerate(cats) if i == 0 or cats[i - 1] != c]
        assert seen == ["Ін'єкційна косметологія", 'Відбілювання зубів',
                        'Догляд за тілом', '']

    def test_moving_a_service_between_folders_is_detected(self, wc, db, monkeypatch):
        wc.sync_catalog(db_path=db, notify=False)
        moved = dict(LIVE)
        moved['id-body'] = dict(name='Моделювання всього тіла', duration_min=55, **INJ)
        monkeypatch.setattr(wc, '_fetch_live', lambda: moved)
        changes, _, _ = wc.sync_catalog(db_path=db, notify=False)
        assert any('переїхала' in c for c in changes)

    def test_column_is_added_to_an_existing_table(self, wc, tmp_path):
        """Таблиця зʼявилась до тек — CREATE TABLE IF NOT EXISTS їх не доллє."""
        path = str(tmp_path / 'old.db')
        conn = sqlite3.connect(path)
        conn.execute('CREATE TABLE wl_services (wl_id TEXT PRIMARY KEY, name TEXT,'
                     " duration_min INTEGER, specialists TEXT, classify TEXT,"
                     ' price_from INTEGER, price_to INTEGER, active INTEGER,'
                     ' first_seen TEXT, synced_at TEXT)')
        conn.commit(); conn.close()

        wc.init_catalog_db(path)

        conn = sqlite3.connect(path)
        cols = {r[1] for r in conn.execute('PRAGMA table_info(wl_services)')}
        conn.close()
        assert 'category' in cols and 'category_ord' in cols

    def test_duration_comes_from_wlaunch_not_a_default(self, wc, db):
        wc.sync_catalog(db_path=db, notify=False)
        durations = {s['name']: s['duration_min'] for s in wc.get_bookable_services(db_path=db)}
        assert durations['Моделювання всього тіла'] == 55
        assert 60 not in {durations['Ботулінотерапія'], durations['Біорепарація шкіри']}
