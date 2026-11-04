# -*- coding: utf-8 -*-
"""
Вхідні вебхуки: Instagram Direct і WLaunch.

  POST /api/webhook/ig-message   — вхідне повідомлення або echo нашої відповіді
                                   (пересилає messenger/webhook.php з localhost)
  POST /api/webhook/ig-ai-reply  — поставити AI-відповідь у чергу (90 с на «друкує»)
  _ig_process_reply              — сама AI-відповідь: guard-и, Anthropic, відправка
  POST /api/webhook/wlaunch      — подія запису з WLaunch

Найдорожчі помилки тут — AI, що відповідає поверх лікаря (25.05.2026), і
«відповіли», якого клієнт не отримав (протухлий токен). Тож перевіряємо guard-и
і те, що в базі лишається лише справді відправлене.
"""
import sys
import json
import types
import sqlite3
import itertools

import pytest
import requests


_seq = itertools.count(1)
OUTSIDE = {'REMOTE_ADDR': '203.0.113.7'}


def _sid():
    return '17841{:010d}'.format(next(_seq))


@pytest.fixture(autouse=True)
def _prod_messages_schema(pwa):
    """messages.avatar_url є в проді (додано вручну ALTER-ом), але init_messages_db
    його не створює — див. test_fresh_database_has_avatar_url. Тут дзеркалимо прод."""
    conn = sqlite3.connect(pwa.DB_PATH)
    cols = [r[1] for r in conn.execute('PRAGMA table_info(messages)')]
    if 'avatar_url' not in cols:
        conn.execute('ALTER TABLE messages ADD COLUMN avatar_url TEXT DEFAULT NULL')
        conn.commit()
    conn.close()


@pytest.mark.xfail(strict=True, reason=(
    'Прод-ризик, чекає рішення власника: init_messages_db не створює messages.avatar_url, '
    'а ig_message_webhook пише в неї. У проді колонку додали вручну; на свіжій базі '
    '(відновлення, новий сервер) кожне вхідне з Instagram падатиме з 500.'))
def test_fresh_database_has_avatar_url(pwa, tmp_path, monkeypatch):
    monkeypatch.setattr(pwa, 'DB_PATH', str(tmp_path / 'fresh.db'))
    pwa.init_messages_db()
    conn = sqlite3.connect(pwa.DB_PATH)
    cols = [r[1] for r in conn.execute('PRAGMA table_info(messages)')]
    conn.close()
    assert 'avatar_url' in cols


def _q(pwa, sql, args=()):
    conn = sqlite3.connect(pwa.DB_PATH)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _exec(pwa, sql, args=()):
    conn = sqlite3.connect(pwa.DB_PATH)
    conn.execute(sql, args)
    conn.commit()
    conn.close()


class _Resp(object):
    def __init__(self, status=200, data=None):
        self.status_code = status
        self._data = data or {}
        self.text = json.dumps(self._data)

    def json(self):
        return self._data


@pytest.fixture
def graph_name(pwa, monkeypatch):
    """Graph API для імені відправника — без мережі; рахуємо звернення."""
    calls = []

    def _get(url, params=None, timeout=None):
        calls.append(url)
        return _Resp(200, {'name': 'Ольга Тест', 'username': 'olya_t', 'profile_pic': 'https://pic'})
    monkeypatch.setattr(pwa._req, 'get', _get)
    return calls


# ── ig-message: вхідні ────────────────────────────────────────────────────────

@pytest.mark.parametrize('route', ['/api/webhook/ig-message', '/api/webhook/ig-ai-reply'])
def test_ig_webhooks_refuse_outside_callers(client, pwa, route):
    """Лише webhook.php з localhost. Ззовні їх ще й ріже nginx (перевірено 04.11.2026)."""
    sid = _sid()
    rv = client.post(route, json={'sender_id': sid, 'text': 'hi'}, environ_base=OUTSIDE)
    assert rv.status_code == 403
    assert _q(pwa, 'SELECT 1 FROM messages WHERE conversation_id=?', ('ig_' + sid,)) == []


def test_ig_message_without_sender_is_rejected(client):
    assert client.post('/api/webhook/ig-message', json={'text': 'hi'}).status_code == 400


