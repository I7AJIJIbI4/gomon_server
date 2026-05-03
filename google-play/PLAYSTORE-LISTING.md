# Dr. Gomon Cosmetology — Google Play Store Listing

## Поточний статус
- **Трек:** Closed Beta Testing
- **Version:** 1.2.0 (versionCode 6)
- **AAB:** потрібно збілдити через PWABuilder (drgomon.beauty)
- **Наступний крок:** повторна подача на Production

---

## Store Listing (Картка додатку)

### Основна інформація

| Поле | Значення |
|------|----------|
| **App name** | Dr. Gomon Cosmetology |
| **Short description** (80 символів) | Записи, баланс, AI-асистент — косметологія Dr. Gomon у Черкасах |
| **Default language** | Ukrainian — uk |
| **App category** | Beauty |
| **Content rating** | Everyone |
| **Contact email** | viktoriia@gomonclinic.com |
| **Contact phone** | +380733103110 |
| **Website** | https://drgomon.beauty |
| **Privacy Policy URL** | https://drgomon.beauty/privacy-policy.html |

### Full description (до 4000 символів)

```
Dr. Gomon Cosmetology — додаток для клієнтів косметологічного простору у Черкасах.

🪪 Особистий кабінет:
• Перегляд та управління записами (дата, час, спеціаліст, процедура)
• Скасування запису в один клік
• Баланс: депозит + кешбек 3% з кожної процедури
• Історія транзакцій та списання

💰 Актуальні ціни:
• Прайс-лист з пошуком по всіх процедурах
• Акції та спеціальні пропозиції
• Безвідсоткове розтермінування від 1000 грн

🤖 AI-асистент GomonAI:
• Підбір процедури під вашу потребу
• Відповіді на питання про процедури та догляд
• Актуальні ціни та рекомендації

📋 Процедури:
• Ін'єкційна косметологія: контурна пластика (Neuramis, Saypha, Neauvia), біоревіталізація (Rejuran, Neauvia), мезотерапія
• Апаратна косметологія: WOW-чистка, кисневий догляд Glow Skin, пілінги (PRX-T33, KEMIKUM, Simildiet)
• DrumRoll масаж та моделювання тіла, пресотерапія
• Відбілювання зубів Magic Smile
• Консультація лікаря-косметолога

👩‍⚕️ Спеціалісти:
• Вікторія Гомон — лікар-косметолог, 7+ років досвіду
• Анастасія — спеціаліст з масажних методик

📱 Зв'язок:
• Push-сповіщення про записи та акції
• Telegram-бот з нагадуваннями
• Instagram Direct (@dr.gomon)
• Телефон: 073-310-31-10

📍 Адреса: м. Черкаси, вул. Смілянська 23, БЦ Галерея, 6 поверх
🕐 Працюємо 7/7 з 9:00 до 20:00, тільки за записом
```

---

## Графічні матеріали

### Обов'язкові

| Ресурс | Розмір | Статус | Файл |
|--------|--------|--------|------|
| App icon | 512×512 PNG | Готово | `icon-512-gomon.png` |
| Feature graphic | 1024×500 PNG | Потрібно створити | — |
| Phone screenshots | мін. 2, рек. 6-8 | Потрібно створити | — |

### Рекомендовані скріншоти (6-8 шт)

1. **Auth screen** — слоган, логотип, поле телефону, TG-бот лінк
2. **Home** — записи, акції, новини, швидкий доступ
3. **Appointment detail** — модалка запису з датою, часом, спеціалістом, ціною
4. **Price list** — пошук, категорії, ціни
5. **AI chat** — діалог з AI-асистентом
6. **Admin calendar** (опціонально) — день з двома колонками спеціалістів
7. **Promos** — акції та знижки
8. **Map** — адреса та маршрут

### Як зробити скріншоти
- Відкрий додаток на телефоні (Android/iPhone)
- Розмір: реальний розмір екрану (1080×1920 або 1080×2340)
- Без рамок браузера (PWA в standalone mode)
- Темна тема (default)

### Feature Graphic (1024×500)
Створити в Canva або Figma:
- Фон: `#111010` (темний)
- Логотип клініки по центру
- Текст: "Dr. Gómon Cosmetology"
- Підтекст: "Косметологія у Черкасах"
- Золотий акцент `#c9a96e`

---

## Release Notes

### v1.0.0 — Closed Beta (02.04.2026)

```
Перший реліз Dr. Gomon Cosmetology:
- Авторизація через Telegram або SMS
- Перегляд записів з деталями (дата, час, спеціаліст, вартість)
- Актуальний прайс-лист з пошуком
- Push-нагадування про записи
- AI-асистент для підбору процедур
- Акції та спеціальні пропозиції
- Адреса клініки та маршрут
```

### v1.1.0 — Production Release (~16.04.2026)

```
Що нового:
- Magic link — автоматичний вхід через Telegram без вводу коду
- Розумний пошук процедур з рекомендаціями
- Детальна модалка запису з ціною та спеціалістом
- Календар для адміністраторів з двома колонками спеціалістів
- Підписка на Google Calendar для спеціалістів
- Промо-картка "Професійна косметика зі знижками"
- Світла тема для адміністраторів
- Покращена стабільність (gunicorn + watchdog кожні 2 хв)
- Виправлення безпеки та оптимізації

Покращення UX:
- Пагінація списку клієнтів
- Inline помилки замість popup
- Кнопки очищення пошуку
- Адаптивний дизайн для всіх розмірів екранів
- Зайняті слоти видимі для спеціалістів
```

