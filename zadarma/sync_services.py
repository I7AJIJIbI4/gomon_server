#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync services from prices.json to WLaunch.
Creates missing services and updates existing ones (name, duration).

Usage: python3 sync_services.py [--dry-run]
"""

import json
import sys
import re
import time
import logging
import requests

sys.path.insert(0, '/home/gomoncli/zadarma')
from wlaunch_api import get_branch_id, get_wlaunch_services, HEADERS
from config import WLAUNCH_API_URL, COMPANY_ID

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

PRICES_PATH = '/home/gomoncli/private_data/prices.json'
SERVICE_URL = '{}/company/{}/service'.format(WLAUNCH_API_URL, COMPANY_ID)


def _norm(s):
    """Normalize string for comparison — remove fancy quotes, extra spaces."""
    return re.sub(r'[\u00ab\u00bb\u201c\u201d\u201e\u201f\'\u0060\u2018\u2019]', '', s).replace('  ', ' ').strip().lower()


def _find_match(name, wl_services):
    """Find matching WLaunch service. Returns (wl_key, wl_data) or (None, None)."""
    nl = name.lower()
    nn = _norm(nl)

    # Exact
    if nl in wl_services:
        return nl, wl_services[nl]

    # Substring (normalized)
    for wl_name, wl_data in wl_services.items():
        wn = _norm(wl_name)
        if nn in wn or wn in nn:
            return wl_name, wl_data

    return None, None


def _parse_duration(item):
    """Parse duration from item. Returns seconds."""
    dur = item.get('duration', '')
    if dur:
        m = re.search(r'(\d+)', dur)
        if m:
            return int(m.group(1)) * 60
    return 1800  # default 30 min


def sync_services(dry_run=False):
    prices = json.load(open(PRICES_PATH, encoding='utf-8'))
    bid = get_branch_id()
    wl_services = get_wlaunch_services(bid)
    h = dict(HEADERS, **{'Content-Type': 'application/json;charset=UTF-8'})

    created = 0
    updated = 0
    skipped = 0
    errors = 0

    for cat in prices:
        cat_name = cat.get('cat', '')
        for item in cat.get('items', []):
            name = item.get('name', '')
            if not name:
                continue

            dur_sec = _parse_duration(item)
            wl_key, wl_data = _find_match(name, wl_services)

            if wl_data:
                skipped += 1
                continue

            # Missing — create with full name (include category for disambiguation)
            # E.g. "1 зона" → "Ботулінотерапія Neuronox: 1 зона"
            full_name = name
            generic_names = {'1 зона', '2 зони', '3 зони', 'full face',
                             'ліфтинг ніфертіті (платизма)', 'офлайн-консультація', 'онлайн-консультація'}
            if name.lower() in generic_names or name.lower().startswith('офлайн') or name.lower().startswith('онлайн'):
                full_name = '{}: {}'.format(cat_name, name)

            payload = {'company_service': {
                'name': full_name,
                'description': cat_name,
                'short_description': cat_name,
                'duration': dur_sec,
                'booking_type': 'GENERAL',
                'type': 'SERVICE',
                'public': True,
                'capacity': 1,
                'capacity_type': 'CAPACITY_1',
                'group_training_service': False,
            }}

            if dry_run:
                logger.info('  WOULD CREATE: {} [{}] ({}хв)'.format(full_name, cat_name, dur_sec // 60))
                created += 1
                continue

            r = requests.post(SERVICE_URL, headers=h, json=payload, timeout=10)
            if r.status_code in (200, 201):
                sid = r.json().get('id', '')[:12]
                logger.info('  CREATED: {} [{}] → {}'.format(name, cat_name, sid))
                created += 1
            else:
                logger.error('  CREATE ERR: {} → {} {}'.format(name, r.status_code, r.text[:150]))
                errors += 1
            time.sleep(0.3)

    logger.info('Done. Created: {}, Updated: {}, Skipped: {}, Errors: {}'.format(
        created, updated, skipped, errors))

    # Sync prices for ALL services
    logger.info('Syncing prices...')
    wl_all = get_wlaunch_services(bid)
    price_list_id = '3f31ae76-0b21-11ed-8355-65920565acdd'
    prices_updated = 0
    for cat in prices:
        for item in cat.get('items', []):
            name = item.get('name', '')
            price_str = item.get('price', '')
            if not name or not price_str:
                continue
            digits = re.sub(r'[^\d]', '', price_str)
            if not digits:
                continue
            our_amount = int(digits) * 100  # kopecks

            wl_key, wl_data = _find_match(name, wl_all)
            if not wl_data:
                continue

            wl_sid = wl_data['id']
            # Read current price
            try:
                r = requests.get('{}/{}/prices'.format(SERVICE_URL, wl_sid),
                    headers=HEADERS, params={'page': 0, 'size': 10}, timeout=10)
                price_entries = r.json().get('content', [])
            except Exception:
                price_entries = []

            if price_entries:
                current = price_entries[0]
                if current.get('amount') == our_amount:
                    continue  # already correct
                # Update existing price
                if dry_run:
                    logger.info('  WOULD UPDATE PRICE: {} → {} грн (was {} грн)'.format(
                        name, our_amount // 100, (current.get('amount') or 0) // 100))
                    prices_updated += 1
                else:
                    payload = {'prices': [{
                        'id': current['id'],
                        'service_id': wl_sid,
                        'amount': our_amount,
                        'service_price_list_id': price_list_id,
                    }]}
                    r2 = requests.post('{}/prices'.format(SERVICE_URL), headers=h,
                        json=payload, timeout=10)
                    if r2.status_code in (200, 201):
                        logger.info('  PRICE UPDATED: {} → {} грн'.format(name, our_amount // 100))
                        prices_updated += 1
                    else:
                        logger.error('  PRICE ERR: {} → {} {}'.format(name, r2.status_code, r2.text[:100]))
                        errors += 1
                    time.sleep(0.3)
            else:
                # No price entry exists — skip (WLaunch creates it when service is assigned to branch)
                pass

    logger.info('Prices updated: {}'.format(prices_updated))

    # Cleanup test services
    if not dry_run:
        wl_new = get_wlaunch_services(bid)
        for wn, wd in wl_new.items():
            if 'тест' in wn and 'видалити' in wn:
                requests.post('{}/{}'.format(SERVICE_URL, wd['id']), headers=h,
                    json={'company_service': {'active': False}}, timeout=10)
                logger.info('Cleaned up test service: {}'.format(wn))


if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    if dry:
        logger.info('=== DRY RUN ===')
    sync_services(dry_run=dry)
