# -*- coding: utf-8 -*-
"""tz_utils.kyiv_day_start_utc — київська північ у UTC для порівняння з created_at."""
from datetime import datetime

import pytest

import tz_utils


@pytest.mark.parametrize('kyiv,expected', [
    ('2026-11-05 00:30', '2026-11-04 22:00:00'),   # зима, одразу після півночі
    ('2026-11-05 23:59', '2026-11-04 22:00:00'),   # та сама доба
    ('2026-07-01 10:00', '2026-06-30 21:00:00'),   # літо
    ('2026-03-29 00:30', '2026-03-28 22:00:00'),   # день переходу на літній: північ ще зимова
    ('2026-03-29 12:00', '2026-03-28 22:00:00'),
    ('2026-10-25 00:30', '2026-10-24 21:00:00'),   # день переходу на зимовий: північ ще літня
    ('2026-10-25 12:00', '2026-10-24 21:00:00'),
    ('2027-01-01 00:10', '2026-12-31 22:00:00'),   # через рік
])
def test_kyiv_day_start_utc(kyiv, expected):
    assert tz_utils.kyiv_day_start_utc(datetime.strptime(kyiv, '%Y-%m-%d %H:%M')) == expected


def test_kyiv_day_start_utc_uses_now_by_default(frozen_kyiv):
    frozen_kyiv('2026-11-05 01:15')
    assert tz_utils.kyiv_day_start_utc() == '2026-11-04 22:00:00'
