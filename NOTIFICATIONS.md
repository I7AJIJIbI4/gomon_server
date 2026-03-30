# GomonClinic — Аудит сповіщень та план міграції з WLaunch

## Поточний стан (станом на 2026-03-31)

### Наш код → клієнти

| # | Тригер | Канал | Отримувач | Файл | Зміст |
|---|--------|-------|-----------|------|-------|
| 1 | Логін в PWA | Viber → SMS fallback | Клієнт | `pwa_api.py` | OTP-код, дійсний 5 хвилин |
| 2 | Клієнт натиснув "Нагадати мені" в PWA | Web Push + SMS | Клієнт | `pwa_api.py /api/push/procedure-reminder` | "Ваша процедура чекає, підібрали [X]" + посилання на IG |
| 3 | Гостьовий юзер `/api/sms/procedure-reminder` | SMS | Клієнт | `pwa_api.py` | Те саме, але без push |
| 4 | Cron щогодини 9–22 | SMS (Viber+SMS) | Клієнт | `sms_reminder.py` | Нагадування про повторну процедуру (8 категорій × 3 шаблони) з посиланням на IG/TG |
| 5 | Cron щодня 10:00 | Web Push | Клієнт | `push_reminder.py --repeat` | Нагадування про повторну процедуру (push-версія) |
| 6 | Cron кожні 2г 8–22 | Web Push | Клієнт | `push_reminder.py --appt` | Нагадування про завтрашній запис |
| 7 | Клієнт скасував запис у PWA | Telegram | Адміни (ADMIN_USER_IDS) | `pwa_api.py _tg_notify_cancel()` | "Скасування запису: клієнт, телефон, дата, послуга" |

### Наш код → адміни

| # | Тригер | Канал | Отримувач | Файл | Зміст |
|---|--------|-------|-----------|------|-------|
| 8 | Cron 09:00 і 21:00 | Telegram | samydoma + DrGomon | `sync_with_notification.sh` | Звіт синхронізації клієнтів (нові за добу) |
| 9 | Cron щогодини (якщо були SMS) | Telegram | samydoma + DrGomon | `sms_reminder.py notify_telegram()` | Звіт відправлених SMS-нагадувань |
| 9b | Помилки SMS | Telegram | тільки samydoma | `sms_reminder.py` | Список помилок |
| 10 | /sync в Telegram боті | Telegram | Той хто запустив | `bot.py` | Підтвердження запуску + звіт після завершення |

### WLaunch → клієнти (автономно, не наш код)

Платформа WLaunch відправляє ці сповіщення напряму, повністю незалежно від нас:

| # | Тригер | Канал | Зміст |
|---|--------|-------|-------|
| W1 | Запис створено | SMS | Підтвердження запису (дата, час, послуга) |
| W2 | Нагадування за день | SMS | Нагадування про завтрашній запис |
| W3 | Запис скасовано | SMS | Підтвердження скасування |
| W4 | Зміна статусу | SMS | Залежить від налаштувань у WLaunch |

### Прогалини (WLaunch є, наш немає)

1. **SMS-підтвердження при створенні запису** — відсутнє в нашому коді повністю
2. **SMS клієнту при скасуванні** — наш код надсилає тільки адмінам, не клієнту
3. **SMS-нагадування для клієнтів без PWA/push** — `push_reminder --appt` покриває тільки PWA-юзерів з підпискою

---

## План міграції — повна заміна WLaunch-сповіщень

### Принцип доставки (пріоритет каналів)

```
Push  — завжди, якщо є активна підписка (незалежно від решти каналів)
TG    — основний транзакційний канал (якщо telegram_id відомий)
SMS   — fallback тільки якщо TG недоступний або повернув помилку
```

Push не впливає на рішення надсилати чи не надсилати SMS/TG — він відправляється паралельно і завжди.

```
notify_client(phone, ...):
  ┌─ push: завжди відправити якщо є підписка (fire-and-forget, не блокує)
  │
  ├─ if telegram_id known:
  │     відправити TG → якщо успіх: DONE (SMS не надсилати)
  │                   → якщо fail (403 / заблокований / timeout): перейти до SMS
  │
  └─ else (TG нема або fail):
        відправити SMS (Viber → SMS fallback через SMSFly)
```

