# GomonClinic PWA — Документація проекту

## Загальна архітектура

**Сайт:** https://drgomon.beauty (redirect від gomonclinic.com та drgomon.com)
**Сервер:** 45.94.157.127, root SSH (key-only), Ubuntu 24.04, nginx
**App path:** `/opt/gomon/app/` (symlink `/home/gomoncli/` → `/opt/gomon/app/`)
**Python:** 3.12, venv `/opt/gomon/venv`
**API:** Flask Python, порт 5001 (127.0.0.1), проксі через nginx `/api/*`
**БД:** SQLite3, `/opt/gomon/app/zadarma/users.db`
**CRM:** WLaunch (api.wlaunch.net/v1), Company ID у config.py
**SSL:** certbot auto-renew, HSTS enabled
**Security:** UFW (22, 80, 443), fail2ban, SSH key-only
**Backups:** daily SQLite 03:00 → `/opt/gomon/backups/` (14 day retention)

---

## Ключові файли

### API
| Файл | Призначення |
|------|-------------|
| `zadarma/pwa_api.py` | **Головний Flask API** (порт 5001). Всі `/api/*` endpoints |
| `zadarma/config.py` | Секрети: WLAUNCH_API_KEY, COMPANY_ID, TELEGRAM_TOKEN, TG_BIZ_TOKEN, ANTHROPIC_KEY, ADMIN_USER_IDS |
| `zadarma/user_db.py` | Функції роботи з SQLite: `add_or_update_client`, `get_client_by_phone` |
| `zadarma/auth.py` | OTP генерація/верифікація |
| `zadarma/push_sender.py` | Web Push: `save_subscription`, `send_push_to_phone`, `get_subscriptions` |
| `zadarma/sms_fly.py` | SMS через sms.fly.ua API |
| `zadarma/wlaunch_api.py` | WLaunch API wrapper |
| `zadarma/bot.py` | Telegram бот (адмін-команди, /admin sync) |
| `zadarma/tg_business_listener.py` | **TG Business Bot** — прийом DM + AI auto-reply через `@DrGomonCosmetologyBot` |
| `zadarma/tz_utils.py` | DST-aware timezone: `kyiv_offset()`, `utc_to_kyiv()`, `kyiv_now()` |

### Месенджер (Адмін + AI)
| Файл | Призначення |
|------|-------------|
| `public_html/app/tg_media.php` | PHP-проксі для TG Business media |
| `public_html/app/msg_upload.php` | PHP-проксі для upload файлів у месенджері |
| `public_html/messenger/auth.php` | Instagram OAuth (code → short → long-lived token) |
| `public_html/messenger/send.php` | Instagram Graph API v25.0 send proxy |

### Синхронізація
| Файл | Призначення |
|------|-------------|
| `zadarma/sync_clients.py` | Нові клієнти з WLaunch за останні 24г → users.db |
| `zadarma/sync_appointments.py` | Appointments sync: merge (не перезапис!) нових зі старими. `--deep` для повної історії |
| `zadarma/sync_with_notification.sh` | Запускає sync_clients + надсилає Telegram-звіт адміну |
| `zadarma/push_reminder.py` | Push/SMS нагадування про завтрашній запис |
| `zadarma/sms_reminder.py` | SMS нагадування (TG-first, SMS fallback) |
| `zadarma/notifier.py` | **Диспетчер сповіщень**: Push→TG→SMS. 4 типи: reminder_24h, post_visit, cancellation (client+spec), spec_new_appt |
| `zadarma/appt_reminder.py` | Cron-скрипт: `--reminder` (10:00/18:00), `--feedback` (20:00), `--specialist` (20:00, активно) |
| `zadarma/photo_reminder.py` | Cron: `--create` (21:30 Kyiv) Drive папки + TG спеціалістам; `--check` (11:00 Kyiv) перевірка фото + TG адміну |
| `zadarma/gdrive.py` | Google Drive API v3 wrapper: JWT auth через openssl, створення папок, share, підрахунок файлів |

### Systemd Services
| Сервіс | Призначення |
|--------|-------------|
| `gomon-api.service` | Flask API (pwa_api.py), auto-restart on failure |
| `gomon-bot.service` | Telegram бот (bot.py) |
| `gomon-tgbiz.service` | TG Business listener (tg_business_listener.py) |

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
| `public_html/sitepro/a188dd94d37a0374c81c636d09cd1f05.php` | **Єдина сторінка сайту** (index). НЕ створювати додаткових сторінок! |
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
- `services_json` — топ-15 записів, відсортовано за датою (новіші першими)
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

### Таблиця `deposits`
```sql
id INTEGER PRIMARY KEY, order_ref TEXT UNIQUE, phone TEXT, amount_eur REAL,
amount_uah REAL, status TEXT, created_at TEXT, approved_at TEXT,
wfp_transaction_id TEXT
```
- WayForPay deposit records (5 EUR)
- Status: Pending → Approved / Declined / Expired

