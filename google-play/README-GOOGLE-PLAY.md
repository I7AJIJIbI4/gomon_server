# Dr. Gomon Cosmetology — Публікація в Google Play

## Що вже готово

| Файл | Де | Призначення |
|------|----|-------------|
| `gomon-release.keystore` | сервер: `/home/gomoncli/google-play/` | Ключ підпису (НЕ ВТРАЧАТИ — без нього неможливо оновити додаток) |
| `twa-manifest.json` | сервер: `/home/gomoncli/google-play/` | Конфіг TWA для Bubblewrap/PWABuilder |
| `assetlinks.json` | сервер: `/home/gomoncli/public_html/.well-known/` | Digital Asset Links (верифікація домену) |
| `icon-192-gomon.png` | сервер: `/home/gomoncli/public_html/app/icons/` | Іконка 192×192 |
| `icon-512-gomon.png` | сервер: `/home/gomoncli/public_html/app/icons/` | Іконка 512×512 |
| `badge-white.png` | сервер: `/home/gomoncli/public_html/app/icons/` | Badge 96×96 |
| `manifest.json` | сервер: `/home/gomoncli/public_html/app/` | PWA маніфест |
| `sw.js` | сервер: `/home/gomoncli/public_html/app/` | Service Worker |

## Дані підпису (ЗБЕРІГАЙ ОКРЕМО)

```
Keystore:     gomon-release.keystore
Alias:        gomon
Store pass:   GomonClinic2026
Key pass:     GomonClinic2026
Validity:     10000 днів (~27 років)
SHA-256:      B2:9C:C6:35:F1:7F:58:DB:0A:56:84:23:D8:31:F3:EB:CA:1E:40:AE:55:86:31:E5:ED:A6:B0:69:9A:EC:55:0F
```

**ВАЖЛИВО**: Якщо втратиш keystore — НЕ ЗМОЖЕШ оновити додаток у Google Play. Зроби бекап!

---

## Крок 1: Згенерувати AAB через PWABuilder

**AAB згенеровано 02.04.2026 через pwabuilder.com**

Процедура (для повторної генерації при оновленні):
1. Відкрий https://www.pwabuilder.com/
2. Введи URL: `https://www.gomonclinic.com/app/`
3. Натисни **"Start"** → PWABuilder перевірить маніфест, SW, іконки
4. На сторінці результатів натисни **"Package for stores"** → **"Android"**
5. У формі заповни:

| Поле | Значення |
|------|----------|
| Package ID | `com.gomonclinic.app` |
| App name | `Dr. Gomon Cosmetology` |
| Launcher name | `Dr. Gómon` |
| App version | `1.0.0` |
| App version code | `1` |
| Host | `https://www.gomonclinic.com` |
| Start URL | `/app/` |
| Theme color | `#111010` |
| Background color | `#111010` |
| Status bar color | `#111010` |
| Orientation | `portrait` |
| Display | `standalone` |
| Notifications | `enabled` |
| Min SDK | `23` (Android 6.0+) |
| Monochrome icon URL | `https://www.gomonclinic.com/app/icons/badge-white.png` |
| Signing key | **Use mine** → завантаж `gomon-release.keystore` |
| Key alias | `gomon` |
| Key password | `GomonClinic2026` |
| Store password | `GomonClinic2026` |
| Notification delegation | Enable |
| Location/Billing/ChromeOS/Meta Quest | **Disable** |
| Fallback behavior | Custom Tabs |

6. Натисни **"Generate"** → "Querying for job..." → завантажиться ZIP з AAB файлом
7. Розпакуй → файл `app-release-signed.aab` готовий для Google Play

**Нотатки щодо генерації:**
- PWABuilder іноді зависає на "Querying for job..." — перезавантажити сторінку і спробувати ще раз
- Bubblewrap CLI (альтернатива) потребує JDK 17 + Android SDK з `bin/` або `tools/` в корені
- Для bubblewrap: `~/.bubblewrap/config.json` повинен мати правильні `jdkPath` і `androidSdkPath`
- SDK повинен мати `bin/` symlink на `cmdline-tools/latest/bin/` (bubblewrap валідація)

---

## Крок 2: Перевірка Digital Asset Links

```bash
# Має повернути JSON з sha256_cert_fingerprints
curl -s https://www.gomonclinic.com/.well-known/assetlinks.json

# Перевірка через Google:
# https://digitalassetlinks.googleapis.com/v1/statements:list?source.web.site=https://www.gomonclinic.com&relation=delegate_permission/common.handle_all_urls
```

---

## Крок 3: Google Play Console

### 3.1 Створити акаунт розробника
- https://play.google.com/console/signup
- Одноразова плата: **$25**
- Потрібен Google-акаунт

### 3.2 Створити додаток
1. **Create app** → заповни:
   - App name: `Dr. Gomon Cosmetology`
   - Default language: `Ukrainian — uk`
   - App or game: **App**
   - Free or paid: **Free**

### 3.3 Store Listing (Опис у магазині)

**Short description** (80 символів max):
```
Особистий кабінет клініки Dr. Gómon — записи, ціни, нагадування
```

