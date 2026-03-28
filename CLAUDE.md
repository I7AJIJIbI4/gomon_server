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
| `zadarma/sms_reminder.py` | SMS нагадування |

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

---

## База даних (users.db)

### Таблиця `clients`
```sql
id TEXT, first_name TEXT, last_name TEXT, phone TEXT,
last_service TEXT, last_visit TEXT, visits_count INT,
services_json TEXT  -- JSON масив [{appt_id, date, hour, service, status}]
```
- `phone` — нормалізований номер (тільки цифри), напр. `380933297777`
- `services_json` — топ-5 записів, відсортовано за датою (новіші першими)
- Статуси: `CONFIRMED_BY_CLIENT`, `CANCELLED`, `CONFIRMED`, тощо

### Таблиця `users`
```sql
telegram_id INTEGER PRIMARY KEY, phone TEXT, username TEXT, first_name TEXT
```
- **Telegram-бот юзери** (69 станом на 2026-03-28) — НЕ PWA-юзери
- Заповнюється через bot.py коли юзер пише боту

### БД `otp_sessions.db` (окремий файл)
```sql
sessions: token TEXT PK, phone TEXT, created_at INT, expires_at INT
otp_codes: phone TEXT PK, code TEXT, expires_at INT, attempts INT
leads: phone TEXT PK, name TEXT, procedure TEXT, created_at TEXT, source TEXT
```
- **PWA-юзери** — унікальні телефони в `sessions` (3 станом на 2026-03-28)
- Сесія: 30 днів sliding window
- `/api/admin/stats` → `pwa_users` = COUNT(DISTINCT phone) FROM sessions