### Таблиця `deposit_deductions`
```sql
id INTEGER PRIMARY KEY, phone TEXT, amount REAL, reason TEXT, created_by TEXT, created_at TEXT
```

### Таблиця `cashback`
```sql
id INTEGER PRIMARY KEY, phone TEXT, amount REAL, procedure_name TEXT,
appt_date TEXT, created_at TEXT, UNIQUE(phone, procedure_name, appt_date)
```
- 3% від суми процедури, auto-accrued by appt_reminder.py --feedback
- Dedup: phone+procedure+date

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
// Client card (від календаря та таби Клієнти):
openClientCard(phone, name)       // модалка з балансом, візитами, фото, кнопкою "Новий запис"
closeClientCard()                 // закриває модалку
_showAdminDepositHistory(phone)   // деталі транзакцій (confirm-modal поверх client-card)
_loadClientPhotoCount(phone, el)  // лічильник фото в блоці
_openPhotoGallery(phone)          // повноекранна галерея зі свайпом
_redeemCashback(phone, amount)    // списання кешбеку
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
| `/api/chat/cancel-appointment` | POST | AI-скасування: `{phone, date?}` → cancel nearest/specific → WLaunch + notifier |
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
| `/api/admin/client-card/<phone>` | GET | **Картка клієнта**: повна історія візитів (local DB + WLaunch API realtime) + manual appointments |
| `/api/admin/clients/add` | POST | Додати нового клієнта в БД |
| `/api/admin/appointments` | GET | Всі WLaunch записи (для старих звітів) |
| `/api/admin/push-list` | GET | Push-підписники |
| `/api/admin/month-visits` | GET | Записи за місяць з цінами |
| `/api/admin/sync` | POST | Запускає sync_clients.py + sync_appointments.py |
| `/api/admin/ai-intent` | POST | NLP → структурований JSON запису через claude-sonnet-4-6 |
| `/api/admin/cashback/redeem` | POST | Списати кешбек клієнта (>=500 грн combined balance) |

### Адмін (`require_full_admin` — тільки superadmin + full)
| Endpoint | Метод | Опис |
|----------|-------|------|
| `/api/admin/prices/edit` | GET | prices.json у форматі `[{cat, items:[{name,price,specialists}]}]` |
| `/api/admin/prices/edit` | PUT | Зберегти оновлений prices.json |

### Депозити та кешбек
| Endpoint | Метод | Опис |
|----------|-------|------|
| `/api/deposit/create` | POST | Створити WayForPay платіж (5 EUR) |
| `/api/deposit/create-internal` | POST | Створити платіж для внутрішніх посилань (TG, rate limit) |
| `/api/deposit/callback` | POST | WayForPay callback (HMAC signature verification) |
| `/api/deposit/balance` | GET | Баланс: deposit + cashback + transactions. `?phone=X` для адміна |
| `/api/deposit/reconcile` | POST | Cron: перевірка pending через WFP CHECK_STATUS |
| `/api/admin/deposit/deduct` | POST | Списання з депозиту адміном |

---

## Формати даних

### prices.json (`/opt/gomon/app/private_data/prices.json`)
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
- Зберігає до **50 останніх** записів (було 15)
- `sync_appointments.py` **мержить** нові записи зі старими по `appt_id` (не перезаписує!)
- `--deep` flag для повної синхронізації всієї історії з WLaunch
- `visits_count` = max(sync count, merged entries count)
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
- Топ-15 записів, нові першими
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

**Важливо:**
- `sync_appointments.py` **мержить** нові записи зі старими по `appt_id` (не перезаписує!)
- Hourly sync: 7 днів назад + 90 вперед (оновлює статуси + нові записи)
- `python3 sync_appointments.py --deep` — повна історія з 2020 (одноразово або при потребі)
- `services_json` зберігає до 50 записів (найновіші)
- **Картка клієнта** (`/api/admin/client-card/<phone>`) додатково підтягує ВСЮ історію з WLaunch API в реальному часі

---

## Cron (crontab -l)

Всі часи — **Kyiv** (`TZ=Europe/Kyiv` в crontab).

```
TZ=Europe/Kyiv
VENV=/opt/gomon/venv/bin/python
APP=/opt/gomon/app/zadarma

0 * * * *       cd $APP && $VENV sync_appointments.py          # Sync WLaunch
0 9,21 * * *    cd $APP && bash sync_with_notification.sh       # Sync clients + TG звіт
0 9-21 * * *    cd $APP && $VENV sms_reminder.py                # Повторні процедури (TG→SMS)
*/15 8-22 * * * cd $APP && $VENV push_reminder.py               # Push нагадування
0 20 * * *      cd $APP && $VENV appt_reminder.py --specialist --tomorrow  # Брифінг спеціалістам
30 21 * * *     cd $APP && $VENV photo_reminder.py --create     # Drive папки + TG
0 11 * * *      cd $APP && $VENV photo_reminder.py --check      # Перевірка фото
0 7,19 * * *    cd $APP && $VENV photo_cache.py                 # Кеш фото
0 3 * * *       SQLite backup → /opt/gomon/backups/ (14 днів)
```

