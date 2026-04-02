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

---

## Google Ads Conversion Tracking

### Загальне
- **Google Ads ID:** `AW-719653819`
- **Google Analytics:** `G-8FC2X4SHKE`
- **gtag завантажується** в `a188dd94d37a0374c81c636d09cd1f05.php` (рядок 157)
- **PWA (index.html) НЕ має gtag** — конверсії працюють тільки на сайті

### Конверсії

| Назва | Мітка | Тригер | Файл | Рядок |
|-------|-------|--------|------|-------|
| APP_CLICK | `EjWcCL7qyY0cELuXlNcC` | Клік "Наш APP" в бургер-меню | a188dd94...php | onclick на `<a>` |
| CHAT_CONVERSION | `WaavCKa45JAcELuXlNcC` | Відкриття AI чату на сайті | gomon-widget.js | `openModal()` |
| CHAT_CONVERSION | `WaavCKa45JAcELuXlNcC` | Перше повідомлення в чаті | gomon-widget.js, gomon-chat.js | `sendMessage()` |
| INSTAGRAM_CLICK | `IK5ZCJbLxIUcELuXlNcC` | Клік на Instagram лінк | a188dd94...php | `conversionMap` |
| TELEGRAM_CLICK | `594oCJnLxIUcELuXlNcC` | Клік на Telegram лінк | a188dd94...php | `conversionMap` |
| PHONE_CLICK | `djjPCJzLxIUcELuXlNcC` | Клік на номер телефону | a188dd94...php | `conversionMap` |

### Механізм на сайті

**Клік-конверсії (IG, TG, Phone):**
```javascript
// a188dd94...php рядок 917-944: делегація через document click
var conversionMap = {
  'ig.me/m/dr.gomon':        'AW-719653819/IK5ZCJbLxIUcELuXlNcC',
  'instagram.com/dr.gomon':  'AW-719653819/IK5ZCJbLxIUcELuXlNcC',
  't.me/DrGomonCosmetology': 'AW-719653819/594oCJnLxIUcELuXlNcC',
  'tel:+380733103110':       'AW-719653819/djjPCJzLxIUcELuXlNcC'
};
// Один handler на document, break після першого збігу — без дублювання
```

**Chat конверсія:**
```javascript
// gomon-widget.js openModal(): спрацьовує при кожному відкритті чату
// gomon-widget.js sendMessage(): спрацьовує при першому повідомленні (messages.length === 1)
// gomon-chat.js sendMessage(): аналогічно (але працює тільки в PWA де немає gtag)
```

### Важливі нюанси

1. **Widget JS кешується** — при зміні `gomon-widget.js` ОБОВ'ЯЗКОВО оновити `?v=YYYYMMDD` в `a188dd94...php` (рядок ~989)
2. **PWA не має gtag** — конверсії в `gomon-chat.js` мовчки ігноруються (`typeof gtag === 'function'` = false)
3. **Google Tag Assistant** перевіряє в реальному часі — потрібно відкрити чат на сайті щоб побачити подію
4. **Нова конверсія** з'являється в Google Ads через 24-48 годин після першого спрацювання
5. **conversionMap** обробляє кліки через делегацію — новий лінк на IG/TG автоматично ловиться без додаткового коду

---

## Правила деплою

### При КОЖНОМУ деплої:
1. **SW cache bump** — збільшити літеру в `sw.js` CACHE (`gomon-YYYY-MM-DDx`)
2. **Widget version bump** — при зміні `gomon-widget.js` оновити `?v=YYYYMMDDx` в `a188dd94...php`
3. **Оновити документацію** — `google-play/PLAYSTORE-LISTING.md` (release notes, зміни, версія)
4. **Оновити CLAUDE.md** — якщо змінились endpoints, структура БД, cron, правила

---

## Правила безпеки та якості коду

### ОБОВ'ЯЗКОВО при написанні коду:

**Python (pwa_api.py, notifier.py, bot.py, ...)**:
1. **Токени/секрети**: використовувати `secrets.token_urlsafe()`, НІКОЛИ `random.choices()` для сесій
2. **SQL**: тільки параметризовані запити `?`. НІКОЛИ `.format()` для SQL
3. **Path traversal**: при `send_from_directory()` завжди перевіряти `'..' not in path`
4. **Зовнішні токени**: НІКОЛИ не передавати API-ключі в redirect URL. Проксувати запити серверсайд
5. **Rate limiting**: кожен публічний endpoint повинен мати ліміт (OTP: 3/год, AI: 5с cooldown, SMS: 1/15хв)
6. **Валідація вхідних даних**: date → `re.match(r'^\d{4}-\d{2}-\d{2}$')`, time → `re.match(r'^\d{2}:\d{2}$')`, specialist → whitelist
7. **Subprocess**: НІКОЛИ `os.system()`. Тільки `subprocess.run(cmd, shell=False, timeout=60)`
8. **Логування**: `RotatingFileHandler(maxBytes=5*1024*1024, backupCount=3)`, НІКОЛИ голий `FileHandler`
9. **Часові зони**: НІКОЛИ хардкодити `+2`. Використовувати `_kyiv_offset()` з DST-розрахунком
10. **Dry-run**: НІКОЛИ не записувати в БД при `--dry-run` (ні `mark_sent`, ні `_log()`)
11. **Атомарність**: overlap-check + INSERT мають бути в одній транзакції (`BEGIN IMMEDIATE`)
12. **`time.sleep()` в хендлерах**: ЗАБОРОНЕНО — блокує диспатчер бота та Flask-потоки