### Таблиця `push_subscriptions`
```sql
id INT, phone TEXT, endpoint TEXT, p256dh TEXT, auth TEXT, active INT
```

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
| `/api/me` | GET | Дані авторизованого клієнта (ім'я, телефон) |
| `/api/me/appointments` | GET | Записи клієнта (upcoming + done), фільтрує CANCELLED |
| `/api/me/appointments/cancel` | POST | Скасовує запис: POST до WLaunch `{"appointment":{"id":...,"status":"CANCELLED"}}` + оновлює БД |
| `/api/prices` | GET | Прайс з `/home/gomoncli/private_data/prices.json` |
| `/api/feed` | GET | Пости з Telegram (feed.db) |
| `/api/feed/media/<fid>` | GET | Редірект на Telegram CDN за file_id |
| `/api/health` | GET | Стан БД, кількість клієнтів |

### Push
| Endpoint | Метод | Опис |
|----------|-------|------|
| `/api/push/vapid-key` | GET | Публічний VAPID ключ |
| `/api/push/subscribe` | POST | Зберігає підписку |
| `/api/push/unsubscribe` | POST | Видаляє підписку |
| `/api/push/status` | GET | Чи є активні підписки у юзера |
| `/api/push/procedure-reminder` | POST | Push + SMS нагадування про процедуру |
| `/api/sms/procedure-reminder` | POST | SMS для гостьового юзера |

### Адмін (require_admin — тільки ADMIN_PHONE)
| Endpoint | Метод | Опис |
|----------|-------|------|
| `/api/admin/stats` | GET | Статистика: clients, `pwa_users` (otp_sessions.db), `pwa_active`, push_subs, visits_month |
| `/api/admin/appointments` | GET | Всі записи всіх клієнтів |
| `/api/admin/clients-list` | GET | Список клієнтів з appointments для модалки |
| `/api/admin/users-list` | GET | PWA-юзери з otp_sessions.db (унікальні телефони + дати логінів) |
| `/api/admin/push-list` | GET | Push-підписники (JOIN clients) |
| `/api/admin/month-visits` | GET | Записи за поточний місяць з цінами з prices.json |
| `/api/admin/sync` | POST | Запускає sync_clients.py + sync_appointments.py послідовно |

---

## Sync Flow

```
/api/admin/sync (PWA кнопка)
├── sync_clients.py      → нові клієнти за 24г
└── sync_appointments.py → оновлює appointments ±7д/+90д

Telegram /admin (бот)
├── sync_with_notification.sh → sync_clients + Telegram звіт
└── sync_appointments.py

Cron (щогодини)
└── sync_appointments.py → оновлює статуси appointments

Cron (09:00 і 21:00)
└── sync_with_notification.sh → sync_clients
```

**Важливо:** `sync_appointments.py` оновлює статуси (CONFIRMED, CANCELLED) в БД.
Якщо запис у WLaunch має статус CANCELLED — він не буде показаний у додатку.

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
# 1. Внести зміни на сервері
ssh -i ~/.ssh/id_rsa -p 21098 gomoncli@31.131.18.79

# 2. Перевірити синтаксис
python3 -m py_compile /home/gomoncli/zadarma/pwa_api.py

# 3. Перезапустити (check_flask.sh перезапустить автоматично через ≤5хв,
#    але краще вручну для негайного ефекту)
pkill -f 'python3.*pwa_api'
nohup python3 /home/gomoncli/zadarma/pwa_api.py >> /home/gomoncli/zadarma/pwa_api.log 2>&1 &

# 4. ВАЖЛИВО: перевірити що новий процес стартував ПІСЛЯ зміни файлу
ps -o pid,lstart -p $(pgrep -f pwa_api)
# lstart повинен бути ПІЗНІШЕ ніж mtime pwa_api.py

# 5. Перевірити
curl -s http://127.0.0.1:5001/api/health

# 6. Скачати локально і закомітити
scp -i ~/.ssh/id_rsa -P 21098 gomoncli@31.131.18.79:/home/gomoncli/zadarma/pwa_api.py ./pwa_api.py
git add pwa_api.py && git commit -m "fix: ..." && git push
```

### Зміни у frontend (index.html)
```bash
# 1. Внести зміни в index.html на сервері
# 2. Обов'язково збільшити версію кешу в sw.js
sed -i 's/gomon-2026-03-28x/gomon-2026-03-28y/' /home/gomoncli/public_html/app/sw.js

# 3. Скачати локально і закомітити
scp ... index.html sw.js ./public_html/app/
git add public_html/app/ && git commit -m "feat: ..." && git push
```

### Перевірка що на сервері актуальне
```bash
curl -si https://www.gomonclinic.com/app/sw.js | grep -E 'last-modified|CACHE'
curl -s https://www.gomonclinic.com/app/index.html | grep -c 'ptr-loader'
```

---

## PWA Frontend — Ключові JS функції

### Навігація
- `showScreen(id)` — перехід між екранами (home, appointments, price, map, chat)
- `screens`: `screen-home`, `screen-appointments`, `screen-price`, `screen-map`, `screen-chat`, `screen-auth`
- `screen-admin-*` — адмін-екрани (виключені з PTR)

### Дані
- `appointments` — масив, кешується в `localStorage('gomon_appointments')`
- `loadAppointments()` — GET `/api/me/appointments`
- `renderAppointments()` — рендерить екран записів
- `renderHomeAppt()` — рендерить "наступний запис" на home-екрані

### Скасування запису
```javascript
cancelAppointment(apptId, date, service)
// → showConfirm() → POST /api/me/appointments/cancel
// → видаляє з localStorage → renderAppointments() → renderHomeAppt()
```

### Pull-to-refresh
- Виключені екрани: `auth`, всі `screen-admin*`, відкриті модалки
- Threshold: 72px свайп вниз при `scrollTop === 0`
- `doRefresh()` → завантажує дані залежно від активного екрану

### Admin stat cards
- `.stat-card[onclick="_admStatClick('clients|users|push|month')"]`
- `_admStatClick('clients')` → GET `/api/admin/clients-list` → модалка зі списком
- `_admStatClick('month')` → GET `/api/admin/month-visits` → список з цінами + сума

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
3. **API endpoints**: кожен `api('/xxx')` — endpoint має бути в pwa_api.py

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

## Відомі особливості

- **Python 3.6** на сервері — f-strings підтримуються, але деякі сучасні синтаксис-конструкції ні
- **LiteSpeed** веб-сервер, без CDN/проксі
- **WLaunch cancel**: використовує `POST {"appointment":{"id":...,"status":"CANCELLED"}}` (не PATCH, не DELETE)
- **Sync**: `sync_appointments.py` зберігає топ-5 записів по даті (новіші першими), включаючи CANCELLED
- **Parse services**: `pwa_api.py::parse_services()` фільтрує CANCELLED при поверненні клієнту
- **OTP доставка**: Viber (відправник `PROMO`, TTL 5хв) → SMS-фолбек. Керується через `SMS_FLY_VIBER_SENDER` в config.py
- **PWA vs Бот юзери**: `users` таблиця в users.db = Telegram-бот (69 осіб). Реальні PWA-юзери = `otp_sessions.db::sessions`
- **Фото локації**: `location-aerial.jpg`, `location-entrance.jpg` лежать у `/home/gomoncli/public_html/sitepro/`
