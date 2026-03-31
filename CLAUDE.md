# GomonClinic PWA — Документація проекту

## Загальна архітектура

**Сайт:** https://www.gomonclinic.com
**Сервер:** 31.131.18.79:21098, user `gomoncli`, key `~/.ssh/id_rsa`
**PWA:** `/home/gomoncli/public_html/app/` → доступна за `/app/`
**API:** Flask Python, порт 5001 (127.0.0.1), проксі через LiteSpeed `/api/*`
**БД:** SQLite3, `/home/gomoncli/zadarma/users.db`
**CRM:** WLaunch (api.wlaunch.net/v1), Company ID у config.py

---

## Ключові файли

### API
| Файл | Призначення |
|------|-------------|
| `zadarma/pwa_api.py` | **Головний Flask API** (порт 5001). Всі `/api/*` endpoints |
| `zadarma/config.py` | Секрети: WLAUNCH_API_KEY, COMPANY_ID, TELEGRAM_TOKEN, ADMIN_USER_IDS |
| `zadarma/user_db.py` | Функції роботи з SQLite: `add_or_update_client`, `get_client_by_phone` |
| `zadarma/auth.py` | OTP генерація/верифікація |
| `zadarma/push_sender.py` | Web Push: `save_subscription`, `send_push_to_phone`, `get_subscriptions` |
| `zadarma/sms_fly.py` | SMS через sms.fly.ua API |
| `zadarma/wlaunch_api.py` | WLaunch API wrapper |
| `zadarma/bot.py` | Telegram бот (адмін-команди, /admin sync) |

### Синхронізація
| Файл | Призначення |
|------|-------------|
| `zadarma/sync_clients.py` | Нові клієнти з WLaunch за останні 24г → users.db |
| `zadarma/sync_appointments.py` | Всі appointments (±7 днів + 90 вперед) → оновлює services_json |
| `zadarma/sync_with_notification.sh` | Запускає sync_clients + надсилає Telegram-звіт адміну |
| `zadarma/push_reminder.py` | Push/SMS нагадування про завтрашній запис |
| `zadarma/sms_reminder.py` | SMS нагадування (TG-first, SMS fallback) |
| `zadarma/notifier.py` | **Диспетчер сповіщень**: Push→TG→SMS. 4 типи: reminder_24h, post_visit, cancellation (client+spec), spec_new_appt |
| `zadarma/appt_reminder.py` | Cron-скрипт: `--reminder` (10:00/18:00), `--feedback` (20:00), `--specialist` (20:00, активно) |

### Watchdog / DevOps
| Файл | Призначення |
|------|-------------|
| `zadarma/check_flask.sh` | Перевіряє що Flask живий, перезапускає якщо ні |
| `zadarma/check_and_run_bot.sh` | Watchdog для Telegram бота |

### Frontend (PWA)
| Файл | Призначення |
|------|-------------|
| `public_html/app/index.html` | **Весь PWA** (~121KB, SPA на vanilla JS) |
| `public_html/app/sw.js` | Service Worker: кеш, push, navigate |
| `public_html/app/manifest.json` | PWA маніфест (іконки, назва, display:standalone) |
| `public_html/app/gomon-chat.js` | GomonAI чат-віджет |
| `public_html/gomon-widget.js` | Виїзний чат-баннер на основному сайті |
| `public_html/promos.php` | JSON з акціями (кешується SW) |
| `public_html/callback_request_handler.php` | Обробка форми зворотного дзвінка |

### Основний сайт (sitepro — website builder)
| Файл | Призначення |
|------|-------------|
| `public_html/sitepro/a188dd94d37a0374c81c636d09cd1f05.php` | Головна сторінка сайту (index) |
| `public_html/sitepro/a19c9ec17aa700fbe3c8ab3f51a1f461.php` | Інша сторінка сайту |
| `public_html/sitepro/prices.php` | Повертає raw prices.json (origin-restricted) |
| `public_html/sitepro/modal_prices.php` | **Трансформує prices.json** у формат `{1:[{title,rows}],...}` для модалок категорій послуг |

---

## База даних (users.db)

