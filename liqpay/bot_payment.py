#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
bot_payment.py — aiogram 2.x handler для /pay
Підключити до основного диспетчера: dp.include_router / register_handlers
Python 3.6 compatible, aiogram 2.x
"""
from __future__ import print_function
import uuid
import sqlite3
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    DB_PATH, LIQPAY_PUBLIC_KEY, LIQPAY_PRIVATE_KEY,
    SITE_URL, LIQPAY_SERVER_URL
)
from liqpay import LiqPay

from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)
liqpay = LiqPay(LIQPAY_PUBLIC_KEY, LIQPAY_PRIVATE_KEY)

# ── Список адмінів (Telegram user_id) ────────────────────────
ADMIN_IDS = {123456789}  # додай потрібні ID


# ── FSM States ────────────────────────────────────────────────
class PayForm(StatesGroup):
    amount = State()
    description = State()


# ── DB helpers ────────────────────────────────────────────────
def save_order(order_id, amount, description):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute('''
            INSERT INTO orders (order_id, amount, description, status, is_permanent)
            VALUES (?, ?, ?, 'pending', 0)
        ''', (order_id, amount, description))
        conn.commit()
    finally:
        conn.close()


def make_order_id():
    return 'clinic_{}'.format(str(uuid.uuid4())[:8])


def make_pay_url(order_id, amount, description):
    """
    Генерує посилання на нашу сторінку форми клієнта
    (не напряму на LiqPay — клієнт спочатку вводить дані)
    """
    return '{}/pay.php?oid={}'.format(SITE_URL, order_id)


# ── Handlers ──────────────────────────────────────────────────
async def cmd_pay(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await PayForm.amount.set()
    await message.answer(
        '💳 <b>Нова оплата</b>\n\n'
        'Введіть суму (грн):',
        parse_mode='HTML',
    )


async def pay_got_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(',', '.'))
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer(
            '❌ Введіть коректну суму, наприклад: <code>850</code>',
            parse_mode='HTML',
        )
        return

    await state.update_data(amount=amount)
    await PayForm.description.set()
    await message.answer(
        '✅ Сума: <b>{:.0f} грн</b>\n\n'
        'Тепер введіть опис послуги\n'
        '<i>наприклад: Мезотерапія обличчя</i>'.format(amount),
        parse_mode='HTML',
    )


async def pay_got_description(message: types.Message, state: FSMContext):
    desc = message.text.strip()
    if len(desc) < 3:
        await message.answer('❌ Опис занадто короткий, спробуйте ще раз:')
        return

    data = await state.get_data()
    amount   = data['amount']
    order_id = make_order_id()

    # Зберігаємо в БД
    save_order(order_id, amount, desc)

    # URL на сторінку форми клієнта
    pay_url = make_pay_url(order_id, amount, desc)

    await state.finish()

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton('🔗 Посилання на оплату', url=pay_url))

    await message.answer(
        '✅ <b>Посилання створено</b>\n\n'
        '📋 <b>{}</b>\n'
        '💰 <b>{:.0f} грн</b>\n'
        '🆔 <code>{}</code>\n\n'
        'Передайте клієнту кнопку або скопіюйте посилання:'.format(
            desc, amount, order_id),
        reply_markup=kb,
        parse_mode='HTML',
    )

    # Також "голе" посилання для копіювання
    await message.answer(
        '<code>{}</code>'.format(pay_url),
        parse_mode='HTML',
    )


async def cmd_cancel(message: types.Message, state: FSMContext):
    current = await state.get_state()
    if current:
        await state.finish()
        await message.answer('↩️ Скасовано.')


async def cmd_status(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            'Використання: <code>/status clinic_ab12cd34</code>',
            parse_mode='HTML',
        )
        return

    order_id = args[1]

    # Читаємо з локальної БД
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,))
    order = c.fetchone()
    c.execute('SELECT * FROM clients WHERE order_id = ?', (order_id,))
    client = c.fetchone()
    c.execute('''SELECT * FROM transactions WHERE order_id = ?
                 ORDER BY created_at DESC LIMIT 1''', (order_id,))
    tx = c.fetchone()
    conn.close()

    if not order:
        await message.answer('❌ Замовлення не знайдено: <code>{}</code>'.format(order_id), parse_mode='HTML')
        return

    status_map = {
        'pending':  '⏳ Очікує оплати',
        'paid':     '✅ Оплачено',
        'failed':   '❌ Помилка',
        'refunded': '↩️ Повернено',
    }
    status = status_map.get(order['status'], order['status'])

    lines = [
        '📊 <b>Замовлення</b>',
        '',
        '📋 {}'.format(order['description']),
        '💰 {:.0f} грн'.format(order['amount']),
        'Статус: {}'.format(status),
        '🆔 <code>{}</code>'.format(order_id),
    ]

    if tx:
        lines.append('🕐 {}'.format(tx['paid_at'] or '—'))

    if client:
        lines.append('')
        lines.append('<b>Клієнт:</b>')
        if client['name']:
            lines.append('👤 {}'.format(client['name']))
        lines.append('📱 {}'.format(client['phone']))
        if client['email']:
            lines.append('📧 {}'.format(client['email']))
        if client['instagram']:
            lines.append('📸 {}'.format(client['instagram']))

    await message.answer('\n'.join(lines), parse_mode='HTML')


async def cmd_refund(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            'Використання:\n'
            '<code>/refund clinic_ab12cd34</code> — повне\n'
            '<code>/refund clinic_ab12cd34 500</code> — часткове',
            parse_mode='HTML',
        )
        return

    order_id = args[1]
    amount = float(args[2]) if len(args) >= 3 else None

    await message.answer('↩️ Виконую повернення...')

    result = liqpay.refund(order_id, amount)
    status = result.get('status', 'unknown')

    if status in ('reversed', 'success'):
        await message.answer(
            '✅ <b>Повернення виконано</b>\n🆔 <code>{}</code>'.format(order_id),
            parse_mode='HTML',
        )
    else:
        err = result.get('err_description') or result.get('err_code') or 'невідома помилка'
        await message.answer(
            '❌ <b>Помилка повернення</b>\nПричина: {}'.format(err),
            parse_mode='HTML',
        )


# ── Реєстрація handlers ───────────────────────────────────────
def register_payment_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_cancel,          commands=['cancel'], state='*')
    dp.register_message_handler(cmd_pay,             commands=['pay'],    state=None)
    dp.register_message_handler(pay_got_amount,      state=PayForm.amount)
    dp.register_message_handler(pay_got_description, state=PayForm.description)
    dp.register_message_handler(cmd_status,          commands=['status'])
    dp.register_message_handler(cmd_refund,          commands=['refund'])