**Підсумкова таблиця каналів:**

| Тип сповіщення | Push | TG | SMS |
|----------------|------|----|-----|
| Підтвердження запису | якщо є підписка | так | тільки якщо TG fail |
| Нагадування за день | якщо є підписка | так | тільки якщо TG fail |
| Нагадування за 2 год | якщо є підписка | так | тільки якщо TG fail |
| Підтвердження скасування | якщо є підписка | так | тільки якщо TG fail |
| Повторна процедура | якщо є підписка | так | тільки якщо TG fail |

---

### Модуль `notifier.py` — центральний диспетчер

```python
def notify_client(phone, tg_text, sms_text=None,
                  push_title=None, push_body=None,
                  push_url='/app/', push_tag='gomon'):
    """
    push_title/push_body — якщо None, push для цього виклику не надсилається
    sms_text             — якщо None, використовується tg_text
                           (SMS зазвичай потребує коротшого тексту без HTML)

    Повертає: {'push': bool|None, 'tg': bool|None, 'sms': bool|None}
    None = канал не намагались (нема підписки / нема TG ID)
    """
    results = {'push': None, 'tg': None, 'sms': None}

    # 1. Push — завжди, незалежно від інших каналів
    if push_title and push_body:
        results['push'] = send_push_to_phone(
            phone, push_title, push_body, push_url, push_tag
        )

    # 2. TG або SMS — взаємовиключно (SMS тільки як fallback)
    tg_id = get_telegram_id_by_phone(phone)
    if tg_id:
        results['tg'] = send_telegram(tg_id, tg_text)
        if not results['tg']:  # fail → SMS fallback
            results['sms'] = send_sms(phone, sms_text or tg_text)
    else:
        results['sms'] = send_sms(phone, sms_text or tg_text)

    return results
```

---

### Lookup Telegram ID за номером телефону

Таблиця `users` в `users.db` вже містить `(telegram_id, phone)` — заповнюється через `bot.py` коли клієнт пише боту.

```python
def get_telegram_id_by_phone(phone: str) -> int | None:
    # 1. нормалізувати phone → digits_only (380XXXXXXXXX)
    # 2. SELECT telegram_id FROM users WHERE
    #      phone = digits_only            -- 380XXXXXXXXX
    #      OR phone = '+' + digits_only   -- +380XXXXXXXXX
    #      OR RIGHT(phone,9) = RIGHT(digits_only,9)  -- fuzzy хвіст
    # 3. Якщо знайдено — повернути telegram_id
    # 4. При відправці: якщо бот заблокований (TelegramError 403) →
    #      позначити телефон як tg_blocked в users або notification_log,
    #      перейти до SMS (не намагатись TG знову до наступного дня)
```

**Важливо:** значна частина клієнтів WLaunch ніколи не відкривала бота → TG ID невідомий → одразу SMS. Для збільшення охоплення через TG потрібна окрема кампанія після міграції (розсилка через бот існуючим клієнтам).

---

### Сповіщення 1 — Підтвердження створення запису (заміна W1)

**Тригер:** `POST /api/admin/calendar/appointments` після успішного збереження

**Текст TG:**
```
Ваш запис підтверджено ✅

📅 {DD.MM.YYYY}, {HH:MM}
💆 {procedure_name}
👩‍⚕️ {specialist_display}   ← "Вікторія" або "Анастасія"
📍 ЖК Графський, другі ворота/хвіртка, ліворуч

Переглянути або скасувати: gomonclinic.com/app/
```

**Текст SMS (коротший, без HTML):**
```
Dr.Gomon: запис {DD.MM} о {HH:MM}, {procedure_name}.
Адреса: ЖК Графський, 2-і ворота, ліворуч.
Скасувати: gomonclinic.com/app/
```

