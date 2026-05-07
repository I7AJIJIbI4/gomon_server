"""
Loyalty Tier System for Dr. Gomon Cosmetology.

Tier is determined by: visits count OR cashback redeem count (whichever unlocks higher tier).
Each tier increases cashback rate by ~10% from previous.

Tiers:
  Start   — 0 visits, 0 redeems → 3.0%
  Silver  — 5 visits OR 1 redeem → 3.3%
  Gold    — 15 visits OR 3 redeems → 3.6%
  Platinum — 30 visits OR 7 redeems → 4.0%
"""

import sqlite3

DB_PATH = '/home/gomoncli/zadarma/users.db'

TIERS = [
    {'name': 'Старт',   'key': 'start',    'min_visits': 0,  'min_redeems': 0, 'rate': 0.030,
     # 'bonus_cosmetics_discount': 0, 'bonus_free_consult': False, 'bonus_priority_booking': False
    },
    {'name': 'Срібло',  'key': 'silver',   'min_visits': 10, 'min_redeems': 1, 'rate': 0.033,
     # 'bonus_cosmetics_discount': 5, 'bonus_free_consult': False, 'bonus_priority_booking': False
    },
    {'name': 'Золото',  'key': 'gold',     'min_visits': 30, 'min_redeems': 3, 'rate': 0.036,
     # 'bonus_cosmetics_discount': 10, 'bonus_free_consult': True, 'bonus_priority_booking': False
    },
    {'name': 'Платина', 'key': 'platinum', 'min_visits': 50, 'min_redeems': 7, 'rate': 0.040,
     # 'bonus_cosmetics_discount': 15, 'bonus_free_consult': True, 'bonus_priority_booking': True
    },
]


def _normalize_phone(phone):
    """Normalize phone to digits only."""
    return ''.join(c for c in (phone or '') if c.isdigit())


def get_client_tier(phone):
    """Determine client loyalty tier.
    Returns dict: name, key, rate, next_name, next_visits, next_redeems, visits, redeems
    """
    phone = _normalize_phone(phone)
    if not phone:
        return {'name': TIERS[0]['name'], 'key': TIERS[0]['key'], 'rate': TIERS[0]['rate'],
                'next_name': TIERS[1]['name'], 'next_visits': TIERS[1]['min_visits'],
                'next_redeems': TIERS[1]['min_redeems'], 'visits': 0, 'redeems': 0}

    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        row = conn.execute("SELECT visits_count FROM clients WHERE phone=?", (phone,)).fetchone()
        visits = row[0] if row and row[0] else 0

        redeem_row = conn.execute(
            "SELECT COUNT(*) FROM deposit_deductions WHERE phone=? AND reason LIKE 'cashback%'",
            (phone,)).fetchone()
        redeems = redeem_row[0] if redeem_row else 0
    finally:
        conn.close()

    # Find highest matching tier (visit OR redeem threshold)
    current = TIERS[0]
    for tier in TIERS:
        if visits >= tier['min_visits'] or redeems >= tier['min_redeems']:
            current = tier
        else:
            break

    idx = TIERS.index(current)
    if idx < len(TIERS) - 1:
        nxt = TIERS[idx + 1]
        return {
            'name': current['name'], 'key': current['key'], 'rate': current['rate'],
            'next_name': nxt['name'], 'next_visits': nxt['min_visits'], 'next_redeems': nxt['min_redeems'],
            'visits': visits, 'redeems': redeems,
        }
    return {
        'name': current['name'], 'key': current['key'], 'rate': current['rate'],
        'next_name': None, 'next_visits': None, 'next_redeems': None,
        'visits': visits, 'redeems': redeems,
    }


def get_cashback_rate(phone):
    """Get cashback rate for client based on loyalty tier + temporary modifiers."""
    base_rate = get_client_tier(phone)['rate']
    modifier = get_rate_modifier(phone)
    final_rate = base_rate + modifier['delta']
    return max(final_rate, 0)  # Never negative


# ── Temporary Rate Modifiers ─────────────────────────────────────────────────
# Stored in DB table `cashback_modifiers`:
#   id, scope (all|group|phone), target (NULL|group_name|phone),
#   delta (+0.02 = +2%), reason, start_date, end_date, created_by, active
#
# Priority: phone-specific > group > all (highest applicable wins)
# Multiple modifiers of same scope stack additively
#
# Examples:
#   Birthday:  scope=phone, target=380..., delta=+0.03, start=birthday-7d, end=birthday+7d
#   Holiday:   scope=all, target=NULL, delta=+0.02, start=dec-20, end=jan-05
#   Sale prep: scope=all, target=NULL, delta=-0.01, start=before-sale, end=sale-start
#   VIP:       scope=group, target=vip, delta=+0.02, start=..., end=...

