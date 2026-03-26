# Звіт деплою: IVR callback + Telegram лікарю
**Дата:** 2026-03-16
**Сервер:** `gomoncli@31.131.18.79:21098`

---

## Змінені файли

| Файл | Дія |
|---|---|
| `public_html/zadarma_ivr_webhook.php` | Додано internal 106/206 для кнопки 2 |
| `public_html/callback_request_handler.php` | SMS API v2, Telegram → лікар, SMS вимкнено |

---

## Ключові зміни

### `zadarma_ivr_webhook.php` — кнопка 2 IVR
Додано internal номери для кнопки 2 в голосовому меню:

```php
'106' => ['name' => 'IVR Кнопка 2 — Callback (direct ext)', 'action' => 'callback_request', 'target' => null],
'206' => ['name' => 'IVR Кнопка 2 — Callback (via menu)', 'action' => 'callback_request', 'target' => null],
```

Обидва варіанти (106/206) покривають різні способи переадресації в Zadarma панелі. Реальний номер з'ясується після першого тест-дзвінка з `ivr_webhook.log`.

---

### `callback_request_handler.php` — три зміни

#### 1. SMS API → v2
**Було:** старий `sms-fly.com/api/api.php` (form POST з login/password)
**Стало:** новий `sms-fly.ua/api/v2/api.php` (JSON з API key) — узгоджено з `zadarma_ivr_webhook.php`

```php
// Було
'sms_url'      => 'http://sms-fly.com/api/api.php',
'sms_login'    => '380933297777',
'sms_password' => 'pJYAWmZpWOvUozqAUvsTaBjxTpu9oJEk',

// Стало
'sms_url'     => 'https://sms-fly.ua/api/v2/api.php',
'sms_api_key' => 'pJYAWmZpWOvUozqAUvsTaBjxTpu9oJEk',
'sms_source'  => 'Dr. Gomon',
```

#### 2. Telegram → лікар Вікторія
**Було:** `tg_chat_id = 573368771` (перший адмін — отримує звіти/помилки)
**Стало:** `tg_chat_id = 7930079513` (лікар Вікторія, +380996093860)

#### 3. SMS клієнту — вимкнено
SMS відправка закоментована, бо текст ще не узгоджений.

```php
// ВИМКНЕНО — розкоментувати після узгодження тексту:
// if ($caller_id && strpos($caller_id, 'Anonymous') === false) {
//     $sms_sent = sendCallbackSMS($caller_id, $client);
// }
```

Текст редагується в константах у верхній частині файлу:
```php
define('SMS_TEXT_KNOWN_CLIENT',   '{name}, дякуємо за дзвінок! Запис: ig.me/m/dr.gomon | t.me/DrGomonCosmetology');
define('SMS_TEXT_UNKNOWN_CLIENT', 'Dr.Gomon - дякуємо за звернення! Запис: ig.me/m/dr.gomon | t.me/DrGomonCosmetology');
```

---

## Логіка кнопки 2 (фінальна)

```
Клієнт натискає кнопку 2 в голосовому меню
    │
    └─ internal 206 → zadarma_ivr_webhook.php
         └─ callback_request_handler.php
              ├─ SQLite lookup (ім'я, остання процедура, візити)
              ├─ SMS клієнту — ВИМКНЕНО (текст не узгоджений)
              └─ Telegram → лікар Вікторія (7930079513)
```

---

## Приклад Telegram сповіщення лікарю

**Відомий клієнт:**
```
📞 Заявка на зворотній зв'язок
👤 Иван Павловський
📱 0933297777
🕐 14:32 16.03.2026
━━━━━━━━━━━━━
Візитів: 5
Остання процедура: Ботокс
Останній візит: 2025-11-14
```

**Новий клієнт (не в базі):**
```
📞 Заявка на зворотній зв'язок
👤 Новий клієнт
📱 0933297777
🕐 14:32 16.03.2026
```

---

## Розподіл Telegram сповіщень

| Одержувач | chat_id | Що отримує |
|---|---|---|
| Перший адмін | 573368771 | Звіти, помилки, апдейти системи |
| Лікар Вікторія | 7930079513 | Запити зворотного зв'язку (кнопка 2 IVR) |

---

## Що залишилось

### 1. Zadarma панель — перевірити internal номер кнопки 2
Після першого тест-дзвінка перевірити `ivr_webhook.log`:
```bash
cat /home/gomoncli/zadarma/ivr_webhook.log | grep "NOTIFY_INTERNAL"
```
Якщо internal номер не 106/206 — додати потрібний до `internal_numbers` в `zadarma_ivr_webhook.php`.

### 2. SMS текст — узгодити і увімкнути
Відредагувати константи в `callback_request_handler.php` (рядки 18-19), потім розкоментувати блок SMS (рядки 263-267).