def test_client_message_is_stored_with_resolved_name(client, pwa, graph_name):
    sid = _sid()
    rv = client.post('/api/webhook/ig-message', json={'sender_id': sid, 'text': 'Скільки коштує ботокс?'})
    assert rv.status_code == 200
    (row,) = _q(pwa, 'SELECT sender_name, content, is_from_admin, avatar_url FROM messages'
                     ' WHERE conversation_id=?', ('ig_' + sid,))
    assert row == ('Ольга Тест', 'Скільки коштує ботокс?', 0, 'https://pic')

    client.post('/api/webhook/ig-message', json={'sender_id': sid, 'text': 'І філер?'})
    assert len(graph_name) == 1, "ім'я вже є — Graph API вдруге не смикаємо"


def test_client_name_is_never_inherited_from_admin_echo(client, pwa, graph_name):
    """Регресія 25.05.2026: перший рядок розмови — echo лікаря з sender_name='Admin',
    і нові повідомлення клієнта успадковували «Admin», а з ним і ai_mute не на того."""
    sid = _sid()
    _exec(pwa, "INSERT INTO messages (conversation_id, sender_id, sender_name, platform, content,"
               " is_from_admin, created_at) VALUES (?, 'admin_ig', 'Admin', 'instagram', 'Добрий день',"
               " 1, datetime('now','-1 day'))", ('ig_' + sid,))
    client.post('/api/webhook/ig-message', json={'sender_id': sid, 'text': 'Дякую'})
    names = _q(pwa, 'SELECT sender_name FROM messages WHERE conversation_id=? AND is_from_admin=0',
               ('ig_' + sid,))
    assert names == [('Ольга Тест',)]


# ── ig-message: echo наших відправок ──────────────────────────────────────────

def test_doctor_reply_from_ig_app_is_stored_as_admin_and_marks_read(client, pwa, graph_name):
    """Відповідь лікаря з телефону — це admin_pause для AI на 72 год."""
    sid = _sid()
    client.post('/api/webhook/ig-message', json={'sender_id': sid, 'text': 'Можна записатись?'})
    rv = client.post('/api/webhook/ig-message', json={
        'sender_id': 'page', 'recipient_id': sid, 'is_echo': True, 'text': 'Так, на четвер о 15:00'})
    assert rv.get_json() == {'ok': True, 'echo': True}
    rows = _q(pwa, 'SELECT sender_id, is_from_admin, is_read FROM messages WHERE conversation_id=?'
                   ' ORDER BY id', ('ig_' + sid,))
    assert rows[-1][:2] == ('admin_ig', 1)
    assert rows[0][2] == 1, 'клієнтське повідомлення позначене прочитаним'


def test_echo_of_our_own_ai_reply_is_not_mistaken_for_the_doctor(client, pwa):
    """Echo AI-відповіді, збережене як «лікар», вимкнуло б AI в розмові на 72 години."""
    sid = _sid()
    _exec(pwa, "INSERT INTO messages (conversation_id, sender_id, platform, content, media_type,"
               " is_from_admin, created_at) VALUES (?, 'ai_bot', 'instagram', ?, 'text', 1, datetime('now'))",
          ('ig_' + sid, 'Ботулінотерапія 1 зона — від 2200 грн'))
    rv = client.post('/api/webhook/ig-message', json={
        'sender_id': 'page', 'recipient_id': sid, 'is_echo': True,
        'text': 'Ботулінотерапія 1 зона — від 2200 грн'})
    assert rv.get_json().get('skipped') == 'ai_dup'
    assert _q(pwa, "SELECT 1 FROM messages WHERE conversation_id=? AND sender_id='admin_ig'",
              ('ig_' + sid,)) == []


# ── ig-message: ціна кешбеку від лікаря в Direct ──────────────────────────────

