#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
notify.py — надсилає Telegram повідомлення лікарю після оплати
Запускається з PHP: python notify.py <order_id>
Python 3.6 compatible
"""
from __future__ import print_function
import sys
import os
import sqlite3
import json
import hashlib
import base64

# Додаємо поточну директорію до шляху
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    DB_PATH, TELEGRAM_BOT_TOKEN, DOCTOR_CHAT_ID,
    LIQPAY_PUBLIC_KEY, LIQPAY_PRIVATE_KEY
)

try:
    from urllib.request import urlopen, Request
    from urllib.parse import urlencode, quote
except ImportError:
    from urllib2 import urlopen, Request
    from urllib import urlencode, quote


def send_telegram(chat_id, text, parse_mode='HTML'):
    """Надсилає повідомлення через Telegram Bot API."""
    url = 'https://api.telegram.org/bot{}/sendMessage'.format(TELEGRAM_BOT_TOKEN)
    data = urlencode({
        'chat_id':    chat_id,
        'text':       text,
        'parse_mode': parse_mode,
    }).encode('utf-8')
    req = Request(url, data)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        resp = urlopen(req, timeout=15)
        return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print('Telegram error: {}'.format(e), file=sys.stderr)
        return None


def get_order_data(order_id):
    """Отримує всі дані замовлення з SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,))
    order = c.fetchone()

    c.execute('SELECT * FROM clients WHERE order_id = ?', (order_id,))
    client = c.fetchone()

    c.execute('''
        SELECT * FROM transactions
        WHERE order_id = ?
        ORDER BY created_at DESC LIMIT 1
    ''', (order_id,))
    tx = c.fetchone()

    conn.close()
    return order, client, tx


def format_message(order, client, tx):
    """Формує текст повідомлення для лікаря."""
    status_map = {
        'success':    '✅ Оплачено',
        'sandbox':    '🧪 Тест оплачено',
        'reversed':   '↩️ Повернено',
        'failure':    '❌ Помилка оплати',
        'error':      '❌ Помилка',
    }

    status = tx['status'] if tx else '—'
    status_label = status_map.get(status, status)

    amount = order['amount'] if order else '—'
    desc   = order['description'] if order else '—'
    paid_at = tx['paid_at'] if tx else '—'

    lines = [
        '💳 <b>Нова оплата</b>',
        '',
        'Статус: {}'.format(status_label),
        '📋 <b>{}</b>'.format(desc),
        '💰 <b>{} грн</b>'.format(int(amount) if amount != '—' else amount),
        '🕐 {}'.format(paid_at),
        '🆔 <code>{}</code>'.format(order['order_id'] if order else '—'),
        '',
        '━━━━━━━━━━━━━━━━━━',
        '<b>Клієнт</b>',
    ]

    if client:
        if client['name']:
            lines.append('👤 {}'.format(client['name']))
        lines.append('📱 {}'.format(client['phone']))
        if client['email']:
            lines.append('📧 {}'.format(client['email']))
        if client['instagram']:
            lines.append('📸 {}'.format(client['instagram']))
    else:
        lines.append('❓ Дані клієнта не збережено')

    return '\n'.join(lines)


def mark_notified(order_id):
    """Позначає транзакцію як сповіщену."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            UPDATE transactions SET notified = 1
            WHERE order_id = ? AND notified = 0
        ''', (order_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print('mark_notified error: {}'.format(e), file=sys.stderr)


def main():
    if len(sys.argv) < 2:
        print('Usage: notify.py <order_id>', file=sys.stderr)
        sys.exit(1)

    order_id = sys.argv[1]

    order, client, tx = get_order_data(order_id)

    if not order:
        print('Order not found: {}'.format(order_id), file=sys.stderr)
        sys.exit(1)

    # Перевіряємо чи вже надсилали
    if tx and tx['notified']:
        print('Already notified for {}'.format(order_id))
        sys.exit(0)

    text = format_message(order, client, tx)
    result = send_telegram(DOCTOR_CHAT_ID, text)

    if result and result.get('ok'):
        mark_notified(order_id)
        print('Notified for {}'.format(order_id))
    else:
        print('Telegram send failed for {}'.format(order_id), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
