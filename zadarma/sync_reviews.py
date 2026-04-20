#!/usr/bin/env python3
"""
Sync Google Reviews → local DB + match with clients.
Cron: 0 8 * * * (daily at 08:00 Kyiv)

Matched clients won't receive "залиште відгук" post-visit messages.
"""
import sys
import sqlite3
import logging
import logging.handlers
import requests

sys.path.insert(0, '/home/gomoncli/zadarma')
from config import GOOGLE_PLACES_KEY, GOOGLE_PLACE_ID
from tz_utils import kyiv_now

DB_PATH = '/home/gomoncli/zadarma/users.db'
LOG_FILE = '/home/gomoncli/zadarma/sync_reviews.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=2*1024*1024, backupCount=2),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger('sync_reviews')


def fetch_reviews():
    """Fetch reviews from Google Places API."""
    url = 'https://maps.googleapis.com/maps/api/place/details/json'
    params = {
        'place_id': GOOGLE_PLACE_ID,
        'fields': 'reviews',
        'key': GOOGLE_PLACES_KEY,
        'language': 'uk',
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get('status') != 'OK':
        logger.error('Google API error: {}'.format(data.get('status')))
        return []
    return data.get('result', {}).get('reviews', [])


def match_client(author_name, conn):
    """Try to match Google review author with a client by name."""
    if not author_name:
        return None
    # Split author name and search by first_name + last_name
    parts = author_name.strip().split()
    if not parts:
        return None
    first = parts[0]
    # Search by first name (case-insensitive)
    rows = conn.execute(
        "SELECT phone, first_name, last_name FROM clients WHERE "
        "LOWER(first_name) = LOWER(?) OR LOWER(last_name) = LOWER(?)",
        (first, first)).fetchall()
    if len(rows) == 1:
        return rows[0][0]
    # If multiple matches, try full name
    if len(parts) >= 2:
        last = parts[1]
        for phone, fn, ln in rows:
            if (fn or '').lower() == first.lower() and (ln or '').lower() == last.lower():
                return phone
            if (fn or '').lower() == last.lower() and (ln or '').lower() == first.lower():
                return phone
    return None


def sync():
    reviews = fetch_reviews()
    if not reviews:
        logger.info('No reviews fetched')
        return

    conn = sqlite3.connect(DB_PATH, timeout=10)
    now = kyiv_now().strftime('%Y-%m-%d %H:%M:%S')
    new = matched = 0

    for r in reviews:
        author = r.get('author_name', '')
        rating = r.get('rating', 0)
        text = r.get('text', '')
        time_val = r.get('time', 0)
        lang = r.get('language', '')

        # Check if already exists
        existing = conn.execute(
            "SELECT id, matched_phone FROM google_reviews WHERE author_name=? AND time=?",
            (author, time_val)).fetchone()
        if existing:
            continue

        # Match with client
        phone = match_client(author, conn)

        conn.execute(
            "INSERT OR IGNORE INTO google_reviews (author_name, rating, text, time, language, matched_phone, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (author, rating, text, time_val, lang, phone, now))
        new += 1
        if phone:
            matched += 1
            logger.info('  Matched: {} → {}'.format(author, phone))
        else:
            logger.info('  New (unmatched): {}'.format(author))

    conn.commit()
    conn.close()
    logger.info('Sync done: {} new, {} matched'.format(new, matched))


def has_google_review(phone):
    """Check if a client has already left a Google review. Used by notifier."""
    if not phone:
        return False
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        row = conn.execute(
            "SELECT 1 FROM google_reviews WHERE matched_phone=? LIMIT 1",
            (phone,)).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


if __name__ == '__main__':
    sync()
