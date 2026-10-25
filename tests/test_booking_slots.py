# -*- coding: utf-8 -*-
"""
Етап 3 онлайн-запису: вільні слоти.

Два правила, заради яких цей модуль існує окремо від `get_free_gaps_today`:

  - зайнятість береться живцем з WLaunch, бо локальна копія оновлюється раз на
    годину, і слот, зайнятий десять хвилин тому, у ній ще вільний. Показати
    такий слот — провести клієнта через увесь вибір і відмовити на останньому кроці;
  - день без робочих фреймів це «розклад ще не відкрито», а не «все зайнято».
    Горизонт запису дорівнює тому, наскільки наперед лікар заповнила розклад —
    станом на 25.10.2026 це ~7 днів.
"""
import os
import sys
import sqlite3
import logging
import logging.handlers
import importlib.util
from datetime import datetime, timedelta

import pytest

ZADARMA = os.path.join(os.path.dirname(__file__), '..', 'zadarma')


class _NullRotatingHandler(logging.NullHandler):
    def __init__(self, *a, **kw):
        super().__init__()


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ZADARMA, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    _orig = logging.handlers.RotatingFileHandler
    logging.handlers.RotatingFileHandler = _NullRotatingHandler
    try:
        spec.loader.exec_module(mod)
    finally:
        logging.handlers.RotatingFileHandler = _orig
    return mod


@pytest.fixture(scope='module')
def bs():
    return _load('booking_slots_real', 'booking_slots.py')


# ── Сітка стартів ─────────────────────────────────────────────────────────────

class TestStarts:

    def test_grid_is_aligned_to_the_step(self, bs):
        """Старти рівняються на сітку, а не на край вікна."""
        starts = bs._starts([(607, 720)], 30, 0, step=15)
        assert starts[0] == 615
        assert all(t % 15 == 0 for t in starts)

    def test_service_must_fit_before_the_window_closes(self, bs):
        """80-хвилинна процедура не влазить у годинне вікно."""
        assert bs._starts([(600, 660)], 80, 0) == []

    def test_last_start_leaves_room_for_the_whole_service(self, bs):
        starts = bs._starts([(600, 720)], 30, 0)
        assert max(starts) + 30 <= 720

    def test_earliest_cuts_off_the_near_past(self, bs):
        """Сьогоднішні слоти раніше за MIN_LEAD_MIN не пропонуються."""
        starts = bs._starts([(600, 720)], 30, 660)
        assert min(starts) >= 660

    def test_several_windows_are_handled(self, bs):
        starts = bs._starts([(540, 600), (660, 720)], 30, 0)
        assert 540 in starts and 660 in starts
        assert 600 not in starts     # перше вікно закінчилось


# ── Зайнятість ────────────────────────────────────────────────────────────────

RESOURCES = {'victoria': 'res-v', 'anastasia': 'res-a'}


def _appt(start_utc, duration_s, resource=None, status='CONFIRMED'):
    out = {'start_time': start_utc, 'duration': duration_s, 'status': status}
    if resource:
        out['service_resource_settings'] = [{'resources': [resource]}]
    return out


class TestFetchBusy:

    @pytest.fixture
    def fetched(self, bs, monkeypatch):
        def _run(items):
            pages = [{'content': items, 'page': {'total_pages': 1}}]

            class _R:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return pages[0]

            import requests
            monkeypatch.setattr(requests, 'get', lambda *a, **kw: _R())
            stub_wl = type(sys)('wlaunch_api')
            stub_wl.HEADERS = {}
            stub_wl.get_branch_id = lambda: 'branch-1'
            stub_wl.get_wlaunch_resources = lambda bid=None: dict(RESOURCES)
            stub_wl.parse_appt_time = _parse_time
            monkeypatch.setitem(sys.modules, 'wlaunch_api', stub_wl)
            stub_cfg = type(sys)('config')
            stub_cfg.WLAUNCH_API_URL = 'https://x'
            stub_cfg.COMPANY_ID = 'c'
            monkeypatch.setitem(sys.modules, 'config', stub_cfg)
            return bs.fetch_busy('2026-10-26', '2026-10-26')
        return _run

    def test_appointment_blocks_its_specialist(self, fetched):
        busy = fetched([_appt('2026-10-26T07:00:00.000Z', 1800, 'res-v')])
        assert busy[('2026-10-26', 'victoria')] == [(600, 630)]
        assert ('2026-10-26', 'anastasia') not in busy

    def test_cancelled_is_ignored(self, fetched):
        busy = fetched([_appt('2026-10-26T07:00:00.000Z', 1800, 'res-v', status='CANCELLED')])
        assert busy == {}

    def test_no_show_is_ignored(self, fetched):
        busy = fetched([_appt('2026-10-26T07:00:00.000Z', 1800, 'res-v', status='NO_SHOW')])
        assert busy == {}

    def test_appointment_without_resource_blocks_everyone(self, fetched):
        """WLaunch усе одно відхилить такий слот — краще не пропонувати."""
        busy = fetched([_appt('2026-10-26T07:00:00.000Z', 1800)])
        assert set(busy) == {('2026-10-26', 'victoria'), ('2026-10-26', 'anastasia')}

    def test_duration_is_taken_from_the_appointment(self, fetched):
        busy = fetched([_appt('2026-10-26T07:00:00.000Z', 4800, 'res-v')])
        assert busy[('2026-10-26', 'victoria')] == [(600, 680)]