@pytest.fixture
def cashback_ig(pwa, monkeypatch):
    """Таблиця photo_tasks, препарати і відповідь лікарю — без мережі."""
    conn = sqlite3.connect(pwa.DB_PATH)
    conn.execute(
        'CREATE TABLE IF NOT EXISTS photo_tasks ('
        ' id INTEGER PRIMARY KEY AUTOINCREMENT, appt_id TEXT, client_phone TEXT NOT NULL,'
        ' client_name TEXT, procedure_name TEXT, specialist TEXT, appt_date TEXT NOT NULL,'
        ' appt_time TEXT, drive_folder_url TEXT, drive_folder_id TEXT,'
        ' photos_uploaded INTEGER DEFAULT 0, photos_checked_at TEXT,'
        " cashback_status TEXT DEFAULT 'pending', cashback_drug TEXT, cashback_price REAL,"
        ' cashback_confirmed_at TEXT, cashback_notified_at TEXT,'
        ' created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(client_phone, appt_date, procedure_name))')
    conn.commit()
    conn.close()

    drugs = types.ModuleType('photo_reminder')
    drugs._get_drugs_for_procedure = lambda proc: (
        [{'name': 'Біорепарація Rejuran S', 'price': 3500},
         {'name': 'Біорепарація Rejuran HB', 'price': 4200}] if proc == 'Біорепарація шкіри' else [])
    monkeypatch.setitem(sys.modules, 'photo_reminder', drugs)
    sent = []
    monkeypatch.setattr(sys.modules['notifier'], '_send_ig',
                        lambda uid, text: sent.append((uid, text)), raising=False)
    return sent


def _tagged_request(pwa, doctor_uid, phone, mmdd, text):
    """Повідомлення лікарю з тегом — так його пише photo_reminder (останні 10 цифр номера)."""
    _exec(pwa, "INSERT INTO messages (conversation_id, sender_id, platform, content, is_from_admin,"
               " created_at) VALUES (?, 'ai_bot', 'instagram', ?, 1, datetime('now','-1 hour'))",
          ('ig_' + doctor_uid, text + '\n#cashback|{}|{}'.format(phone[-10:], mmdd)))


def _photo_task(pwa, phone, date, proc='Біорепарація шкіри'):
    """Візит, що чекає препарат. Клієнт є в clients — за ним вебхук відновлює повний номер з тегу."""
    from conftest import _insert_client
    _insert_client(phone, 'Ірина Тест')
    _exec(pwa, "INSERT INTO photo_tasks (client_phone, client_name, procedure_name, specialist,"
               " appt_date, cashback_status) VALUES (?, 'Ірина', ?, 'victoria', ?, 'needs_drug')",
          (phone, proc, date))


def test_doctor_price_reply_confirms_the_cashback(client, pwa, cashback_ig, frozen_kyiv):
    frozen_kyiv('2026-11-04 12:00')
    doctor, phone = _sid(), '380507770001'
    _photo_task(pwa, phone, '2026-11-03')
    _tagged_request(pwa, doctor, phone, '1103', '💰 Кешбек: Ірина (Біорепарація шкіри)\n\n'
                    '  Біорепарація Rejuran S — ₴3500\n  Біорепарація Rejuran HB — ₴4200')

    rv = client.post('/api/webhook/ig-message', json={
        'sender_id': 'page', 'recipient_id': doctor, 'is_echo': True, 'text': '3500'})

    assert rv.get_json() == {'ok': True, 'cashback': True}
    assert _q(pwa, 'SELECT cashback_status, cashback_drug, cashback_price FROM photo_tasks'
                   ' WHERE client_phone=?', (phone,)) == [('confirmed', 'Біорепарація Rejuran S', 3500)]
    assert _q(pwa, 'SELECT drug_specific, price, appt_date, confirmed_by FROM cashback_pending'
                   ' WHERE phone=?', (phone,)) == [('Біорепарація Rejuran S', 3500, '2026-11-03', 'ig_doctor')]
    assert '+105 грн' in cashback_ig[0][1]      # 3% з 3500


@pytest.mark.xfail(strict=True, reason=(
    'Прод-баг, чекає рішення власника: процедуру беруть з ОСТАННІХ дужок повідомлення, '
    'а справжнє повідомлення з препаратами закінчується на «(наприклад: 3500)». '
    'У результаті drug_specific = «наприклад: 3500». У проді ще не спрацьовувало '
    '(0 IG-підтверджень станом на 04.11.2026) — лікар підтверджує через TG-бот.'))