### Таблиця `clients`
```sql
id TEXT, first_name TEXT, last_name TEXT, phone TEXT,
last_service TEXT, last_visit TEXT, visits_count INT,
services_json TEXT  -- JSON масив [{appt_id, date, hour, service, status, specialist}]
```
- `phone` — нормалізований номер (тільки цифри), напр. `380933297777`
- `services_json` — топ-5 записів, відсортовано за датою (новіші першими)
- Статуси: `CONFIRMED_BY_CLIENT`, `CANCELLED`, `CONFIRMED`, тощо
- `specialist` — `'victoria'` або `'anastasia'` (заповнюється при sync через `resources[].phone`)

### Таблиця `manual_appointments`
```sql
id INT PK, client_phone TEXT, client_name TEXT, procedure_name TEXT,
specialist TEXT, date TEXT, time TEXT, status TEXT, notes TEXT, created_by TEXT
```
- Записи, створені вручну через адмінку (не з WLaunch)
- `status`: `CONFIRMED`, `DONE`, `NO_SHOW`, `CANCELLED`

### Таблиця `users`
```sql
telegram_id INTEGER PRIMARY KEY, phone TEXT, username TEXT, first_name TEXT
```
- **Telegram-бот юзери** — НЕ PWA-юзери
- Заповнюється через bot.py коли юзер пише боту

### БД `otp_sessions.db` (окремий файл)
```sql
sessions: token TEXT PK, phone TEXT, created_at INT, expires_at INT
otp_codes: phone TEXT PK, code TEXT, expires_at INT, attempts INT
leads: phone TEXT PK, name TEXT, procedure TEXT, created_at TEXT, source TEXT
```
- **PWA-юзери** — унікальні телефони в `sessions`
- Сесія: 30 днів sliding window
- `/api/admin/stats` → `pwa_users` = COUNT(DISTINCT phone) FROM sessions

### Таблиця `push_subscriptions`
```sql
id INT, phone TEXT, endpoint TEXT, p256dh TEXT, auth TEXT, active INT
```

---

## Адмін-система

### Ролі
```python
ADMIN_ROLES = {
    '380733103110': 'superadmin',   # головний адмін
    '380996093860': 'full',         # Вікторія — повний доступ
    '380685129121': 'specialist',   # Анастасія — бачить тільки свої записи, не може редагувати ціни
    '16452040153':  'specialist',   # тестовий акаунт Анастасії
}
SPECIALIST_MAP = {
    '380996093860': 'victoria',
    '380685129121': 'anastasia',
    '16452040153':  'anastasia',    # тестовий акаунт → anastasia
}
```

### Права доступу
| Дія | superadmin | full | specialist |
|-----|-----------|------|-----------|
| Календар (всі) | ✓ | ✓ | ✗ (тільки свої) |
| Календар (свої) | ✓ | ✓ | ✓ |
| Створити запис | ✓ | ✓ | ✓ (тільки собі) |
| Клієнти | ✓ | ✓ | ✓ |
| Редагувати процедури/ціни | ✓ | ✓ | ✗ |

### Адмін-екрани (index.html)
- `screen-admin-home` — статистика, останні відвідування, кнопка синхронізації
- `screen-admin-appts` — календар (День/Тиждень/Місяць) + FAB "+"
- `screen-admin-price` — редактор процедур і цін
- `screen-admin-clients` — пошук/список клієнтів + додати нового

### Адмін JS-функції
```javascript
adminGo(id)          // перехід між admin-екранами
loadCalendarData()   // GET /api/admin/calendar/appointments?from=&to=
renderCalDay/Week/Month()  // рендер відповідно до calView
openApptAction(id)   // action sheet для ручного запису
showNewApptForm()    // overlay форми нового запису
submitNewAppt()      // POST /api/admin/calendar/appointments
loadClientsAdmin()   // GET /api/admin/clients-list
loadProcedures()     // GET /api/admin/prices/edit або /api/prices
saveProcedures()     // PUT /api/admin/prices/edit
adminSync()          // POST /api/admin/sync → скидає _calLoaded, _clientsLoaded
// AI assistant (admin-home screen):
admAiSend()          // читає input → admAiRequest()
admAiRequest(text)   // POST /api/admin/ai-intent → admAiRenderCard()
admAiRenderCard(d)   // рендерить картку з превʼю запису та кнопками
admAiConfirm()       // admAiFill() + admAiClose()
admAiEdit()          // admAiFill() + admAiClose() (відкриває форму для ручного редагування)
admAiFill()          // заповнює showNewApptForm() з даних AI-результату
admAiClose()         // ховає картку, очищує input
admAiToggleMic()     // Web Speech API (uk-UA), автосабміт після розпізнавання
```

