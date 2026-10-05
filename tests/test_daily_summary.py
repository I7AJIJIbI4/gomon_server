"""
Regression test for the daily summary total (reported 05.10.2026).

The report listed "Бріфінг на завтра: 2 відпр." and "Відгук: 1 відпр." but
closed with "Всього за день: 4". The per-type numbers are deduplicated per
(phone, type); the total used len(notif_entries), the raw notification_log row
count. Those rows overcount twice over:

  - one notification delivered on several channels is one message — the live
    05.10 data had push+tg rows for the same feedback to 380503443139;
  - spec_new writes one row per appointment for a single grouped
    "📋 N нових записів" message — 02.10 had 5 rows for one message.

The mismatch showed up on 11 of the preceding days; on 15.09 the body listed 2
and the total said 8.
"""
import os
import sys
import sqlite3
import logging
import logging.handlers
import importlib.util
import pytest

ZADARMA = os.path.join(os.path.dirname(__file__), '..', 'zadarma')


class _NullRotatingHandler(logging.NullHandler):
    def __init__(self, *a, **kw):
        super().__init__()


def _load_sms_reminder(db_path):
    spec = importlib.util.spec_from_file_location(
        'sms_reminder_real', os.path.join(ZADARMA, 'sms_reminder.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules['sms_reminder_real'] = mod
    _orig = logging.handlers.RotatingFileHandler
    logging.handlers.RotatingFileHandler = _NullRotatingHandler
    try:
        spec.loader.exec_module(mod)
    finally:
        logging.handlers.RotatingFileHandler = _orig
    mod.DB_PATH = db_path
    return mod


ROWS_2026_10_05 = [
    # (phone, type, reference, channel, sent_at) — the live data behind the report
    ('380996093860', 'tomorrow_briefing', 'briefing_2026-10-05', 'tg',
     '2026-10-05 21:05:02'),
    ('380685129121', 'tomorrow_briefing', 'briefing_anastasia_2026-10-05', 'tg',
     '2026-10-05 21:05:04'),
    # one feedback, two channels → one message
    ('380503443139', 'feedback', 'feedback|2026-10-05', 'push',
     '2026-10-05 22:00:04'),
    ('380503443139', 'feedback', 'feedback|2026-10-05', 'tg',
     '2026-10-05 22:00:05'),
]


def _make_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute(
        'CREATE TABLE notification_log (id INTEGER PRIMARY KEY AUTOINCREMENT,'
        ' phone TEXT NOT NULL, type TEXT NOT NULL, reference TEXT NOT NULL,'
        ' channel TEXT NOT NULL, status TEXT DEFAULT "sent", sent_at TEXT NOT NULL,'
        ' message_preview TEXT, UNIQUE(phone, type, reference, channel))'
    )
    for phone, ntype, ref, chan, ts in rows:
        conn.execute(
            'INSERT INTO notification_log (phone, type, reference, channel,'
            ' status, sent_at, message_preview) VALUES (?,?,?,?,"sent",?,?)',
            (phone, ntype, ref, chan, ts, 'preview'))
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def summary(monkeypatch, tmp_path):
    """Run send_daily_summary for a fixed date and return the message text."""
    def _run(rows, today='2026-10-05'):
        db = _make_db(str(tmp_path / ('s' + today + '.db')), rows)
        mod = _load_sms_reminder(db)

        from datetime import datetime
        fixed = datetime.strptime(today + ' 22:10', '%Y-%m-%d %H:%M')
        monkeypatch.setattr(mod, 'kyiv_now', lambda: fixed)

        sent = []
        monkeypatch.setattr(mod, '_tg_send_long',
                            lambda uid, text, token, **kw: sent.append(text))
        # the repeat-procedure log is a real path; keep it out of the way
        monkeypatch.setattr(mod, 'logger', logging.getLogger('test_sms'))
        mod.send_daily_summary()
        return sent[0] if sent else ''
    return _run


def _total(text):
    """Pull the number out of 'Всього за день: N'."""
    import re
    m = re.search(r'Всього за день: (\d+)', text)
    assert m, 'no total line in:\n' + text
    return int(m.group(1))


def _per_type(text):
    """Sum the 'N відпр.' numbers listed per type."""
    import re
    return sum(int(n) for n in re.findall(r'</b>: (\d+) відпр', text))


def test_total_matches_the_listed_numbers(summary):
    text = summary(ROWS_2026_10_05)
    assert _per_type(text) == 3, text
    assert _total(text) == 3, text


def test_multichannel_delivery_counts_once(summary):
    """push + tg for the same feedback is one message, not two."""
    text = summary([
        ('380503443139', 'feedback', 'feedback|2026-10-05', 'push',
         '2026-10-05 22:00:04'),
        ('380503443139', 'feedback', 'feedback|2026-10-05', 'tg',
         '2026-10-05 22:00:05'),
    ])
    assert _total(text) == 1, text


def test_grouped_spec_new_counts_once(summary):
    """spec_new logs a row per appointment for one grouped message."""
    rows = [
        ('380685129121', 'spec_new', 'wl-{}|2026-10-06|1{}:00'.format(i, i),
         'tg', '2026-10-05 18:0{}:00'.format(i))
        for i in range(5)
    ]
    text = summary(rows)
    assert _total(text) == 1, text


def test_distinct_recipients_still_counted_separately(summary):
    """The dedup must not swallow two different people."""
    text = summary([
        ('380996093860', 'tomorrow_briefing', 'briefing_2026-10-05', 'tg',
         '2026-10-05 21:05:02'),
        ('380685129121', 'tomorrow_briefing', 'briefing_a_2026-10-05', 'tg',
         '2026-10-05 21:05:04'),
    ])
    assert _total(text) == 2, text


def test_distinct_types_still_counted_separately(summary):
    text = summary([
        ('380503443139', 'feedback', 'feedback|2026-10-05', 'tg',
         '2026-10-05 22:00:05'),
        ('380503443139', 'cancel', 'cancel|1|2026-10-05', 'tg',
         '2026-10-05 20:00:00'),
    ])
    assert _total(text) == 2, text
