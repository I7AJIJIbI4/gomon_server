# -*- coding: utf-8 -*-
"""
Regression tests for the post-visit blast of 17.10.2026.

Between 12:47 and 13:44 Kyiv one doctor (TG id 827551951) clicked through a
backlog of 124 pending drug/price confirmation buttons in the bot, covering
appointments from 2026-07-16 onwards. One hour later `photo_reminder.py
--cashback-notify` picked every one of them up (`cashback_status='confirmed'
AND cashback_notified_at IS NULL`, confirmed >= 1h ago) and called
`notifier.send_post_visit` for each: 125 delivered messages (100 SMS, 19 TG,
6 push) to 80 clients, up to 5 SMS to one person, asking them to review a
procedure that had happened up to three months earlier.

Nothing capped the visit's age: `send_post_visit` used `appt['date']` only to
build the dedup reference, and `notification_log` is pruned after 30 days, so
dedup could not have held the old dates back either.

Guard: `notifier.POST_VISIT_MAX_AGE_DAYS`. Cashback still accrues for a stale
visit — only the thank-you/review message is dropped.
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
sys.path.insert(0, ZADARMA)
from tz_utils import kyiv_now  # noqa: E402


class _NullRotatingHandler(logging.NullHandler):
    def __init__(self, *a, **kw):
        super().__init__()


def _load_real(name, filename, db_path=None):
    """Load a zadarma module under an alias so conftest's stubs stay intact."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(ZADARMA, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    _orig_rfh = logging.handlers.RotatingFileHandler
    logging.handlers.RotatingFileHandler = _NullRotatingHandler
    try:
        spec.loader.exec_module(mod)
    finally:
        logging.handlers.RotatingFileHandler = _orig_rfh
    if db_path:
        mod.DB_PATH = db_path
    return mod


def _ago(days):
    return (kyiv_now() - timedelta(days=days)).strftime('%Y-%m-%d')


# ── DB fixtures ───────────────────────────────────────────────────────────────

def _make_users_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        'CREATE TABLE users (id INTEGER PRIMARY KEY, phone TEXT, telegram_id INTEGER);'
        'CREATE TABLE cashback ('
        ' id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, amount REAL,'
        ' procedure_name TEXT, procedure_price REAL DEFAULT 0, appt_date TEXT,'
        " created_at TEXT DEFAULT (datetime('now')),"
        ' UNIQUE(phone, procedure_name, appt_date));'
        'CREATE TABLE deposits ('
        ' id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, amount_uah REAL, status TEXT);'
        'CREATE TABLE deposit_deductions ('
        ' id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, amount REAL, reason TEXT);'
        'CREATE TABLE photo_tasks ('
        ' id INTEGER PRIMARY KEY AUTOINCREMENT, appt_id TEXT,'
        ' client_phone TEXT NOT NULL, client_name TEXT, procedure_name TEXT,'
        ' specialist TEXT, appt_date TEXT NOT NULL, appt_time TEXT,'
        ' drive_folder_url TEXT, drive_folder_id TEXT,'
        ' photos_uploaded INTEGER DEFAULT 0, photos_checked_at TEXT,'
        " cashback_status TEXT DEFAULT 'pending', cashback_drug TEXT,"
        ' cashback_price REAL, cashback_confirmed_at TEXT, cashback_notified_at TEXT,'
        ' created_at TEXT DEFAULT CURRENT_TIMESTAMP,'
        ' UNIQUE(client_phone, appt_date, procedure_name));'
    )
    conn.commit()
    conn.close()


def _make_otp_db(path, app_phones=()):
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY, phone TEXT)')
    for ph in app_phones:
        conn.execute('INSERT INTO sessions (phone) VALUES (?)', (ph,))
    conn.commit()
    conn.close()


