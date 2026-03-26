# SMS-тексти для IVR кнопка 2 (заявка на зворотній зв'язок)

> Клієнт натиснув кнопку 2 в IVR → надсилається SMS-підтвердження.
> Усі варіанти = **2 SMS** (кирилиця, UCS-2, 70 симв./SMS).
> Код: `callback_request_handler.php`, константи `SMS_TEXT_KNOWN_CLIENT` / `SMS_TEXT_UNKNOWN_CLIENT`.
> `{name}` — підставляється ім'я клієнта (тільки для known).

---

## Варіант 1 — Лаконічний, один канал (Instagram)

```
KNOWN:   {name}, дякуємо за дзвінок! Передзвонимо найближчим часом. Запис онлайн: ig.me/m/dr.gomon
UNKNOWN: Dr.Gomon: дякуємо за дзвінок! Передзвонимо найближчим часом. Запис онлайн: ig.me/m/dr.gomon
```

| | Символів | SMS |
|---|---|---|
| Known (ім'я ~5 симв.) | 88 | 2 |
| Unknown | 91 | 2 |

Простий, чіткий. Підтвердження + один шлях для запису. Нічого зайвого.

---

## Варіант 2 — З брендовим слоганом сайту ⭐ рекомендований

```
KNOWN:   {name}, ваша заявка прийнята! Зателефонуємо. Краса — це коли відчуваєш себе собою: ig.me/m/dr.gomon
UNKNOWN: Dr.Gomon: ваша заявка прийнята! Зателефонуємо. Краса — це коли відчуваєш себе собою: ig.me/m/dr.gomon
```

| | Символів | SMS |
|---|---|---|
| Known (ім'я ~5 симв.) | 98 | 2 |
| Unknown | 101 | 2 |

Використовує слоган з головної сторінки gomonclinic.com — впізнаваний тон бренду.

---

## Варіант 3 — Обидва канали (Instagram + Telegram)

```
KNOWN:   {name}, дякуємо за дзвінок до Dr.Gomon! Передзвонимо незабаром. Пишіть: t.me/DrGomonCosmetology або ig.me/m/dr.gomon
UNKNOWN: Dr.Gomon Cosmetology: дякуємо! Передзвонимо найближчим часом. Пишіть: t.me/DrGomonCosmetology або ig.me/m/dr.gomon
```

| | Символів | SMS |
|---|---|---|
| Known (ім'я ~5 симв.) | 115 | 2 |
| Unknown | 114 | 2 |

Дає клієнту вибір каналу. Підходить якщо аудиторія активна і в Telegram, і в Instagram.

---

## Де змінити

Файл: `/home/gomoncli/public_html/callback_request_handler.php`

```php
define('SMS_TEXT_KNOWN_CLIENT',   '...');   // ← {name} підставляється автоматично
define('SMS_TEXT_UNKNOWN_CLIENT', '...');
```

Щоб увімкнути відправку SMS — розкоментувати в `handleCallbackRequest()`:
```php
// $sms_sent = sendCallbackSMS($caller_id, $client);
```

---

## Джерело тексту

Сайт: https://gomonclinic.com  
Слоган: "Краса — це коли відчуваєш себе собою"  
Instagram: ig.me/m/dr.gomon (@dr.gomon)  
Telegram: t.me/DrGomonCosmetology (@DrGomonCosmetology)  
