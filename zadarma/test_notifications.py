#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# test_notifications.py — Ручне тестування всіх типів сповіщень
# Запускати вручну: python3 test_notifications.py
# Calls notify_client / notify_specialist DIRECTLY — bypasses notification_log dedup.

import sys
sys.path.insert(0, '/home/gomoncli/zadarma')

from notifier import (
    notify_client, notify_specialist,
    fmt_reminder_24h, fmt_post_visit, fmt_cancel_client,
    fmt_cancel_specialist, fmt_specialist_new_appt,
)

IVAN     = '380933297777'
VICTORIA = '380996093860'

# Тестовий запис: Іван записаний до Вікторії
APPT_IVAN = {
    'id':             9999,
    'client_phone':   IVAN,
    'client_name':    'Іван Павловський',
    'procedure_name': 'WOW-чистка',
    'specialist':     'victoria',
    'date':           '2026-04-05',
    'time':           '11:00',
    'duration_min':   60,
    'source':         'manual',
}

# Тестовий запис: Вікторія записана до Анастасії (щоб перевірити клієнтські сповіщення для неї)
APPT_VICTORIA = {
    'id':             9998,
    'client_phone':   VICTORIA,
    'client_name':    'Вікторія Гомон',
    'procedure_name': 'Пресотерапія',
    'specialist':     'anastasia',
    'date':           '2026-04-05',
    'time':           '14:00',
    'duration_min':   90,
    'source':         'manual',
}

SEP = '=' * 55

def run():
    print(SEP)
    print('TEST NOTIFICATIONS — {}'.format(__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    print(SEP)

    # ── 1. reminder_24h → Іван (клієнт) ─────────────────────────
    print('\n[1] REMINDER 24h → Іван (клієнт)')
    tg, sms, pt, pb = fmt_reminder_24h(APPT_IVAN)
    print('  TG text:', tg[:80])
    r = notify_client(IVAN, tg, sms, pt, pb, push_tag='test-reminder')
    print('  result:', r)

    # ── 2. post_visit → Іван (клієнт) ───────────────────────────
    print('\n[2] POST-VISIT feedback → Іван (клієнт)')
    tg, sms, pt, pb = fmt_post_visit(APPT_IVAN)
    print('  TG text:', tg[:80])
    r = notify_client(IVAN, tg, sms, pt, pb, push_tag='test-feedback')
    print('  result:', r)

    # ── 3. cancel_client → Іван (клієнт) ────────────────────────
    print('\n[3] CANCEL CLIENT → Іван (клієнт)')
    tg, sms, pt, pb = fmt_cancel_client(APPT_IVAN)
    print('  TG text:', tg[:80])
    r = notify_client(IVAN, tg, sms, pt, pb, push_tag='test-cancel')
    print('  result:', r)

    # ── 4. reminder_24h → Вікторія (як клієнт) ──────────────────
    print('\n[4] REMINDER 24h → Вікторія (як клієнт)')
    tg, sms, pt, pb = fmt_reminder_24h(APPT_VICTORIA)
    print('  TG text:', tg[:80])
    r = notify_client(VICTORIA, tg, sms, pt, pb, push_tag='test-reminder')
    print('  result:', r)

    # ── 5. post_visit → Вікторія (як клієнт) ────────────────────
    print('\n[5] POST-VISIT feedback → Вікторія (як клієнт)')
    tg, sms, pt, pb = fmt_post_visit(APPT_VICTORIA)
    print('  TG text:', tg[:80])
    r = notify_client(VICTORIA, tg, sms, pt, pb, push_tag='test-feedback')
    print('  result:', r)

    # ── 6. cancel_client → Вікторія (як клієнт) ─────────────────
    print('\n[6] CANCEL CLIENT → Вікторія (як клієнт)')
    tg, sms, pt, pb = fmt_cancel_client(APPT_VICTORIA)
    print('  TG text:', tg[:80])
    r = notify_client(VICTORIA, tg, sms, pt, pb, push_tag='test-cancel')
    print('  result:', r)

    # ── 7. spec_new_appt → Вікторія (як спеціаліст) ─────────────
    print('\n[7] SPEC NEW APPT → Вікторія (як спеціаліст)')
    text = fmt_specialist_new_appt(APPT_IVAN)
    print('  Text:', text[:100])
    r = notify_specialist('victoria', text)
    print('  result (TG ok):', r)

    # ── 8. cancel_specialist → Вікторія (як спеціаліст) ─────────
    print('\n[8] CANCEL SPECIALIST → Вікторія (як спеціаліст)')
    text = fmt_cancel_specialist(APPT_IVAN)
    print('  Text:', text)
    r = notify_specialist('victoria', text)
    print('  result (TG ok):', r)

    print('\n' + SEP)
    print('DONE')
    print(SEP)

if __name__ == '__main__':
    run()
