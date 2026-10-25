# -*- coding: utf-8 -*-
"""
Readiness tests for client-facing online booking (web page / TG / IG bots).

Every booking path has to end in a WLaunch appointment — WLaunch is the source
of truth for the schedule, and a local-only row is a ghost nobody in the studio
can see. `admin_cal_create` is today the only code path that creates one, and it
is WLaunch-first with rollback, so the invariants worth pinning are:

  - a procedure WLaunch cannot match must create NOTHING, locally or remotely;
  - a WLaunch rejection must not leave a local row behind;
  - a successful create must store the returned wlaunch_id.

The service lookup is the fragile part. `create_wlaunch_appointment` resolves
our procedure name against WLaunch's own catalogue by exact match, then by
substring, then through a hand-written `_cat_map`. WLaunch sells generic
services ("Біорепарація шкіри"), while our price list sells drug variants
("Біорепарація Rejuran HB"), so the mapping is what bridges the two — and when
it misses, the booking fails outright with service_not_found.

WLAUNCH_SERVICES below is the live catalogue as of 25.10.2026 (33 active,
non-group services), captured so these tests never touch the network.
"""
import os
import sys
import json
import sqlite3
import logging
import logging.handlers
import importlib.util

import pytest
from unittest.mock import patch

from conftest import auth, _pwa

ZADARMA = os.path.join(os.path.dirname(__file__), '..', 'zadarma')

# Живий каталог WLaunch, знятий 25.10.2026 (33 активні послуги, без груп)
WLAUNCH_SERVICES = [
    'KEMIKUM', 'KEMIKUM + мікронідлінг', 'PRX-T33', 'PRX-T33 + мікронідлінг',
    'SPA-догляд від Christina', 'WOW-чистка «Сяяння»', 'WOW-чистка обличчя',
    'Азелаїновий / Мигдальний / Феруловий', 'Ботулінотерапія',
    'Біоревіталізація шкіри', 'Біорепарація шкіри', 'Відбілювання зубів',
    'Гіалуронідаза (розчинення філера)', 'Загальний релакс-масаж всього тіла',
    'Карбокситерапія', 'Кисневий догляд Glow Skin', 'Консультація',
    'Контурна пластика губ', 'Контурна пластика обличчя',
    'Корекція ботулотоксину', 'Корекція філера', 'Лазерна епіляція',
    'Лікування гіпергідрозу (Botox)', 'Ліполітики (обличчя, 4 мл)',
    'Ліполітики (тіло, 10 мл)', 'Мезоботокс «Монако» (4 ml)', 'Мезотерапія',
    'Моделювання всього тіла', 'Моделювання окремої ділянки',
    'Онлайн-консультація', 'Офлайн-консультація',
    'Пресотерапія «Легкість тіла»', 'Підліткова делікатна чистка',
]


class _NullRotatingHandler(logging.NullHandler):
    def __init__(self, *a, **kw):
        super().__init__()


class _FakeResp(object):
    """Відповідь WLaunch на POST — щоб тест ніколи не ходив у мережу."""
    status_code = 200
    text = '{"id": "wl-created-id"}'

    def json(self):
        return {'id': 'wl-created-id', 'price': 1500}


# ── Реальний wlaunch_api з підміненим HTTP ────────────────────────────────────

