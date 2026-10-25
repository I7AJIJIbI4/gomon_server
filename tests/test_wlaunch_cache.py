# -*- coding: utf-8 -*-
"""
Кеш довідників WLaunch.

`get_branch_id` і `get_wlaunch_resources` викликались на кожен запит слотів і
на кожне створення запису, хоча філія і склад спеціалістів змінюються раз на
місяці. Разом із переходом на один запит розкладу це те, що тримало
/api/booking/slots на секундах.

Головне, що тут перевіряється — порожню відповідь не кешувати. Обидві функції
повертають None/{} і на мережевій помилці теж; запамʼятати це на годину
означало б покласти запис на годину.
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


@pytest.fixture
def wl():
    """Свіжий wlaunch_api на кожен тест — кеш модульного рівня."""
    sys.modules['config'].WLAUNCH_API_BEARER = 'Bearer test'
    spec = importlib.util.spec_from_file_location(
        'wlaunch_api_cache_real', os.path.join(ZADARMA, 'wlaunch_api.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules['wlaunch_api_cache_real'] = mod
    _orig = logging.handlers.RotatingFileHandler
    logging.handlers.RotatingFileHandler = _NullRotatingHandler
    try:
        spec.loader.exec_module(mod)
    finally:
        logging.handlers.RotatingFileHandler = _orig
    mod._LOOKUP_CACHE.clear()
    return mod


class TestBranchCache:

    def test_second_call_does_not_refetch(self, wl, monkeypatch):
        calls = []
        monkeypatch.setattr(wl, '_get_branch_id_uncached',
                            lambda: calls.append(1) or 'branch-1')
        assert wl.get_branch_id() == 'branch-1'
        assert wl.get_branch_id() == 'branch-1'
        assert wl.get_branch_id() == 'branch-1'
        assert len(calls) == 1

    def test_failure_is_not_cached(self, wl, monkeypatch):
        """Інакше одна мережева помилка клала б запис на цілу годину."""
        results = [None, None, 'branch-1']
        monkeypatch.setattr(wl, '_get_branch_id_uncached', lambda: results.pop(0))
        assert wl.get_branch_id() is None
        assert wl.get_branch_id() is None
        assert wl.get_branch_id() == 'branch-1'
        assert results == []

    def test_cache_expires(self, wl, monkeypatch):
        calls = []
        monkeypatch.setattr(wl, '_get_branch_id_uncached',
                            lambda: calls.append(1) or 'branch-1')
        wl.get_branch_id()
        # відмотуємо мітку часу так, ніби запис зроблено до закінчення TTL
        ts, val = wl._LOOKUP_CACHE['branch']
        wl._LOOKUP_CACHE['branch'] = (ts - wl.LOOKUP_CACHE_TTL - 1, val)
        wl.get_branch_id()
        assert len(calls) == 2


class TestResourcesCache:

    def test_second_call_does_not_refetch(self, wl, monkeypatch):
        calls = []
        monkeypatch.setattr(wl, '_get_wlaunch_resources_uncached',
                            lambda branch_id=None: calls.append(branch_id) or
                            {'victoria': 'res-v'})
        assert wl.get_wlaunch_resources('b1') == {'victoria': 'res-v'}
        assert wl.get_wlaunch_resources('b1') == {'victoria': 'res-v'}
        assert len(calls) == 1

    def test_different_branches_cached_apart(self, wl, monkeypatch):
        calls = []
        monkeypatch.setattr(wl, '_get_wlaunch_resources_uncached',
                            lambda branch_id=None: calls.append(branch_id) or
                            {'victoria': 'res-' + str(branch_id)})
        assert wl.get_wlaunch_resources('b1')['victoria'] == 'res-b1'
        assert wl.get_wlaunch_resources('b2')['victoria'] == 'res-b2'
        assert calls == ['b1', 'b2']

    def test_empty_result_is_not_cached(self, wl, monkeypatch):
        results = [{}, {'victoria': 'res-v'}]
        monkeypatch.setattr(wl, '_get_wlaunch_resources_uncached',
                            lambda branch_id=None: results.pop(0))
        assert wl.get_wlaunch_resources('b1') == {}
        assert wl.get_wlaunch_resources('b1') == {'victoria': 'res-v'}
        assert results == []
