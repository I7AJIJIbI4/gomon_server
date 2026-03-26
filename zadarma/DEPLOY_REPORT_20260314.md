# Звіт деплою: Оновлення системи Dr. Gomon
**Дата:** 2026-03-14
**Сервер:** `gomoncli@31.131.18.79:21098`

---

## Задеплоєні файли

| Файл | Розташування | Дія |
|---|---|---|
| `wlaunch_api.py` | `/home/gomoncli/zadarma/` | ЗАМІНЕНО |
| `user_db.py` | `/home/gomoncli/zadarma/` | ЗАМІНЕНО |
| `sms_fly.py` | `/home/gomoncli/zadarma/` | НОВИЙ |
| `callback_request_handler.php` | `/home/gomoncli/public_html/` | НОВИЙ |

**Змінені файли (під час деплою):**

| Файл | Зміна |
|---|---|
| `public_html/zadarma_ivr_webhook.php` | Додано internal `204` + `case 'callback_request'` |

---

## Ключові зміни

### `wlaunch_api.py` — критичне виправлення
**Проблема:** Старий код читав `branch.notification_settings.telegram` — отримував лише 2 контакти (адміни сповіщень).
**Рішення:** Новий код читає `/appointment` endpoint — тягне всі записи за 3 роки.

- **Було:** ~2 клієнти в базі
- **Стало:** 553 клієнти після першої синхронізації (2814 appointment-записів, 29 сторінок)
- Нові поля: `last_service`, `last_visit`, `visits_count`

### `user_db.py` — розширення схеми
- `add_or_update_client()` отримав 3 нові параметри з дефолтами: `last_service=""`, `last_visit=""`, `visits_count=0` — зворотньо сумісно
- `find_client_by_phone()` повертає нові поля
- `update_clients()` зберігає нові поля
- `init_db()` має автоміграцію — нові колонки додаються самостійно
- Повернуто `sync_specific_client()` (використовується `sync_management.py`)
- Видалено `add_test_client()` — debug-функція

### `sms_fly.py` — новий модуль
- Відправка SMS через `http://sms-fly.com/api/api.php`
- Нормалізація номерів: `0XXXXXXXXX` / `80XXXXXXXXX` / `380XXXXXXXXX` → `380XXXXXXXXX`
- ⚠️ Credentials захардкоджені — рекомендується вивести в `config.py`

### `callback_request_handler.php` — новий модуль
- Обробляє заявку "зворотній зв'язок" від IVR (internal `204`)
- SQLite lookup клієнта за номером (prepared statements, без SQL injection)
- SMS калеру через SMSFly: персоналізоване (для відомих) / загальне (для нових)
- Telegram-сповіщення спеціалісту: ім'я клієнта + остання процедура + кількість візитів
- ⚠️ Credentials захардкоджені — рекомендується вивести в конфіг

### `zadarma_ivr_webhook.php` — інтеграція
```php
// Додано в internal_numbers:
'204' => ['name' => 'IVR Callback', 'action' => 'callback_request', 'target' => null]

// Додано в handleCorrectSource():
case 'callback_request':
    require_once __DIR__ . '/callback_request_handler.php';
    handleCallbackRequest($caller_id);
    break;
```

---

## Міграція БД

Виконана вручну (один раз):
```sql
ALTER TABLE clients ADD COLUMN last_service TEXT DEFAULT '';
ALTER TABLE clients ADD COLUMN last_visit TEXT DEFAULT '';
ALTER TABLE clients ADD COLUMN visits_count INTEGER DEFAULT 0;
```

Схема після міграції:
```sql
CREATE TABLE clients (
    id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT, phone TEXT UNIQUE,
    last_service TEXT DEFAULT '', last_visit TEXT DEFAULT '', visits_count INTEGER DEFAULT 0
);
```

> Надалі `init_db()` робить міграцію автоматично при кожному старті.

---

## Результати

| Перевірка | Результат |
|---|---|
| WLaunch API connection | ✅ 1 філія "Dr. Gomon Cosmetology" |
| Записів в системі | ✅ 2845 appointments |
| Синхронізовано клієнтів | ✅ **553** (з 2814 записів, 29 сторінок) |
| Клієнтів в базі після sync | ✅ **566** |
| DB schema | ✅ 7 колонок |
| `sync_specific_client` в user_db | ✅ присутня |
| Backup | ✅ `*_backup_20260314_210031.*` |

---

## Cron (після деплою)