@pytest.fixture(scope='module')
def wl():
    """wlaunch_api під псевдонімом, з каталогом-фікстурою замість мережі."""
    # config-стаб у conftest не містить цього символу, а модуль його імпортує
    sys.modules['config'].WLAUNCH_API_BEARER = 'Bearer test_bearer'

    spec = importlib.util.spec_from_file_location(
        'wlaunch_api_booking_real', os.path.join(ZADARMA, 'wlaunch_api.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules['wlaunch_api_booking_real'] = mod
    _orig_rfh = logging.handlers.RotatingFileHandler
    logging.handlers.RotatingFileHandler = _NullRotatingHandler
    try:
        spec.loader.exec_module(mod)
    finally:
        logging.handlers.RotatingFileHandler = _orig_rfh

    catalogue = {}
    for i, name in enumerate(WLAUNCH_SERVICES):
        catalogue[name.lower()] = {'id': 'svc-{}'.format(i), 'name': name, 'duration': 60}

    mod.get_branch_id = lambda: 'branch-1'
    mod.find_wlaunch_client_id = lambda phone: 'wl-client-1'
    mod.create_wlaunch_client = lambda *a, **kw: 'wl-client-1'
    mod.get_wlaunch_resources = lambda branch_id=None: {
        'victoria': 'res-victoria', 'anastasia': 'res-anastasia'}
    mod.get_wlaunch_services = lambda branch_id=None: dict(catalogue)
    return mod


@pytest.fixture
def book(wl):
    """resolve(procedure) -> (err, обрана послуга WLaunch, кількість POST-ів)."""
    def _resolve(procedure, specialist='victoria'):
        posts = []

        def _fake_post(url, *a, **kw):
            posts.append((url, kw.get('json')))
            return _FakeResp()

        with patch.object(wl.requests, 'post', _fake_post):
            wl_id, err = wl.create_wlaunch_appointment(
                '380991234567', 'Тест Клієнт', procedure,
                specialist, '2099-03-10', '12:00', 60)

        chosen = None
        for url, body in posts:
            if url.endswith('/appointment'):
                srs = (body or {}).get('appointment', {}).get('service_resource_settings') or []
                if srs:
                    chosen = srs[0].get('service')
        return err, chosen, len(posts)
    return _resolve


def _svc_name(wl, svc_id):
    for name in WLAUNCH_SERVICES:
        idx = WLAUNCH_SERVICES.index(name)
        if 'svc-{}'.format(idx) == svc_id:
            return name
    return None


# ── 1. Що мапиться сьогодні ───────────────────────────────────────────────────

class TestServiceMappingWorks:
    """Процедури, які справді доїдуть до WLaunch."""

    @pytest.mark.parametrize('procedure,expected', [
        ('Консультація',                 'Консультація'),
        ('Карбокситерапія',              'Карбокситерапія'),
        ('WOW-чистка обличчя',           'WOW-чистка обличчя'),
        ('Моделювання всього тіла',      'Моделювання всього тіла'),
        ('Підліткова делікатна чистка',  'Підліткова делікатна чистка'),
    ])
    def test_exact_name_matches(self, wl, book, procedure, expected):
        err, chosen, _ = book(procedure)
        assert err is None
        assert _svc_name(wl, chosen) == expected

    @pytest.mark.parametrize('procedure,expected', [
        # через _cat_map: назва препарату → узагальнена послуга WLaunch
        ('Ботулінотерапія 1 зона',           'Ботулінотерапія'),
        ('Ботулінотерапія 2 зони (Neuronox)', 'Ботулінотерапія'),
        ('Neuramis Lips',                     'Контурна пластика губ'),
        ('Saypha Volume',                     'Контурна пластика обличчя'),
        ('Vitaran I',                         'Мезотерапія'),
        ('Ліполітики (тіло, 10 мл)',          'Ліполітики (тіло, 10 мл)'),
    ])
    def test_category_map_matches(self, wl, book, procedure, expected):
        err, chosen, _ = book(procedure)
        assert err is None, 'очікували мапінг, отримали {}'.format(err)
        assert _svc_name(wl, chosen) == expected

    def test_successful_match_posts_appointment(self, book):
        """Два POST-и: розрахунок ціни + створення запису."""
        err, chosen, posts = book('Консультація')
        assert err is None
        assert chosen is not None
        assert posts == 2


# ── 2. Чого НЕ записати — і що при цьому нічого не створюється ────────────────

#: Процедури прайсу, які станом на 25.10.2026 не мапляться на жодну послугу
#: WLaunch. Для кожної в WLaunch є узагальнена послуга, але ні точний збіг, ні
#: підрядок, ні `_cat_map` до неї не доводять.
UNMAPPED_TODAY = [
    ('Біорепарація Rejuran HB',                  'Біорепарація шкіри'),
    ('Біорепарація Rejuran I',                   'Біорепарація шкіри'),
    ('Біорепарація Rejuran S',                   'Біорепарація шкіри'),
    ('Біорепарація Екзосоми (Exoxe) 2.5 ml',     'Біорепарація шкіри'),
    ('Smart-біоревіталізація',                   'Біоревіталізація шкіри'),
    ('Біоревіталізація Neauvia Hydro Deluxe',    'Біоревіталізація шкіри'),
]


class TestUnmappedProcedures:

    @pytest.mark.parametrize('procedure', [p for p, _ in UNMAPPED_TODAY])
    def test_unmapped_creates_nothing_anywhere(self, book, procedure):
        """Головний інваріант: немає мапінгу → немає ні запису в WLaunch, ні POST-а."""
        err, chosen, posts = book(procedure)
        assert err == 'service_not_found'
        assert chosen is None
        assert posts == 0, 'не мало бути жодного POST — інакше створився б запис'

    @pytest.mark.parametrize('procedure,target', UNMAPPED_TODAY)
    @pytest.mark.xfail(strict=True, reason=(
        'Відома прогалина: _cat_map не містить rejuran / hydro deluxe, а записи '
        'для екзосом і smart вказують на назви послуг, яких у WLaunch більше нема. '
        'Коли мапінг виправлять, цей тест XPASS-ить і strict=True завалить сюїту — '
        'це сигнал прибрати маркер і перенести процедуру в TestServiceMappingWorks.'))
    def test_unmapped_should_map_to_generic_service(self, wl, book, procedure, target):
        """Бажана поведінка: варіант препарату йде на узагальнену послугу."""
        err, chosen, _ = book(procedure)
        assert err is None
        assert _svc_name(wl, chosen) == target


# ── 3. Інваріанти route-а створення ───────────────────────────────────────────

def _manual_count(where='', params=()):
    conn = sqlite3.connect(_pwa.DB_PATH)
    try:
        q = 'SELECT count(*) FROM manual_appointments'
        if where:
            q += ' WHERE ' + where
        return conn.execute(q, params).fetchone()[0]
    finally:
        conn.close()


def _payload(**over):
    body = {
        'client_name': 'Тест Бронювання',
        'client_phone': '0991234567',
        'procedure_name': 'Консультація',
        'specialist': 'victoria',
        'date': '2099-04-01',
        'time': '10:00',
        'duration': 60,
    }
    body.update(over)
    return body


class TestCreateRouteInvariants:
    """POST /api/admin/calendar/appointments — єдиний шлях створення запису."""

    def test_wlaunch_id_is_stored_on_success(self, client, admin_token):
        body = _payload(date='2099-04-01', time='10:00')
        with patch.dict(sys.modules):
            sys.modules['wlaunch_api'].create_wlaunch_appointment = \
                lambda *a, **kw: ('wl-ok-id', None)
            rv = client.post('/api/admin/calendar/appointments',
                             json=body, headers=auth(admin_token))
        assert rv.status_code == 200, rv.get_data(as_text=True)
        assert rv.get_json().get('wlaunch_id') == 'wl-ok-id'
        assert _manual_count('wlaunch_id=?', ('wl-ok-id',)) == 1

    @pytest.mark.parametrize('wl_error,expected_status', [
        ('service_not_found', 409),   # процедури немає в каталозі WLaunch
        ('unavailable',       409),   # спеціаліст зайнятий за розкладом WLaunch
        ('http_422: bad',     409),   # WLaunch відхилив дані
        ('client_not_found',  409),   # клієнта не створити
    ])
    def test_wlaunch_refusal_leaves_no_local_row(self, client, admin_token,
                                                 wl_error, expected_status):
        """Відмова WLaunch не має залишати локальний запис-привид."""
        body = _payload(date='2099-04-02', time='11:00')
        before = _manual_count('date=?', ('2099-04-02',))
        with patch.dict(sys.modules):
            sys.modules['wlaunch_api'].create_wlaunch_appointment = \
                lambda *a, **kw: (None, wl_error)
            rv = client.post('/api/admin/calendar/appointments',
                             json=body, headers=auth(admin_token))
        assert rv.status_code == expected_status
        assert rv.get_json().get('error') == 'wlaunch_rejected'
        assert _manual_count('date=?', ('2099-04-02',)) == before

    def test_wlaunch_exception_leaves_no_local_row(self, client, admin_token):
        """WLaunch недоступний (мережа) — теж нічого локально."""
        def _boom(*a, **kw):
            raise RuntimeError('connection refused')

        body = _payload(date='2099-04-03', time='12:00')
        before = _manual_count('date=?', ('2099-04-03',))
        with patch.dict(sys.modules):
            sys.modules['wlaunch_api'].create_wlaunch_appointment = _boom
            rv = client.post('/api/admin/calendar/appointments',
                             json=body, headers=auth(admin_token))
        assert rv.status_code == 503
        assert _manual_count('date=?', ('2099-04-03',)) == before

    def test_local_overlap_rolls_back_wlaunch(self, client, admin_token):
        """Локальний конфлікт після створення в WLaunch → WLaunch треба відкотити."""
        first = _payload(date='2099-04-04', time='13:00', duration=60)
        with patch.dict(sys.modules):
            sys.modules['wlaunch_api'].create_wlaunch_appointment = \
                lambda *a, **kw: ('wl-first', None)
            rv = client.post('/api/admin/calendar/appointments',
                             json=first, headers=auth(admin_token))
        assert rv.status_code == 200

        cancelled = []
        second = _payload(date='2099-04-04', time='13:30', duration=60)
        # відкат робить ядро, тож підміняємо канонічну функцію, не аліас у pwa_api
        import booking as _booking
        with patch.dict(sys.modules), \
             patch.object(_booking, 'cancel_wlaunch_appt',
                          lambda wl_id, **kw: cancelled.append(wl_id) or (True, None)):
            sys.modules['wlaunch_api'].create_wlaunch_appointment = \
                lambda *a, **kw: ('wl-orphan', None)
            rv = client.post('/api/admin/calendar/appointments',
                             json=second, headers=auth(admin_token))

        assert rv.status_code == 409
        assert rv.get_json().get('error') == 'conflict'
        assert cancelled == ['wl-orphan'], 'запис у WLaunch лишився сиротою'
        assert _manual_count('wlaunch_id=?', ('wl-orphan',)) == 0


# ── 4. HTTP-оболонка онлайн-запису ────────────────────────────────────────────

class TestBookingEndpoints:
    """Потік клієнта: послуги → (опційно) спеціаліст → дата і час."""

    def test_create_requires_authentication(self, client):
        rv = client.post('/api/booking/create', json={'service': 'X'})
        assert rv.status_code in (401, 403)

    def test_phone_is_taken_from_the_session_not_the_body(self, client, client_token,
                                                          client_phone):
        """Інакше будь-хто записував би чужим номером."""
        seen = {}

        def _fake(**kw):
            seen.update(kw)
            return {'wlaunch_id': 'wl-x', 'local_id': 1, 'service': kw['service_name'],
                    'specialist': 'victoria', 'date': kw['date'], 'time': kw['time_str'],
                    'duration_min': 30}

        stub = type(sys)('booking')
        stub.create_booking = _fake

        class _E(Exception):
            def __init__(self, code, message):
                self.code, self.message = code, message
        stub.BookingError = _E

        with patch.dict(sys.modules, {'booking': stub}):
            rv = client.post('/api/booking/create', headers=auth(client_token), json={
                'name': 'Тест', 'service': 'Біорепарація шкіри',
                'date': '2099-05-05', 'time': '10:00',
                'phone': '380000000000',          # спроба підміни
            })
        assert rv.status_code == 200
        assert seen['phone'] == client_phone
        assert seen['phone'] != '380000000000'

    def test_booking_error_maps_to_a_useful_status(self, client, client_token):
        class _E(Exception):
            def __init__(self, code, message):
                self.code, self.message = code, message

        def _fake(**kw):
            raise _E('slot_taken', 'Цей час щойно зайняли')

        stub = type(sys)('booking')
        stub.create_booking = _fake
        stub.BookingError = _E

        with patch.dict(sys.modules, {'booking': stub}):
            rv = client.post('/api/booking/create', headers=auth(client_token), json={
                'name': 'Тест', 'service': 'Біорепарація шкіри',
                'date': '2099-05-05', 'time': '10:00'})
        assert rv.status_code == 409
        assert rv.get_json()['error'] == 'slot_taken'

    def test_slots_rejects_a_bad_date(self, client):
        rv = client.get('/api/booking/slots?service=X&from=05.05.2099')
        assert rv.status_code == 400
        assert rv.get_json()['error'] == 'invalid_params'

    def test_slots_requires_a_service(self, client):
        rv = client.get('/api/booking/slots?from=2099-05-05')
        assert rv.status_code == 400


class TestNewClientCanStartBooking:
    """Телефон, якого немає в clients, мусить отримати код.

    Інакше новий клієнт — той, заради кого сторінка й робилась — упирається
    в екран «введіть код», якого йому ніхто не надсилав: send-otp віддає
    {'ok': True, 'guest': True} без коду, сторінка бачить лише ok і йде далі.
    """

    def test_unknown_phone_in_guest_mode_gets_no_code(self, client):
        """Базова поведінка для чату лишається — гостю код не потрібен."""
        rv = client.post('/api/auth/send-otp', json={'phone': '0631112233'})
        assert rv.status_code == 200
        assert rv.get_json().get('guest') is True

    def test_booking_purpose_forces_a_real_code(self, client):
        rv = client.post('/api/auth/send-otp',
                         json={'phone': '0631112244', 'purpose': 'booking'})
        assert rv.status_code == 200
        data = rv.get_json()
        assert not data.get('guest'), 'для запису гостьовий режим недопустимий'

        conn = sqlite3.connect(_pwa.OTP_DB)
        row = conn.execute('SELECT code FROM otp_codes WHERE phone=?',
                           ('380631112244',)).fetchone()
        conn.close()
        assert row and row[0], 'код має бути згенерований'