### v1.2.0 — Closed Beta (03.05.2026)

```
Що нового:

Баланс та кешбек:
• Кешбек 3% з кожної процедури — автоматичне нарахування
• Баланс у додатку: депозит + кешбек з детальною історією
• Поповнення депозиту через WayForPay (безвідсоткове розтермінування)
• Списання кешбеку при досягненні 500 грн

AI-асистент GomonAI:
• Підбір процедури під проблему/побажання
• Актуальні ціни на всі процедури
• Рекомендації по догляду
• Скасування запису через чат

Сповіщення:
• Push-нагадування про записи
• Подяка + відгук після процедури
• Повідомлення про нарахування кешбеку
• Нагадування про повторні процедури (індивідуальні інтервали)

Покращення додатку:
• Оновлений прайс-лист з пошуком
• Швидший запуск та навігація
• Виправлено роботу на повільних мережах
• Покращена стабільність Service Worker

Для адміністраторів:
• Месенджер: Telegram + Instagram в одному вікні
• AI-асистент для створення записів з розкладом
• Календар з datepicker для швидкого переходу
• Картка клієнта з балансом та фото
• Управління сповіщеннями по спеціалістах
• Синхронізація записів з WLaunch CRM
```

### v1.3.0 — Planned
- Відгук після візиту через push
```

---

## Чеклист перед кожним релізом

### Підготовка AAB
- [ ] Збільшити `appVersionCode` в twa-manifest.json (поточний: 1)
- [ ] Збільшити `appVersionName` (поточний: 1.0.0)
- [ ] Згенерувати AAB через pwabuilder.com
- [ ] Підписати тим же keystore (gomon-release.keystore)

### Перевірка перед upload
- [ ] `curl https://www.gomonclinic.com/api/health` → OK
- [ ] `curl https://www.gomonclinic.com/.well-known/assetlinks.json` → valid JSON
- [ ] `curl https://www.gomonclinic.com/app/manifest.json` → all fields present
- [ ] `curl https://www.gomonclinic.com/app/sw.js` → latest CACHE version
- [ ] Privacy Policy доступна: gomonclinic.com/privacy-policy.html
- [ ] Merchant feed валідний: gomonclinic.com/merchant-feed.xml

### Upload в Google Play Console
- [ ] Production → Create new release
- [ ] Upload AAB
- [ ] Заповнити Release notes (Ukrainian)
- [ ] Review → Start rollout

### Після релізу
- [ ] Перевірити що додаток оновлюється
- [ ] Перевірити TWA bar (не повинен показувати URL)
- [ ] Перевірити push notifications
- [ ] Моніторити Crashes в Play Console
- [ ] Відповідати на відгуки
- [ ] **Оновити цю документацію** (PLAYSTORE-LISTING.md) з новими змінами

---

## Треки Google Play

| Трек | Аудиторія | Коли використовувати |
|------|-----------|---------------------|
| Internal testing | До 100 тестерів (email list) | Перші тести, баги |
| Closed testing | Обмежена група (email list) | **Зараз тут** — beta |
| Open testing | Будь-хто (з Play Store, позначено як Beta) | Перед production |
| Production | Всі | Фінальний реліз |

### Перехід між треками
1. **Closed → Open:** коли всі критичні баги виправлені
2. **Open → Production:** після 1-2 тижні без критичних проблем
3. Кожен перехід потребує **новий AAB** з versionCode+1

---

## Google Merchant Center

| Поле | Значення |
|------|----------|
| Feed URL | `https://www.gomonclinic.com/merchant-feed.xml` |
| Формат | RSS 2.0 з Google Shopping namespace |
| Товарів | 6 (категорії послуг) |
| Оновлення | Ручне (при зміні цін — оновити XML) |

---

## Google Ads Conversion IDs

| Конверсія | Мітка | Де спрацьовує |
|-----------|-------|--------------|
| APP_CLICK | `EjWcCL7qyY0cELuXlNcC` | Бургер-меню → "Наш APP" |
| CHAT | `WaavCKa45JAcELuXlNcC` | Відкриття AI чату на сайті |
| INSTAGRAM | `IK5ZCJbLxIUcELuXlNcC` | Клік на Instagram |
| TELEGRAM | `594oCJnLxIUcELuXlNcC` | Клік на Telegram |
| PHONE | `djjPCJzLxIUcELuXlNcC` | Клік на телефон |

---

## iCalendar Feeds (для спеціалістів)

| Хто | URL |
|-----|-----|
| Superadmin (всі) | `https://www.gomonclinic.com/api/admin/calendar.ics?key=rtsqIeZt6zJICZOIHOQW545DYI3sRxajum-oGL3EEnw` |
| Вікторія | `https://www.gomonclinic.com/api/admin/calendar.ics?key=3zIZzKlBoW37t_-T7zjmhQTDunK9bQUVde3JiQGg4rk` |
| Анастасія | `https://www.gomonclinic.com/api/admin/calendar.ics?key=z_eszoPbMUFTt_TKiGUkI6ZOkaZGu4P7YfT8-yJLX8k` |