### Важливо: дві функції `_fmtDate`
- `_fmtDate(d)` (рядок ~1486) — приймає `Date` об'єкт → повертає `YYYY-MM-DD` (для calendar)
- `_fmtDateStr(d)` (рядок ~3031) — приймає рядок `YYYY-MM-DD` → повертає `DD.MM.YYYY` (для відображення)
- **НЕ перейменовувати** і не додавати третю функцію з тим самим іменем!

---

## API Endpoints (pwa_api.py)

### Auth
| Endpoint | Метод | Опис |
|----------|-------|------|
| `/api/auth/send-otp` | POST | Відправляє OTP через Viber (з SMS-фолбеком). Для не-клієнтів — гостьовий режим |
| `/api/auth/verify` | POST | Верифікує OTP, видає сесію (30 днів, sliding window) |

### Клієнт
| Endpoint | Метод | Опис |
|----------|-------|------|
| `/api/me` | GET | Дані авторизованого клієнта + `is_admin`, `admin_role`, `specialist` |
| `/api/me/appointments` | GET | Записи клієнта: WLaunch (services_json) + manual_appointments, фільтрує CANCELLED |
| `/api/me/appointments/cancel` | POST | Скасовує запис у WLaunch + оновлює БД |
| `/api/prices` | GET | Прайс у форматі `[{cat, items:[{name,price}]}]` |
| `/api/feed` | GET | Пости з Telegram (feed.db) |
| `/api/health` | GET | Стан БД, кількість клієнтів |

### Push
| Endpoint | Метод | Опис |
|----------|-------|------|
| `/api/push/vapid-key` | GET | Публічний VAPID ключ |
| `/api/push/subscribe` | POST | Зберігає підписку |
| `/api/push/unsubscribe` | POST | Видаляє підписку |
| `/api/push/status` | GET | Чи є активні підписки у юзера |
| `/api/push/procedure-reminder` | POST | Push + SMS нагадування |
| `/api/sms/procedure-reminder` | POST | SMS для гостьового юзера |

### Адмін (`require_admin` — superadmin + full + specialist)
| Endpoint | Метод | Опис |
|----------|-------|------|
| `/api/admin/stats` | GET | `total_clients`, `pwa_users` (з otp_sessions.db), `push_subs`, `visits_month`, `recent`; для `specialist` — тільки свої записи |
| `/api/admin/role` | GET | Поточна роль і specialist |
| `/api/admin/calendar/appointments` | GET | Календар: manual + WLaunch; specialist бачить тільки свої |
| `/api/admin/calendar/appointments` | POST | Створити ручний запис |
| `/api/admin/calendar/appointments/<id>` | PUT | Оновити статус/дані ручного запису |
| `/api/admin/calendar/appointments/<id>` | DELETE | Скасувати ручний запис |
| `/api/admin/clients-list` | GET | Список клієнтів для пошуку |
| `/api/admin/clients/add` | POST | Додати нового клієнта в БД |
| `/api/admin/appointments` | GET | Всі WLaunch записи (для старих звітів) |
| `/api/admin/push-list` | GET | Push-підписники |
| `/api/admin/month-visits` | GET | Записи за місяць з цінами |
| `/api/admin/sync` | POST | Запускає sync_clients.py + sync_appointments.py |
| `/api/admin/ai-intent` | POST | NLP → структурований JSON запису через claude-sonnet-4-6 |

### Адмін (`require_full_admin` — тільки superadmin + full)
| Endpoint | Метод | Опис |
|----------|-------|------|
| `/api/admin/prices/edit` | GET | prices.json у форматі `[{cat, items:[{name,price,specialists}]}]` |
| `/api/admin/prices/edit` | PUT | Зберегти оновлений prices.json |

---

## Формати даних

### prices.json (`/home/gomoncli/private_data/prices.json`)
```json
[
  {
    "cat": "Апаратна косметологія",
    "items": [
      {"name": "WOW-чистка", "price": "1400 грн", "specialists": ["victoria", "anastasia"]},
      ...
    ]
  }
]
```