**НЕ В CRON** (обслуговується WLaunch): нагадування за 24 год, відгук після процедури.

> **Примітка:** Watchdog cron-скрипти замінені на systemd services (`gomon-api`, `gomon-bot`, `gomon-tgbiz`) з auto-restart.

---

## Service Worker (sw.js)

- **CACHE**: `gomon-YYYY-MM-DDx` — бампати при кожному деплої frontend
- **STATIC**: `/app/index.html`, `/app/gomon-chat.js`, `/app/manifest.json`, `/promos.php`, Google Fonts
- **navigate**: `fetch(request, {cache:'reload'})` → завжди свіжий index.html з мережі
- **API**: тільки мережа, без кешу
- **activate**: видаляє старі кеші → `clients.claim()` → `postMessage({type:'sw-updated'})` → `location.reload()` на сторінці

---

## Deploy Flow

Код знаходиться на сервері у `/opt/gomon/app/` (git repo). Деплой через `git pull` + restart.

### Зміни в API (pwa_api.py)
```bash
# 1. На сервері: pull змін
ssh root@45.94.157.127
cd /opt/gomon/app && git pull

# 2. Перезапуск API
systemctl restart gomon-api

# 3. Перевірити статус
systemctl status gomon-api
```

### Зміни в Telegram боті / TG Business
```bash
systemctl restart gomon-bot       # Telegram бот
systemctl restart gomon-tgbiz     # TG Business listener
```

### Зміни у frontend (index.html)
> **ОБОВ'ЯЗКОВО після КОЖНОЇ зміни frontend:**
> 1. Збільшити CACHE в `sw.js` (формат `gomon-YYYY-MM-DDx`, де x — літера a/b/c/...)
> 2. Коммітити **обидва** файли разом: `index.html` + `sw.js`
> Без цього браузери клієнтів бачать стару версію.

```bash
# 1. Bump CACHE в sw.js: "gomon-2026-03-30a" → "gomon-2026-03-30b"
# 2. git pull на сервері (frontend файли оновляться автоматично через symlink)
ssh root@45.94.157.127 'cd /opt/gomon/app && git pull'
```

### Перевірка
```bash
# API живий
curl -si https://drgomon.beauty/api/health

# SW версія (має відповідати sw.js)
curl -si https://drgomon.beauty/app/sw.js | grep CACHE
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
1. `curl -s https://drgomon.beauty/api/health` — API живий
2. `systemctl status gomon-api` — сервіс активний
3. SW версія збільшена → браузери отримають оновлення

### При аудитах ОБОВ'ЯЗКОВО перевіряти:

**Інфраструктура (nginx, DNS, SSL):**
1. **Webhooks по HTTP**: `curl -X POST http://drgomon.beauty/zadarma_webhook.php` — POST має працювати без redirect (Zadarma, WLaunch, WayForPay шлють по HTTP)
2. **Certbot if-блоки**: перевірити що `if ($host)` redirect в nginx не перехоплює webhook location blocks
3. **nginx access.log**: `grep "webhook\|callback" /var/log/nginx/access.log | tail` — чи приходять запити і який HTTP код
4. **File permissions**: `ls -la private_data/prices.json` — www-data повинен мати доступ (644, не 600)
5. **Symlinks**: `/home/gomoncli/ → /opt/gomon/app/` — перевірити що не зламаний

**Сервіси та cron:**
6. **Systemd**: `systemctl is-active gomon-api gomon-bot gomon-tgbiz` — всі три active
7. **Cron**: `crontab -l | grep -v "^#"` — всі записи валідні, шляхи правильні
8. **Порти**: `ss -tlnp | grep -E "5001|80|443"` — gunicorn на 5001, nginx на 80/443
9. **PHP-FPM**: `systemctl is-active php*-fpm` — PHP обробляє .php файли

**Зовнішні інтеграції (перевірити реальними запитами):**
10. **Zadarma webhook**: зателефонувати і натиснути кнопку IVR — перевірити лог
11. **WayForPay callback**: створити тестовий платіж — перевірити що callback приходить
12. **WLaunch sync**: `python3 sync_appointments.py` — перевірити що працює без помилок
13. **TG bot**: надіслати /help — перевірити відповідь
14. **TG Business**: написати в DM @DrGomonCosmetology — AI відповідає