@pytest.fixture
def notif(tmp_path, monkeypatch):
    """Real notifier on a temp users.db, with SMS/TG/push captured."""
    db = str(tmp_path / 'users.db')
    _make_users_db(db)
    mod = _load_real('notifier_stale_real', 'notifier.py', db)

    sent = {'sms': [], 'tg': [], 'push': []}
    monkeypatch.setattr(sys.modules['sms_fly'], 'send_sms',
                        lambda to, msg: sent['sms'].append((to, msg)) or True)
    monkeypatch.setattr(mod, '_send_tg',
                        lambda tg_id, text, **kw: sent['tg'].append((tg_id, text)) or True)
    monkeypatch.setattr(mod, '_send_push',
                        lambda phone, t, b, tag='gomon', url='/app/':
                        sent['push'].append((phone, t)) or True)
    mod._sent = sent
    mod._db_file = db
    return mod


def _log_rows(db):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(
            'SELECT phone, type, reference, channel FROM notification_log').fetchall()
    except sqlite3.OperationalError:
        return []          # таблиця ще не створена — нічого не писалось
    finally:
        conn.close()


# ── 1. Вікова межа ────────────────────────────────────────────────────────────

class TestIsStaleVisit:
    """Межа POST_VISIT_MAX_AGE_DAYS на фіксованому годиннику."""

    @pytest.fixture(autouse=True)
    def _freeze(self, notif, monkeypatch):
        monkeypatch.setattr(notif, 'kyiv_now', lambda: datetime(2026, 10, 17, 14, 0, 0))
        self.mod = notif

    def test_default_cap_is_a_week(self):
        assert self.mod.POST_VISIT_MAX_AGE_DAYS == 7

    @pytest.mark.parametrize('date_str', [
        '2026-10-17',   # сьогодні
        '2026-10-16',   # вчора — звичайний шлях
        '2026-10-10',   # рівно 7 днів — межа включна
        '2026-10-18',   # майбутнє (перенесений запис)
    ])
    def test_fresh_dates_pass(self, date_str):
        assert self.mod._is_stale_visit(date_str) is False

    @pytest.mark.parametrize('date_str', [
        '2026-10-09',   # 8 днів — перший старий день
        '2026-09-15',
        '2026-07-16',   # найстаріший візит з інциденту 17.10
    ])
    def test_old_dates_are_stale(self, date_str):
        assert self.mod._is_stale_visit(date_str) is True

    @pytest.mark.parametrize('bad', ['', None, 'not-a-date', '17.10.2026', '2026-13-99'])
    def test_unparseable_date_is_not_stale(self, bad):
        """Зламану дату не глушимо — хай іде звичайним шляхом, як раніше."""
        assert self.mod._is_stale_visit(bad) is False


# ── 2. send_post_visit ────────────────────────────────────────────────────────

class TestSendPostVisitGuard:

    def test_stale_visit_sends_nothing_and_logs_nothing(self, notif):
        res = notif.send_post_visit({
            'client_phone': '380956719471', 'client_name': 'Віта',
            'procedure_name': 'Біорепарація шкіри', 'specialist': 'victoria',
            'date': _ago(90), 'time': '12:00', 'duration_min': 60,
        })
        assert res == {'skipped': 'stale'}
        assert notif._sent == {'sms': [], 'tg': [], 'push': []}
        assert _log_rows(notif._db_file) == []

    def test_fresh_visit_still_sends(self, notif):
        res = notif.send_post_visit({
            'client_phone': '380507653106', 'client_name': 'Олена',
            'procedure_name': 'Карбокситерапія', 'specialist': 'victoria',
            'date': _ago(1), 'time': '12:00', 'duration_min': 60,
        })
        assert res.get('skipped') is None
        assert [to for to, _ in notif._sent['sms']] == ['380507653106']
        assert 'sms' in {r[3] for r in _log_rows(notif._db_file)}

    def test_day_eight_is_the_first_blocked_day(self, notif):
        """7 днів ще шле, 8 — вже ні."""
        appt = {'client_phone': '380632287745', 'client_name': 'Тест',
                'procedure_name': 'Консультація', 'specialist': 'victoria',
                'time': '10:00', 'duration_min': 60}
        assert notif.send_post_visit(dict(appt, date=_ago(7))).get('skipped') is None
        assert notif.send_post_visit(dict(appt, date=_ago(8))) == {'skipped': 'stale'}
        assert [to for to, _ in notif._sent['sms']] == ['380632287745']


