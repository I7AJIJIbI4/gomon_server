#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Локальний кеш каталогу послуг WLaunch + детектор розходжень.

WLaunch — джерело правди для розкладу лікаря, тож меню онлайн-запису це його
активні послуги філії, а не позиції прайсу. Прайс лишається довідником цін по
препаратах: клієнт записується на узагальнену послугу, препарат лікар проставляє
після процедури кнопками в TG.

Кеш потрібен з двох причин. Перша — швидкість: get_branch_id / get_wlaunch_resources
/ get_wlaunch_services ходять у мережу щоразу, і один запис коштує 6-7 round-trip-ів.
Друга — детектор: коли послугу перейменували, вимкнули або додали лише з одного
боку, ми маємо дізнатись того ж дня. Без нього _cat_map тихо згнив на 55% (18 із 33
цілей указували на послуги, яких уже не існує), і помітили це лише через відмови
при записі.

Usage:
  python3 wl_catalog.py --sync       # оновити кеш, повідомити про розходження
  python3 wl_catalog.py --dry-run    # показати, що змінилось би
  python3 wl_catalog.py --show       # вивести поточний кеш
"""

import sys
import json
import sqlite3
import logging
import argparse

sys.path.insert(0, '/home/gomoncli/zadarma')

DB_PATH = '/home/gomoncli/zadarma/users.db'
PRICES_PATH = '/home/gomoncli/private_data/prices.json'

logger = logging.getLogger('wl_catalog')

#: Послуги, для яких клієнт обирає спеціаліста сам. Усі інші предефайнені —
#: WLaunch не зберігає правил «хто кому дозволений» (company_service_resource_restrictions
#: порожній у всіх послуг), тож це знання наше.
SPECIALIST_CHOICE_ALLOWED = {'Відбілювання зубів'}

#: Ручні перевизначення там, де прайс не дає відповіді.
#: «Консультація» йде через віртуальну категорію `_консультація`, яка спеціалістів
#: не несе, тож виводиться порожнім набором.
SPECIALIST_OVERRIDE = {
    'Консультація': ['victoria'],
    'Офлайн-консультація': ['victoria'],
}

#: Активні у WLaunch, але не пропонуються клієнту для самостійного запису.
#: Онлайн-консультацій поки не проводимо; «Офлайн-консультація» дублює
#: «Консультацію», у меню лишається одна.
HIDDEN_FROM_BOOKING = {'Онлайн-консультація', 'Офлайн-консультація'}


def init_catalog_db(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH, timeout=5)
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS wl_services (
                wl_id        TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                duration_min INTEGER NOT NULL,
                specialists  TEXT NOT NULL DEFAULT '',
                category     TEXT NOT NULL DEFAULT '',
                category_ord INTEGER NOT NULL DEFAULT 999,
                classify     TEXT,
                price_from   INTEGER,
                price_to     INTEGER,
                active       INTEGER NOT NULL DEFAULT 1,
                first_seen   TEXT NOT NULL DEFAULT (datetime('now')),
                synced_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')
        # Таблиця могла зʼявитись до того, як додали теки: CREATE TABLE IF NOT
        # EXISTS нові колонки не доливає, тож доливаємо вручну.
        have = {r[1] for r in conn.execute('PRAGMA table_info(wl_services)')}
        for col, decl in (('category', "TEXT NOT NULL DEFAULT ''"),
                          ('category_ord', 'INTEGER NOT NULL DEFAULT 999')):
            if col not in have:
                conn.execute('ALTER TABLE wl_services ADD COLUMN {} {}'.format(col, decl))
        conn.commit()
    finally:
        conn.close()


# ── Хто виконує послугу ───────────────────────────────────────────────────────

def _price_index(prices):
    """prices.json -> (за позицією, за категорією) з наборами спеціалістів."""
    by_item, by_cat = {}, {}
    for group in prices:
        cat = group.get('cat', '')
        for item in group.get('items', []):
            specs = set(item.get('specialists') or [])
            by_item[(item.get('name') or '').lower()] = specs
            by_cat.setdefault(cat, set()).update(specs)
    return by_item, by_cat


def derive_specialists(service_name, prices, proc_to_categories):
    """Хто виконує узагальнену послугу, за даними прайсу.

    Три джерела, у порядку надійності: однойменна позиція прайсу, категорії
    препаратів цієї послуги, однойменна категорія. Порожній набір означає
    «не знаємо» — такі послуги не потрапляють у меню запису, і про них
    сигналить sync.
    """
    if service_name in SPECIALIST_OVERRIDE:
        return set(SPECIALIST_OVERRIDE[service_name])

    by_item, by_cat = _price_index(prices)

    exact = by_item.get(service_name.lower())
    if exact:
        return set(exact)

    specs = set()
    for cat in proc_to_categories.get(service_name, ()):
        if not cat.startswith('_'):          # віртуальні категорії спеціалістів не несуть
            specs |= by_cat.get(cat, set())
    if specs:
        return specs

    return set(by_cat.get(service_name, set()))


def _price_range(service_name, classify, prices):
    """(від, до) у гривнях. Для needs_drug — діапазон по препаратах."""
    import re

    def _num(v):
        m = re.search(r'\d+', str(v).replace(' ', ''))
        return int(m.group()) if m else None

    if classify == 'needs_drug':
        try:
            from photo_reminder import _get_drugs_for_procedure
            amounts = [d['price'] for d in _get_drugs_for_procedure(service_name)
                       if d.get('price')]
        except Exception:
            amounts = []
        if amounts:
            return min(amounts), max(amounts)

    for group in prices:
        for item in group.get('items', []):
            if (item.get('name') or '').lower() == service_name.lower():
                p = _num(item.get('price'))
                return (p, p) if p else (None, None)
    return None, None


# ── Синхронізація ─────────────────────────────────────────────────────────────

def _fetch_live():
    """Активні послуги філії з WLaunch -> {wl_id: {...}}.

    Тягнемо сирий каталог, а не `get_wlaunch_services`, бо та функція відкидає
    теки (`type: GROUP`), а нам потрібна саме приналежність послуги до теки —
    меню запису групується так само, як бачить лікар у WLaunch.
    """
    import requests
    from config import WLAUNCH_API_URL, COMPANY_ID
    from wlaunch_api import HEADERS, get_branch_id

    bid = get_branch_id()
    if not bid:
        raise RuntimeError('WLaunch: не вдалося визначити філію')

    url = '{}/company/{}/branch/{}/service'.format(WLAUNCH_API_URL, COMPANY_ID, bid)
    rows, page = [], 0
    while page < 50:
        resp = requests.get(url, headers=HEADERS,
                            params={'page': page, 'size': 100}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        rows.extend(data.get('content', []))
        page += 1
        if page >= data.get('page', {}).get('total_pages', 1):
            break

    groups = {s['id']: s for s in rows if s.get('type') == 'GROUP'}
    out = {}
    for s in rows:
        if not s.get('active') or s.get('type') == 'GROUP':
            continue
        g = groups.get(s.get('parent_id'))
        out[s['id']] = {
            'name': s.get('name') or '',
            'duration_min': int((s.get('duration') or 3600) // 60),
            'category': (g or {}).get('name') or '',
            'category_ord': int((g or {}).get('ordinal') or 0) if g else 999,
        }
    return out


def _load_cached(conn):
    try:
        rows = conn.execute(
            'SELECT wl_id, name, duration_min, active, category FROM wl_services').fetchall()
    except sqlite3.OperationalError:
        return {}                     # таблиці ще немає — перший прогін
    return {r[0]: {'name': r[1], 'duration_min': r[2], 'active': r[3],
                   'category': r[4]} for r in rows}


def diff_catalog(cached, live):
    """Розходження між кешем і живим каталогом. Повертає список рядків."""
    changes = []
    for wl_id, new in sorted(live.items(), key=lambda kv: kv[1]['name']):
        old = cached.get(wl_id)
        if old is None:
            changes.append('нова послуга: «{}» ({} хв)'.format(
                new['name'], new['duration_min']))
            continue
        if not old.get('active'):
            changes.append('знову активна: «{}»'.format(new['name']))
        if old['name'] != new['name']:
            changes.append('перейменовано: «{}» -> «{}»'.format(old['name'], new['name']))
        if old['duration_min'] != new['duration_min']:
            changes.append('тривалість «{}»: {} -> {} хв'.format(
                new['name'], old['duration_min'], new['duration_min']))
        if old.get('category', '') != new.get('category', ''):
            changes.append('«{}» переїхала: «{}» -> «{}»'.format(
                new['name'], old.get('category') or 'без теки',
                new.get('category') or 'без теки'))
    for wl_id, old in sorted(cached.items(), key=lambda kv: kv[1]['name']):
        if old.get('active') and wl_id not in live:
            changes.append('зникла або вимкнена: «{}»'.format(old['name']))
    return changes


def sync_catalog(dry_run=False, db_path=None, notify=True):
    """Оновити кеш. Повертає (changes, services, without_specialist)."""
    db_path = db_path or DB_PATH
    if not dry_run:
        init_catalog_db(db_path)      # --dry-run не має створювати навіть таблицю

    live = _fetch_live()
    try:
        prices = json.load(open(PRICES_PATH, encoding='utf-8'))
    except Exception as e:
        logger.warning('prices.json недоступний: {}'.format(e))
        prices = []
    try:
        from photo_reminder import PROCEDURE_TO_CATEGORIES, cashback_classify
    except Exception:
        PROCEDURE_TO_CATEGORIES, cashback_classify = {}, lambda n: 'auto'

    conn = sqlite3.connect(db_path, timeout=5)
    try:
        cached = _load_cached(conn)
        first_run = not cached
        changes = diff_catalog(cached, live)

        services, without_specialist = [], []
        for wl_id, item in live.items():
            name = item['name']
            specs = sorted(derive_specialists(name, prices, PROCEDURE_TO_CATEGORIES))
            if not specs:
                without_specialist.append(name)
            classify = cashback_classify(name)
            p_from, p_to = _price_range(name, classify, prices)
            services.append({
                'wl_id': wl_id, 'name': name, 'duration_min': item['duration_min'],
                'specialists': ','.join(specs), 'classify': classify,
                'price_from': p_from, 'price_to': p_to,
                'category': item.get('category', ''),
                'category_ord': item.get('category_ord', 999),
            })

        if not dry_run:
            live_ids = set(live)
            for s in services:
                conn.execute(
                    "INSERT INTO wl_services"
                    " (wl_id, name, duration_min, specialists, classify, price_from, price_to,"
                    "  category, category_ord, active, synced_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,1,datetime('now'))"
                    " ON CONFLICT(wl_id) DO UPDATE SET"
                    "  name=excluded.name, duration_min=excluded.duration_min,"
                    "  specialists=excluded.specialists, classify=excluded.classify,"
                    "  price_from=excluded.price_from, price_to=excluded.price_to,"
                    "  category=excluded.category, category_ord=excluded.category_ord,"
                    "  active=1, synced_at=excluded.synced_at",
                    (s['wl_id'], s['name'], s['duration_min'], s['specialists'],
                     s['classify'], s['price_from'], s['price_to'],
                     s['category'], s['category_ord']))
            if live_ids:
                conn.execute(
                    'UPDATE wl_services SET active=0 WHERE wl_id NOT IN ({})'.format(
                        ','.join('?' * len(live_ids))), tuple(live_ids))
            conn.commit()
    finally:
        conn.close()

    # На порожньому кеші «нове» — це весь каталог; алерт про це безглуздий.
    if changes and notify and not dry_run and not first_run:
        _alert(changes, without_specialist)
    logger.info('catalog sync: {} послуг, {} розходжень, {} без спеціаліста'.format(
        len(services), len(changes), len(without_specialist)))
    return changes, services, without_specialist


def _alert(changes, without_specialist):
    lines = ['Каталог WLaunch змінився:', ''] + ['- ' + c for c in changes]
    if without_specialist:
        lines += ['', 'Без відомого спеціаліста (не потраплять у меню запису):']
        lines += ['- ' + n for n in without_specialist]
    try:
        from notifier import alert_admin
        alert_admin('\n'.join(lines))
    except Exception as e:
        logger.error('TG alert failed: {}'.format(e))


def get_bookable_services(db_path=None):
    """Меню запису: активні послуги з відомим спеціалістом."""
    # Міграція колонок живе в init_catalog_db, а його кличе лише sync_catalog:
    # між деплоєм і найближчим синком меню інакше падало б у 500.
    init_catalog_db(db_path)
    conn = sqlite3.connect(db_path or DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM wl_services WHERE active=1 AND specialists != ''"
            ' ORDER BY category_ord, category, name').fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        if r['name'] in HIDDEN_FROM_BOOKING:
            continue
        specs = r['specialists'].split(',')
        out.append({
            'wl_id': r['wl_id'], 'name': r['name'],
            'duration_min': r['duration_min'], 'specialists': specs,
            'specialist_choice': r['name'] in SPECIALIST_CHOICE_ALLOWED and len(specs) > 1,
            'classify': r['classify'],
            'price_from': r['price_from'], 'price_to': r['price_to'],
            'category': r['category'] or '',
        })
    return out


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    ap = argparse.ArgumentParser()
    ap.add_argument('--sync', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--show', action='store_true')
    args = ap.parse_args()

    if args.show:
        for s in get_bookable_services():
            price = ('від {} до {} грн'.format(s['price_from'], s['price_to'])
                     if s['price_from'] and s['price_to'] and s['price_from'] != s['price_to']
                     else ('{} грн'.format(s['price_from']) if s['price_from'] else '—'))
            print('{:<38} {:>3} хв  {:<20} {}{}'.format(
                s['name'][:38], s['duration_min'], price, ','.join(s['specialists']),
                '  (вибір спеціаліста)' if s['specialist_choice'] else ''))
    elif args.sync or args.dry_run:
        changes, services, no_spec = sync_catalog(dry_run=args.dry_run)
        print('послуг: {}'.format(len(services)))
        print('розходжень: {}'.format(len(changes)))
        for c in changes:
            print('  - ' + c)
        if no_spec:
            print('без спеціаліста: {}'.format(', '.join(no_spec)))
        if args.dry_run:
            print('DRY-RUN — у базу не записано')
    else:
        ap.print_help()