### modal_prices.php — формат для модалок сайту
```json
{
  "1": [{"title": "Апаратна косметологія", "rows": [["WOW-чистка", "", "1400 грн"], ...]}],
  "2": [...],
  "3": [...],
  "5": [...],
  "6": [...]
}
```
Маппінг service ID → ключові слова в назві категорії прописаний в `modal_prices.php`.
Категорія 4 ("Домашній догляд") — `noPrice: true`, не запитує ціни.

### services_json в clients (WLaunch дані)
```json
[
  {
    "appt_id": "abc123",
    "date": "2026-03-30",
    "hour": 14,
    "service": "WOW-чистка",
    "status": "CONFIRMED",
    "specialist": "victoria"
  }
]
```
- Топ-5 записів, нові першими
- `specialist` — заповнюється `sync_appointments.py` через `resources[].phone`

---

## Sync Flow

```
/api/admin/sync (PWA кнопка)
├── sync_clients.py      → нові клієнти за 24г
└── sync_appointments.py → оновлює appointments ±7д/+90д + поле specialist

Telegram /admin (бот)
├── sync_with_notification.sh → sync_clients + Telegram звіт
└── sync_appointments.py

Cron (щогодини)
└── sync_appointments.py → оновлює статуси appointments

Cron (09:00 і 21:00)
└── sync_with_notification.sh → sync_clients
```

**Важливо:** `sync_appointments.py` оновлює статуси (CONFIRMED, CANCELLED) і поле `specialist` в БД.

---

## Cron (crontab -l)

```cron
*/5 * * * *     /home/gomoncli/zadarma/check_flask.sh
*/5 * * * *     /home/gomoncli/zadarma/check_and_run_bot.sh
@reboot         sleep 15 && /home/gomoncli/zadarma/check_flask.sh
0 * * * *       python3 /home/gomoncli/zadarma/sync_appointments.py
0 9,21 * * *    /home/gomoncli/zadarma/sync_with_notification.sh
0 9 * * *       python3 /home/gomoncli/zadarma/sms_reminder.py
*/15 8-22 * * * python3 /home/gomoncli/zadarma/push_reminder.py
# Сповіщення спеціалістам про нові записи (АКТИВНО з 2026-03-31)
0 20 * * *      python3 /home/gomoncli/zadarma/appt_reminder.py --specialist
# (НЕ В CRON) Нагадування за 24 год: 0 10,18 * * * appt_reminder.py --reminder
# (НЕ В CRON) Відгук після процедури:  0 20   * * * appt_reminder.py --feedback
```

---

## Service Worker (sw.js)

- **CACHE**: `gomon-YYYY-MM-DDx` — бампати при кожному деплої frontend
- **STATIC**: `/app/index.html`, `/app/gomon-chat.js`, `/app/manifest.json`, `/promos.php`, Google Fonts
- **navigate**: `fetch(request, {cache:'reload'})` → завжди свіжий index.html з мережі
- **API**: тільки мережа, без кешу
- **activate**: видаляє старі кеші → `clients.claim()` → `postMessage({type:'sw-updated'})` → `location.reload()` на сторінці

---

## Deploy Flow

### Зміни в API (pwa_api.py)
```bash
# 1. Скопіювати змінений файл на сервер
scp -i ~/.ssh/id_rsa -P 21098 pwa_api.py gomoncli@31.131.18.79:/home/gomoncli/zadarma/

# 2. check_flask.sh перезапустить автоматично через ≤5хв
#    Або вручну для негайного ефекту:
ssh -i ~/.ssh/id_rsa -p 21098 gomoncli@31.131.18.79 \
  'pkill -f pwa_api; sleep 1; nohup python3 /home/gomoncli/zadarma/pwa_api.py >> /home/gomoncli/zadarma/pwa_api.log 2>&1 &'

# 3. ВАЖЛИВО: перевірити що процес стартував ПІСЛЯ зміни файлу
ssh ... 'ps -o pid,lstart -p $(pgrep -f pwa_api); stat -c "%y" /home/gomoncli/zadarma/pwa_api.py'
# lstart повинен бути ПІЗНІШЕ ніж mtime pwa_api.py
```

