# Підсумок налаштування синхронізації

## ✅ Проблему вирішено

Запис користувача **093329777** на **12:30** тепер відображається в додатку.

## Що було зроблено

### 1. Створено оптимізований скрипт синхронізації appointments
- **Файл**: `/home/gomoncli/zadarma/sync_appointments.py`
- **Що робить**: Синхронізує appointments за останні 7 днів + наступні 90 днів
- **Час виконання**: ~10-15 секунд (замість 2-3 хвилин для повної синхронізації)

### 2. Створено webhook handler (для майбутнього використання)
- **Файл**: `/home/gomoncli/zadarma/wlaunch_webhook.py`
- **Порт**: 5003
- **Статус**: Запущений і готовий до використання
- **Proxy**: `/home/gomoncli/public_html/wlaunch_webhook.php`

### 3. Інструкції для налаштування cron
- **Файл**: `/home/gomoncli/zadarma/CRON_SETUP.txt`
- Детальні інструкції для додавання через cPanel

## Схема синхронізації

```
┌─────────────────────────────────────────────────────────┐
│  СИНХРОНІЗАЦІЯ КЛІЄНТІВ (двічі на день)                │
│  09:00 та 21:00                                         │
│  ├─ sync_with_notification.sh                          │
│  └─ sync_clients.py                                     │
│     └─ Оновлює НОВИХ клієнтів з Wlaunch                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  СИНХРОНІЗАЦІЯ APPOINTMENTS (кожну годину)              │
│  Кожну годину: 00:00, 01:00, 02:00...                  │
│  └─ sync_appointments.py                                │
│     ├─ Останні 7 днів (минулі візити)                  │
│     └─ Наступні 90 днів (майбутні записи)              │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  РЕЗУЛЬТАТ                                              │
│  ✅ Новий запис існуючого клієнта → оновиться годину    │
│  ✅ Новий клієнт з записом → оновиться годину + двічі   │
│  ✅ Зміна запису → оновиться годину                     │
└─────────────────────────────────────────────────────────┘
```

## Налаштування через cPanel

1. Відкрийте: **cPanel → Advanced → Cron Jobs**
2. Додайте 2 основні завдання:

### Завдання 1: Синхронізація клієнтів
```
Minute: 0
Hour: 9,21
Command: /home/gomoncli/zadarma/sync_with_notification.sh >> /home/gomoncli/zadarma/cron.log 2>&1
```

### Завдання 2: Синхронізація appointments
```
Minute: 0
Hour: *
Command: cd /home/gomoncli/zadarma && /usr/bin/python3 sync_appointments.py >> /home/gomoncli/zadarma/cron.log 2>&1
```

## Перевірка роботи

### Перевірити логи синхронізації appointments:
```bash
tail -50 /home/gomoncli/zadarma/sync_appointments.log
```

### Перевірити логи синхронізації клієнтів:
```bash
tail -50 /home/gomoncli/zadarma/sync_notification.log
```

### Перевірити записи конкретного клієнта:
```bash
sqlite3 /home/gomoncli/zadarma/users.db "SELECT services_json FROM clients WHERE phone LIKE %93329777%"
```

## Тестування

Запустити синхронізацію вручну:
```bash
cd /home/gomoncli/zadarma
python3 sync_appointments.py
```

Очікуваний результат:
```
✅ Оброблено X appointments, оновлено Y клієнтів
```

## Файли та шляхи

- Основний скрипт: `/home/gomoncli/zadarma/sync_appointments.py`
- Логи: `/home/gomoncli/zadarma/sync_appointments.log`
- База даних: `/home/gomoncli/zadarma/users.db`
- Інструкції cron: `/home/gomoncli/zadarma/CRON_SETUP.txt`

## Підтримка

При виникненні проблем перевірте:
1. Логи синхронізації
2. Доступність Wlaunch API
3. Правильність налаштування cron в cPanel
