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
    {'name': 'Срібло',  'key': 'silver',   'min_visits': 5,  'min_redeems': 1, 'rate': 0.033,
     # 'bonus_cosmetics_discount': 5, 'bonus_free_consult': False, 'bonus_priority_booking': False
    },
    {'name': 'Золото',  'key': 'gold',     'min_visits': 15, 'min_redeems': 3, 'rate': 0.036,
     # 'bonus_cosmetics_discount': 10, 'bonus_free_consult': True, 'bonus_priority_booking': False
    },
    {'name': 'Платина', 'key': 'platinum', 'min_visits': 30, 'min_redeems': 7, 'rate': 0.040,
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
    """Get cashback rate for client based on loyalty tier."""
    return get_client_tier(phone)['rate']