**Логіка:**
- `notifier.notify_client(phone, tg_text, sms_text, push_title, push_body)`
- Push title: `"Запис підтверджено ✅"`, body: `"{procedure_name}, {DD.MM} о {HH:MM}"`
- Не надсилати для статусів не `CONFIRMED`
- Якщо клієнт новий (нема в `clients`, тільки phone) — TG lookup може не знайти → SMS
- Логувати в `notification_log (type='appt_confirm', reference='confirm|{appt_id}')`

---

### Сповіщення 2 — Нагадування за день до запису (заміна W2)

**Тригер:** cron щодня о 10:00 та 18:00

**Джерела записів:**
```
1. clients.services_json → WLaunch-записи зі статусом CONFIRMED/CONFIRMED_BY_CLIENT
2. manual_appointments   → status IN ('CONFIRMED') AND date = tomorrow
```
Обидва джерела об'єднуються, дедупліцируються за `(phone, date)`.

**Текст TG:**
```
Нагадуємо про ваш запис завтра 🌸

📅 {DD.MM}, {HH:MM}
💆 {procedure_name}
👩‍⚕️ {specialist_display}

Чекаємо вас! Dr. Gómon Cosmetology
gomonclinic.com/app/
```

**Текст SMS:**
```
Dr.Gomon: нагадуємо — завтра {DD.MM} о {HH:MM} {procedure_name}.
Скасувати: gomonclinic.com/app/
```

**Логіка:**
- Push: `push_title="Запис завтра 🌸"`, `push_body="{procedure_name}, {HH:MM}"`
- Дедуплікація: `notification_log (phone, type='appt_reminder', reference='appt|{date}')`
- Якщо запис скасований на момент запуску → пропустити
- Замінює `push_reminder.py --appt` (злиття)

---

### Сповіщення 3 — Нагадування за 2 години (нове, немає в WLaunch)

**Тригер:** cron кожні 30 хвилин, 8:00–20:00

**Умова:** запис сьогодні, до початку залишилось 1.5–2.5 год

**Текст TG:**
```
⏰ Нагадуємо: ваш запис сьогодні о {HH:MM}
{procedure_name} — Dr. Gómon
```

**Логіка:**
- Push + TG only, **SMS не надсилати** (занадто близько, може дратувати)
- `transactional=True` для TG
- Дедуплікація: `notification_log (phone, type='appt_2h', reference='2h|{date}')`

---

### Сповіщення 4 — Підтвердження скасування клієнту (заміна W3)

**Тригер:**
- `DELETE /api/admin/calendar/appointments/<id>` (адмін скасовує)
- `cancel_my_appointment()` (клієнт скасовує сам у PWA)

**Текст TG:**
```
Ваш запис скасовано

📅 {DD.MM.YYYY}
💆 {procedure_name}

Записатись знову: gomonclinic.com/app/
або ig.me/m/dr.gomon
```

**Текст SMS:**
```
Dr.Gomon: запис {DD.MM} скасовано.
Записатись: gomonclinic.com/app/ або ig.me/m/dr.gomon
```

**Логіка:**
- Push: `push_title="Запис скасовано"`, `push_body="{procedure_name}, {DD.MM}"`
- Адмінське повідомлення `_tg_notify_cancel()` → залишити як є
- Логувати: `notification_log (type='cancel', reference='cancel|{appt_id}|{date}')`

---

### Сповіщення 5 — Нагадування про повторну процедуру (рефактор існуючого)

**Проблема зараз:** два окремих скрипти (`sms_reminder.py` + `push_reminder.py`) з дублюванням логіки інтервалів і окремими таблицями дедуплікації (`sms_reminders` + `push_log`).

**Нова логіка (єдиний `repeat_reminder.py`):**
```
для кожного клієнта:
  знайти effective_entry (та сама логіка груп/корекцій що в sms_reminder.py)
  перевірити вікно нагадування (remind_date <= today <= remind_date+3d)
  перевірити дедуплікацію в notification_log
  якщо час відправки (прив'язка до години запису) → надіслати через notifier

  push: одноразово в 10:00 або 12:00 (не прив'язувати до години запису)
  TG/SMS: прив'язка до години запису зберігається (щоб не дратувати)
```

