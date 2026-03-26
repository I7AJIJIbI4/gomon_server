"""
init_db.py — ініціалізація SQLite бази даних
Запустити один раз: python init_db.py
Python 3.6 compatible
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'payments.db')


def init():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Таблиця замовлень (створюється ботом при /pay)
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id     TEXT PRIMARY KEY,
            amount       REAL NOT NULL,
            description  TEXT NOT NULL,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            status       TEXT NOT NULL DEFAULT 'pending',
            is_permanent INTEGER NOT NULL DEFAULT 0
        )
    ''')

    # Таблиця даних клієнта (заповнюється на сторінці форми)
    c.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            order_id     TEXT PRIMARY KEY,
            phone        TEXT NOT NULL,
            name         TEXT,
            email        TEXT,
            instagram    TEXT,
            filled_at    TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        )
    ''')

    # Таблиця транзакцій (заповнюється з LiqPay callback)
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id        TEXT NOT NULL,
            liqpay_id       TEXT,
            status          TEXT NOT NULL,
            amount          REAL,
            currency        TEXT,
            payment_method  TEXT,
            paid_at         TEXT,
            liqpay_raw      TEXT,
            notified        INTEGER NOT NULL DEFAULT 0,
            receipt_sent    INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        )
    ''')

    conn.commit()
    conn.close()
    print('DB initialized: {}'.format(DB_PATH))


if __name__ == '__main__':
    init()