**Дані та БД:**
15. **prices.json readable**: `curl -s https://drgomon.beauty/sitepro/modal_prices.php | head -c 50` — не порожній `{}`
16. **promos.json**: `curl -s https://drgomon.beauty/promos.php | head -c 50` — не порожній
17. **SQLite locks**: `fuser zadarma/users.db` — ніхто не тримає lock

---

## Конфіденційні файли (НЕ в git)

- `zadarma/config.py` — API ключі (є `config.example.php` як шаблон)
- `zadarma/vapid_private.key` — VAPID приватний ключ
- `zadarma/vapid_public.txt` — VAPID публічний ключ
- `private_data/prices.json` — прайс-лист
- `public_html/app/config.php` — конфіг чату

> На сервері шляхи з префіксом `/opt/gomon/app/` (symlink `/home/gomoncli/` → `/opt/gomon/app/`)

---

## Сервер (міграція завершена 2026-04-14)

> **Старий сервер (31.131.18.79):** тримає API через watchdog cron для клієнтів зі старим DNS кешем. Боти вимкнені (.disabled). Буде деком після TWA update в Google Play.

### Конфігурація VPS
- **IP:** 45.94.157.127, root SSH (key-only)
- **OS:** Ubuntu 24.04, Python 3.12
- **Web:** nginx, certbot SSL (auto-renew), HSTS
- **Security:** UFW (22, 80, 443), fail2ban
- **Domain:** drgomon.beauty (primary), redirect від gomonclinic.com та drgomon.com

### Структура
| Шлях | Призначення |
|------|-------------|
| `/opt/gomon/app/` | Код (git repo) |
| `/opt/gomon/venv/` | Python venv |
| `/opt/gomon/backups/` | Daily SQLite backups (14 day retention) |
| `/home/gomoncli/` | Symlink → `/opt/gomon/app/` (backward compat) |
| `/var/log/gomon/` | Логи cron-скриптів |

### Конфіденційні файли на сервері
| Що | Шлях | Примітка |
|----|------|----------|
| `users.db` | `/opt/gomon/app/zadarma/` | Клієнти, бот-юзери, push |
| `otp_sessions.db` | `/opt/gomon/app/zadarma/` | PWA сесії |
| `feed.db` | `/opt/gomon/app/zadarma/` | Telegram feed |
| `config.py` | `/opt/gomon/app/zadarma/` | **НЕ в git** — вручну |
| `vapid_private.key` | `/opt/gomon/app/zadarma/` | **Критично** — push підписки прив'язані |
| `prices.json` | `/opt/gomon/app/private_data/` | |

---

## WLaunch API (недокументоване, знайдено reverse-engineering)

**Base:** `https://api.wlaunch.net/v1`
**Auth:** `Authorization: Bearer {WLAUNCH_API_KEY}` (config.py)
**Company ID:** `3f3027ca-0b21-11ed-8355-65920565acdd`
**Branch ID:** динамічний, отримується через GET /branch/

### Офіційно задокументовані (специфікація v0.1.0 від 10.07.2025)

| Endpoint | Метод | Опис |
|----------|-------|------|
| `/company/{cid}/branch/` | GET | Список філій |
| `/company/{cid}/branch/{bid}/appointment` | GET | Записи по філії (з пагінацією, фільтрами start/end) |
| `/company/{cid}/client` | GET | Клієнти (пагінація, фільтр по phone) |

### Знайдені endpoints (працюють, не задокументовані)

| Endpoint | Метод | Payload | Опис |
|----------|-------|---------|------|
| `/company/{cid}/branch/{bid}/appointment` | POST | `{"appointment":{...}}` | Створити запис |
| `/company/{cid}/branch/{bid}/appointment/{aid}` | POST | `{"appointment":{"id":"..","status":"CANCELLED"}}` | Скасувати запис |
| `/company/{cid}/branch/{bid}/resource` | GET | — | Список спеціалістів (resources) |
| `/company/{cid}/branch/{bid}/service` | GET | `?page=0&size=200` | Список послуг |
| `/company/{cid}/service` | POST | `{"company_service":{name,duration,type:"SERVICE",...}}` | **Створити послугу** |
| `/company/{cid}/service/{sid}` | POST | `{"company_service":{"active":false}}` | Деактивувати послугу |
| `/company/{cid}/client` | POST | `{"client":{first_name,last_name,phone}}` | Створити клієнта |
| `/company/{cid}/branch/{bid}/resource/schedule` | GET | `?start=YYYY-MM-DD&end=YYYY-MM-DD` | **Читати розклад** (ON/OFF frames per resource) |
| `/company/{cid}/branch/{bid}/resource/{rid}/schedule/day` | POST | `{"frame":{"date":"..","start_time":sec,"end_time":sec,"type":"OFF"}}` | **Створити перерву** |
| `/company/{cid}/branch/{bid}/resource/{rid}/schedule/day/{fid}` | POST | `{"frame":{"active":false}}` | **Видалити перерву** |