**Таблиця дедуп:** `notification_log (phone, type='repeat', reference='repeat|{service}|{visit_date}', channel)`

Окремий запис на кожен канал — дозволяє повторно надіслати push якщо SMS вже відправлено (або навпаки).

---

### Нова таблиця `notification_log`

```sql
CREATE TABLE notification_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    phone           TEXT NOT NULL,
    type            TEXT NOT NULL,
    -- типи: appt_confirm | appt_reminder | appt_2h | cancel | repeat | procedure_push
    reference       TEXT NOT NULL,
    -- унікальний ключ події:
    --   'confirm|{appt_id}'
    --   'appt|2026-04-15'
    --   '2h|2026-04-15'
    --   'cancel|{appt_id}|2026-04-15'
    --   'repeat|ботокс|2026-01-10'
    channel         TEXT NOT NULL,   -- 'tg' | 'push' | 'sms' | 'viber'
    status          TEXT DEFAULT 'sent',  -- 'sent' | 'failed' | 'skipped'
    sent_at         TEXT NOT NULL,
    message_preview TEXT,            -- перші 100 символів для дебагу
    UNIQUE(phone, type, reference, channel)
    -- channel в UNIQUE дозволяє надіслати push навіть якщо SMS вже відправлено
);
```

Замінює `sms_reminders` + `push_log` (зберегти старі таблиці для зворотної сумісності на перехідний період).

---

### Список файлів для створення/зміни при реалізації

| Файл | Дія | Пріоритет |
|------|-----|-----------|
| `zadarma/notifier.py` | **новий** — диспетчер каналів (TG → Push → SMS) | 1 |
| `zadarma/users.db` | **міграція** — `CREATE TABLE notification_log` | 1 |
| `zadarma/pwa_api.py` | **зміна** — `POST /api/admin/calendar/appointments` викликає `notifier` | 2 |
| `zadarma/pwa_api.py` | **зміна** — `cancel_my_appointment` надсилає клієнту підтвердження | 2 |
| `zadarma/appt_reminder.py` | **новий** — заміна `push_reminder.py --appt` + W2 | 3 |
| `zadarma/repeat_reminder.py` | **новий** — злиття `sms_reminder.py` + `push_reminder.py --repeat` | 4 |
| `zadarma/sms_reminder.py` | **deprecated** після тестування | — |
| `zadarma/push_reminder.py` | **deprecated** після тестування | — |

---

### Порядок міграції

```
Крок 1. Реалізувати notifier.py + notification_log (без зміни cron і API)
Крок 2. Підключити Сповіщення 1 (підтвердження запису) — найбільша цінність для клієнтів
Крок 3. Підключити Сповіщення 4 (підтвердження скасування клієнту)
Крок 4. Запустити appt_reminder.py паралельно зі старим push_reminder --appt (порівняти охоплення TG vs push-only)
Крок 5. Запустити repeat_reminder.py паралельно зі старим sms_reminder.py (--dry-run тиждень, порівняти)
Крок 6. Вимкнути WLaunch-сповіщення в налаштуваннях WLaunch (W1–W4)
Крок 7. Вимкнути cron sms_reminder + push_reminder, увімкнути нові
Крок 8. Провести кампанію — розіслати клієнтам запрошення підписатись на бота (збільшить TG-охоплення)
```

---

### Канали доставки — конфіг (config.py)

| Параметр | Що це | Де використовується |
|----------|-------|---------------------|
| `TELEGRAM_TOKEN` | Бот-токен | TG-відправка в notifier, bot.py, sms_reminder |
| `SMS_FLY_PASSWORD` | API ключ SMSFly | sms_fly.py |
| `SMS_FLY_SENDER` | SMS-відправник | sms_fly.py |
| `SMS_FLY_VIBER_SENDER` | Viber-відправник (якщо є) | sms_fly.py — увімкнює Viber+SMS режим |
| `ADMIN_USER_IDS` | Список TG-чатів адмінів | pwa_api.py, sms_reminder, sync_with_notification |