def _parse_time(start_time_str):
    """Копія wlaunch_api.parse_appt_time для UTC+3 (жовтень, EEST)."""
    dt = datetime.strptime(start_time_str[:19], '%Y-%m-%dT%H:%M:%S') + timedelta(hours=3)
    return dt.strftime('%Y-%m-%d'), dt.hour, dt.minute


# ── Повний розрахунок ─────────────────────────────────────────────────────────

MENU = [
    {'name': 'Біорепарація шкіри', 'duration_min': 30, 'specialists': ['victoria'],
     'specialist_choice': False, 'price_from': 3500, 'price_to': 4500,
     'wl_id': 'svc-1', 'classify': 'needs_drug'},
    {'name': 'Відбілювання зубів', 'duration_min': 60,
     'specialists': ['anastasia', 'victoria'], 'specialist_choice': True,
     'price_from': 1400, 'price_to': 2200, 'wl_id': 'svc-2', 'classify': 'needs_drug'},
    {'name': 'WOW-чистка обличчя', 'duration_min': 80, 'specialists': ['victoria'],
     'specialist_choice': False, 'price_from': 1400, 'price_to': 1400,
     'wl_id': 'svc-3', 'classify': 'auto'},
]

TOMORROW = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
NEXT_WEEK = (datetime.now() + timedelta(days=8)).strftime('%Y-%m-%d')


@pytest.fixture
def slots(bs, monkeypatch):
    """get_free_slots із підміненими WLaunch-джерелами."""
    state = {'frames': {}, 'busy': {}}

    stub_cat = type(sys)('wl_catalog')
    stub_cat.get_bookable_services = lambda db_path=None: list(MENU)
    monkeypatch.setitem(sys.modules, 'wl_catalog', stub_cat)

    stub_wl = type(sys)('wlaunch_api')
    stub_wl.get_branch_id = lambda: 'branch-1'
    stub_wl.get_wlaunch_resources = lambda bid=None: dict(RESOURCES)
    stub_wl._subtract_intervals = _subtract_intervals
    monkeypatch.setitem(sys.modules, 'wlaunch_api', stub_wl)

    state['schedule_calls'] = []

    def _frames(d, s, resources=None, schedule=None):
        return state['frames'].get((d, s), [])

    def _sched(f, t, branch_id=None):
        state['schedule_calls'].append((f, t))
        return {'content': []}

    monkeypatch.setattr(bs, 'open_frames', _frames)
    monkeypatch.setattr(bs, 'fetch_schedule', _sched)
    monkeypatch.setattr(bs, 'fetch_busy',
                        lambda f, t, branch_id=None: state['busy'])
    monkeypatch.setattr(bs, '_local_breaks', lambda d, s, db_path=None: [])
    return state


def _subtract_intervals(base, cuts):
    result = list(base)
    for cs, ce in cuts:
        nxt = []
        for s, e in result:
            if ce <= s or cs >= e:
                nxt.append((s, e))
                continue
            if cs > s:
                nxt.append((s, cs))
            if ce < e:
                nxt.append((ce, e))
        result = nxt
    return result


