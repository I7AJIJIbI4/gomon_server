# -*- coding: utf-8 -*-
"""
Прайс 25.11.2026: що з нового прайсу має працювати в коді.

- Колагеностимуляція — нова послуга WLaunch з кнопками препаратів для кешбеку;
  True Self 400 коштує «300 $», а кнопки рахують гривні, тож її там немає
  (лікарка вводить ціну вручну).
- Тіло перейменовано під прайс («DrumRoll · усе тіло» тощо): кешбек і далі
  рахується з курсової ціни, інакше після перейменування йшов би з повної.
- Нові пілінги (APPeex, BioRePeel, BIO C, Redness / Xeroskin Peel) мають
  пілінговий інтервал і текст нагадування, а не загальні 60 днів.
"""
import json
import sqlite3
import sys
import types

import pytest

from conftest import load_real

if 'fcntl' not in sys.modules:       # appt_reminder імпортує його; на Windows немає
    try:
        import fcntl  # noqa: F401
    except ImportError:
        _f = types.ModuleType('fcntl')
        _f.flock = lambda *a, **kw: None
        _f.LOCK_EX, _f.LOCK_NB, _f.LOCK_UN = 2, 4, 8
        sys.modules['fcntl'] = _f

COLLAGEN = {'cat': 'Колагеностимуляція', 'items': [
    {'name': 'Facetem S (0,8 + 0,8 мл)', 'price': '₴ 9500', 'specialists': ['victoria']},
    {'name': 'Radiesse (1,5 мл)', 'price': '₴ 12000', 'specialists': ['victoria']},
    {'name': 'True Self 400 (12 мл)', 'price': '300 $', 'specialists': ['victoria']},
    {'name': 'ZQ-II (5 мл)', 'price': '₴ 9500', 'specialists': ['victoria']},
]}
BODY = {'cat': 'DrumRoll «Моделювання фігури»', 'items': [
    {'name': 'DrumRoll · усе тіло', 'price': '₴ 900 (курсом ₴ 720)', 'specialists': ['anastasia']},
]}
PRESSO = {'cat': 'Лімфодренажна пресотерапія', 'items': [
    {'name': 'Пресотерапія', 'price': '₴ 650 (курсом ₴ 520)', 'specialists': ['anastasia']},
]}


def _write_prices(path, cats):
    # appt_reminder читає prices.json без encoding= (cp1251 на Windows) — ASCII-екранування
    with open(path, 'w') as fh:
        json.dump(cats, fh)


@pytest.fixture
def photo(tmp_path):
    mod = load_real('photo_reminder_price_2026_11', 'photo_reminder.py')
    p = tmp_path / 'prices.json'
    _write_prices(str(p), [COLLAGEN, BODY])
    mod.PRICES_PATH = str(p)
    return mod


def test_collagen_offers_drug_buttons_without_dollar_price(photo):
    assert photo.cashback_classify('Колагеностимуляція') == 'needs_drug'
    drugs = photo._get_drugs_for_procedure('Колагеностимуляція')
    assert [d['name'] for d in drugs] == ['Facetem S (0,8 + 0,8 мл)', 'Radiesse (1,5 мл)', 'ZQ-II (5 мл)']
    assert all(d['price'] >= 9500 for d in drugs), 'жодних «300 грн» з доларової ціни'


def test_collagen_shows_on_the_injection_card(pwa):
    assert pwa.price_group('Колагеностимуляція')[0] == 2
    assert pwa.price_group('Пілінги InnoAesthetics')[0] == 3


@pytest.fixture
def accrue(tmp_path, monkeypatch):
    db = str(tmp_path / 'users.db')
    c = sqlite3.connect(db)
    c.execute('CREATE TABLE cashback (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT,'
              ' amount REAL, procedure_name TEXT, procedure_price REAL, appt_date TEXT,'
              ' UNIQUE(phone, procedure_name, appt_date))')
    c.commit()
    c.close()
    otp = str(tmp_path / 'otp.db')
    c = sqlite3.connect(otp)
    c.execute('CREATE TABLE sessions (phone TEXT)')
    c.execute("INSERT INTO sessions VALUES ('380631234519')")
    c.commit()
    c.close()
    prices = str(tmp_path / 'prices.json')
    _write_prices(prices, [BODY, PRESSO])
    ar = load_real('appt_reminder_price_2026_11', 'appt_reminder.py', db_path=db)
    ar.OTP_DB_PATH = otp
    ar.PRICES_PATH = prices
    loyalty = types.ModuleType('loyalty')
    loyalty.get_cashback_rate = lambda phone: 0.03
    monkeypatch.setitem(sys.modules, 'loyalty', loyalty)

    def run(procedure):
        ar._accrue_cashback({'client_phone': '380631234519', 'procedure_name': procedure,
                             'date': '2026-11-24'})
        conn = sqlite3.connect(db)
        row = conn.execute('SELECT procedure_price, amount FROM cashback WHERE procedure_name=?',
                           (procedure,)).fetchone()
        conn.close()
        return row
    return run


@pytest.mark.parametrize('procedure,price', [('DrumRoll · усе тіло', 720), ('Пресотерапія', 520)])
def test_renamed_body_service_earns_from_the_course_price(accrue, procedure, price):
    assert accrue(procedure) == (price, round(price * 0.03, 2))


@pytest.fixture(scope='module')
def sms():
    return load_real('sms_reminder_price_2026_11', 'sms_reminder.py')


@pytest.mark.parametrize('service', ['APPeex', 'BioRePeel', 'BIO C', 'Redness Peel', 'Xeroskin Peel'])
def test_new_peels_get_the_peeling_interval(sms, service):
    assert sms.get_interval_days(service) == 18
    assert sms.get_service_category(service) == 'peeling'
