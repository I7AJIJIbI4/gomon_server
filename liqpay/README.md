# Dr. Gomon — LiqPay Payment System

## Структура файлів

```
На сервері (gomonclinic.com):
├── liqpay_callback.php        ← ловить webhook від LiqPay
├── pay.php                    ← форма клієнта (одноразові посилання)
├── consult.php                ← постійна сторінка онлайн консультації
├── payment-success.php        ← success сторінка
├── already_paid.php           ← показується при повторному відкритті
│
└── gomon_payments/            ← папка Python скриптів
    ├── config.py              ← налаштування (редагуй цей файл)
    ├── liqpay.py              ← LiqPay API core
    ├── liqpay_php.php         ← LiqPay helper для PHP
    ├── init_db.py             ← ініціалізація БД (запустити один раз)
    ├── notify.py              ← Telegram сповіщення лікарю
    ├── receipt.py             ← PDF + email квитанція
    ├── bot_payment.py         ← aiogram handlers для /pay
    ├── payments.db            ← SQLite БД (створюється автоматично)
    ├── .public_key            ← LiqPay public key (текстовий файл)
    └── .private_key           ← LiqPay private key (текстовий файл)
```

## Розгортання

### 1. Завантажити файли
Завантажити всі файли на сервер через FTP або Git.

### 2. Створити файли ключів
```
gomon_payments/.public_key    ← вставити LiqPay public key
gomon_payments/.private_key   ← вставити LiqPay private key
```

### 3. Відредагувати config.py
```python
LIQPAY_PUBLIC_KEY  = 'your_public_key'
LIQPAY_PRIVATE_KEY = 'your_private_key'
TELEGRAM_BOT_TOKEN = 'your_bot_token'
DOCTOR_CHAT_ID     = 123456789  # Telegram ID лікаря
SMTP_HOST          = 'mail.gomonclinic.com'
SMTP_USER          = 'noreply@gomonclinic.com'
SMTP_PASSWORD      = 'your_password'
```

### 4. Ініціалізувати БД (один раз)
```bash
cd ~/public_html/gomon_payments
python3.6 init_db.py
```

### 5. Встановити reportlab для PDF
```bash
pip3.6 install reportlab --user
# або через cPanel Terminal:
pip install reportlab --user
```

### 6. Підключити bot_payment.py до бота
```python
# У main.py бота:
from gomon_payments.bot_payment import register_payment_handlers
register_payment_handlers(dp)
```

### 7. Додати ADMIN_IDS у bot_payment.py
```python
ADMIN_IDS = {твій_telegram_id}
```

### 8. Налаштувати .htaccess (опціонально — красиві URL)
```apache
RewriteEngine On
RewriteRule ^pay/([a-z0-9_]+)/?$  pay.php?oid=$1 [L,QSA]
RewriteRule ^consult/?$           consult.php    [L]
RewriteRule ^payment-success/?$   payment-success.php [L,QSA]
```

## Флоу

```
Лікар: /pay → вводить суму → вводить опис
     → Бот генерує order_id → зберігає в БД
     → Надсилає посилання: gomonclinic.com/pay.php?oid=clinic_abc12345

Клієнт: відкриває посилання
     → Вводить телефон (обов'язково), ім'я, email, Instagram
     → POST → дані зберігаються в БД → редирект на LiqPay

LiqPay: клієнт платить
     → POST callback на liqpay_callback.php
     → PHP записує транзакцію в БД
     → exec(notify.py clinic_abc12345) → Telegram лікарю
     → exec(receipt.py clinic_abc12345) → PDF на email (якщо вказано)
     → Редирект клієнта на payment-success.php

Постійна консультація: gomonclinic.com/consult.php
     → Кожне відкриття або reuse pending order_id
     → Та ж форма + оплата 500 грн
```

## Команди бота

| Команда | Опис |
|---------|------|
| `/pay` | Новий платіж (FSM діалог) |
| `/status clinic_abc12345` | Статус замовлення з БД |
| `/refund clinic_abc12345` | Повне повернення |
| `/refund clinic_abc12345 300` | Часткове повернення |
| `/cancel` | Скасувати поточний діалог |

## Тестові картки LiqPay (sandbox)

| Картка | Результат |
|--------|-----------|
| 4242 4242 4242 4242 | Success |
| 4000 0000 0000 0002 | Failure |

Для тесту додати `'sandbox': 1` у параметри в `liqpay.py → create_payment_url`.

## Захист .private_key та .public_key

Додати в .htaccess:
```apache
<Files ".private_key">
    Order allow,deny
    Deny from all
</Files>
<Files ".public_key">
    Order allow,deny
    Deny from all
</Files>
```