class TestGetFreeSlots:

    def test_day_without_frames_is_not_open(self, bs, slots):
        """Головна відмінність: «розклад не відкрито» ≠ «все зайнято»."""
        days = bs.get_free_slots('Біорепарація шкіри', TOMORROW, TOMORROW)
        assert len(days) == 1
        assert days[0]['open'] is False
        assert days[0]['specialists'] == {}

    def test_open_day_yields_slots(self, bs, slots):
        slots['frames'][(TOMORROW, 'victoria')] = [(540, 720)]
        days = bs.get_free_slots('Біорепарація шкіри', TOMORROW, TOMORROW)
        assert days[0]['open'] is True
        assert days[0]['specialists']['victoria'][0] == '09:00'

    def test_booked_time_is_removed(self, bs, slots):
        slots['frames'][(TOMORROW, 'victoria')] = [(540, 660)]
        slots['busy'][(TOMORROW, 'victoria')] = [(570, 600)]   # 09:30-10:00
        times = bs.get_free_slots(
            'Біорепарація шкіри', TOMORROW, TOMORROW)[0]['specialists']['victoria']
        assert '09:00' in times
        assert '09:30' not in times
        assert '09:45' not in times, 'процедура наклалась би на зайнятий інтервал'
        assert '10:00' in times

    def test_open_but_fully_booked_is_open_with_no_times(self, bs, slots):
        """UI має сказати «все зайнято», а не «розклад не відкрито»."""
        slots['frames'][(TOMORROW, 'victoria')] = [(540, 600)]
        slots['busy'][(TOMORROW, 'victoria')] = [(540, 600)]
        day = bs.get_free_slots('Біорепарація шкіри', TOMORROW, TOMORROW)[0]
        assert day['open'] is True
        assert day['specialists'] == {}

    def test_long_service_gets_fewer_slots(self, bs, slots):
        slots['frames'][(TOMORROW, 'victoria')] = [(540, 700)]
        short = bs.get_free_slots('Біорепарація шкіри', TOMORROW, TOMORROW)[0]
        long = bs.get_free_slots('WOW-чистка обличчя', TOMORROW, TOMORROW)[0]
        assert len(long['specialists']['victoria']) < len(short['specialists']['victoria'])

    def test_choice_service_returns_both_specialists(self, bs, slots):
        slots['frames'][(TOMORROW, 'victoria')] = [(540, 720)]
        slots['frames'][(TOMORROW, 'anastasia')] = [(540, 720)]
        day = bs.get_free_slots('Відбілювання зубів', TOMORROW, TOMORROW)[0]
        assert set(day['specialists']) == {'victoria', 'anastasia'}

    def test_specialist_filter_narrows_the_answer(self, bs, slots):
        slots['frames'][(TOMORROW, 'victoria')] = [(540, 720)]
        slots['frames'][(TOMORROW, 'anastasia')] = [(540, 720)]
        day = bs.get_free_slots('Відбілювання зубів', TOMORROW, TOMORROW,
                                specialist='anastasia')[0]
        assert set(day['specialists']) == {'anastasia'}

    def test_wrong_specialist_is_refused(self, bs, slots):
        """Ін'єкції робить лише Вікторія — підміна в запиті не проходить."""
        with pytest.raises(ValueError, match='не виконує'):
            bs.get_free_slots('Біорепарація шкіри', TOMORROW, TOMORROW,
                              specialist='anastasia')

    def test_unknown_service_is_refused(self, bs, slots):
        with pytest.raises(ValueError, match='недоступна'):
            bs.get_free_slots('Онлайн-консультація', TOMORROW, TOMORROW)

    def test_past_dates_are_skipped(self, bs, slots):
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        days = bs.get_free_slots('Біорепарація шкіри', yesterday, TOMORROW)
        assert all(d['date'] >= datetime.now().strftime('%Y-%m-%d') for d in days)

    def test_range_is_capped(self, bs, slots):
        far = (datetime.now() + timedelta(days=400)).strftime('%Y-%m-%d')
        days = bs.get_free_slots('Біорепарація шкіри', TOMORROW, far)
        assert len(days) <= bs.MAX_RANGE_DAYS

    def test_schedule_is_fetched_once_for_the_whole_range(self, bs, slots):
        """Розклад тягнувся окремим запитом на кожен день — місяць коштував 15 с
        (замір: 10 днів = 4.77 с проти 0.27 с одним запитом)."""
        bs.get_free_slots('Біорепарація шкіри', TOMORROW, NEXT_WEEK)
        assert len(slots['schedule_calls']) == 1
        assert slots['schedule_calls'][0] == (TOMORROW, NEXT_WEEK)

    def test_empty_week_is_reported_day_by_day(self, bs, slots):
        """Горизонт = наскільки лікар заповнила розклад; решта днів open=False."""
        days = bs.get_free_slots('Біорепарація шкіри', TOMORROW, NEXT_WEEK)
        assert len(days) == 8
        assert all(d['open'] is False for d in days)


