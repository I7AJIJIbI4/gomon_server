#!/usr/bin/env python3
"""Пропускає cron-запуск лише в потрібний київський час.

Ubuntu cron працює в UTC і не вміє ні TZ=, ні CRON_TZ=, а Київ двічі на рік
змінює зсув (UTC+2 взимку, UTC+3 влітку). Раніше години в crontab зсували
вручну в останню неділю березня й жовтня — і забути означало, що SMS і
нагадування йдуть на годину раніше чи пізніше.

Тепер кожна джоба з фіксованою годиною стоїть у crontab на ОБИДВІ можливі
UTC-години, а перед командою — цей гейт, який пропускає лише запуск, що
припадає на потрібний київський час:

    5 6,7 * * *   cd $APP && $VENV kyiv_gate.py 09:05 && $VENV script.py

Специфікація — через кому:
    HH:MM          у межах TOLERANCE_MIN хвилин після цього часу
    HH:MM-HH:MM    у вікні включно (для */15-джоб)

Код виходу: 0 — запускати, 1 — пропустити, 2 — невірна специфікація.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tz_utils import kyiv_now  # noqa: E402

#: Запас на запізнення старту крону. Сусідній кандидат завжди на годину далі.
TOLERANCE_MIN = 10


def _minutes(hhmm):
    h, m = hhmm.split(':')
    h, m = int(h), int(m)
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(hhmm)
    return h * 60 + m


def parse(spec):
    """'09:05,21:05' / '08:00-22:59' -> [('at', 545), ('between', 480, 1379)]."""
    out = []
    for part in spec.split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-', 1)
            lo, hi = _minutes(a), _minutes(b)
            if hi < lo:
                raise ValueError(part)
            out.append(('between', lo, hi))
        else:
            out.append(('at', _minutes(part)))
    if not out:
        raise ValueError(spec)
    return out


def should_run(spec, kyiv_dt):
    now = kyiv_dt.hour * 60 + kyiv_dt.minute
    for rule in parse(spec):
        if rule[0] == 'at' and 0 <= now - rule[1] < TOLERANCE_MIN:
            return True
        if rule[0] == 'between' and rule[1] <= now <= rule[2]:
            return True
    return False


def main(argv):
    if len(argv) != 2:
        sys.stderr.write('usage: kyiv_gate.py HH:MM[,HH:MM|HH:MM-HH:MM...]\n')
        return 2
    try:
        return 0 if should_run(argv[1], kyiv_now()) else 1
    except ValueError as e:
        sys.stderr.write('kyiv_gate: bad spec {!r}: {}\n'.format(argv[1], e))
        return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