### Формати

**Appointment payload:**
```json
{"appointment": {
  "client": {"id": "uuid"},
  "start_time": "2026-04-15T10:00:00.000Z",
  "duration": 3600,
  "status": "CONFIRMED",
  "booking_type": "GENERAL",
  "source": "BO",
  "service_resource_settings": [{
    "service": "service-uuid",
    "resources": ["resource-uuid"],
    "auto_selected_resources": false,
    "ordinal": 1,
    "duration": 3600
  }]
}}
```

**Schedule frame:**
- `start_time` / `end_time` — **секунди від початку доби, local Kyiv time** (не UTC!)
- `type: "ON"` = робочий час, `type: "OFF"` = перерва/вихідний
- `cycle_frames` = регулярний графік (день тижня), `day_frames` = конкретні дні

**Service creation:**
```json
{"company_service": {
  "name": "Назва", "duration": 1800, "type": "SERVICE",
  "booking_type": "GENERAL", "public": true, "capacity": 1,
  "capacity_type": "CAPACITY_1"
}}
```

### WLaunch Services — повна синхронізація з prices.json (2026-04-18)

**5 категорій (type=GROUP) + Консультація top-level, 57 процедур:**
| Категорія | Кількість |
|---|---|
| Ін'єкційна косметологія | 37 |
| Доглядові процедури | 6 (пілінги, SPA) |
| Апаратна косметологія | 5 (WOW-чистки, кисневий, карбокситерапія) |
| Догляд за тілом | 5 (масаж, моделювання, пресотерапія) |
| Відбілювання зубів | 3 |
| Консультація (top-level) | 1 |

**Назви 1:1 з prices.json** — кешбек працює без fuzzy matching.
Назви з контекстом: "Ботулінотерапія 1 зона (Neuronox)", "Контурна пластика Saypha Filler", тощо.