**Full description** (4000 символів max):
```
Dr. Gomon Cosmetology — додаток для клієнтів косметологічної клініки у Черкасах.

Зручний особистий кабінет:
• Перегляд та управління записами
• Актуальний прайс-лист процедур
• Нагадування про записи через Telegram та Push
• AI-помічник для підбору процедур
• Акції та спеціальні пропозиції
• Новини клініки
• Адреса та маршрут до клініки

Спеціалісти:
• Вікторія Гомон — лікар-косметолог
• Анастасія — майстер косметології

Адреса: м. Черкаси, БЦ Галерея, 6 поверх
Телефон: 073-310-31-10
Instagram: @dr.gomon

Додаток безкоштовний, потрібна реєстрація за номером телефону.
```

**Category**: `Beauty`
**Content rating**: `Everyone`
**Contact email**: `admin@gomonclinic.com`
**Contact phone**: `+380733103110`
**Website**: `https://www.gomonclinic.com`

### 3.4 Графіка (обов'язково)

| Ресурс | Розмір | Опис |
|--------|--------|------|
| **App icon** | 512×512 PNG | `icon-512-gomon.png` (вже є) |
| **Feature graphic** | 1024×500 PNG | Банер для сторінки в Play Store — потрібно створити |
| **Screenshots phone** | мін. 2 шт, 320-3840px | Скріншоти додатку на телефоні (мін. 2, рек. 4-8) |
| **Screenshots tablet** | опціонально | Скріншоти на планшеті |

**Як зробити скріншоти:**
1. Відкрий https://www.gomonclinic.com/app/ на телефоні
2. Зроби скріншоти основних екранів:
   - Авторизація (з AI-асистентом)
   - Головна (записи, акції)
   - Прайс-лист
   - Карта
3. Розмір: 1080×1920 або 1080×2340 (реальний розмір екрану)

**Feature Graphic (1024×500):**
Створи в Canva або Figma:
- Фон: `#111010`
- Логотип клініки по центру
- Текст: "Dr. Gómon Cosmetology"
- Підтекст: "Черкаси"

### 3.5 Privacy Policy (обов'язково)

Google Play вимагає Privacy Policy URL. Потрібно створити сторінку:
`https://www.gomonclinic.com/privacy-policy`

Мінімальний зміст:

```
Політика конфіденційності Dr. Gomon Cosmetology

Дата оновлення: 01.04.2026

Які дані ми збираємо:
- Номер телефону (для авторизації)
- Ім'я та прізвище (з бази клієнтів клініки)
- Історія записів на процедури
- Push-підписки для сповіщень

Як використовуємо:
- Авторизація в додатку
- Відображення записів
- Нагадування про процедури
- Сповіщення про акції

Як зберігаємо:
- Дані зберігаються на захищеному сервері в Україні
- Доступ тільки для авторизованих адміністраторів клініки
- Не передаємо третім сторонам

Контакти:
Dr. Gomon Cosmetology
Телефон: 073-310-31-10
Email: admin@gomonclinic.com
Адреса: м. Черкаси, БЦ Галерея, 6 поверх
```

### 3.6 Завантаження AAB

1. Google Play Console → **Production** → **Create new release**
2. Завантаж `app-release-signed.aab`
3. Release name: `1.0.0`
4. Release notes (Ukrainian):
```
Перший реліз додатку Dr. Gomon Cosmetology:
- Авторизація за номером телефону
- Перегляд записів та прайс-листу
- AI-помічник для підбору процедур
- Push-нагадування
- Акції та новини
```
5. **Review** → **Start rollout to Production**

### 3.7 App Signing (ВАЖЛИВО)

Google Play підтримує два режими:
- **Google-managed signing** (рекомендовано): Google зберігає upload key, ви завантажуєте AAB підписаний upload key
- **Self-managed signing**: ви підписуєте самі (наш keystore)

При першому завантаженні Google запропонує використати Google-managed signing.
**Якщо оберете Google-managed** — потрібно буде оновити SHA-256 в `assetlinks.json` на новий від Google.

---

## Крок 4: Після публікації

1. **Оновити assetlinks.json** якщо Google-managed signing змінив fingerprint
2. **Перевірити TWA**: відкрити додаток → адресний рядок Chrome НЕ повинен з'являтись
3. **Моніторити**: Google Play Console → Statistics, Crashes, Reviews

---

## Оновлення додатку

PWA оновлюється автоматично через Service Worker. Для оновлення у Google Play:
1. Збільшити `appVersionCode` та `appVersionName` в twa-manifest.json
2. Перезібрати AAB через PWABuilder
3. Завантажити новий AAB у Google Play Console

---

## Чеклист перед публікацією

- [ ] Google Play Developer акаунт ($25)
- [ ] AAB файл згенерований через PWABuilder
- [ ] assetlinks.json доступний: `curl https://www.gomonclinic.com/.well-known/assetlinks.json`
- [ ] Privacy Policy сторінка створена
- [ ] Feature Graphic 1024×500 створена
- [ ] Мін. 2 скріншоти телефону
- [ ] Store listing заповнений (title, description, category)
- [ ] Бекап keystore зроблений (окреме місце від сервера)