def test_real_drug_prompt_text_still_resolves_the_drug(client, pwa, cashback_ig, frozen_kyiv):
    frozen_kyiv('2026-11-04 12:00')
    doctor, phone = _sid(), '380507770002'
    _photo_task(pwa, phone, '2026-11-03')
    _tagged_request(pwa, doctor, phone, '1103', '💰 Кешбек: Ірина (Біорепарація шкіри)\n\n'
                    '  Біорепарація Rejuran S — ₴3500\n  Біорепарація Rejuran HB — ₴4200\n\n'
                    'Відправте ціну числом (наприклад: 3500)')
    client.post('/api/webhook/ig-message', json={
        'sender_id': 'page', 'recipient_id': doctor, 'is_echo': True, 'text': '3500'})
    assert _q(pwa, 'SELECT cashback_drug FROM photo_tasks WHERE client_phone=?', (phone,)) == \
        [('Біорепарація Rejuran S',)]


@pytest.mark.xfail(strict=True, reason=(
    'Прод-баг, чекає рішення власника: рік візиту береться з поточної дати. Візит 28.12, '
    'підтверджений 02.01, отримує дату наступного року — photo_tasks не знаходиться, '
    'кешбек «зависає».'))
def test_price_reply_across_new_year_keeps_the_visit_year(client, pwa, cashback_ig, frozen_kyiv):
    frozen_kyiv('2027-01-02 12:00')
    doctor, phone = _sid(), '380507770003'
    _photo_task(pwa, phone, '2026-12-28')
    _tagged_request(pwa, doctor, phone, '1228', '💰 Кешбек: Ірина (Біорепарація шкіри)')
    client.post('/api/webhook/ig-message', json={
        'sender_id': 'page', 'recipient_id': doctor, 'is_echo': True, 'text': '4200'})
    assert _q(pwa, 'SELECT cashback_status FROM photo_tasks WHERE client_phone=?', (phone,)) == \
        [('confirmed',)]


# ── ig-ai-reply: черга ────────────────────────────────────────────────────────

@pytest.fixture
def queued(monkeypatch):
    """Потік із 90-секундним sleep не запускаємо — лише фіксуємо, що його поставили."""
    import threading
    started = []

    class _Rec(object):
        def __init__(self, target=None, args=(), kwargs=None, daemon=None):
            self.args = args

        def start(self):
            started.append(self.args)
    monkeypatch.setattr(threading, 'Thread', _Rec)
    return started


def test_ai_reply_is_queued_for_a_quiet_conversation(client, queued):
    sid = _sid()
    rv = client.post('/api/webhook/ig-ai-reply', json={'sender_id': sid, 'text': 'Привіт'})
    assert rv.get_json() == {'ok': True, 'queued': True}
    assert queued == [(sid,)]


def test_ai_reply_needs_sender_and_text(client, queued):
    assert client.post('/api/webhook/ig-ai-reply', json={'sender_id': _sid()}).status_code == 400
    assert queued == []


def test_muted_client_gets_no_ai(client, pwa, queued):
    sid = _sid()
    _exec(pwa, "INSERT INTO ai_mute (channel, user_id, active) VALUES ('ig', ?, 1)", (sid,))
    rv = client.post('/api/webhook/ig-ai-reply', json={'sender_id': sid, 'text': 'Привіт'})
    assert rv.get_json() == {'skipped': True, 'reason': 'muted'}
    assert queued == []


def test_ai_stays_quiet_for_72h_after_the_doctor_wrote(client, pwa, queued):
    sid = _sid()
    _exec(pwa, "INSERT INTO messages (conversation_id, sender_id, platform, content, is_from_admin,"
               " created_at) VALUES (?, 'admin_ig', 'instagram', 'Пишу вам', 1, datetime('now','-71 hours'))",
          ('ig_' + sid,))
    rv = client.post('/api/webhook/ig-ai-reply', json={'sender_id': sid, 'text': 'Добре'})
    assert rv.get_json() == {'skipped': True, 'reason': 'admin_active'}
    assert queued == []


