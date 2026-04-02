# Dr. Gomon Cosmetology — Google Play Store Listing

## Поточний статус
- **Трек:** Closed Beta Testing
- **Version:** 1.0.0 (versionCode 1)
- **AAB:** згенерований 02.04.2026 через PWABuilder
- **Наступний реліз:** ~16.04.2026 (Production або Open Beta)

---

## Store Listing (Картка додатку)

### Основна інформація

| Поле | Значення |
|------|----------|
| **App name** | Dr. Gomon Cosmetology |
| **Short description** (80 символів) | Записи, ціни, нагадування — косметологічна клініка у Черкасах |
| **Default language** | Ukrainian — uk |
| **App category** | Beauty |
| **Content rating** | Everyone |
| **Contact email** | viktoriia@gomonclinic.com |
| **Contact phone** | +380733103110 |
| **Website** | https://www.gomonclinic.com |
| **Privacy Policy URL** | https://www.gomonclinic.com/privacy-policy.html |

### Full description (до 4000 символів)

```
Dr. Gomon Cosmetology — додаток для клієнтів косметологічної клініки у Черкасах.

Зручний особистий кабінет:
- Перегляд та управління записами
- Детальна інформація про кожен запис: дата, час, спеціаліст, вартість
- Скасування запису в один клік
- Актуальний прайс-лист процедур з пошуком
- Push-нагадування про записи
- AI-помічник для підбору процедур
- Акції та спеціальні пропозиції
- Професійна косметика зі знижками
- Новини клініки з Telegram-каналу
- Адреса та маршрут до клініки

Процедури:
- Ін'єкційна косметологія: ботулінотерапія, контурна пластика, біоревіталізація
- Апаратна косметологія: WOW-чистка, пілінги, киснева терапія
- DrumRoll масаж та моделювання тіла
- Доглядові процедури: SPA-догляд Christina, карбокситерапія
- Відбілювання зубів Magic Smile
- Консультація лікаря-косметолога

Спеціалісти:
- Вікторія Гомон — лікар-косметолог
- Анастасія — майстер косметології

Зв'язок через додаток:
- Telegram-бот з нагадуваннями та акціями
- AI-асистент для підбору процедур онлайн
- Instagram Direct
- Телефон: 073-310-31-10

Адреса: м. Черкаси, БЦ Галерея, 6 поверх
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

### v1.2.0 — Planned (~30.04.2026)

```
Заплановано:
- Фото-альбоми клієнтів (Google Photos / iCloud інтеграція)
- Серверний rate-limit для AI-чату
- Запис на процедуру через додаток
- Нагадування за 2 години до запису
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
