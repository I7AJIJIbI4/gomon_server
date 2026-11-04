# -*- coding: utf-8 -*-
"""
deploy/crontab — джерело правди для крону — і kyiv_gate.py.

Двічі цього року крон тихо робив не те:
  - червень: змінні APP/VENV/PATH опинились після джоб → 6 днів нічого не працювало;
  - 25–28.10: Київ перейшов на зимовий час, а години в crontab — ні → SMS на годину
    раніше, нагадування о 21:00 не йшли.

Тест імітує крон хвилина за хвилиною на всю київську добу — звичайну зимову й
літню, обидва дні переходу й Новий рік — і перевіряє, що кожна джоба спрацьовує
рівно в обіцяний київський час: не на годину раніше, не двічі, не пропущена.
"""
import os
import re
import sys
from datetime import datetime, timedelta

import pytest

import tz_utils
from conftest import load_real

CRONTAB = os.path.join(os.path.dirname(__file__), '..', 'deploy', 'crontab')
GATE_RE = re.compile(r'kyiv_gate\.py (\S+) &&')

DAYS = ['2026-11-04', '2026-07-15', '2027-03-28', '2026-10-25', '2027-01-01']


@pytest.fixture(scope='module')
def gate():
    return load_real('kyiv_gate_real', 'kyiv_gate.py')


def _lines():
    with open(CRONTAB, encoding='utf-8') as f:
        return [l.rstrip('\n') for l in f]


def _jobs():
    out = []
    for l in _lines():
        s = l.strip()
        if not s or s.startswith('#') or re.match(r'^[A-Z_]+=', s):
            continue
        minute, hour, dom, mon, dow, cmd = s.split(None, 5)
        out.append({'minute': minute, 'hour': hour, 'rest': (dom, mon, dow), 'cmd': cmd, 'line': s})
    return out


def _field(spec, value):
    """Мінімальний матчер полів cron: *, */N, a-b, a,b,c, a."""
    for part in spec.split(','):
        if part == '*':
            return True
        if part.startswith('*/'):
            if value % int(part[2:]) == 0:
                return True
        elif '-' in part:
            a, b = map(int, part.split('-'))
            if a <= value <= b:
                return True
        elif int(part) == value:
            return True
    return False


def _kyiv_runs(job, gate, kyiv_day):
    """Київські HH:MM, коли джоба реально відпрацює протягом київської доби kyiv_day."""
    day = datetime.strptime(kyiv_day, '%Y-%m-%d')
    start = datetime.strptime(tz_utils.kyiv_day_start_utc(day), '%Y-%m-%d %H:%M:%S')
    end = datetime.strptime(tz_utils.kyiv_day_start_utc(day + timedelta(days=1)), '%Y-%m-%d %H:%M:%S')
    m = GATE_RE.search(job['cmd'])
    runs, t = [], start
    while t < end:
        if _field(job['minute'], t.minute) and _field(job['hour'], t.hour):
            k = tz_utils.utc_to_kyiv(t)
            if not m or gate.should_run(m.group(1), k):
                runs.append(k.strftime('%H:%M'))
        t += timedelta(minutes=1)
    return runs