def test_doctor_reply_older_than_72h_no_longer_blocks_ai(client, pwa, queued):
    sid = _sid()
    _exec(pwa, "INSERT INTO messages (conversation_id, sender_id, platform, content, is_from_admin,"
               " created_at) VALUES (?, 'admin_ig', 'instagram', 'Пишу вам', 1, datetime('now','-73 hours'))",
          ('ig_' + sid,))
    rv = client.post('/api/webhook/ig-ai-reply', json={'sender_id': sid, 'text': 'Добре'})
    assert rv.get_json() == {'ok': True, 'queued': True}


# ── _ig_process_reply: сама відповідь ─────────────────────────────────────────

@pytest.fixture
def ai(pwa, monkeypatch, app):
    """Anthropic і Graph API send — без мережі. on_ai дає «втрутитись» під час виклику AI."""
    state = {'anthropic': 0, 'sent': [], 'ai_status': 200, 'ig_status': 200, 'on_ai': None,
             'reply': 'Вітаю! Ботулінотерапія 1 зона — від 2200 грн. <ESCALATE>'}

    def _post(url, headers=None, json=None, timeout=None, **kw):
        if 'api.anthropic.com' in url:
            state['anthropic'] += 1
            if state['on_ai']:
                state['on_ai']()
            return _Resp(state['ai_status'], {'content': [{'text': state['reply']}]})
        if 'graph.instagram.com' in url:
            state['sent'].append((json['recipient']['id'], json['message']['text']))
            return _Resp(state['ig_status'], {'message_id': 'm1'})
        raise AssertionError('unexpected POST ' + url)

    monkeypatch.setattr(requests, 'post', _post)
    # system_prompt.txt відкривається без encoding — на сервері UTF-8 за замовчуванням,
    # на Windows ні. Підставляємо серверну поведінку лише для pwa_api.
    import io
    import functools
    monkeypatch.setattr(pwa, 'open', functools.partial(io.open, encoding='utf-8'), raising=False)

    def run(sid):
        with app.app_context():
            return pwa._ig_process_reply(sid)
    state['run'] = run
    return state


def _client_wrote(pwa, sid, ago='-5 minutes', text='Скільки коштує ботокс?'):
    _exec(pwa, "INSERT INTO messages (conversation_id, sender_id, platform, content, is_from_admin,"
               " created_at) VALUES (?, ?, 'instagram', ?, 0, datetime('now', ?))",
          ('ig_' + sid, sid, text, ago))


def _ai_rows(pwa, sid):
    return _q(pwa, "SELECT content FROM messages WHERE conversation_id=? AND sender_id='ai_bot'",
              ('ig_' + sid,))


def test_ai_reply_is_sent_without_tags_and_recorded(pwa, ai):
    sid = _sid()
    _client_wrote(pwa, sid)
    ai['run'](sid)
    assert ai['sent'] == [(sid, 'Вітаю! Ботулінотерапія 1 зона — від 2200 грн.')]
    assert _ai_rows(pwa, sid) == [('Вітаю! Ботулінотерапія 1 зона — від 2200 грн.',)]


def test_no_reply_while_the_client_is_still_typing(pwa, ai):
    sid = _sid()
    _client_wrote(pwa, sid, ago='-10 seconds')
    ai['run'](sid)
    assert ai['anthropic'] == 0
    assert ai['sent'] == []


def test_doctor_reply_during_ai_call_cancels_the_send(pwa, ai):
    """Регресія 29.04.2026: AI відповів через 3 с після echo лікаря."""
    sid = _sid()
    _client_wrote(pwa, sid)
    ai['on_ai'] = lambda: _exec(
        pwa, "INSERT INTO messages (conversation_id, sender_id, platform, content, is_from_admin,"
             " created_at) VALUES (?, 'admin_ig', 'instagram', 'Я відповім', 1, datetime('now'))",
        ('ig_' + sid,))
    ai['run'](sid)
    assert ai['anthropic'] == 1
    assert ai['sent'] == [], 'відповідь AI пішла поверх лікаря'
    assert _ai_rows(pwa, sid) == []


def test_mute_during_ai_call_cancels_the_send(pwa, ai):
    sid = _sid()
    _client_wrote(pwa, sid)
    ai['on_ai'] = lambda: _exec(pwa, "INSERT INTO ai_mute (channel, user_id, active) VALUES ('ig', ?, 1)",
                                (sid,))
    ai['run'](sid)
    assert ai['sent'] == []


