# Деплой: Оновлення системи Dr. Gomon

## Файли для завантаження

| Файл | Куди | Дія |
|---|---|---|
| `sms_fly.py` | `/home/gomoncli/zadarma/` | **НОВИЙ** |
| `wlaunch_api.py` | `/home/gomoncli/zadarma/` | **ЗАМІНИТИ** |
| `user_db.py` | `/home/gomoncli/zadarma/` | **ЗАМІНИТИ** |
| `callback_request_handler.php` | `/home/gomoncli/public_html/` | **НОВИЙ** |

---

## Крок 1: Backup

```bash
cd /home/gomoncli/zadarma

# Backup файлів
cp wlaunch_api.py wlaunch_api_backup_$(date +%Y%m%d).py
cp user_db.py user_db_backup_$(date +%Y%m%d).py
cp users.db users_backup_$(date +%Y%m%d).db

# Backup PHP
cp /home/gomoncli/public_html/zadarma_ivr_webhook.php \
   /home/gomoncli/public_html/zadarma_ivr_webhook_backup_$(date +%Y%m%d).php
```

---

## Крок 2: Завантажити нові файли

Скопіювати 4 файли на сервер (через SCP, FTP або вставити вручну).

---

## Крок 3: Міграція бази даних

Нові колонки додадуться автоматично при першому запуску (`init_db()` має міграцію).
Але для перевірки можна запустити вручну:

```bash
cd /home/gomoncli/zadarma

# Перевірити поточний стан бази
sqlite3 users.db ".schema clients"

# Якщо колонок last_service, last_visit, visits_count немає - додати:
sqlite3 users.db "ALTER TABLE clients ADD COLUMN last_service TEXT DEFAULT '';"
sqlite3 users.db "ALTER TABLE clients ADD COLUMN last_visit TEXT DEFAULT '';"
sqlite3 users.db "ALTER TABLE clients ADD COLUMN visits_count INTEGER DEFAULT 0;"

# Перевірити результат
sqlite3 users.db ".schema clients"
# Має бути: id, first_name, last_name, phone, last_service, last_visit, visits_count
```

---

## Крок 4: Тестування Python (без перезапуску бота)

```bash
cd /home/gomoncli/zadarma

# 4.1. Тест підключення до WLaunch API
python3 -c "
from wlaunch_api import test_wlaunch_connection
test_wlaunch_connection()
"
# Очікується: ✅ Підключення працює. Записів в системі: XXX

# 4.2. Тест синхронізації клієнтів
python3 -c "
from wlaunch_api import fetch_all_clients
total = fetch_all_clients()
print('Клієнтів: {}'.format(total))
"
# Очікується: Клієнтів: 400+ (замість попередніх 2)

# 4.3. Перевірка бази після синхронізації
sqlite3 users.db "SELECT first_name, last_name, phone, last_service, last_visit, visits_count FROM clients ORDER BY visits_count DESC LIMIT 10;"

# 4.4. Тест пошуку конкретного клієнта
python3 -c "
from user_db import find_client_by_phone
result = find_client_by_phone('380996093860')
print(result)
"
# Очікується: {'id': '...', 'first_name': '...', 'last_service': '...', 'visits_count': N}

# 4.5. Тест SMSFly (на свій номер)
python3 -c "
from sms_fly import send_sms
send_sms('380933297777', 'Тест SMS від Dr. Gomon системи')
"
```

---

## Крок 5: Підключити callback handler до IVR

В існуючому `zadarma_ivr_webhook.php` додати новий case для DTMF.

### Варіант A: Новий пункт на першому рівні IVR (цифра 1)

В Zadarma PBX (панель) додати голосове привітання:
> "Натисніть 1, щоб залишити заявку на зворотній зв'язок. Натисніть 2 для доступу."

В PHP `handleIvrResponse` додати case:

```php
// На початку файлу додати:
require_once __DIR__ . '/callback_request_handler.php';

// В switch($digits) додати:
case '1':
    // Заявка на зворотній зв'язок
    writeLog("📞 IVR: Заявка від $caller_id");
    $ivr_response = handleCallbackRequest($caller_id);
    echo json_encode($ivr_response);
    break;
```

### Варіант B: Новий пункт у другому меню (цифра 24)

```php
case '24':
    // Заявка на зворотній зв'язок (друге меню, опція 4)
    writeLog("📞 IVR: Заявка від $caller_id (меню 2)");
    $ivr_response = handleCallbackRequest($caller_id);
    echo json_encode($ivr_response);
    break;
```

---

## Крок 6: Тестування PHP callback handler

```bash
# Тест прямий (без IVR)
curl -X POST "https://gomonclinic.com/callback_request_handler.php" \
  -d "test=1&caller_id=380996093860"

# Тест через IVR webhook (якщо додали як цифру 1)
curl -X POST "https://gomonclinic.com/zadarma_webhook.php" \
  -d "event=NOTIFY_IVR&caller_id=380933297777&called_did=380733103110&wait_dtmf[digits]=1"

# Перевірити логи
tail -20 /home/gomoncli/zadarma/callback_requests.log
```

**Очікуваний результат:**
- SMS на номер калера
- Telegram повідомлення спеціалісту з іменем клієнта, послугою і кількістю візитів

---

## Крок 7: Оновити cron для синхронізації

Перевірити існуючий cron:
```bash
crontab -l | grep -i "sync\|wlaunch\|fetch"
```

Якщо синхронізація вже налаштована - вона автоматично почне
тягнути повну інформацію (послуги, візити).

Якщо ні - додати:
```bash
crontab -e

# Синхронізація клієнтів — двічі на добу (06:00 і 18:00)
0 6,18 * * * cd /home/gomoncli/zadarma && /usr/bin/python3 -c "from wlaunch_api import fetch_all_clients; fetch_all_clients()" >> /home/gomoncli/zadarma/sync.log 2>&1
```

---

## Rollback (якщо щось пішло не так)

```bash
cd /home/gomoncli/zadarma

# Відновити файли
cp wlaunch_api_backup_YYYYMMDD.py wlaunch_api.py
cp user_db_backup_YYYYMMDD.py user_db.py
cp users_backup_YYYYMMDD.db users.db

# Відновити PHP
cp /home/gomoncli/public_html/zadarma_ivr_webhook_backup_YYYYMMDD.php \
   /home/gomoncli/public_html/zadarma_ivr_webhook.php

# Перезапустити бота
pkill -f bot.py
cd /home/gomoncli/zadarma && nohup python3 bot.py &
```

---

## Архітектура після оновлення

```
Дзвінок на 073-310-31-10
    │
    ├─ IVR: "1" ─→ callback_request_handler.php
    │                ├─ SQLite lookup (clients)
    │                ├─ SMS через SMSFly (персоналізоване)
    │                └─ Telegram сповіщення спеціалісту
    │
    ├─ IVR: "21" ─→ відкриття хвіртки (існуюче)
    ├─ IVR: "22" ─→ відкриття воріт (існуюче)
    └─ IVR: "23" ─→ SMS з лінкою на бот (існуюче)

Cron (06:00, 18:00):
    wlaunch_api.py → appointments API
        → clients таблиця (phone, ім'я, послуга, дата, візити)
```
