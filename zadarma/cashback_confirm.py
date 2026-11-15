# -*- coding: utf-8 -*-
"""
Підтвердження кешбеку лікаркою: яке завдання photo_tasks закрити.

Підтвердження приходить трьома шляхами (кнопка препарата в боті, ручна ціна в боті,
відповідь у IG Direct) і несе телефон, дату та назву процедури. Раніше всі три
оновлювали photo_tasks за телефоном і датою, тож за два живі візити в один день
ціна одного позначала підтвердженими обидва завдання: другий візит отримував кешбек
за чужу процедуру.

Окремий модуль без важких імпортів: його викликають bot.py і pwa_api.py, а
photo_reminder підтягує з нього `same_procedure`.
"""

PENDING_STATUSES = ('needs_drug', 'needs_price', 'pending')

# cashback_pending.accrued: 0 — чекає, 1 — нараховано (або сума < 1 грн),
# -1 — закрито без виплати, бо візит скасовано
ACCRUED_CANCELLED = -1


def save_pending(conn, phone, client_name, procedure, drug, price, appt_date,
                 confirmed_by, confirmed_at):
    """Записує підтверджену лікаркою ціну в cashback_pending.

    Раніше всі три шляхи робили INSERT OR REPLACE з accrued=0: повторне
    підтвердження вже нарахованого візиту скидало accrued, і кешбек ішов удруге
    (з іншим препаратом — окремим рядком cashback), а закритий скасований візит
    повертався в чергу. Тепер ціну можна змінити лише доки рядок чекає.
    Повертає True, якщо записано, False — рядок уже закритий.
    """
    cur = conn.execute(
        "INSERT INTO cashback_pending (phone, client_name, procedure_generic, drug_specific,"
        " price, appt_date, confirmed_by, confirmed_at, accrued) VALUES (?,?,?,?,?,?,?,?,0) "
        "ON CONFLICT(phone, procedure_generic, appt_date) DO UPDATE SET"
        " drug_specific=excluded.drug_specific, price=excluded.price,"
        " confirmed_by=excluded.confirmed_by, confirmed_at=excluded.confirmed_at"
        " WHERE cashback_pending.accrued=0",
        (phone, client_name or '', procedure, drug, price, appt_date, confirmed_by, confirmed_at))
    return cur.rowcount > 0


def same_procedure(service, procedure):
    """Назва з завдання/підтвердження vs назва послуги в записі.

    Комбіновані візити приходять у різному порядку («A, B» / «B, A»), а бот бере
    процедуру з тексту в дужках: «розчинення філера» замість «гіалуронідаза
    (розчинення філера)». Перевірено на проді: точний збіг ловив 727 з 729 завдань
    і 202 з 221 підтверджень.
    """
    s = (service or '').strip().casefold()
    p = (procedure or '').strip().casefold()
    if not s or not p:
        return False
    if s == p or s.endswith('(' + p + ')'):
        return True
    return sorted(x.strip() for x in s.split(',')) == sorted(x.strip() for x in p.split(','))


def confirm_photo_tasks(conn, phone, appt_date, procedure, drug, price, confirmed_at):
    """Позначає підтвердженим завдання саме цієї процедури; повертає, скільки оновлено.

    Не комітить — це робить викликач разом із cashback_pending. Якщо процедуру
    впізнати не вдалося (бот узяв шматок із дужок, назви немає), підтверджується
    лише єдине непідтверджене завдання дня. Коли таких кілька, нічого не чіпаємо:
    інакше ціна однієї процедури пішла б за всі візити дня.
    """
    tasks = conn.execute(
        "SELECT id, procedure_name, cashback_status FROM photo_tasks "
        "WHERE client_phone=? AND appt_date=?", (phone, appt_date)).fetchall()
    named = [t for t in tasks if same_procedure(t[1], procedure)]
    # Процедуру впізнано серед завдань дня — чіпаємо лише її, і лише якщо вона ще не
    # підтверджена (повторний клік не має перекинути ціну на сусідній візит).
    # Не впізнано — лише якщо непідтверджене завдання дня одне.
    ids = [tid for tid, _, st in (named or tasks) if st in PENDING_STATUSES]
    if not named and len(ids) > 1:
        ids = []
    for tid in ids:
        conn.execute(
            "UPDATE photo_tasks SET cashback_status='confirmed', cashback_drug=?, "
            "cashback_price=?, cashback_confirmed_at=? WHERE id=?",
            (drug, price, confirmed_at, tid))
    return len(ids)