def test_failed_send_leaves_no_phantom_reply(pwa, ai):
    """Протухлий токен (401): відповіді в базі бути не має — інакше в адмінці «відповіли»."""
    sid = _sid()
    _client_wrote(pwa, sid)
    ai['ig_status'] = 401
    ai['run'](sid)
    assert len(ai['sent']) == 1
    assert _ai_rows(pwa, sid) == []


def test_anthropic_failure_sends_nothing(pwa, ai):
    sid = _sid()
    _client_wrote(pwa, sid)
    ai['ai_status'] = 529
    ai['run'](sid)
    assert ai['sent'] == []
    assert _ai_rows(pwa, sid) == []


# ── WLaunch ───────────────────────────────────────────────────────────────────

WL_SECRET = 'wl-test-secret'
WL_URL = '/api/webhook/wlaunch?token=' + WL_SECRET


@pytest.fixture
def cancellations(monkeypatch):
    sent = []
    monkeypatch.setattr(sys.modules['notifier'], 'send_cancellation', sent.append)
    monkeypatch.setattr(sys.modules['config'], 'WLAUNCH_WEBHOOK_SECRET', WL_SECRET, raising=False)
    return sent


def test_wlaunch_cancellation_notifies_with_parsed_fields(client, cancellations):
    rv = client.post(WL_URL, json={
        'status': 'CANCELLED', 'client_phone': '0671234567', 'client_name': 'Ірина',
        'services': 'Біорепарація шкіри', 'specialist': 'Victoria Gomon',
        'start_time': '2026-11-10T14:30:00', 'appt_id': 'wl-1'})
    assert rv.status_code == 200
    (appt,) = cancellations
    assert (appt['client_phone'], appt['specialist'], appt['date'], appt['time']) == \
        ('380671234567', 'victoria', '2026-11-10', '14:30')


@pytest.mark.parametrize('status', ['CONFIRMED', 'CONFIRMED_BY_CLIENT', 'DONE', ''])
def test_wlaunch_other_statuses_send_nothing(client, cancellations, status):
    """Підтвердження шле сам WLaunch — дублювати не можна."""
    rv = client.post(WL_URL, json={'status': status, 'client_phone': '0671234567'})
    assert rv.status_code == 200
    assert cancellations == []


def test_wlaunch_without_phone_is_rejected(client, cancellations):
    assert client.post(WL_URL, json={'status': 'CANCELLED'}).status_code == 400
    assert cancellations == []


_CANCEL = {'status': 'CANCELLED', 'client_phone': '0671234567', 'start_time': '2026-11-10T14:30:00'}


def test_wlaunch_webhook_rejects_requests_without_the_token(client, cancellations):
    """Маршрут відкритий з інтернету: без токена будь-хто розсилав би клієнтам
    повідомлення про скасування (виявлено й закрито 04.11.2026)."""
    rv = client.post('/api/webhook/wlaunch', environ_base=OUTSIDE, json=_CANCEL)
    assert rv.status_code == 403
    assert cancellations == []


@pytest.mark.parametrize('token', ['wrong', WL_SECRET + 'x', ''])
def test_wlaunch_webhook_rejects_a_wrong_token(client, cancellations, token):
    rv = client.post('/api/webhook/wlaunch?token=' + token, json=_CANCEL)
    assert rv.status_code == 403
    assert cancellations == []


def test_wlaunch_webhook_accepts_the_token_as_a_header(client, cancellations):
    rv = client.post('/api/webhook/wlaunch', headers={'X-Webhook-Token': WL_SECRET}, json=_CANCEL)
    assert rv.status_code == 200
    assert len(cancellations) == 1


def test_wlaunch_webhook_is_off_until_a_secret_is_configured(client, cancellations, monkeypatch):
    """Як на сервері зараз: секрету в config.py немає — вебхук не приймає нічого."""
    monkeypatch.setattr(sys.modules['config'], 'WLAUNCH_WEBHOOK_SECRET', '', raising=False)
    for url in ('/api/webhook/wlaunch', '/api/webhook/wlaunch?token='):
        assert client.post(url, json=_CANCEL).status_code == 403
    assert cancellations == []