# ── Межі діапазону і чужі ресурси ─────────────────────────────────────────────

class TestClampRange:
    """Обрізати треба ДО звернення у WLaunch, інакше запит на 10 років тягне
    звідти десятирічний розклад, скільки б днів ми потім не віддали."""

    def test_horizon_is_two_weeks_from_today(self, bs):
        today = datetime.now().date()
        f, t = bs.clamp_range(today.strftime('%Y-%m-%d'),
                              (today + timedelta(days=400)).strftime('%Y-%m-%d'))
        assert t == (today + timedelta(days=bs.BOOKING_HORIZON_DAYS)).strftime('%Y-%m-%d')

    def test_horizon_counts_from_today_not_from_range_start(self, bs):
        """Інакше запит із `from` у майбутньому відкрив би запис за горизонт."""
        today = datetime.now().date()
        far = (today + timedelta(days=10)).strftime('%Y-%m-%d')
        _, t = bs.clamp_range(far, (today + timedelta(days=90)).strftime('%Y-%m-%d'))
        assert t == (today + timedelta(days=bs.BOOKING_HORIZON_DAYS)).strftime('%Y-%m-%d')

    def test_range_entirely_beyond_the_horizon_is_refused(self, bs):
        today = datetime.now().date()
        with pytest.raises(ValueError, match='горизонт'):
            bs.clamp_range((today + timedelta(days=60)).strftime('%Y-%m-%d'),
                           (today + timedelta(days=70)).strftime('%Y-%m-%d'))

    def test_short_range_is_left_alone(self, bs):
        today = datetime.now().date()
        f = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        t = (today + timedelta(days=3)).strftime('%Y-%m-%d')
        assert bs.clamp_range(f, t) == (f, t)

    def test_reversed_range_is_refused(self, bs):
        """Було 500 від WLaunch замість зрозумілої відмови."""
        with pytest.raises(ValueError, match='раніший'):
            bs.clamp_range('2026-10-28', '2026-10-26')

    def test_garbage_is_refused(self, bs):
        with pytest.raises(ValueError):
            bs.clamp_range('28.10.2026', '2026-10-30')

    def test_wlaunch_never_sees_the_raw_range(self, bs, slots):
        far = (datetime.now() + timedelta(days=4000)).strftime('%Y-%m-%d')
        bs.get_free_slots('Біорепарація шкіри', TOMORROW, far)
        _, asked_to = slots['schedule_calls'][0]
        horizon = (datetime.now().date() +
                   timedelta(days=bs.BOOKING_HORIZON_DAYS)).strftime('%Y-%m-%d')
        assert asked_to == horizon


class TestUnknownResource:
    """Третій ресурс у WLaunch (новий працівник, кабінет, апарат) не має тихо
    прибирати слоти в обох наших лікарів."""

    def test_our_resource_blocks_only_itself(self, bs):
        appt = {'service_resource_settings': [{'resources': ['res-v']}]}
        assert bs._appt_specialists(appt, {'res-v': 'victoria',
                                           'res-a': 'anastasia'}) == {'victoria'}

    def test_no_resource_at_all_blocks_everyone(self, bs):
        """WLaunch такий слот усе одно відхилить — краще не пропонувати."""
        assert bs._appt_specialists({}, {'res-v': 'victoria', 'res-a': 'anastasia'}) == \
            {'victoria', 'anastasia'}

    def test_foreign_resource_blocks_nobody(self, bs):
        appt = {'service_resource_settings': [{'resources': ['res-newcomer']}]}
        assert bs._appt_specialists(appt, {'res-v': 'victoria',
                                           'res-a': 'anastasia'}) == set()

    def test_mixed_resources_block_only_ours(self, bs):
        appt = {'service_resource_settings': [{'resources': ['res-newcomer', 'res-a']}]}
        assert bs._appt_specialists(appt, {'res-v': 'victoria',
                                           'res-a': 'anastasia'}) == {'anastasia'}