### Зміни у frontend (index.html)
> **ОБОВ'ЯЗКОВО після КОЖНОЇ зміни frontend:**
> 1. Збільшити CACHE в `sw.js` (формат `gomon-YYYY-MM-DDx`, де x — літера a/b/c/...)
> 2. Деплоїти **обидва** файли разом: `index.html` + `sw.js`
> Без цього браузери клієнтів бачать стару версію.

```bash
# 1. Bump CACHE в sw.js: "gomon-2026-03-30a" → "gomon-2026-03-30b"
# 2. Скопіювати файли:
scp -i ~/.ssh/id_rsa -P 21098 \
  public_html/app/index.html \
  public_html/app/sw.js \
  gomoncli@31.131.18.79:/home/gomoncli/public_html/app/
```

### Зміни на сайті (sitepro)
```bash
scp -i ~/.ssh/id_rsa -P 21098 \
  public_html/sitepro/modal_prices.php \
  public_html/sitepro/a188dd94d37a0374c81c636d09cd1f05.php \
  gomoncli@31.131.18.79:/home/gomoncli/public_html/sitepro/
```

### Перевірка
```bash
# API живий
curl -si https://www.gomonclinic.com/api/health

# SW версія (має відповідати sw.js)
curl -si https://www.gomonclinic.com/app/sw.js | grep CACHE
```

---

## PWA Frontend — Ключові JS функції

### Навігація (клієнт)
- `go(id)` — перехід між екранами (home, appointments, price, map, chat)
- `showScreen(id)` — низькорівневий перехід

### Навігація (адмін)
- `adminGo(id)` — перехід між admin-home, admin-appts, admin-price, admin-clients
- `afterLogin()` → якщо `user.is_admin` → `adminGo('admin-home')`

### Дані клієнта
- `appointments` — масив, кешується в `localStorage('gomon_appointments')`
- `loadAppointments()` — GET `/api/me/appointments`

### Pull-to-refresh
- Виключені екрани: `auth`, всі `screen-admin*`, відкриті модалки
- Threshold: 72px свайп вниз при `scrollTop === 0`

### SW update listener
```javascript
navigator.serviceWorker.addEventListener('message', e => {
  if (e.data?.type === 'sw-updated') location.reload();
});
```

---

## Правила розробки

### Перед деплоєм JS-коду обов'язково перевірити:
1. **Імена функцій**: кожен виклик `renderXxx()` — `grep -n 'function renderXxx'` → функція має існувати
2. **ID елементів**: кожен `getElementById('...')` — елемент має бути в HTML
3. **API endpoints**: кожен `fetch('/api/xxx')` — endpoint має бути в pwa_api.py
4. **Дублікати функцій**: `grep -n 'function _fmtDate'` — не повинно бути двох однакових

### Після деплою перевірити:
1. `curl -s http://127.0.0.1:5001/api/health` — API живий
2. `ps -o pid,lstart -p $(pgrep -f pwa_api)` — процес стартував ПІСЛЯ зміни файлу
3. SW версія збільшена → браузери отримають оновлення

---

## Конфіденційні файли (НЕ в git)

- `zadarma/config.py` — API ключі (є `config.example.php` як шаблон)
- `zadarma/vapid_private.key` — VAPID приватний ключ
- `zadarma/vapid_public.txt` — VAPID публічний ключ
- `private_data/prices.json` — прайс-лист
- `public_html/app/config.php` — конфіг чату

---

## Міграція на новий сервер

### Що потрібно від нового сервера
- ОС (Ubuntu/Debian/CentOS), IP, SSH доступ, root/sudo
- Веб-сервер (nginx/apache або чистий), реєстратор домену + DNS

### Що переносимо
| Що | Звідки | Примітка |
|----|--------|----------|
| Код | `git clone` з GitHub | Автоматично |
| `users.db` | `/home/gomoncli/zadarma/` | Клієнти, бот-юзери, push |
| `otp_sessions.db` | `/home/gomoncli/zadarma/` | PWA сесії |
| `feed.db` | `/home/gomoncli/zadarma/` | Telegram feed |
| `config.py` | `/home/gomoncli/zadarma/` | **НЕ в git** — вручну |
| `vapid_private.key` | `/home/gomoncli/zadarma/` | **Критично** — push підписки прив'язані |
| `prices.json` | `/home/gomoncli/private_data/` | |
| `public_html/` | весь каталог | Сайт + PWA + фото |