**WLaunch API для сервісів:**
- `POST /company/{cid}/service` — створити (company-level)
- `PUT /company/{cid}/branch/{bid}/service/{sid}` — лінкувати до branch (ОБОВ'ЯЗКОВО після POST!)
- `POST /company/{cid}/service/{sid}` з `{parentId: "..."}` — переміщення між категоріями
- `type: "GROUP"` для категорій, `type: "SERVICE"` для послуг
- Обмеження: неактивну послугу не можна активувати якщо батько неактивний (каскадна деактивація)

### Service matching (fuzzy) — для кешбеку

`appt_reminder.py::_accrue_cashback()` матчить назви через 3 рівні:
1. **Exact** — `procedure_name.lower() == price_item_name.lower()`
2. **Substring** — назва містить/міститься (найдовший збіг)
3. **Category map** — keyword → перша процедура з ціною в категорії

### Specialist breaks (sync)

При створенні перерви через наш додаток:
1. Зберігається локально в `specialist_breaks` таблицю
2. Створюється OFF frame в WLaunch через `/resource/{rid}/schedule/day`
3. WLaunch ID зберігається в полі `reason` як `wl:UUID`

При видаленні: деактивується в WLaunch через `POST /schedule/day/{id}` з `{"frame":{"active":false}}`

---

## Відомі особливості

- **Python 3.12** на сервері (venv `/opt/gomon/venv`)
- **nginx** веб-сервер, certbot SSL, HSTS
- **WLaunch cancel**: `POST {"appointment":{"id":...,"status":"CANCELLED"}}` (не PATCH, не DELETE)
- **WLaunch обов'язковий**: при створенні записів WLaunch повинен підтвердити. Якщо WLaunch відхиляє (unavailable, 422) — запис НЕ створюється. Fallback local тільки при network/500 помилках
- **WLaunch breaks**: перерви синхронізуються через `/resource/{rid}/schedule/day` (type=OFF). Видалення через POST з `{frame:{active:false}}`
- **Sync**: `sync_appointments.py` мержить нові записи зі старими по `appt_id` (до 50). `--deep` для повної історії
- **Parse services**: `pwa_api.py::parse_services()` фільтрує CANCELLED при поверненні клієнту
- **OTP доставка**: TG-first (plain text, без Viber-суфіксу) → SMS з `@drgomon.beauty #code` для Viber auto-fill
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
- **Часові зони**: СКРІЗЬ kyiv_now() — Python (tz_utils), PHP (date_default_timezone_set), cron (TZ=Europe/Kyiv). НІКОЛИ datetime.now() або utcnow() для порівняння дат.
- **Слово "клініка"**: ЗАБОРОНЕНО у всіх текстах для клієнтів. Замість цього: "Dr. Gomon Cosmetology", "простір Dr. Gomon", "студія", "ми"/"у нас". Правило прописане в system_prompt.txt.
- **AI скасування записів**: TG Business бот і GomonAI в додатку можуть скасовувати записи клієнтів через теги `<CANCEL>` / `<CANCEL date="YYYY-MM-DD">`. AI спочатку уточнює, потім скасовує найближчий або вказаний запис. Скасування проходить через WLaunch + local DB + notifier (як при скасуванні адміном). Гостям — відмова з порадою авторизуватись.
- **AI НЕ записує**: Бот не створює записи. При запиті на запис збирає ПІБ, телефон, процедуру, час → ескалює до лікаря через `<ESCALATE>`.
- **TG Markdown fallback**: `parse_mode='Markdown'` з автоматичним retry без parse_mode якщо TG API відхиляє (кривий markdown).
- **Admin client update**: `POST /api/admin/clients/add` оновлює ім'я/прізвище існуючого клієнта (не тільки створює нового).
- **WLaunch client search**: `phone` фільтр в API запиті (не тільки перші 50 клієнтів).

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

### Cron (оновлено 2026-04-14)

Дивись головну секцію "Cron (crontab -l)" вище — єдине джерело правди. `TZ=Europe/Kyiv`.

---

## GomonAI — AI-асистент (3 канали)

### Архітектура

GomonAI працює в **трьох незалежних каналах** з єдиним system prompt:

| Канал | Endpoint | Модель | Rate limit | Історія | Ескалація |
|-------|----------|--------|-----------|---------|-----------|
| **Сайт** (gomon-widget.js) | `chat.php` | claude-sonnet-4-6 + fallback chain | 10/день (guest) | sessionStorage | Ні |
| **Додаток** (gomon-chat.js) | `chat.php` | claude-sonnet-4-6 + fallback chain | 20/день (authed) | in-memory JS | Ні |
| **Telegram Business** | `tg_business_listener.py` | claude-sonnet-4-5 | 20/день | БД messages | **Так** → адмін |

### System prompt

Єдиний файл: `/opt/gomon/app/public_html/app/system_prompt.txt` (~22KB)

Кожен канал додає свій контекст:
- **Сайт**: "Ти спілкуєшся з відвідувачем сайту..." + пропонує записатись через IG/TG/додаток
- **Додаток**: "Ти вбудований асистент у додатку..." + знижки через додаток
- **Telegram**: "Ти спілкуєшся в Telegram бізнес-акаунті..." + правила ескалації

Динамічні доповнення (при кожному запиті):
- Дані клієнта (ім'я, телефон) — з `users.db`
- **Майбутні записи** (активні + скасовані з позначкою) — з `services_json`
- **Історія візитів** (останні 5) — з `services_json`
- Якщо телефон невідомий (TG) — підказка прив'язати через `/start @DrGomonConciergeBot`
- Актуальний прайс — з `prices.json`
- Поточні акції — з `promos.json`

### chat.php — модель fallback chain

```
claude-sonnet-4-6 → claude-sonnet-4-5 → claude-3-5-sonnet-20241022 → claude-haiku-4-5
```
- Кешована модель у `/opt/gomon/app/private_data/active_model.txt`
- 429 (rate limit) НЕ пробує наступну модель (key-level, не model-level)
- Rate limit списується ПІСЛЯ успішної відповіді (не до)
- Клієнтський timeout: 25с, серверний: 20с (primary) / 12с (fallback)

### Telegram Business AI — tg_business_listener.py

**Процес**: окремий Python-демон, polling через `getUpdates`

**Потік обробки клієнтського повідомлення:**
1. Повідомлення зберігається в `messages` таблицю
2. Перевірка: чи не стікер, чи не від адміна
3. **Медіа** (фото/відео/голосовушка/документ) → миттєва відповідь "працюю лише з текстом" (без AI)
4. **Текст** → запуск `handle_ai_reply()` в окремому `threading.Thread(daemon=True)`:
   - `_check_ai_should_reply()` — admin pause + rate limit
   - `_build_system_prompt()` — prompt + клієнт + прайс + акції
   - `_get_conversation_history()` — останні 20 повідомлень з БД, alternating roles
   - `_call_anthropic()` → claude-sonnet-4-5
   - Перевірка `<CANCEL>` / `<CANCEL date="YYYY-MM-DD">` → `_cancel_client_appointment()` → WLaunch + DB + notifier
   - Перевірка `<ESCALATE>` тегу → повідомлення адміну
   - `_send_ai_reply()` — через Business Bot API з `business_connection_id`, `parse_mode='Markdown'` з plain text fallback
   - `_save_ai_message()` — зберігає з `sender_id='ai_bot'`

**Ескалація:**
- AI додає `<ESCALATE>` тег у відповідь коли:
  - Клієнт просить живу людину
  - Скарга/претензія
  - Медична проблема для лікаря
  - Запис на конкретну дату/час
  - Питання поза прайсом
  - AI не впевнений
- При ескалації: відповідь клієнту (ввічливий handoff) + TG-нотифікація адміну через основного бота

**Admin pause (30 хв):**
- Якщо реальний адмін відповідав протягом 30 хв — AI мовчить
- Автопривітання TG (приходить <5с від повідомлення клієнта) НЕ вважається відповіддю адміна
- AI-відповіді (`sender_id='ai_bot'`) НЕ вважаються відповіддю адміна

**Thread limiter:** max 3 одночасних AI потоки (6 total threads)

**Offset persistence:** зберігається в `.tg_business_offset` файлі, відновлюється після рестарту

---

## Адмін-месенджер

### Архітектура

Уніфікований inbox для **Telegram Business** + **Instagram** (IG поки read-only, App Review pending).

**Backend endpoints** (pwa_api.py, всі `@require_admin`):
| Endpoint | Метод | Опис |
|----------|-------|------|
| `/api/admin/messages` | GET | Список conversations (50 останніх) з unread count. Фільтри: `?unread_only=1`, `?platform=telegram` |
| `/api/admin/messages/<conv_id>` | GET | Повідомлення треду (limit 50) |
| `/api/admin/messages/send` | POST | Відправити відповідь (TG через Business Bot, IG через Graph API) |
| `/api/admin/messages/read` | POST | Позначити прочитаним |
| `/api/admin/messages/upload` | POST | Upload медіа |
| `/api/admin/messages/tg-media/<fid>` | GET | Proxy TG media (без auth, file_ids unguessable) |
| `/api/admin/messages/media/<fname>` | GET | Serve uploaded files |

**Frontend** (index.html, screen-admin-chat):
- Sidebar: список conversations з фільтрами (Всі/Непрочитані/TG/IG)
- Thread: повідомлення з media display (фото/відео/аудіо)
- 10с polling для conversations + **auto-refresh відкритого треду**
- Відправка: текст + фото/відео upload + voice recording (MediaRecorder API)
- Platform badges: TG (синій), IG (рожевий)

**Telegram sending flow:**
1. `_get_biz_connection_id(chat_id)` — з таблиці `biz_connections`
2. `_send_tg_from_api()` — sendMessage/sendPhoto/sendVideo/sendVoice через Business Bot API
3. Якщо `business_connection_id` присутній — надсилає від імені бізнес-акаунта
4. Якщо відсутній — надсилає від імені бота (fallback, логується warning)

**biz_connections таблиця:**
```sql
chat_id TEXT PRIMARY KEY, biz_conn_id TEXT NOT NULL
```
- Оновлюється при кожному вхідному повідомленні від клієнта
- Оновлюється при `business_connection` event (reconnect)

---

## Конфіденційні файли (НЕ в git)

- `zadarma/config.py` — Python секрети: TG_TOKEN, TG_BIZ_TOKEN, ANTHROPIC_KEY, WLAUNCH_API_KEY, SMS_FLY_*
- `public_html/app/config.php` — PHP секрети: ANTHROPIC_API_KEY, TG_BIZ_TOKEN, IG_APP_SECRET, IG_FALLBACK_TOKEN
- `zadarma/vapid_private.key` — VAPID приватний ключ
- `zadarma/vapid_public.txt` — VAPID публічний ключ
- `private_data/prices.json` — прайс-лист
- `private_data/promos.json` — акції
- `private_data/gdrive_sa.json` — Google Drive Service Account key

**ВАЖЛИВО:** Всі токени/секрети тільки в config.py та config.php. НІКОЛИ не хардкодити в інших файлах.
**Шляхи на сервері:** `/opt/gomon/app/zadarma/config.py`, `/opt/gomon/app/public_html/app/config.php` тощо.

---

## Аудит стабільності (2026-04-10)

### Виправлено (критичні + високі)

**Auth (pwa_api.py):**
- `BEGIN IMMEDIATE` транзакції для OTP rate limit, OTP verify, magic token pop — атомарність
- Admin session sliding — `_get_session_phone()` тепер продовжує `expires_at`
- Session cap — max 5 сесій на phone (видаляє старі при login)

**Appointments (pwa_api.py):**
- `BEGIN IMMEDIATE` для PUT overlap check — запобігає double-booking
- WLaunch rollback — якщо local DB відхиляє/падає після WLaunch create, WLaunch запис скасовується
- DELETE → WLaunch cancel — при видаленні manual appointment скасовує і в WLaunch (через `wlaunch_id` або `wl:UUID` з notes)
- `specialist=''` заборонено — тільки `victoria` або `anastasia`
- `wlaunch_id` тепер записується в INSERT при створенні

**AI Chat (chat.php, gomon-chat.js):**
- Rate limit списується ПІСЛЯ успішної відповіді (не до)
- 429 від Anthropic не пробує fallback моделі (key-level)
- Client timeout збільшено до 25с (server до 20с)
- History cap: 20 повідомлень (запобігає context overflow)
- XSS fix в `linkify()` — URL ескейпить `"` і `'` перед вставкою в `href`

**Messenger (pwa_api.py, index.html):**
- Thread auto-refresh — відкритий тред оновлюється кожні 10с
- `_get_biz_connection_id` — single query, proper error logging (було bare `except: pass`)
- `MAX_CONTENT_LENGTH = 16MB` на Flask

**CORS (всі PHP + Flask):**
- `api/index.php` — `Access-Control-Allow-Origin: *` → whitelist
- `messenger/send.php` — `str_ends_with` + localhost → `parse_url` + `in_array`
- `chat.php` — додано `drgomon.beauty`
- Flask CORS — додано `drgomon.beauty`

**DevOps:**
- `check_flask.sh` — */2 cron + auto HUP reload при зміні `pwa_api.py`
- Secrets centralized — всі токени в config.py / config.php

### Google Drive — фото до/після

**Архітектура:** Service Account (`id-303@gomon-492922.iam.gserviceaccount.com`) має Editor доступ до `GomonClinic` папки на Drive (2TB). Створює підпапки і шарить "anyone with link = editor".

**Структура папок:** `GomonClinic / Ім'я Клієнта / YYYY-MM-DD_Процедура`

**Файли:**
- `gdrive.py` — Google Drive API v3 wrapper (JWT auth через openssl, Python 3.6 сумісний)
  - `_get_access_token()` — кешований на 50 хв
  - `create_visit_folder(client_name, date, procedure)` → `(visit_url, client_url)`
  - `count_files_in_folder(folder_id)` — підрахунок завантажених фото
  - `_find_or_create_folder()` — dedup (не створює дублікатів)
- `photo_reminder.py` — cron-скрипт:
  - `--create` (21:30 Kyiv): створює папки для всіх незмасованих записів дня → TG спеціалістам зі списком + лінками
  - `--check` (11:00 Kyiv): перевіряє кожну папку → якщо є файли → TG адміну з підсумком
  - `--date YYYY-MM-DD` — override дати для ручного запуску

**Конфіг:**
- SA key: `/home/gomoncli/private_data/gdrive_sa.json` (НЕ в git)
- Root folder ID: `1Cj2MseN7toVQ_R4u8_PBVDnKAfngOA-N` (hardcoded в gdrive.py)

**DB:** `manual_appointments.drive_folder_url TEXT` — URL папки Drive для запису

**Frontend:** кнопка 📷 "Фото до/після" в action sheet для записів з `drive_folder_url`

### Картка клієнта (адмін-календар)

При натисканні на запис в календарі відкривається action sheet. Ім'я клієнта — **клікабельне** (золотий, підкреслений). Клік → модалка `#client-card-modal`:
- Ім'я + клікабельний телефон
- Повна історія візитів (WLaunch API realtime + local DB + manual appointments)
- Спеціаліст (В/А кольором), скасовані — перекреслені
- API: `GET /api/admin/client-card/<phone>`

### Відомі обмеження (не виправлено, прийнятні)

- **PTR в TWA** — не працює, задокументовано в TODO_PTR.md
- **IG messenger** — App Review pending, receive не працює
- **Safari voice recording** — обмежена підтримка MediaRecorder codecs
- **Calendar timezone** — "now" лінія використовує device time (не Kyiv)
- **Conversation list** — LIMIT 50, без пагінації

### Відомі пастки (з досвіду)

- **`doRefresh()` в PTR IIFE** — не ламати `try { if/else if } catch` структуру. Syntax error вбиває ВСЕ нижче, включаючи `_fmtDateStr` і весь admin функціонал
- **Phone display regex** — `/^380/` → `'0'` (НЕ `/^38/` — це дає `00...`)
- **Calendar onclick ID** — завжди передавати як string: `openApptAction('id')` + порівнювати `String(x.id) === String(id)`. Працює для numeric (manual) і string (WLaunch) IDs
- **CSS `transform` на hover** — НЕ видаляти `.adm-tl-appt:hover{transform:scale(1.01)}` — без нього інші CSS зміни можуть зламати stacking order

### Instagram AI — план (після App Review)

Коли IG App Review пройде, додамо AI auto-reply для Instagram DM:
1. Webhook endpoint для вхідних IG messages (замість polling)
2. Та ж `_build_system_prompt()` + `_call_anthropic()` логіка з контекстом "Instagram"
3. Відповідь через Graph API v25.0 `/me/messages`
4. Ескалація аналогічна TG

---

## Відоме: Webuzo Apache на VPS

VPS має встановлений Webuzo з Apache (httpd). Apache **замаскований** (`systemctl mask httpd`), але Webuzo може спробувати його рестартити (нічний cron). Якщо nginx падає з `bind :80 failed` — перевірити `ss -tlnp | grep :80` на наявність httpd і вбити його.