def _ensure_modifiers_table():
    """Create cashback_modifiers table if not exists."""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        conn.execute('''CREATE TABLE IF NOT EXISTS cashback_modifiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL DEFAULT 'all',
            target TEXT,
            delta REAL NOT NULL DEFAULT 0.0,
            reason TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            created_by TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()
    finally:
        conn.close()


def get_rate_modifier(phone):
    """Get active cashback rate modifier for a phone number.
    Returns {'delta': float, 'reasons': [str]}
    Priority: phone > group > all. Same-scope modifiers stack."""
    phone = _normalize_phone(phone)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        from datetime import date
        today = date.today().isoformat()
        rows = conn.execute(
            "SELECT scope, target, delta, reason FROM cashback_modifiers "
            "WHERE active=1 AND start_date <= ? AND end_date >= ? "
            "ORDER BY scope DESC",  # phone > group > all (alphabetical DESC)
            (today, today)).fetchall()
    except Exception:
        return {'delta': 0.0, 'reasons': []}
    finally:
        conn.close()

    delta = 0.0
    reasons = []

    # Collect applicable modifiers
    for scope, target, d, reason in rows:
        if scope == 'phone' and target == phone:
            delta += d
            if reason:
                reasons.append(reason)
        elif scope == 'group':
            # Check if phone belongs to group (stored in client tags or separate table)
            # For now: group membership checked via simple lookup
            if _phone_in_group(phone, target):
                delta += d
                if reason:
                    reasons.append(reason)
        elif scope == 'all':
            delta += d
            if reason:
                reasons.append(reason)

    return {'delta': delta, 'reasons': reasons}


def _phone_in_group(phone, group_name):
    """Check if phone belongs to a group. Groups can be defined by tags or lists."""
    # TODO: implement group membership (e.g. 'vip', 'new_clients', 'birthday_week')
    # For now, 'birthday_week' is handled automatically via birthday check
    if group_name == 'birthday_week':
        return _is_birthday_week(phone)
    return False


def _is_birthday_week(phone):
    """Check if client's birthday is within ±7 days of today."""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        # birth_date stored in clients table (if available from WLaunch)
        row = conn.execute(
            "SELECT birth_date FROM clients WHERE phone=?", (phone,)).fetchone()
        if not row or not row[0]:
            return False
        from datetime import date, timedelta
        today = date.today()
        try:
            birth = date.fromisoformat(row[0])
        except (ValueError, TypeError):
            return False
        # This year's birthday
        this_year_bday = birth.replace(year=today.year)
        diff = abs((today - this_year_bday).days)
        return diff <= 7
    except Exception:
        return False
    finally:
        conn.close()


# ── Admin API helpers ────────────────────────────────────────────────────────

def add_modifier(scope, target, delta, reason, start_date, end_date, created_by='system'):
    """Add a temporary cashback modifier.
    scope: 'all' | 'group' | 'phone'
    target: None (all) | group_name | phone number
    delta: float (e.g. 0.02 for +2%, -0.01 for -1%)
    """
    _ensure_modifiers_table()
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        conn.execute(
            "INSERT INTO cashback_modifiers (scope, target, delta, reason, start_date, end_date, created_by) "
            "VALUES (?,?,?,?,?,?,?)",
            (scope, target, delta, reason, start_date, end_date, created_by))
        conn.commit()
    finally:
        conn.close()


def list_active_modifiers():
    """List all currently active modifiers."""
    _ensure_modifiers_table()
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        from datetime import date
        today = date.today().isoformat()
        rows = conn.execute(
            "SELECT id, scope, target, delta, reason, start_date, end_date, created_by "
            "FROM cashback_modifiers WHERE active=1 AND end_date >= ? ORDER BY start_date",
            (today,)).fetchall()
        return [{'id': r[0], 'scope': r[1], 'target': r[2], 'delta': r[3], 'reason': r[4],
                 'start_date': r[5], 'end_date': r[6], 'created_by': r[7]} for r in rows]
    finally:
        conn.close()


def deactivate_modifier(modifier_id):
    """Deactivate a modifier by ID."""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        conn.execute("UPDATE cashback_modifiers SET active=0 WHERE id=?", (modifier_id,))
        conn.commit()
    finally:
        conn.close()