```
*/5  * * * *       check_and_run_bot.sh             — watchdog бота
0    6,18 * * *    fetch_all_clients (wlaunch_api)   — NEW: appointment sync
0    8 * * *       sync_with_notification.sh          — client sync + TG звіт
0    19 * * *      daily_api_report.sh
0    23 * * *      sync_with_notification.sh          — client sync + TG звіт
0    3 * * *       daily_maintenance.sh
*/30 9-18 * * 1-5  critical_api_check.sh
0    5 * * 0       sync_clients.py (weekly)
@reboot            check_and_run_bot.sh
```

---

## Архітектура після оновлення

```
Дзвінок на 073-310-31-10
    │
    ├─ Internal 201 ─→ відкриття хвіртки
    ├─ Internal 202 ─→ відкриття воріт
    ├─ Internal 203 ─→ SMS з посиланням на бот
    └─ Internal 204 ─→ callback_request_handler.php  ← НОВЕ
                         ├─ SQLite lookup (clients: ім'я, послуга, візити)
                         ├─ SMS CallerID (персоналізоване)
                         └─ Telegram → спеціалісту

Cron 06:00 і 18:00:
    wlaunch_api.fetch_all_clients()
        → /appointment API (3 роки, ~29 сторінок)
        → clients: last_service, last_visit, visits_count
```

---

## Клієнтський IVR — схема (оновлено 2026-03-14)

```
Клієнт дзвонить на 073-310-31-10
    │
    IVR greeting (голосовий запис, Zadarma panel)
    │
    ├─ Кнопка 1 → internal 204 → zadarma_ivr_webhook.php
    │               └─ callback_request_handler.php
    │                    ├─ SQLite: lookup клієнта (ім'я, послуга, візити)
    │                    ├─ SMS клієнту (текст у SMS_TEXT_* константах)
    │                    └─ Telegram → спеціалісту (ім'я, процедура, к-сть візитів)
    │
    ├─ Кнопка 2 → голосове повідомлення (Zadarma panel)
    │               └─ PHP не потрібен
    │
    └─ Кнопка 3 → internal 205 → zadarma_ivr_webhook.php
                    └─ makeCallback($config['doctor_phone'])
                         └─ Zadarma API ініціює дзвінок лікарю
```

## Що ще залишилось (потрібно від тебе)

### 1. Номер лікаря — заповнити в `zadarma_ivr_webhook.php`
```php
'doctor_phone' => 'ВСТАВИТИ_НОМЕР_ЛІКАРЯ',  // ← замінити на реальний номер
```

### 2. SMS текст — за бажанням відредагувати в `callback_request_handler.php`
```php
define('SMS_TEXT_KNOWN_CLIENT',   '{name}, дякуємо за дзвінок! ...');
define('SMS_TEXT_UNKNOWN_CLIENT', 'Dr.Gomon - дякуємо за звернення! ...');
```

### 3. Zadarma PBX — налаштувати IVR сценарій
У панелі Zadarma (АТС → IVR-сценарії):

| Дія | Що зробити |
|---|---|
| Створити новий IVR | Призначити на вхідний номер 073-310-31-10 |
| Записати/завантажити greeting | "Натисніть 1 щоб залишити заявку, 2 ..., 3 щоб зв'язатись з лікарем" |
| Кнопка 1 | Переадресація на **внутрішній номер 204** |
| Кнопка 2 | Відтворити голосове + завершити (без переадресації) |
| Кнопка 3 | Переадресація на **внутрішній номер 205** |

### 4. `last_service` порожній — перевірити API
Для частини клієнтів поле пусте. Можлива причина: appointments не мають `operations`. Перевірити:
```bash
ssh -i ~/.ssh/id_rsa_termius -p 21098 gomoncli@31.131.18.79
cd zadarma
python3 -c "
from wlaunch_api import get_branch_id, WLAUNCH_API_URL, HEADERS
import requests
branch_id = get_branch_id()
url = f'{WLAUNCH_API_URL}/company/3f3027ca-0b21-11ed-8355-65920565acdd/branch/{branch_id}/appointment'
r = requests.get(url, headers=HEADERS, params={'page':0,'size':1,'sort':'start_time,desc'}, timeout=10)
import json; print(json.dumps(r.json()['content'][0], indent=2, ensure_ascii=False))
"
```

### 5. Credentials — рекомендовано вивести в `config.py`
SMS login/password захардкоджені в `sms_fly.py` і `callback_request_handler.php`.

---

## Rollback

```bash
cd /home/gomoncli/zadarma
cp wlaunch_api_backup_20260314_210031.py wlaunch_api.py
cp user_db_backup_20260314_210031.py user_db.py
cp users_backup_20260314_210031.db users.db
```