def _expected(job, gate):
    """Що обіцяє специфікація гейта: кожен 'at' — один раз; вікно — кожен слот крону в ньому."""
    spec = GATE_RE.search(job['cmd']).group(1)
    out = []
    for rule in gate.parse(spec):
        if rule[0] == 'at':
            out.append(rule[1])
        else:
            out += [x for x in range(rule[1], rule[2] + 1)
                    if _field(job['minute'], x % 60)]
    return sorted('{:02d}:{:02d}'.format(x // 60, x % 60) for x in out)


# ── Структура файлу ───────────────────────────────────────────────────────────

def test_variables_come_before_every_job():
    """Vixie cron ігнорує змінні після джоб — так стався 6-денний збій у червні."""
    first_job = next(i for i, l in enumerate(_lines())
                     if l.strip() and not l.lstrip().startswith('#') and not re.match(r'^[A-Z_]+=', l))
    for i, l in enumerate(_lines()):
        if re.match(r'^[A-Z_]+=', l):
            assert i < first_job, 'змінна після джоби: {}'.format(l)
    for var in ('APP', 'VENV', 'PATH'):
        assert any(l.startswith(var + '=') for l in _lines()[:first_job])


def test_every_fixed_hour_job_is_gated():
    """Джоба з конкретною годиною без гейта зсунеться на годину при зміні часу."""
    for job in _jobs():
        interval = job['hour'] == '*' or job['hour'].startswith('*/')
        assert interval or GATE_RE.search(job['cmd']), job['line']
        assert job['rest'] == ('*', '*', '*'), job['line']


def test_the_jobs_we_rely_on_are_all_there():
    cmds = ' '.join(j['cmd'] for j in _jobs())
    for needle in ('sync_appointments.py', 'sync_with_notification.sh', 'push_reminder.py',
                   'sms_reminder.py', 'sms_reminder.py --daily-summary', 'appt_reminder.py --reminder',
                   'appt_reminder.py --feedback', 'appt_reminder.py --specialist',
                   'photo_reminder.py --create', 'photo_reminder.py --check',
                   'photo_reminder.py --cashback-notify', 'photo_cache.py', 'wl_catalog.py --sync',
                   'sync_reviews.py', 'ig_health.py', 'health_check.py', 'anthropic_health.py',
                   'deposit/reconcile', '.backup', 'otp_sessions.db', 'appointment_audit_log'):
        assert needle in cmds, needle


# ── Розклад: рівно в обіцяний київський час, у будь-яку пору року ────────────

GATED = [j for j in _jobs() if GATE_RE.search(j['cmd'])]


@pytest.mark.parametrize('day', DAYS)
@pytest.mark.parametrize('job', GATED, ids=[GATE_RE.search(j['cmd']).group(1) + ' ' +
                                            j['cmd'].split('&&')[-1].split('>>')[0].strip()[-40:]
                                            for j in GATED])
def test_job_runs_exactly_at_its_kyiv_time(gate, job, day):
    assert _kyiv_runs(job, gate, day) == _expected(job, gate)


@pytest.mark.parametrize('day', DAYS)
def test_promised_kyiv_times(gate, day):
    """Ключові часи, що їх бачать клієнти й лікар, — явно, а не з самого файлу."""
    def runs(needle):
        job = next(j for j in GATED if needle in j['cmd'])
        return _kyiv_runs(job, gate, day)
    assert runs('sync_with_notification.sh') == ['09:05', '21:05']
    assert runs('appt_reminder.py --reminder') == ['10:10', '18:10']
    assert runs('appt_reminder.py --specialist') == ['21:05']
    assert runs('photo_reminder.py --create') == ['21:00']
    assert runs('--daily-summary') == ['22:10']
    assert runs('.backup') == ['02:50']
    sms = runs('$VENV sms_reminder.py >>')
    assert sms[0] == '09:00' and sms[-1] == '21:00' and len(sms) == 13
    push = runs('push_reminder.py')
    assert push[0] == '08:00' and push[-1] == '22:45'


# ── kyiv_gate.py ──────────────────────────────────────────────────────────────

def _k(hhmm):
    return datetime(2026, 11, 4, *map(int, hhmm.split(':')))


@pytest.mark.parametrize('spec,now,run', [
    ('09:05', '09:05', True),
    ('09:05', '09:14', True),
    ('09:05', '09:15', False),       # поза допуском
    ('09:05', '08:05', False),       # «зимовий» кандидат улітку — на годину раніше
    ('09:05', '10:05', False),
    ('09:05,21:05', '21:06', True),
    ('08:00-22:59', '08:00', True),
    ('08:00-22:59', '22:59', True),
    ('08:00-22:59', '07:45', False),
    ('08:00-22:59', '23:00', False),
])
def test_gate_decision(gate, spec, now, run):
    assert gate.should_run(spec, _k(now)) is run


@pytest.mark.parametrize('spec', ['', '25:00', '09:60', '9', '22:00-08:00', 'abc'])
def test_gate_rejects_bad_specs(gate, spec):
    with pytest.raises(ValueError):
        gate.parse(spec)


def test_gate_exit_codes(gate, frozen_kyiv):
    frozen_kyiv('2026-11-04 09:05')
    assert gate.main(['kyiv_gate.py', '09:05']) == 0
    assert gate.main(['kyiv_gate.py', '10:05']) == 1
    assert gate.main(['kyiv_gate.py', '9:61']) == 2, 'помилка в crontab має бути видна, а не тихим «пропустити»'
    assert gate.main(['kyiv_gate.py']) == 2