**JavaScript (index.html, gomon-*.js)**:
1. **XSS**: ЗАВЖДИ ескейпити динамічні дані через `_esc()` перед вставкою в `innerHTML`
2. **Посилання з API**: парсити через `new URL(url)` + `url.replace(/"/g, '&quot;')` перед вставкою в `href`
3. **console.log**: НІКОЛИ не логувати OTP коди, токени, паролі (навіть за `if debug`)
4. **Мертвий код**: функції без викликів видаляти одразу
5. **Модалки**: завжди додавати `Escape` key handler при створенні нового модального вікна
6. **Fetch**: завжди використовувати `AbortController` з таймаутом 30с
7. **SW notification click**: `clients.openWindow()` тільки для same-origin URL (перевіряти `url.startsWith('/')`)
8. **setInterval/setTimeout**: завжди зберігати ID і очищувати через `clearInterval/clearTimeout` у всіх code paths

**PHP (promos.php, prices.php, modal_prices.php)**:
1. **CORS**: ТІЛЬКИ `parse_url($origin, PHP_URL_HOST)` + `in_array($host, $allowed)`. НІКОЛИ `str_contains()`
2. **Помилки**: `error_reporting(0)` в продакшені, щоб не витікали шляхи файлів

### НЕ дублювати код між файлами:
- `get_specialist()`, `get_branch_id()` — тільки в `wlaunch_api.py`, решта імпортує
- `_send_tg()` — тільки в `notifier.py`, решта імпортує
- `normalize_phone()` — тільки в `user_db.py`
- `send_admin_error()` — тільки в одному місці, решта імпортує

---

## Аудит інтеграцій та рішення (2026-04-01)

### Що працює і не потребує змін

| Компонент | Статус | Примітка |
|-----------|--------|----------|
| WLaunch cancel з клієнтського додатку | Працює | `/api/me/appointments/cancel` → `_cancel_wlaunch_appt()` |
| 24h нагадування, SMS feedback | На стороні WLaunch | Не дублюємо — WLaunch надсилає |
| Скасування + створення (замість редагування) | На стороні WLaunch | Адмін скасовує і створює новий |

### Виправлення (імплементовано 2026-04-01)

| # | Проблема | Рішення | Файл |
|---|----------|---------|------|
| 3 | Briefing о 20:00 UTC = 23:00 Київ | Cron змінено на `0 17 * * *` (= 20:00 Київ DST) | crontab |
| 4 | Deep link `connect_093...` без нормалізації | Нормалізує до `380...` в bot.py start_command | bot.py |
| 7 | Спеціаліст не бачить чужі слоти | Показує "Зайнято" (без деталей) для чужих записів | pwa_api.py, index.html |
| 8 | Push click → загальний /app/ | Push URL тепер `/app/#appointments` для записів | notifier.py |
| 9 | Feedback через TG+SMS | Змінено на push-only (TG/SMS на стороні WLaunch) | notifier.py |
| 12 | prices.json — не атомарний запис | `os.replace(tmp, path)` — атомарний на POSIX | pwa_api.py |
| 13 | Stale push-підписки не очищуються | Видалення inactive > 30 днів при старті | push_sender.py |

### Рішення без імплементації (нотатки)

**#5 Guest dead end:** Гість може використовувати AI-асистента на auth-екрані або Telegram-бот. Для повноцінної реєстрації — зателефонувати або написати в Instagram Direct. Не потребує коду — UX вже покриває.

**#6 Chat rate limit (localStorage → серверний):**
Рекомендовано: нова таблиця `chat_rate(phone TEXT, date TEXT, count INT, UNIQUE(phone,date))` в otp_sessions.db. При кожному запиті до chat.php перевіряти count < 20. Найнадійніший варіант.

**#10 Manual appointments sync TO WLaunch:** Поки не імплементовано. Manual записи живуть тільки в нашій БД. WLaunch не знає про них. При міграції з WLaunch — реалізувати POST до WLaunch API при створенні manual запису.

**#14 Admin stats O(n²):** Запит через `json_each(services_json)` при 580 клієнтах × 5 записів = 2900 рядків. Поки не критично (~50ms). Оптимізація: використовувати `last_visit` + `visits_count` колонки (вже є) замість json_each. Додати колонку `last_specialist` при потребі.

### Specialist view — логіка "Зайнято"

Спеціаліст (роль `specialist`) бачить в календарі:
- **Свої записи** — повна інформація (ім'я, телефон, процедура, нотатки)
- **Чужі записи** — `procedure_name='Зайнято'`, без імені/телефону/нотаток, `busy=true`
- **Busy слоти** — відображаються напівпрозоро, не клікабельні
- Адмін (`full`/`superadmin`) бачить ВСЕ як раніше

### Cron (оновлено 2026-04-01)

```cron
*/5 * * * *     /home/gomoncli/zadarma/check_flask.sh
*/5 * * * *     /home/gomoncli/zadarma/check_and_run_bot.sh
@reboot         sleep 15 && /home/gomoncli/zadarma/check_flask.sh
0 * * * *       python3 /home/gomoncli/zadarma/sync_appointments.py
0 9,21 * * *    /home/gomoncli/zadarma/sync_with_notification.sh
0 9 * * *       python3 /home/gomoncli/zadarma/sms_reminder.py
*/15 8-22 * * * python3 /home/gomoncli/zadarma/push_reminder.py
0 17 * * *      python3 /home/gomoncli/zadarma/appt_reminder.py --specialist --tomorrow
# 17:00 UTC = 20:00 Київ (DST, літо). Зимою буде 19:00 Київ — прийнятно.
# Для точного 20:00 Київ цілий рік — потрібен wrapper з _kyiv_offset().
```