# ── 3. Інцидент: прогін беклогу підтверджень ──────────────────────────────────

class TestCashbackBacklogFlush:
    """photo_reminder.py --cashback-notify після масового підтвердження в боті."""

    @pytest.fixture
    def flush(self, tmp_path, monkeypatch, notif):
        _make_otp_db(str(tmp_path / 'otp_sessions.db'), app_phones=['380936487807'])
        photo = _load_real('photo_reminder_stale_real', 'photo_reminder.py', notif._db_file)

        # обидва модулі ходять у хардкодні /home/gomoncli/... шляхи
        _orig_connect = sqlite3.connect

        def _redirect(path, *a, **kw):
            if isinstance(path, str) and path.startswith('/home/gomoncli/zadarma/'):
                path = str(tmp_path / os.path.basename(path))
            return _orig_connect(path, *a, **kw)

        monkeypatch.setattr(sqlite3, 'connect', _redirect)
        monkeypatch.setitem(sys.modules, 'notifier', notif)
        return photo

    @staticmethod
    def _seed(db, rows):
        """rows: (phone, name, proc, days_ago, price). Підтверджено вчора — вже час слати."""
        confirmed = (kyiv_now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect(db)
        for phone, name, proc, days, price in rows:
            conn.execute(
                'INSERT INTO photo_tasks (client_phone, client_name, procedure_name,'
                " specialist, appt_date, appt_time, cashback_status, cashback_drug,"
                ' cashback_price, cashback_confirmed_at)'
                " VALUES (?,?,?,'victoria',?,NULL,'confirmed',?,?,?)",
                (phone, name, proc, _ago(days), proc, price, confirmed))
        conn.commit()
        conn.close()

    @staticmethod
    def _tasks(db):
        conn = sqlite3.connect(db)
        rows = conn.execute(
            'SELECT client_phone, appt_date, cashback_status, cashback_notified_at'
            ' FROM photo_tasks ORDER BY id').fetchall()
        conn.close()
        return rows

    def test_three_month_backlog_does_not_blast(self, flush, notif):
        """Старі візити не шлють нічого, свіжий у тій же пачці — шле."""
        db = notif._db_file
        self._seed(db, [
            ('380956719471', 'Віта',    'Біорепарація шкіри',      93, 4000),
            ('380972614818', 'Клієнт',  'Консультація',            29, 1500),
            ('380963579829', 'Клієнт',  'Консультація',            10, 1500),
            ('380632835290', 'Наталія', 'Корекція ботулотоксину',   8, 2000),
            ('380507653106', 'Олена',   'Карбокситерапія',          1, 2500),
        ])
        flush.check_pending_cashback_reminders()

        assert [to for to, _ in notif._sent['sms']] == ['380507653106']
        assert {r[0] for r in _log_rows(db)} == {'380507653106'}
        assert {r[1] for r in _log_rows(db)} == {'feedback'}

    def test_backlog_rows_are_not_retried(self, flush, notif):
        """Пропущений рядок має бути закритий — інакше крон повторює щочверть."""
        db = notif._db_file
        self._seed(db, [('380956719471', 'Віта', 'Біорепарація шкіри', 93, 4000)])
        flush.check_pending_cashback_reminders()

        (row,) = self._tasks(db)
        assert row[2] == 'notified'
        assert row[3] is not None

        notif._sent['sms'].clear()
        flush.check_pending_cashback_reminders()
        assert notif._sent['sms'] == []

    def test_app_user_still_gets_cashback_for_a_stale_visit(self, flush, notif):
        """Кешбек — це гроші клієнта, вік візиту глушить лише повідомлення."""
        db = notif._db_file
        self._seed(db, [('380936487807', 'App', 'Ботулінотерапія', 60, 5000)])
        flush.check_pending_cashback_reminders()

        conn = sqlite3.connect(db)
        cb = conn.execute('SELECT phone, amount, appt_date FROM cashback').fetchall()
        conn.close()
        assert len(cb) == 1
        assert cb[0][0] == '380936487807'
        assert cb[0][1] == pytest.approx(150.0)      # 3% з 5000
        assert notif._sent == {'sms': [], 'tg': [], 'push': []}
        assert _log_rows(db) == []

    # ── Коли слати: наступного дня в годину візиту ────────────────────────────
    #
    # 28.10.2026 о 20:05 лікар підтвердила препарати по 13 візитах, бот відповів
    # «клієнт отримає повідомлення наступного дня» — а о 21:15 того ж вечора
    # клієнтам пішли SMS: код чекав лише годину після підтвердження.

    @staticmethod
    def _at(monkeypatch, day, hhmm):
        """Підмінити «зараз» для check_pending_cashback_reminders."""
        h, m = map(int, hhmm.split(':'))
        fake = datetime.combine(day, datetime.min.time()).replace(hour=h, minute=m)
        monkeypatch.setattr(sys.modules['tz_utils'], 'kyiv_now', lambda: fake)

    @staticmethod
    def _seed_one(db, appt_date, appt_time, confirmed_at):
        conn = sqlite3.connect(db)
        conn.execute(
            'INSERT INTO photo_tasks (client_phone, client_name, procedure_name,'
            " specialist, appt_date, appt_time, cashback_status, cashback_drug,"
            ' cashback_price, cashback_confirmed_at)'
            " VALUES ('380631234519','Світлана','Ботулінотерапія','victoria',?,?,"
            "'confirmed','Ботулінотерапія 1 зона (Neuronox)',2200,?)",
            (appt_date, appt_time, confirmed_at))
        conn.commit()
        conn.close()

    def test_evening_confirmation_waits_for_next_day(self, flush, notif, monkeypatch):
        """Підтверджено о 20:05 — о 21:15 того ж дня клієнту нічого не йде."""
        today = kyiv_now().date()
        self._seed_one(notif._db_file, today.isoformat(), '13:00',
                       '{} 20:05:30'.format(today.isoformat()))
        self._at(monkeypatch, today, '21:15')
        flush.check_pending_cashback_reminders()

        assert notif._sent == {'sms': [], 'tg': [], 'push': []}
        assert self._tasks(notif._db_file)[0][2] == 'confirmed'   # не закрито, чекає

    def test_next_day_sends_at_the_visit_hour(self, flush, notif, monkeypatch):
        today = kyiv_now().date()
        yesterday = today - timedelta(days=1)
        self._seed_one(notif._db_file, yesterday.isoformat(), '13:00',
                       '{} 20:05:30'.format(yesterday.isoformat()))

        self._at(monkeypatch, today, '12:45')
        flush.check_pending_cashback_reminders()
        assert notif._sent['sms'] == []

        self._at(monkeypatch, today, '13:00')
        flush.check_pending_cashback_reminders()
        assert [to for to, _ in notif._sent['sms']] == ['380631234519']

    def test_unknown_visit_hour_sends_at_ten(self, flush, notif, monkeypatch):
        today = kyiv_now().date()
        yesterday = today - timedelta(days=1)
        self._seed_one(notif._db_file, yesterday.isoformat(), None,
                       '{} 20:05:30'.format(yesterday.isoformat()))

        self._at(monkeypatch, today, '09:30')
        flush.check_pending_cashback_reminders()
        assert notif._sent['sms'] == []

        self._at(monkeypatch, today, '10:00')
        flush.check_pending_cashback_reminders()
        assert len(notif._sent['sms']) == 1

    def test_late_visit_still_sends_within_working_hours(self, flush, notif, monkeypatch):
        """Візит о 21:30 не має застрягнути: крон останній раз ходить о 21:45."""
        today = kyiv_now().date()
        yesterday = today - timedelta(days=1)
        self._seed_one(notif._db_file, yesterday.isoformat(), '21:30',
                       '{} 21:50:00'.format(yesterday.isoformat()))

        self._at(monkeypatch, today, '21:00')
        flush.check_pending_cashback_reminders()
        assert len(notif._sent['sms']) == 1