---

## Відомі особливості

- **Python 3.6** на сервері — f-strings підтримуються, але деякі сучасні конструкції ні
- **LiteSpeed** веб-сервер, без CDN/проксі
- **WLaunch cancel**: `POST {"appointment":{"id":...,"status":"CANCELLED"}}` (не PATCH, не DELETE)
- **Sync**: `sync_appointments.py` зберігає топ-5 записів по даті (новіші першими), включаючи CANCELLED
- **Parse services**: `pwa_api.py::parse_services()` фільтрує CANCELLED при поверненні клієнту
- **OTP доставка**: TG-first (plain text, без Viber-суфіксу) → SMS з `@www.gomonclinic.com #code` для Viber auto-fill
- **Notification stack (notifier.py)**: Push (завжди, fire-and-forget) → TG (основний) → SMS (fallback тільки якщо TG fail/невідомий). Дедуплікація через `notification_log` (UNIQUE phone+type+reference+channel). АКТИВНО: cancellation клієнт+спеціаліст, spec_new_appt (о 20:00 дня створення). НЕ АКТИВНО: reminder_24h, post_visit.
- **send_cancellation**: викликається в `DELETE /api/admin/calendar/appointments/<id>`. Надсилає клієнту підтвердження + спеціалісту внутрішнє повідомлення. WLaunch-запис: specialist витягується з services_json.
- **PWA vs Бот юзери**: `users` таблиця в users.db = Telegram-бот. Реальні PWA-юзери = `otp_sessions.db::sessions`
- **Specialist detection**: `sync_appointments.py` + `wlaunch_api.py` визначають спеціаліста через `resources[].phone` → маппінг у `RESOURCE_SPECIALIST_MAP`
- **WLaunch в календарі**: показуються з бейджом `WL`, не редагуються через адмінку (тільки через WLaunch)
- **PIN_AUTH**: словник `{phone: pin}` у pwa_api.py для bypass SMS OTP. Наразі: `16452040153` (тестовий аккаунт Анастасії, PIN `0375`)
- **Міжнародні номери в auth**: `formatPhone()` і `sendOtp()` визначають міжнародний номер як `≥11 цифр і не починається з 0`. В такому випадку `380` НЕ додається. UA-номери (0XXXXXXXXX або XXXXXXXXX) — як і раніше. Для тестового `+1`: вводити `16452040153` у поле (незважаючи на `+38` в префіксі — працює функціонально).
- **Admin AI assistant**: `/api/admin/ai-intent` — NLP через `claude-sonnet-4-6` (ANTHROPIC_KEY захардкоджений в ендпоінті). Повертає `{action, client, client_options, procedure, procedure_options, date, time, specialist, notes, reply}`. "null" рядки від моделі нормалізуються до `None`. Markdown-блоки у відповіді стрипаються. Картка показує `procedure.price` (з prices.json). Якщо клієнт новий — картка показує поле вводу телефону; при підтвердженні клієнт автоматично зберігається через `POST /api/admin/clients/add`. `_load_clients_for_ai()` сортує клієнтів без `NULLS LAST` (не підтримується SQLite 3.6).
- **Specialist stats filter**: `/api/admin/stats` для ролі `specialist` фільтрує `visits_month` і `recent` по `specialist` полю у `services_json`. Тестовий акаунт `16452040153` → `'anastasia'` в `SPECIALIST_MAP`.
- **Push dedup**: `push_sender.py::save_subscription()` лімітує до 2 активних підписок на телефон (найновіші), щоб уникнути дублікатів push.

---

## AI Chat Rate Limiting

| Місце | localStorage ключ | Ліміт |
|-------|------------------|-------|
| Сайт (`gomon-widget.js`) | `gw_rl` | 10/день |
| PWA гість | `gc_rl_guest` | 10/день |
| PWA авторизований | `gc_rl_{phone}` | 20/день |

Структура: `{"date":"2026-03-30","count":5}` — скидається наступного дня.
При ліміті — картка "Записатись на консультацію" (Instagram Direct).
