#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Photo cache builder — fetches all client photos from Google Drive and caches in SQLite.
Runs via cron twice daily (morning + evening).

Usage: python3 photo_cache.py
"""

import sys
import json
import sqlite3
import logging
import logging.handlers
import time

sys.path.insert(0, '/home/gomoncli/zadarma')

CACHE_DB = '/home/gomoncli/zadarma/photo_cache.db'
LOG_FILE = '/home/gomoncli/zadarma/photo_cache.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=2*1024*1024, backupCount=2),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


def init_cache_db():
    conn = sqlite3.connect(CACHE_DB)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('''CREATE TABLE IF NOT EXISTS photo_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT NOT NULL,
        visit TEXT NOT NULL,
        subfolder TEXT,
        file_id TEXT NOT NULL,
        file_name TEXT,
        thumbnail TEXT,
        created_time TEXT,
        cached_at TEXT DEFAULT (datetime('now'))
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_pc_client ON photo_cache(client_name)')
    conn.commit()
    conn.close()


def rebuild_cache():
    from gdrive import list_all_client_folders, list_all_files_under

    init_cache_db()
    logger.info('Starting photo cache rebuild...')

    client_folders = list_all_client_folders()
    logger.info('Found {} client folders'.format(len(client_folders)))

    conn = sqlite3.connect(CACHE_DB, timeout=10)
    # Clear old cache
    conn.execute('DELETE FROM photo_cache')
    conn.commit()

    total_files = 0
    for cf in client_folders:
        client_name = cf['name']
        files = list_all_files_under(cf['id'])
        if not files:
            continue

        for f in files:
            if f.get('mimeType', '').startswith('application/vnd.google-apps'):
                continue  # skip folders
            fid = f.get('id', '')
            conn.execute(
                'INSERT INTO photo_cache (client_name, visit, subfolder, file_id, file_name, thumbnail, created_time) '
                'VALUES (?,?,?,?,?,?,?)',
                (client_name, f.get('visit', ''), f.get('subfolder', ''),
                 fid, f.get('name', ''),
                 'https://lh3.googleusercontent.com/d/{}'.format(fid),
                 f.get('createdTime', '')))
            total_files += 1

        logger.info('  {} — {} photos'.format(client_name, len(files)))
        time.sleep(0.5)  # rate limit between clients

    conn.commit()
    conn.close()
    logger.info('Cache rebuilt: {} files for {} clients'.format(total_files, len(client_folders)))


if __name__ == '__main__':
    rebuild_cache()
